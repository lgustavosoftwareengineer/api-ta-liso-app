import json
from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from app.config import get_settings
from app.helpers.chat_helpers import extract_tool_args_from_content
from app.models.category import Category
from app.models.chat_message import ChatMessage

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
HISTORY_LIMIT = 20


async def get_chat_response(
    message: str,
    history: list[ChatMessage],
    categories: list[Category],
) -> dict | str | None:
    """Call the LLM and return either parsed transaction fields (dict) or a conversational reply (str).

    Returns:
        dict  — transaction args extracted; caller should create the transaction.
        str   — model replied conversationally; caller should save and return as-is.
        None  — model returned nothing (edge case).
    """
    category_names = ", ".join(f'"{c.name}"' for c in categories)
    system = (
        "Você é um assistente financeiro do app Tá Liso. "
        "Aja como um nordestino raiz, usando expressões e gírias típicas da região, mas sempre claro.\n\n"
        "FUNÇÃO PRINCIPAL: registrar gastos. "
        "Quando o usuário descrever um gasto, chame a função `registrar_transacao` com categoria, descrição e valor.\n\n"
        "REGRAS PARA REGISTRO:\n"
        "1. Extraia a categoria exatamente como o usuário mencionou.\n"
        "2. Se o valor não estiver na mensagem, pergunte — não chame a função.\n"
        "3. Se a categoria não estiver na mensagem, pergunte e liste as opções: "
        f"{category_names}.\n"
        "4. Chame a função apenas quando tiver categoria, descrição e valor.\n\n"
        "CONVERSA GERAL:\n"
        "- Pode conversar sobre finanças pessoais, dar dicas e tirar dúvidas sobre o app.\n"
        "- Nunca invente saldos, totais ou histórico financeiro do usuário — você não tem acesso a esses dados.\n"
        "- Se perguntado sobre dados que não possui, diga que não tem acesso e oriente o usuário a consultar o app."
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
    content = choice.message.content

    if choice.message.tool_calls:
        try:
            raw_args = cast(ChatCompletionMessageToolCall, choice.message.tool_calls[0]).function.arguments
            return json.loads(raw_args)
        except (json.JSONDecodeError, TypeError, IndexError):
            if content:
                return extract_tool_args_from_content(content) or content

    if content:
        # Model replied conversationally — try to extract tool args first (models without
        # native function calling may embed JSON in content), then fall back to the text reply.
        return extract_tool_args_from_content(content) or content

    return None
