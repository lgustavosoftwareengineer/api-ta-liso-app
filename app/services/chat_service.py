import json
import re
from decimal import Decimal

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chat_message import ChatMessage
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate
from app.services import categories as category_service
from app.services import transactions as transaction_service

# O LLM extrai o nome da categoria como o usuário disse — o servidor faz o match estrito.
_TOOL = {
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

# Número máximo de mensagens anteriores enviadas ao LLM como contexto
_HISTORY_LIMIT = 20


def _extract_tool_args_from_content(content: str) -> dict | None:
    """Fallback para modelos que retornam tool calls como texto no content.

    Alguns modelos gratuitos do OpenRouter não suportam function calling nativo
    e emitem o tool call como texto (ex: 'TOOL_CALL>[{...}]'). Esta função
    extrai os argumentos da função registrar_transacao nesses casos.
    """
    try:
        # Tenta extrair o bloco "arguments": {...} do texto
        match = re.search(r'"arguments"\s*:\s*(\{[^{}]+\})', content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


async def list_history(db: AsyncSession, user_id: str) -> list[ChatMessage]:
    """Retorna o histórico completo de mensagens do usuário (ordem cronológica)."""
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
) -> None:
    """Salva o par de mensagens (usuário + assistente) no banco."""
    db.add(ChatMessage(user_id=user_id, role="user", content=user_content))
    db.add(ChatMessage(
        user_id=user_id,
        role="assistant",
        content=assistant_content,
        transaction_id=transaction_id,
    ))
    await db.commit()


async def process_message(
    db: AsyncSession, user_id: str, message: str
) -> tuple[str, Transaction | None]:
    categories = await category_service.list_categories(db, user_id)
    if not categories:
        reply = "Você não tem categorias cadastradas ainda. Crie uma categoria primeiro."
        await _save_messages(db, user_id, message, reply, None)
        return reply, None

    # Carrega as últimas N mensagens para contexto do LLM
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
        "O usuário vai descrever um gasto em linguagem natural (português).\n\n"
        "REGRAS:\n"
        "1. Extraia o nome da categoria exatamente como o usuário disse na mensagem.\n"
        "2. Extraia a descrição curta do gasto e o valor em reais.\n"
        "3. Se o valor não for mencionado, pergunte o valor sem chamar a função.\n"
        "4. Se a categoria não for mencionada, pergunte qual categoria usar "
        f"e liste as opções disponíveis: {category_names}.\n"
        "5. Chame a função apenas quando tiver categoria, descrição e valor."
    )

    messages = [{"role": "system", "content": system}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=get_settings().openrouter_api_key,
    )
    response = await client.chat.completions.create(
        model="openrouter/free",
        messages=messages,
        tools=[_TOOL],
        tool_choice="auto",
    )

    choice = response.choices[0]

    # Extrai os argumentos: primeiro via tool_calls (padrão), depois via content (fallback)
    inputs = None
    if choice.message.tool_calls:
        inputs = json.loads(choice.message.tool_calls[0].function.arguments)
    elif choice.message.content:
        inputs = _extract_tool_args_from_content(choice.message.content)

    if inputs is None:
        reply = choice.message.content or "Não entendi. Pode descrever o gasto com valor e categoria?"
        await _save_messages(db, user_id, message, reply, None)
        return reply, None
    category_name_input = inputs["category_name"].strip().lower()

    # Match estrito feito pelo servidor — sem alucinação possível do modelo
    matched = next(
        (c for c in categories if c.name.strip().lower() == category_name_input),
        None,
    )
    if matched is None:
        available = ", ".join(f'"{c.name}"' for c in categories)
        reply = (
            f"Categoria \"{inputs['category_name']}\" não encontrada. "
            f"Categorias disponíveis: {available}."
        )
        await _save_messages(db, user_id, message, reply, None)
        return reply, None

    data = TransactionCreate(
        category_id=matched.id,
        description=inputs["description"],
        amount=Decimal(str(inputs["amount"])),
    )

    try:
        transaction = await transaction_service.create_transaction(db, user_id, data)
    except (LookupError, ValueError) as e:
        reply = str(e)
        await _save_messages(db, user_id, message, reply, None)
        return reply, None

    reply = f"Registrei R${transaction.amount:.2f} em {matched.name} ({transaction.description})."
    await _save_messages(db, user_id, message, reply, transaction.id)
    return reply, transaction
