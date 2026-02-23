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
        with patch("app.services.chat_service.AsyncOpenAI", return_value=mock_client):
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
        with patch("app.services.chat_service.AsyncOpenAI", return_value=mock_client):
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
        with patch("app.services.chat_service.AsyncOpenAI", return_value=mock_client):
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
