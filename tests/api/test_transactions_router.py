"""
Testes do Transactions Router — BDD: Registro de gastos, listar/ criar/ atualizar/ excluir.
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user_settings import UserSettings
from app.services.user_service import create_user_with_settings
from app.services.jwt_service import create_token


@pytest.mark.asyncio
class TestTransactionsRouter:
    """Cenários de transações via API."""

    async def _auth_headers(self, db_session, email: str = "tx@example.com"):
        user = await create_user_with_settings(db_session, email)
        token = create_token(user.id)
        return {"Authorization": f"Bearer {token}"}, user

    async def _create_category(self, client, headers, name="Alimentação", amount="1000.00"):
        resp = await client.post(
            "/api/categories/",
            headers=headers,
            json={"name": name, "icon": "🛒", "initial_amount": amount},
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_list_transactions_empty(self, client: AsyncClient, db_session):
        headers, _ = await self._auth_headers(db_session, "listtx@example.com")
        resp = await client.get("/api/transactions/", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_transaction_returns_201(self, client: AsyncClient, db_session):
        headers, _ = await self._auth_headers(db_session, "createtx@example.com")
        cat = await self._create_category(client, headers)
        resp = await client.post(
            "/api/transactions/",
            headers=headers,
            json={"category_id": cat["id"], "description": "Mercado", "amount": "200.00"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Mercado"
        assert float(data["amount"]) == 200.0
        assert data["category_id"] == cat["id"]

    # --- BDD: Criar transação reduz o saldo da categoria ---

    async def test_create_transaction_decreases_category_balance(
        self, client: AsyncClient, db_session
    ):
        """Ao criar transação de R$200 em categoria com R$1000, saldo deve ir para R$800."""
        headers, _ = await self._auth_headers(db_session, "balance_decrease@example.com")
        cat = await self._create_category(client, headers, amount="1000.00")

        await client.post(
            "/api/transactions/",
            headers=headers,
            json={"category_id": cat["id"], "description": "Mercado", "amount": "200.00"},
        )

        cat_resp = await client.get("/api/categories/", headers=headers)
        updated = next(c for c in cat_resp.json() if c["id"] == cat["id"])
        assert float(updated["current_balance"]) == 800.0

    # --- BDD: Excluir transação restaura o saldo da categoria ---

    async def test_delete_transaction_restores_category_balance(
        self, client: AsyncClient, db_session
    ):
        """Ao excluir transação de R$200, saldo deve voltar de R$800 para R$1000."""
        headers, _ = await self._auth_headers(db_session, "balance_restore@example.com")
        cat = await self._create_category(client, headers, amount="1000.00")

        tx_resp = await client.post(
            "/api/transactions/",
            headers=headers,
            json={"category_id": cat["id"], "description": "Mercado", "amount": "200.00"},
        )
        tx_id = tx_resp.json()["id"]

        await client.delete(f"/api/transactions/{tx_id}", headers=headers)

        cat_resp = await client.get("/api/categories/", headers=headers)
        updated = next(c for c in cat_resp.json() if c["id"] == cat["id"])
        assert float(updated["current_balance"]) == 1000.0

    # --- BDD: Atualizar valor de transação ajusta o saldo ---

    async def test_update_transaction_adjusts_category_balance(
        self, client: AsyncClient, db_session
    ):
        """Ao alterar transação de R$200 para R$300, saldo deve ir de R$800 para R$700."""
        headers, _ = await self._auth_headers(db_session, "balance_adjust@example.com")
        cat = await self._create_category(client, headers, amount="1000.00")

        tx_resp = await client.post(
            "/api/transactions/",
            headers=headers,
            json={"category_id": cat["id"], "description": "Mercado", "amount": "200.00"},
        )
        tx_id = tx_resp.json()["id"]

        await client.put(
            f"/api/transactions/{tx_id}",
            headers=headers,
            json={"amount": "300.00"},
        )

        cat_resp = await client.get("/api/categories/", headers=headers)
        updated = next(c for c in cat_resp.json() if c["id"] == cat["id"])
        assert float(updated["current_balance"]) == 700.0

    # --- BDD: Bloquear transação com saldo insuficiente (bloqueio ativado) ---

    async def test_create_transaction_blocked_when_insufficient_balance(
        self, client: AsyncClient, db_session
    ):
        """Com block_negative_balance=True e saldo R$30, transação de R$150 deve retornar 422."""
        headers, user = await self._auth_headers(db_session, "blocked@example.com")

        # Ativa block_negative_balance
        result = await db_session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        user_settings = result.scalar_one()
        user_settings.block_negative_balance = True
        await db_session.commit()

        cat = await self._create_category(client, headers, name="Saúde", amount="30.00")

        resp = await client.post(
            "/api/transactions/",
            headers=headers,
            json={"category_id": cat["id"], "description": "Consulta", "amount": "150.00"},
        )
        assert resp.status_code == 422
        assert "insuficiente" in resp.json()["detail"].lower()

        # Saldo não deve ter sido alterado
        cat_resp = await client.get("/api/categories/", headers=headers)
        updated = next(c for c in cat_resp.json() if c["id"] == cat["id"])
        assert float(updated["current_balance"]) == 30.0

    # --- BDD: Permitir transação com saldo insuficiente (bloqueio desativado) ---

    async def test_create_transaction_allowed_when_insufficient_balance_no_block(
        self, client: AsyncClient, db_session
    ):
        """Com block_negative_balance=False (padrão), transação acima do saldo deve ser permitida."""
        headers, _ = await self._auth_headers(db_session, "noblock@example.com")
        cat = await self._create_category(client, headers, name="Lazer", amount="50.00")

        resp = await client.post(
            "/api/transactions/",
            headers=headers,
            json={"category_id": cat["id"], "description": "Show", "amount": "200.00"},
        )
        assert resp.status_code == 201

        cat_resp = await client.get("/api/categories/", headers=headers)
        updated = next(c for c in cat_resp.json() if c["id"] == cat["id"])
        assert float(updated["current_balance"]) == -150.0
