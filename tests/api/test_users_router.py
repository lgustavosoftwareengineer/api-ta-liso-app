"""
Testes do Users Router — BDD: Consultar e atualizar perfil do usuário.
"""
import pytest
from httpx import AsyncClient

from app.services.user_service import create_user_with_settings
from app.services.jwt_service import create_token


@pytest.mark.asyncio
class TestUsersRouter:
    """Cenários de perfil de usuário via API."""

    async def _auth_headers(self, db_session, email: str = "profile@example.com"):
        user = await create_user_with_settings(db_session, email)
        token = create_token(user.id)
        return {"Authorization": f"Bearer {token}"}, user

    # --- BDD: Consultar perfil ---

    async def test_get_profile_returns_email_and_name(self, client: AsyncClient, db_session):
        """GET /api/users/me/ deve retornar id, email e name do usuário."""
        headers, user = await self._auth_headers(db_session, "get_profile@example.com")
        resp = await client.get("/api/users/me/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "get_profile@example.com"
        assert "name" in data
        assert "id" in data

    # --- BDD: Atualizar nome do usuário ---

    async def test_patch_name_updates_profile(self, client: AsyncClient, db_session):
        """PATCH /api/users/me/ deve atualizar o nome do usuário."""
        headers, _ = await self._auth_headers(db_session, "patch_name@example.com")
        resp = await client.patch("/api/users/me/", headers=headers, json={"name": "João Silva"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "João Silva"

    async def test_patch_name_persists_on_get(self, client: AsyncClient, db_session):
        """Nome atualizado deve ser retornado no GET seguinte."""
        headers, _ = await self._auth_headers(db_session, "patch_persist@example.com")
        await client.patch("/api/users/me/", headers=headers, json={"name": "Maria Souza"})
        resp = await client.get("/api/users/me/", headers=headers)
        assert resp.json()["name"] == "Maria Souza"

    async def test_patch_name_empty_returns_422(self, client: AsyncClient, db_session):
        """PATCH com nome vazio deve retornar 422."""
        headers, _ = await self._auth_headers(db_session, "patch_empty@example.com")
        resp = await client.patch("/api/users/me/", headers=headers, json={"name": ""})
        assert resp.status_code == 422

    # --- BDD: Autenticação obrigatória ---

    async def test_get_profile_requires_auth(self, client: AsyncClient, db_session):
        """GET /api/users/me/ sem token deve retornar 403."""
        resp = await client.get("/api/users/me/")
        assert resp.status_code == 403

    async def test_patch_profile_requires_auth(self, client: AsyncClient, db_session):
        """PATCH /api/users/me/ sem token deve retornar 403."""
        resp = await client.patch("/api/users/me/", json={"name": "Alguém"})
        assert resp.status_code == 403
