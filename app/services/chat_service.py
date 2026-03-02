from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InsufficientBalanceError
from app.helpers.chat_helpers import dedup_response_lines, message_to_simple_string, normalize_category_name
from app.models.category import Category
from app.models.chat_message import ChatMessage
from app.models.transaction import Transaction
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.chat import InsufficientBalanceDetail
from app.schemas.chat_result import ChatProcessResult
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.services import ai_service
from app.services import categories as category_service
from app.services import transactions as transaction_service


def _utcnow() -> datetime:
    """Current time in UTC (extracted for testability)."""
    return datetime.now(timezone.utc)


async def clear_history(db: AsyncSession, user_id: str) -> None:
    """Delete all chat messages for the user."""
    from sqlalchemy import delete
    await db.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id))
    await db.commit()


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


def _find_category(categories: list[Category], category_name: str) -> Category | None:
    normalized = normalize_category_name(category_name)
    return next((c for c in categories if c.name.strip().lower() == normalized), None)


def _find_transactions_by_description(
    transactions: list[Transaction], description: str
) -> list[Transaction]:
    """Case-insensitive partial match; returns all matches sorted most-recent first."""
    needle = description.strip().lower()
    matches = [t for t in transactions if needle in t.description.lower()]
    return sorted(matches, key=lambda t: t.created_at, reverse=True)


def _build_transaction_data(inputs: dict, category: Category) -> TransactionCreate:
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
) -> ChatProcessResult:
    await _save_messages(db, user_id, message, reply, None)
    return ChatProcessResult(reply=reply)


# ── Tool handlers ─────────────────────────────────────────────────────────────

async def _handle_listar_categorias(
    db: AsyncSession, user_id: str, message: str, args: dict, categories: list[Category]
) -> ChatProcessResult:
    if not categories:
        reply = "Você ainda não tem nenhuma categoria cadastrada, não. Crie uma primeiro!"
    else:
        lines = [f"• {c.icon or '📦'} {c.name} — saldo R${c.current_balance:.2f} / R${c.initial_amount:.2f}" for c in categories]
        reply = "Suas categorias:\n" + "\n".join(lines)
    await _save_messages(db, user_id, message, reply, None)
    return ChatProcessResult(reply=reply, action="list_categories", categories=categories)


async def _handle_criar_categoria(
    db: AsyncSession, user_id: str, message: str, args: dict, categories: list[Category]
) -> ChatProcessResult:
    name = (args.get("name") or "").strip()
    icon = args.get("icon")
    initial_amount = args.get("initial_amount", 0)
    if not name:
        return await _reject(db, user_id, message, "Preciso do nome da categoria, visse?")
    try:
        cat = await category_service.create_category(
            db, user_id, CategoryCreate(name=name, icon=icon, initial_amount=Decimal(str(initial_amount)))
        )
    except ValueError as e:
        return await _reject(db, user_id, message, str(e))
    reply = f"Categoria {cat.icon or ''} {cat.name} criada com orçamento de R${cat.initial_amount:.2f}!"
    await _save_messages(db, user_id, message, reply, None, category_id=cat.id)
    return ChatProcessResult(reply=reply, action="create_category", category=cat)


async def _handle_editar_categoria(
    db: AsyncSession, user_id: str, message: str, args: dict, categories: list[Category]
) -> ChatProcessResult:
    category_name = (args.get("category_name") or "").strip()
    matched = _find_category(categories, category_name)
    if matched is None:
        available = ", ".join(f'"{c.name}"' for c in categories)
        return await _reject(db, user_id, message, f'Categoria "{category_name}" não encontrada. Disponíveis: {available}.')
    update_data = CategoryUpdate(
        name=args.get("new_name"),
        icon=args.get("new_icon"),
        initial_amount=Decimal(str(args["new_budget"])) if args.get("new_budget") is not None else None,
    )
    updated = await category_service.update_category(db, user_id, matched.id, update_data)
    if updated is None:
        return await _reject(db, user_id, message, "Não consegui atualizar a categoria.")
    reply = f"Categoria {updated.icon or ''} {updated.name} atualizada!"
    await _save_messages(db, user_id, message, reply, None, category_id=updated.id)
    return ChatProcessResult(reply=reply, action="edit_category", category=updated)


async def _handle_deletar_categoria(
    db: AsyncSession, user_id: str, message: str, args: dict, categories: list[Category]
) -> ChatProcessResult:
    category_name = (args.get("category_name") or "").strip()
    matched = _find_category(categories, category_name)
    if matched is None:
        available = ", ".join(f'"{c.name}"' for c in categories)
        return await _reject(db, user_id, message, f'Categoria "{category_name}" não encontrada. Disponíveis: {available}.')
    deleted = await category_service.delete_category(db, user_id, matched.id)
    if not deleted:
        return await _reject(db, user_id, message, "Não consegui deletar a categoria.")
    reply = f'Categoria "{matched.name}" deletada com sucesso!'
    await _save_messages(db, user_id, message, reply, None)
    return ChatProcessResult(reply=reply, action="delete_category")


def _parse_date_filter(date_filter: str | None) -> tuple[datetime, datetime | None, str] | None:
    """
    Interpreta date_filter e retorna (início, fim ou None, label) ou None para "sem filtro".
    - "hoje" -> dia atual (até agora)
    - "semana" -> últimos 7 dias
    - "mes" -> mês atual
    - "YYYY-MM-DD" -> dia exato (00:00 a 23:59:59)
    Quando fim é None, considera até "agora".
    """
    if not date_filter or not date_filter.strip():
        return None
    date_filter = date_filter.strip()
    now = _utcnow()
    if date_filter == "hoje":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return (start, None, "hoje")
    if date_filter == "semana":
        start = now - timedelta(days=7)
        return (start, None, "nos últimos 7 dias")
    if date_filter == "mes":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (start, None, f"em {now.strftime('%B/%Y')}")
    # Data exata no formato ISO (YYYY-MM-DD)
    try:
        day = datetime.strptime(date_filter, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        label = day.strftime("%d/%m/%Y")
        return (start, end, f"em {label}")
    except ValueError:
        return None


def _apply_date_filter(transactions: list[Transaction], date_filter: str | None) -> tuple[list[Transaction], str]:
    parsed = _parse_date_filter(date_filter)
    if parsed is None:
        return sorted(transactions, key=lambda t: t.created_at, reverse=True)[:10], ""

    start, end, label = parsed
    def in_range(t: Transaction) -> bool:
        utc_at = t.created_at.replace(tzinfo=timezone.utc) if t.created_at.tzinfo is None else t.created_at
        if end is None:
            return utc_at >= start
        return start <= utc_at <= end

    filtered = [t for t in transactions if in_range(t)]
    return sorted(filtered, key=lambda t: t.created_at, reverse=True), label


async def _handle_listar_transacoes(
    db: AsyncSession, user_id: str, message: str, args: dict, categories: list[Category]
) -> ChatProcessResult:
    all_transactions = await transaction_service.list_transactions(db, user_id)
    date_filter = args.get("date_filter")
    filtered, label = _apply_date_filter(all_transactions, date_filter)

    if not filtered:
        period = f" {label}" if label else ""
        reply = f"Você não tem nenhuma transação registrada{period}, não!"
    else:
        cat_map = {c.id: c for c in categories}
        lines = []
        total = Decimal(0)
        for t in filtered:
            cat = cat_map.get(t.category_id)
            cat_name = cat.name if cat else "?"
            lines.append(f"• {t.description} — {cat_name} — R${t.amount:.2f} — {t.created_at.strftime('%d/%m/%Y')}")
            total += t.amount
        header = f"Seus gastos {label}:" if label else "Suas últimas transações:"
        reply = header + "\n" + "\n".join(lines) + f"\n\nTotal: R${total:.2f}"
    await _save_messages(db, user_id, message, reply, None)
    return ChatProcessResult(reply=reply, action="list_transactions", transactions=filtered)


async def _handle_editar_transacao(
    db: AsyncSession, user_id: str, message: str, args: dict, categories: list[Category]
) -> ChatProcessResult:
    description = (args.get("transaction_description") or "").strip()
    all_transactions = await transaction_service.list_transactions(db, user_id)
    matches = _find_transactions_by_description(all_transactions, description)
    if not matches:
        return await _reject(db, user_id, message, f'Não encontrei nenhuma transação com "{description}".')
    if len(matches) > 1:
        lines = [f"• {t.description} — R${t.amount:.2f} — {t.created_at.strftime('%d/%m/%Y')}" for t in matches[:5]]
        reply = f'Encontrei várias transações com "{description}". Qual delas?\n' + "\n".join(lines)
        return await _reject(db, user_id, message, reply)
    target = matches[0]
    update_kwargs: dict = {}
    if args.get("new_description") is not None:
        raw = (args.get("new_description") or "").strip()
        update_kwargs["description"] = (raw[:255] if raw else "Gasto")
    if args.get("new_amount") is not None:
        update_kwargs["amount"] = Decimal(str(args["new_amount"]))
    if args.get("new_category_name"):
        new_cat = _find_category(categories, args["new_category_name"])
        if new_cat is None:
            available = ", ".join(f'"{c.name}"' for c in categories)
            return await _reject(db, user_id, message, f'Categoria "{args["new_category_name"]}" não encontrada. Disponíveis: {available}.')
        update_kwargs["category_id"] = new_cat.id
    update_data = TransactionUpdate(**update_kwargs)
    updated = await transaction_service.update_transaction(db, user_id, target.id, update_data)
    if updated is None:
        return await _reject(db, user_id, message, "Não consegui atualizar a transação.")
    reply = f"Transação atualizada: {updated.description} — R${updated.amount:.2f}."
    await _save_messages(db, user_id, message, reply, updated.id)
    await db.refresh(updated)
    return ChatProcessResult(reply=reply, action="edit_transaction", transaction=updated)


async def _handle_deletar_transacao(
    db: AsyncSession, user_id: str, message: str, args: dict, categories: list[Category]
) -> ChatProcessResult:
    description = (args.get("transaction_description") or "").strip()
    all_transactions = await transaction_service.list_transactions(db, user_id)
    matches = _find_transactions_by_description(all_transactions, description)
    if not matches:
        return await _reject(db, user_id, message, f'Não encontrei nenhuma transação com "{description}".')
    if len(matches) > 1:
        lines = [f"• {t.description} — R${t.amount:.2f} — {t.created_at.strftime('%d/%m/%Y')}" for t in matches[:5]]
        reply = f'Encontrei várias transações com "{description}". Qual delas?\n' + "\n".join(lines)
        return await _reject(db, user_id, message, reply)
    target = matches[0]
    target_desc = target.description
    deleted = await transaction_service.delete_transaction(db, user_id, target.id)
    if not deleted:
        return await _reject(db, user_id, message, "Não consegui deletar a transação.")
    reply = f'Transação "{target_desc}" deletada com sucesso!'
    await _save_messages(db, user_id, message, reply, None)
    return ChatProcessResult(reply=reply, action="delete_transaction")


async def _handle_registrar_transacao(
    db: AsyncSession, user_id: str, message: str, args: dict, categories: list[Category]
) -> ChatProcessResult:
    if not categories:
        return await _reject(db, user_id, message, "Você não tem categorias cadastradas ainda. Crie uma categoria primeiro.")

    matched = _find_category(categories, args.get("category_name", ""))
    if matched is None:
        available = ", ".join(f'"{c.name}"' for c in categories)
        display_name = (args.get("category_name") or "").strip()
        return await _reject(db, user_id, message, f'Categoria "{display_name}" não encontrada. Categorias disponíveis: {available}.')

    data = _build_transaction_data(args, matched)

    try:
        transaction = await transaction_service.create_transaction(db, user_id, data)
    except InsufficientBalanceError as e:
        reply = "Saldo insuficiente"
        await _save_messages(db, user_id, message, reply, None, balance_available=e.available, balance_requested=e.requested)
        return ChatProcessResult(
            reply=reply,
            insufficient_balance=InsufficientBalanceDetail(available=e.available, requested=e.requested, message=reply),
        )
    except (LookupError, ValueError) as e:
        return await _reject(db, user_id, message, str(e))

    reply = f"Registrei R${transaction.amount:.2f} em {matched.name} ({transaction.description})."
    await _save_messages(db, user_id, message, reply, transaction.id, matched.id)
    await db.refresh(transaction)
    return ChatProcessResult(reply=reply, action="create_transaction", transaction=transaction)


async def process_message(
    db: AsyncSession, user_id: str, message: str
) -> ChatProcessResult:
    message = message_to_simple_string(message)

    categories = await category_service.list_categories(db, user_id)
    history = await _fetch_recent_history(db, user_id)
    response = await ai_service.get_chat_response(message, history, categories)

    if isinstance(response, str):
        return await _reject(db, user_id, message, dedup_response_lines(response))

    if response is None:
        return await _reject(db, user_id, message, "Não entendi. Pode repetir de outro jeito?")

    tool = response["tool"]
    args = response["args"]

    match tool:
        case "listar_categorias":
            return await _handle_listar_categorias(db, user_id, message, args, categories)
        case "criar_categoria":
            return await _handle_criar_categoria(db, user_id, message, args, categories)
        case "editar_categoria":
            return await _handle_editar_categoria(db, user_id, message, args, categories)
        case "deletar_categoria":
            return await _handle_deletar_categoria(db, user_id, message, args, categories)
        case "listar_transacoes":
            return await _handle_listar_transacoes(db, user_id, message, args, categories)
        case "editar_transacao":
            return await _handle_editar_transacao(db, user_id, message, args, categories)
        case "deletar_transacao":
            return await _handle_deletar_transacao(db, user_id, message, args, categories)
        case "registrar_transacao":
            return await _handle_registrar_transacao(db, user_id, message, args, categories)
        case _:
            return await _reject(db, user_id, message, "Não entendi o que você quis dizer. Pode repetir?")
