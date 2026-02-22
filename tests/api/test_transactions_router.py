"""
Testes do Transactions Router — BDD: Registro de gastos, listar/ criar/ atualizar/ excluir.
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.services.user_service import create_user_with_settings
from app.services.jwt_service import create_token


@pytest.mark.asyncio
class TestTransactionsRouter:
    """Cenários de transações via API."""

    async def _auth_headers(self, db_session, email: str = "tx@example.com"):
        user = await create_user_with_settings(db_session, email)
        token = create_token(user.id)
        return {"Authorization": f"Bearer {token}"}, user

    async def test_list_transactions_empty(self, client: AsyncClient, db_session):
        headers, _ = await self._auth_headers(db_session, "listtx@example.com")
        resp = await client.get("/api/transactions/", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_transaction_returns_201(self, client: AsyncClient, db_session):
        headers, user = await self._auth_headers(db_session, "createtx@example.com")
        # Criar categoria para vincular (opcional no schema)
        cat_resp = await client.post(
            "/api/categories/",
            headers=headers,
            json={"name": "Alimentação", "icon": "🛒", "initial_amount": "1000.00"},
        )
        cat_id = cat_resp.json()["id"]
        resp = await client.post(
            "/api/transactions/",
            headers=headers,
            json={
                "category_id": cat_id,
                "description": "Mercado",
                "amount": "200.00",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Mercado"
        assert float(data["amount"]) == 200.0
        assert data["category_id"] == cat_id
