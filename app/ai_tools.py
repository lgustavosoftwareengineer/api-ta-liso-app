"""Definições das ferramentas (function calling) usadas pelo chat com a LLM."""

from openai.types.chat import ChatCompletionToolParam

CHAT_COMPLETION_TOOLS: list[ChatCompletionToolParam] = [
    {
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
    },
    {
        "type": "function",
        "function": {
            "name": "listar_categorias",
            "description": "Lista todas as categorias financeiras do usuário.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "criar_categoria",
            "description": "Cria uma nova categoria financeira.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nome da categoria",
                    },
                    "icon": {
                        "type": "string",
                        "description": "Emoji representando a categoria (opcional)",
                    },
                    "initial_amount": {
                        "type": "number",
                        "description": "Valor inicial do orçamento em reais",
                    },
                },
                "required": ["name", "initial_amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "editar_categoria",
            "description": "Edita uma categoria financeira existente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {
                        "type": "string",
                        "description": "Nome atual da categoria a editar",
                    },
                    "new_name": {
                        "type": "string",
                        "description": "Novo nome para a categoria (opcional)",
                    },
                    "new_icon": {
                        "type": "string",
                        "description": "Novo emoji para a categoria (opcional)",
                    },
                    "new_budget": {
                        "type": "number",
                        "description": "Novo orçamento inicial em reais (opcional)",
                    },
                },
                "required": ["category_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deletar_categoria",
            "description": "Deleta uma categoria financeira existente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {
                        "type": "string",
                        "description": "Nome da categoria a deletar",
                    },
                },
                "required": ["category_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_transacoes",
            "description": "Lista as transações financeiras do usuário, com filtro de período opcional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_filter": {
                        "type": "string",
                        "enum": ["hoje", "semana", "mes"],
                        "description": "Filtra por período: 'hoje' para gastos do dia, 'semana' para os últimos 7 dias, 'mes' para o mês atual. Omitir retorna as 10 mais recentes.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "editar_transacao",
            "description": "Edita uma transação financeira existente identificada pela descrição.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_description": {
                        "type": "string",
                        "description": "Descrição da transação a editar",
                    },
                    "new_description": {
                        "type": "string",
                        "description": "Nova descrição para a transação (opcional)",
                    },
                    "new_amount": {
                        "type": "number",
                        "description": "Novo valor em reais (opcional)",
                    },
                    "new_category_name": {
                        "type": "string",
                        "description": "Nome da nova categoria (opcional)",
                    },
                },
                "required": ["transaction_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deletar_transacao",
            "description": "Deleta uma transação financeira existente identificada pela descrição.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_description": {
                        "type": "string",
                        "description": "Descrição da transação a deletar",
                    },
                },
                "required": ["transaction_description"],
            },
        },
    },
]
