import json
from decimal import Decimal

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
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


async def process_message(
    db: AsyncSession, user_id: str, message: str
) -> tuple[str, Transaction | None]:
    categories = await category_service.list_categories(db, user_id)
    if not categories:
        return (
            "Você não tem categorias cadastradas ainda. Crie uma categoria primeiro.",
            None,
        )

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

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=get_settings().openrouter_api_key,
    )
    response = await client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
        tools=[_TOOL],
        tool_choice="auto",
    )

    choice = response.choices[0]
    if not choice.message.tool_calls:
        reply = choice.message.content or "Não entendi. Pode descrever o gasto com valor e categoria?"
        return reply, None

    inputs = json.loads(choice.message.tool_calls[0].function.arguments)
    category_name_input = inputs["category_name"].strip().lower()

    # Match estrito feito pelo servidor — sem alucinação possível do modelo
    matched = next(
        (c for c in categories if c.name.strip().lower() == category_name_input),
        None,
    )
    if matched is None:
        available = ", ".join(f'"{c.name}"' for c in categories)
        return (
            f"Categoria \"{inputs['category_name']}\" não encontrada. "
            f"Categorias disponíveis: {available}.",
            None,
        )

    data = TransactionCreate(
        category_id=matched.id,
        description=inputs["description"],
        amount=Decimal(str(inputs["amount"])),
    )

    try:
        transaction = await transaction_service.create_transaction(db, user_id, data)
    except (LookupError, ValueError) as e:
        return str(e), None

    reply = f"Registrei R${transaction.amount:.2f} em {matched.name} ({transaction.description})."
    return reply, transaction
