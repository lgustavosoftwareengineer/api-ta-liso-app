"""
Testes do Chat Router — BDD: Registro de gastos via linguagem natural.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.user_service import create_user_with_settings
from app.services.jwt_service import create_token


def _mock_tool_use(category_name: str, description: str, amount: float) -> MagicMock:
    """Simula resposta do OpenRouter com tool_call (campos extraídos com sucesso)."""
    tool_call = MagicMock()
    tool_call.function = MagicMock()
    tool_call.function.arguments = json.dumps(
        {"category_name": category_name, "description": description, "amount": amount}
    )

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

        mock_client = _mock_tool_use(cat["name"], "Mercado", 80.0)
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

        mock_client = _mock_tool_use(cat["name"], "Farmácia", 100.0)
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
        """Sem categorias, resposta orienta o usuário a criar uma."""
        headers = await self._auth_headers(db_session, "chat_nocat@example.com")

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

        mock_client = _mock_tool_use(cat["name"], "Mercado", 80.0)
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
