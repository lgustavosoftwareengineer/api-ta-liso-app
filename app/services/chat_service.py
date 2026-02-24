import json
from decimal import Decimal
from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import InsufficientBalanceError
from app.helpers.chat_helpers import (
    extract_tool_args_from_content,
    message_to_simple_string,
    normalize_category_name,
)
from app.models.chat_message import ChatMessage
from app.models.transaction import Transaction
from app.schemas.chat import InsufficientBalanceDetail
from app.schemas.transaction import TransactionCreate
from app.services import categories as category_service
from app.services import transactions as transaction_service

# LLM extracts category name as user said — server does strict match.
_TOOL: ChatCompletionToolParam = {
    "type": "function",
    "function": {
        "name": "registrar_transacao",
        "description": "Registra uma transação financeira com os dados extraídos da mensagem do usuário.",
        "parameters": {
            "type": "object",
            "properties": {
                "category_name": {
                    "type": "string",
                    "description": "Nome da categoria exatamente como o usuário mencionou na mensagem",
                },
                "description": {
                    "type": "string",
                    "description": "Descrição curta da transação (máx. 60 caracteres)",
                },
                "amount": {
                    "type": "number",
                    "description": "Valor em reais, número positivo",
                },
            },
            "required": ["category_name", "description", "amount"],
        },
    },
}

# Max number of prior messages sent to LLM as context.
_HISTORY_LIMIT = 20


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
) -> None:
    """Persist user + assistant message pair to the database. category_id is set when the message was processed and category was matched (CASCADE deletes messages when category is removed)."""
    db.add(
        ChatMessage(
            user_id=user_id,
            role="user",
            content=user_content,
            category_id=category_id,
        )
    )
    db.add(
        ChatMessage(
            user_id=user_id,
            role="assistant",
            content=assistant_content,
            transaction_id=transaction_id,
            category_id=category_id,
        )
    )
    await db.commit()


async def process_message(
    db: AsyncSession, user_id: str, message: str
) -> tuple[str, Transaction | None, InsufficientBalanceDetail | None]:
    message = message_to_simple_string(message)

    categories = await category_service.list_categories(db, user_id)
    if not categories:
        reply = "Você não tem categorias cadastradas ainda. Crie uma categoria primeiro."
        await _save_messages(db, user_id, message, reply, None, None)
        return reply, None, None

    # Load last N messages for LLM context
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(_HISTORY_LIMIT)
    )
    history = list(reversed(history_result.scalars().all()))

    category_names = ", ".join(f'"{c.name}"' for c in categories)
    system = (
        "Você é um assistente financeiro do app Tá Liso. "
        "Você deve agir como um nordestino raiz, usando expressões e gírias típicas da região. "
        "Você pode conversar com o usuário de uma maneira um pouco mais informal, mas sempre mantendo o respeito e a clareza. "
        "O usuário vai descrever um gasto em linguagem natural (português).\n\n"
        "REGRAS:\n"
        "1. Extraia o nome da categoria exatamente como o usuário disse na mensagem.\n"
        "2. Extraia a descrição curta do gasto e o valor em reais.\n"
        "3. Se o valor não for mencionado, pergunte o valor sem chamar a função.\n"
        "4. Se a categoria não for mencionada, pergunte qual categoria usar "
        f"e liste as opções disponíveis: {category_names}.\n"
        "5. Chame a função apenas quando tiver categoria, descrição e valor."
    )

    messages: list[Any] = [{"role": "system", "content": system}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=get_settings().openrouter_api_key,
    )
    response = await client.chat.completions.create(
        model="openrouter/free",
        messages=cast(list[ChatCompletionMessageParam], messages),
        tools=[_TOOL],
        tool_choice="auto",
    )

    choice = response.choices[0]

    # Extract args: tool_calls first, then content fallback
    inputs = None
    if choice.message.tool_calls:
        try:
            raw_args = cast(ChatCompletionMessageToolCall, choice.message.tool_calls[0]).function.arguments
            inputs = json.loads(raw_args)
        except (json.JSONDecodeError, TypeError, IndexError):
            if choice.message.content:
                inputs = extract_tool_args_from_content(choice.message.content)
    elif choice.message.content:
        inputs = extract_tool_args_from_content(choice.message.content)

    if inputs is None:
        reply = choice.message.content or "Não entendi. Pode descrever o gasto com valor e categoria?"
        await _save_messages(db, user_id, message, reply, None, None)
        return reply, None, None
    category_name_input = normalize_category_name(inputs["category_name"])

    # Strict server-side match — no model hallucination
    matched = next(
        (c for c in categories if c.name.strip().lower() == category_name_input),
        None,
    )
    if matched is None:
        available = ", ".join(f'"{c.name}"' for c in categories)
        display_name = (inputs["category_name"] or "").strip()
        reply = (
            f"Categoria \"{display_name}\" não encontrada. "
            f"Categorias disponíveis: {available}."
        )
        await _save_messages(db, user_id, message, reply, None, None)
        return reply, None, None

    raw_desc = (inputs.get("description") or "").strip()
    if len(raw_desc) >= 2 and raw_desc[0] == '"' and raw_desc[-1] == '"':
        raw_desc = raw_desc[1:-1].strip()
    description = (raw_desc or "Gasto")[:255]

    data = TransactionCreate(
        category_id=matched.id,
        description=description,
        amount=Decimal(str(inputs["amount"])),
    )

    try:
        transaction = await transaction_service.create_transaction(db, user_id, data)
    except InsufficientBalanceError as e:
        reply = str(e)
        await _save_messages(db, user_id, message, reply, None, None)
        detail = InsufficientBalanceDetail(available=e.available, requested=e.requested, message="Saldo insuficiente")
        return reply, None, detail
    except (LookupError, ValueError) as e:
        reply = str(e)
        await _save_messages(db, user_id, message, reply, None, None)
        return reply, None, None

    reply = f"Registrei R${transaction.amount:.2f} em {matched.name} ({transaction.description})."
    await _save_messages(db, user_id, message, reply, transaction.id, matched.id)
    return reply, transaction, None
