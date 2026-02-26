import json
from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from app.ai_tools import CHAT_COMPLETION_TOOLS
from app.config import get_settings
from app.helpers.chat_helpers import extract_tool_args_from_content
from app.models.category import Category
from app.models.chat_message import ChatMessage

# Max number of prior messages sent to LLM as context.
HISTORY_LIMIT = 20


async def get_chat_response(
    message: str,
    history: list[ChatMessage],
    categories: list[Category],
) -> dict[str, Any] | str | None:
    """Call the LLM and return a tool call dict or a conversational reply (str).

    Returns:
        dict  — {"tool": "<tool_name>", "args": {...}}; caller should execute the tool.
        str   — model replied conversationally; caller should save and return as-is.
        None  — model returned nothing (edge case).
    """
    category_names = ", ".join(f'"{c.name}"' for c in categories) if categories else "nenhuma"
    system = (
        "Você é um assistente financeiro do app Tá Liso. "
        "Aja como um nordestino raiz, usando expressões e gírias típicas da região, mas sempre claro.\n\n"
        "CAPACIDADES:\n"
        "1. Registrar gastos — chame `registrar_transacao` com categoria, descrição e valor.\n"
        "2. Listar categorias — chame `listar_categorias`.\n"
        "3. Criar categoria — chame `criar_categoria` com nome e orçamento inicial.\n"
        "4. Editar categoria — chame `editar_categoria` com nome atual e campos a alterar.\n"
        "5. Deletar categoria — chame `deletar_categoria` com o nome.\n"
        "6. Listar transações recentes — chame `listar_transacoes`.\n"
        "7. Editar transação — chame `editar_transacao` com a descrição e campos a alterar.\n"
        "8. Deletar transação — chame `deletar_transacao` com a descrição.\n\n"
        "REGRAS PARA REGISTRO DE GASTOS:\n"
        "1. Extraia a categoria exatamente como o usuário mencionou.\n"
        "2. Se o valor não estiver na mensagem, pergunte — não chame a função.\n"
        f"3. Categorias disponíveis: {category_names}.\n"
        "4. Chame `registrar_transacao` apenas quando tiver categoria, descrição e valor.\n\n"
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
        tools=CHAT_COMPLETION_TOOLS,
        tool_choice="auto",
    )

    choice = response.choices[0]
    content = choice.message.content

    if choice.message.tool_calls:
        try:
            tool_call = cast(ChatCompletionMessageToolCall, choice.message.tool_calls[0])
            tool_name = tool_call.function.name
            raw_args = tool_call.function.arguments
            args = json.loads(raw_args)
            return {"tool": tool_name, "args": args}
        except (json.JSONDecodeError, TypeError, IndexError):
            if content:
                extracted = extract_tool_args_from_content(content)
                if extracted:
                    return {"tool": "registrar_transacao", "args": extracted}
                return content

    if content:
        # Model replied conversationally — try to extract tool args first (models without
        # native function calling may embed JSON in content), then fall back to the text reply.
        extracted = extract_tool_args_from_content(content)
        if extracted:
            return {"tool": "registrar_transacao", "args": extracted}
        return content

    return None
