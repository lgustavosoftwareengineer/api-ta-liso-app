"""
Testes do Categories Router — BDD: Gerenciamento de Categorias (CRUD via API).
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.services.user_service import create_user_with_settings
from app.services.jwt_service import create_token


@pytest.mark.asyncio
class TestCategoriesRouter:
    """Cenários de listar, criar, editar e excluir categorias via API."""

    async def _auth_headers(self, db_session, email: str = "catrouter@example.com"):
        user = await create_user_with_settings(db_session, email)
        token = create_token(user.id)
        return {"Authorization": f"Bearer {token}"}, user

    async def test_list_categories_empty(self, client: AsyncClient, db_session):
        headers, _ = await self._auth_headers(db_session, "listcat@example.com")
        resp = await client.get("/api/categories/", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_category_returns_201(self, client: AsyncClient, db_session):
        headers, user = await self._auth_headers(db_session, "createcat@example.com")
        resp = await client.post(
            "/api/categories/",
            headers=headers,
            json={
                "name": "Alimentação",
                "icon": "🛒",
                "initial_amount": "1000.00",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Alimentação"
        assert data["icon"] == "🛒"
        assert float(data["initial_amount"]) == 1000.0
        assert float(data["current_balance"]) == 1000.0

    async def test_create_category_duplicate_name_returns_error(
        self, client: AsyncClient, db_session
    ):
        headers, _ = await self._auth_headers(db_session, "dup@example.com")
        payload = {
            "name": "Transporte",
            "icon": "🚗",
            "initial_amount": "500.00",
        }
        await client.post("/api/categories/", headers=headers, json=payload)
        resp = await client.post("/api/categories/", headers=headers, json=payload)
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        assert "já existe" in detail.lower()

    async def test_update_category_returns_200(self, client: AsyncClient, db_session):
        headers, _ = await self._auth_headers(db_session, "upcat@example.com")
        create_resp = await client.post(
            "/api/categories/",
            headers=headers,
            json={"name": "Lazer", "icon": "🎉", "initial_amount": "300.00"},
        )
        cat_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/categories/{cat_id}",
            headers=headers,
            json={"name": "Lazer e Viagens", "initial_amount": "500.00"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Lazer e Viagens"
        assert float(resp.json()["initial_amount"]) == 500.0

    async def test_delete_category_returns_204(self, client: AsyncClient, db_session):
        headers, _ = await self._auth_headers(db_session, "delcat@example.com")
        create_resp = await client.post(
            "/api/categories/",
            headers=headers,
            json={"name": "Teste", "icon": "📁", "initial_amount": "100.00"},
        )
        cat_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/categories/{cat_id}", headers=headers)
        assert resp.status_code == 204
        list_resp = await client.get("/api/categories/", headers=headers)
        assert len(list_resp.json()) == 0
