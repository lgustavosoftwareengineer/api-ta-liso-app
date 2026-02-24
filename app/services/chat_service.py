from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InsufficientBalanceError
from app.helpers.chat_helpers import message_to_simple_string, normalize_category_name
from app.models.chat_message import ChatMessage
from app.models.transaction import Transaction
from app.schemas.chat import InsufficientBalanceDetail
from app.schemas.transaction import TransactionCreate
from app.services import ai_service
from app.services import categories as category_service
from app.services import transactions as transaction_service


async def list_history(db: AsyncSession, user_id: str) -> list[ChatMessage]:
    """Return full message history for the user in chronological order."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def _save_messages(
    db: AsyncSession,
    user_id: str,
    user_content: str,
    assistant_content: str,
    transaction_id: str | None,
    category_id: str | None = None,
    balance_available: Decimal | None = None,
    balance_requested: Decimal | None = None,
) -> None:
    """Persist user + assistant message pair to the database."""
    db.add(ChatMessage(user_id=user_id, role="user", content=user_content, category_id=category_id))
    db.add(ChatMessage(
        user_id=user_id,
        role="assistant",
        content=assistant_content,
        transaction_id=transaction_id,
        category_id=category_id,
        balance_available=balance_available,
        balance_requested=balance_requested,
    ))
    await db.commit()


async def _fetch_recent_history(db: AsyncSession, user_id: str) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(ai_service.HISTORY_LIMIT)
    )
    return list(reversed(result.scalars().all()))


def _find_category(categories, category_name: str):
    normalized = normalize_category_name(category_name)
    return next((c for c in categories if c.name.strip().lower() == normalized), None)


def _build_transaction_data(inputs: dict, category) -> TransactionCreate:
    raw_desc = (inputs.get("description") or "").strip()
    if len(raw_desc) >= 2 and raw_desc[0] == '"' and raw_desc[-1] == '"':
        raw_desc = raw_desc[1:-1].strip()
    description = (raw_desc or "Gasto")[:255]
    return TransactionCreate(
        category_id=category.id,
        description=description,
        amount=Decimal(str(inputs["amount"])),
    )


async def _reject(
    db: AsyncSession, user_id: str, message: str, reply: str
) -> tuple[str, None, None]:
    await _save_messages(db, user_id, message, reply, None)
    return reply, None, None


async def process_message(
    db: AsyncSession, user_id: str, message: str
) -> tuple[str, Transaction | None, InsufficientBalanceDetail | None]:
    message = message_to_simple_string(message)

    categories = await category_service.list_categories(db, user_id)
    if not categories:
        return await _reject(db, user_id, message, "Você não tem categorias cadastradas ainda. Crie uma categoria primeiro.")

    history = await _fetch_recent_history(db, user_id)
    response = await ai_service.get_chat_response(message, history, categories)

    if isinstance(response, str):
        return await _reject(db, user_id, message, response)

    inputs = response
    if inputs is None:
        return await _reject(db, user_id, message, "Não entendi. Pode descrever o gasto com valor e categoria?")

    matched = _find_category(categories, inputs["category_name"])
    if matched is None:
        available = ", ".join(f'"{c.name}"' for c in categories)
        display_name = (inputs["category_name"] or "").strip()
        return await _reject(db, user_id, message, f'Categoria "{display_name}" não encontrada. Categorias disponíveis: {available}.')

    data = _build_transaction_data(inputs, matched)

    try:
        transaction = await transaction_service.create_transaction(db, user_id, data)
    except InsufficientBalanceError as e:
        reply = "Saldo insuficiente"
        await _save_messages(db, user_id, message, reply, None, balance_available=e.available, balance_requested=e.requested)
        return reply, None, InsufficientBalanceDetail(available=e.available, requested=e.requested, message=reply)
    except (LookupError, ValueError) as e:
        return await _reject(db, user_id, message, str(e))

    reply = f"Registrei R${transaction.amount:.2f} em {matched.name} ({transaction.description})."
    await _save_messages(db, user_id, message, reply, transaction.id, matched.id)
    await db.refresh(transaction)
    return reply, transaction, None
