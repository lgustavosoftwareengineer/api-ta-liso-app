"""
Testes do Chat Router — BDD: Controle completo via linguagem natural.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.user_service import create_user_with_settings
from app.services.jwt_service import create_token


def _mock_tool_use(tool_name: str, args: dict) -> MagicMock:
    """Simula resposta do OpenRouter com tool_call."""
    tool_call = MagicMock()
    tool_call.function = MagicMock()
    tool_call.function.name = tool_name
    tool_call.function.arguments = json.dumps(args)

    message = MagicMock()
    message.tool_calls = [tool_call]
    message.content = None

    response = MagicMock()
    response.choices = [MagicMock(message=message)]

    mock_completions = AsyncMock()
    mock_completions.create = AsyncMock(return_value=response)

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = mock_completions
    return mock_client


def _mock_text_response(text: str) -> MagicMock:
    """Simula resposta do OpenRouter com texto (não identificou os campos)."""
    message = MagicMock()
    message.tool_calls = None
    message.content = text

    response = MagicMock()
    response.choices = [MagicMock(message=message)]

    mock_completions = AsyncMock()
    mock_completions.create = AsyncMock(return_value=response)

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = mock_completions
    return mock_client


@pytest.mark.asyncio
class TestChatRouter:
    async def _auth_headers(self, db_session, email: str = "chat@example.com"):
        user = await create_user_with_settings(db_session, email)
        token = create_token(user.id)
        return {"Authorization": f"Bearer {token}"}

    async def _create_category(self, client, headers, name="Alimentação", amount="1000.00"):
        resp = await client.post(
            "/api/categories/",
            headers=headers,
            json={"name": name, "icon": "🛒", "initial_amount": amount},
        )
        assert resp.status_code == 201
        return resp.json()

    # --- BDD: Registrar gasto via mensagem de texto ---

    async def test_chat_creates_transaction_from_message(
        self, client: AsyncClient, db_session
    ):
        """Mensagem 'gastei 80 reais no mercado' deve criar transação na categoria correta."""
        headers = await self._auth_headers(db_session, "chat_create@example.com")
        cat = await self._create_category(client, headers)

        mock_client = _mock_tool_use("registrar_transacao", {"category_name": cat["name"], "description": "Mercado", "amount": 80.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "gastei 80 reais no mercado"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction"] is not None
        assert float(data["transaction"]["amount"]) == 80.0
        assert data["transaction"]["category_id"] == cat["id"]
        assert "reply" in data

    async def test_chat_decreases_category_balance(
        self, client: AsyncClient, db_session
    ):
        """Após criar transação via chat, o saldo da categoria deve diminuir."""
        headers = await self._auth_headers(db_session, "chat_balance@example.com")
        cat = await self._create_category(client, headers, amount="500.00")

        mock_client = _mock_tool_use("registrar_transacao", {"category_name": cat["name"], "description": "Farmácia", "amount": 100.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "gastei 100 reais na farmácia"},
            )

        cat_resp = await client.get("/api/categories/", headers=headers)
        updated = next(c for c in cat_resp.json() if c["id"] == cat["id"])
        assert float(updated["current_balance"]) == 400.0

    # --- BDD: Mensagem não reconhecida retorna resposta sem transação ---

    async def test_chat_returns_text_when_cannot_parse(
        self, client: AsyncClient, db_session
    ):
        """Quando o modelo não identifica os campos, retorna reply sem criar transação."""
        headers = await self._auth_headers(db_session, "chat_noparse@example.com")
        await self._create_category(client, headers)

        mock_client = _mock_text_response("Não entendi o valor. Quanto você gastou?")
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "gastei no mercado"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction"] is None
        assert "Não entendi o valor" in data["reply"]

    # --- BDD: Sem categorias cadastradas ---

    async def test_chat_without_categories_returns_guidance(
        self, client: AsyncClient, db_session
    ):
        """Sem categorias, registrar_transacao orienta o usuário a criar uma."""
        headers = await self._auth_headers(db_session, "chat_nocat@example.com")

        mock_client = _mock_tool_use("registrar_transacao", {"category_name": "Mercado", "description": "mercado", "amount": 50.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "gastei 50 reais no mercado"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction"] is None
        assert "categor" in data["reply"].lower()

    # --- BDD: Histórico do chat ---

    async def test_chat_history_empty_initially(self, client: AsyncClient, db_session):
        """Histórico começa vazio para um novo usuário."""
        headers = await self._auth_headers(db_session, "history_empty@example.com")
        resp = await client.get("/api/chat/", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    async def test_chat_history_saves_messages(self, client: AsyncClient, db_session):
        """Após enviar uma mensagem, o histórico deve conter user + assistant."""
        headers = await self._auth_headers(db_session, "history_save@example.com")
        await self._create_category(client, headers)

        mock_client = _mock_text_response("Quanto você gastou?")
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "gastei no mercado"},
            )

        resp = await client.get("/api/chat/", headers=headers)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "gastei no mercado"
        assert messages[1]["role"] == "assistant"
        assert "Quanto você gastou?" in messages[1]["content"]

    async def test_chat_history_links_transaction(self, client: AsyncClient, db_session):
        """Mensagem do assistente deve ter transaction_id quando transação foi criada."""
        headers = await self._auth_headers(db_session, "history_tx@example.com")
        cat = await self._create_category(client, headers)

        mock_client = _mock_tool_use("registrar_transacao", {"category_name": cat["name"], "description": "Mercado", "amount": 80.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            post_resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "gastei 80 reais no mercado"},
            )

        transaction_id = post_resp.json()["transaction"]["id"]

        resp = await client.get("/api/chat/", headers=headers)
        messages = resp.json()["messages"]
        assistant_msg = next(m for m in messages if m["role"] == "assistant")
        assert assistant_msg["transaction_id"] == transaction_id

    async def test_chat_history_is_used_as_llm_context(
        self, client: AsyncClient, db_session
    ):
        """O histórico deve ser enviado ao LLM nas chamadas seguintes."""
        headers = await self._auth_headers(db_session, "history_ctx@example.com")
        await self._create_category(client, headers)

        mock_client = _mock_text_response("Quanto você gastou?")
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client) as mock_cls:
            await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "gastei no mercado"},
            )
            # Segunda mensagem — verifica que o histórico foi incluído
            await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "foram 50 reais"},
            )

        last_call_messages = mock_cls.return_value.chat.completions.create.call_args_list[-1][1]["messages"]
        roles = [m["role"] for m in last_call_messages]
        # system + user anterior + assistant anterior + nova mensagem user
        assert roles.count("user") >= 2
        assert "assistant" in roles

    # --- BDD: Listar categorias via chat ---

    async def test_chat_lists_categories(self, client: AsyncClient, db_session):
        """listar_categorias retorna lista de categorias no reply."""
        headers = await self._auth_headers(db_session, "chat_listcat@example.com")
        cat = await self._create_category(client, headers, name="Lazer", amount="300.00")

        mock_client = _mock_tool_use("listar_categorias", {})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "lista minhas categorias"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "list_categories"
        assert data["categories"] is not None
        assert any(c["id"] == cat["id"] for c in data["categories"])
        assert cat["name"] in data["reply"]

    # --- BDD: Criar categoria via chat ---

    async def test_chat_creates_category(self, client: AsyncClient, db_session):
        """criar_categoria cria e retorna a categoria na resposta."""
        headers = await self._auth_headers(db_session, "chat_createcat@example.com")

        mock_client = _mock_tool_use("criar_categoria", {"name": "Transporte", "icon": "🚗", "initial_amount": 500.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "cria a categoria Transporte com 500 reais"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "create_category"
        assert data["category"] is not None
        assert data["category"]["name"] == "Transporte"
        assert float(data["category"]["initial_amount"]) == 500.0

    # --- BDD: Editar categoria via chat ---

    async def test_chat_edits_category(self, client: AsyncClient, db_session):
        """editar_categoria atualiza e retorna a categoria atualizada."""
        headers = await self._auth_headers(db_session, "chat_editcat@example.com")
        cat = await self._create_category(client, headers, name="Transporte", amount="500.00")

        mock_client = _mock_tool_use("editar_categoria", {"category_name": "Transporte", "new_budget": 800.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "muda o orçamento de Transporte para 800"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "edit_category"
        assert data["category"] is not None
        assert float(data["category"]["initial_amount"]) == 800.0

    # --- BDD: Deletar categoria via chat ---

    async def test_chat_deletes_category(self, client: AsyncClient, db_session):
        """deletar_categoria remove a categoria."""
        headers = await self._auth_headers(db_session, "chat_deletecat@example.com")
        cat = await self._create_category(client, headers, name="Lazer", amount="200.00")

        mock_client = _mock_tool_use("deletar_categoria", {"category_name": "Lazer"})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "deleta a categoria Lazer"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "delete_category"
        assert "Lazer" in data["reply"]

        # Verify category is actually gone
        cat_resp = await client.get("/api/categories/", headers=headers)
        assert not any(c["id"] == cat["id"] for c in cat_resp.json())

    # --- BDD: Listar transações via chat ---

    async def test_chat_lists_transactions(self, client: AsyncClient, db_session):
        """listar_transacoes retorna as transações recentes."""
        headers = await self._auth_headers(db_session, "chat_listtx@example.com")
        cat = await self._create_category(client, headers)

        # Create a transaction first
        mock_create = _mock_tool_use("registrar_transacao", {"category_name": cat["name"], "description": "Mercado", "amount": 50.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_create):
            await client.post("/api/chat/", headers=headers, json={"message": "gastei 50 no mercado"})

        mock_list = _mock_tool_use("listar_transacoes", {})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_list):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "mostra meus últimos gastos"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "list_transactions"
        assert data["transactions"] is not None
        assert len(data["transactions"]) >= 1

    # --- BDD: Editar transação via chat ---

    async def test_chat_edits_transaction(self, client: AsyncClient, db_session):
        """editar_transacao atualiza valor/descrição da transação."""
        headers = await self._auth_headers(db_session, "chat_edittx@example.com")
        cat = await self._create_category(client, headers)

        mock_create = _mock_tool_use("registrar_transacao", {"category_name": cat["name"], "description": "Mercado", "amount": 50.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_create):
            await client.post("/api/chat/", headers=headers, json={"message": "gastei 50 no mercado"})

        mock_edit = _mock_tool_use("editar_transacao", {"transaction_description": "Mercado", "new_amount": 90.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_edit):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "muda o valor do mercado para 90"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "edit_transaction"
        assert data["transaction"] is not None
        assert float(data["transaction"]["amount"]) == 90.0

    # --- BDD: Deletar transação via chat ---

    async def test_chat_deletes_transaction(self, client: AsyncClient, db_session):
        """deletar_transacao remove a transação e restaura o saldo."""
        headers = await self._auth_headers(db_session, "chat_deletetx@example.com")
        cat = await self._create_category(client, headers, amount="500.00")

        mock_create = _mock_tool_use("registrar_transacao", {"category_name": cat["name"], "description": "Mercado", "amount": 50.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_create):
            await client.post("/api/chat/", headers=headers, json={"message": "gastei 50 no mercado"})

        mock_delete = _mock_tool_use("deletar_transacao", {"transaction_description": "Mercado"})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_delete):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "deleta o gasto do mercado"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "delete_transaction"
        assert "Mercado" in data["reply"]

        # Verify balance restored
        cat_resp = await client.get("/api/categories/", headers=headers)
        updated = next(c for c in cat_resp.json() if c["id"] == cat["id"])
        assert float(updated["current_balance"]) == 500.0

    # --- BDD: Editar transação não encontrada ---

    async def test_chat_edit_transaction_not_found(self, client: AsyncClient, db_session):
        """Quando descrição não bate com nenhuma transação, retorna mensagem de erro."""
        headers = await self._auth_headers(db_session, "chat_edittx_nf@example.com")
        await self._create_category(client, headers)

        mock_edit = _mock_tool_use("editar_transacao", {"transaction_description": "xpto inexistente", "new_amount": 99.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_edit):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "muda o valor do xpto para 99"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction"] is None
        assert "xpto inexistente" in data["reply"]

    # --- BDD: Listar transações com filtro de data ---

    async def test_chat_lists_transactions_hoje(self, client: AsyncClient, db_session):
        """listar_transacoes com date_filter='hoje' retorna transações do dia com total."""
        headers = await self._auth_headers(db_session, "chat_hoje@example.com")
        cat = await self._create_category(client, headers)

        mock_create = _mock_tool_use("registrar_transacao", {"category_name": cat["name"], "description": "Almoço", "amount": 35.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_create):
            await client.post("/api/chat/", headers=headers, json={"message": "gastei 35 no almoço"})

        mock_list = _mock_tool_use("listar_transacoes", {"date_filter": "hoje"})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_list):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "quanto gastei hoje?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "list_transactions"
        assert data["transactions"] is not None
        assert len(data["transactions"]) >= 1
        assert "hoje" in data["reply"]
        assert "Total" in data["reply"]

    async def test_chat_lists_transactions_semana(self, client: AsyncClient, db_session):
        """listar_transacoes com date_filter='semana' retorna transações da semana com total."""
        headers = await self._auth_headers(db_session, "chat_semana@example.com")
        cat = await self._create_category(client, headers)

        mock_create = _mock_tool_use("registrar_transacao", {"category_name": cat["name"], "description": "Uber", "amount": 20.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_create):
            await client.post("/api/chat/", headers=headers, json={"message": "gastei 20 no uber"})

        mock_list = _mock_tool_use("listar_transacoes", {"date_filter": "semana"})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_list):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "gastos da semana"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "list_transactions"
        assert len(data["transactions"]) >= 1
        assert "últimos 7 dias" in data["reply"]
        assert "Total" in data["reply"]

    async def test_chat_listar_transacoes_hoje_vazio(self, client: AsyncClient, db_session):
        """listar_transacoes com date_filter='hoje' sem transações retorna mensagem vazia."""
        headers = await self._auth_headers(db_session, "chat_hoje_empty@example.com")
        await self._create_category(client, headers)

        mock_list = _mock_tool_use("listar_transacoes", {"date_filter": "hoje"})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_list):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "quanto gastei hoje?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "list_transactions"
        assert not data["transactions"]
        assert "hoje" in data["reply"]

    # --- BDD: Criar categoria com nome duplicado ---

    async def test_chat_create_category_duplicate_name(self, client: AsyncClient, db_session):
        """Criar categoria com nome duplicado retorna mensagem de erro sem crash."""
        headers = await self._auth_headers(db_session, "chat_dupcat@example.com")
        await self._create_category(client, headers, name="Alimentação")

        mock_client = _mock_tool_use("criar_categoria", {"name": "Alimentação", "initial_amount": 300.0})
        with patch("app.services.ai_service.AsyncOpenAI", return_value=mock_client):
            resp = await client.post(
                "/api/chat/",
                headers=headers,
                json={"message": "cria a categoria Alimentação com 300 reais"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] is None
        assert "Alimentação" in data["reply"]
