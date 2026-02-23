"""
Testes do UserSettings Router — BDD: Consultar e atualizar configurações do usuário.
"""
import pytest
from httpx import AsyncClient

from app.services.user_service import create_user_with_settings
from app.services.jwt_service import create_token


@pytest.mark.asyncio
class TestUserSettingsRouter:
    """Cenários de configurações de usuário via API."""

    async def _auth_headers(self, db_session, email: str = "settings@example.com"):
        user = await create_user_with_settings(db_session, email)
        token = create_token(user.id)
        return {"Authorization": f"Bearer {token}"}, user

    # --- BDD: Consultar configurações do usuário ---

    async def test_get_settings_returns_defaults(self, client: AsyncClient, db_session):
        """GET /api/settings/ deve retornar configurações padrão do usuário."""
        headers, _ = await self._auth_headers(db_session, "get_settings@example.com")
        resp = await client.get("/api/settings/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["alert_low_balance"] is True
        assert data["monthly_reset"] is True
        assert data["block_negative_balance"] is False

    # --- BDD: Ativar/desativar notificação de saldo crítico ---

    async def test_patch_alert_low_balance(self, client: AsyncClient, db_session):
        """PATCH /api/settings/ deve atualizar alert_low_balance."""
        headers, _ = await self._auth_headers(db_session, "patch_alert@example.com")
        resp = await client.patch("/api/settings/", headers=headers, json={"alert_low_balance": False})
        assert resp.status_code == 200
        assert resp.json()["alert_low_balance"] is False

    # --- BDD: Ativar/desativar reset mensal automático ---

    async def test_patch_monthly_reset(self, client: AsyncClient, db_session):
        """PATCH /api/settings/ deve atualizar monthly_reset."""
        headers, _ = await self._auth_headers(db_session, "patch_reset@example.com")
        resp = await client.patch("/api/settings/", headers=headers, json={"monthly_reset": False})
        assert resp.status_code == 200
        assert resp.json()["monthly_reset"] is False

    # --- BDD: Ativar/desativar bloqueio de saldo negativo ---

    async def test_patch_block_negative_balance(self, client: AsyncClient, db_session):
        """PATCH /api/settings/ deve atualizar block_negative_balance."""
        headers, _ = await self._auth_headers(db_session, "patch_block@example.com")
        resp = await client.patch(
            "/api/settings/", headers=headers, json={"block_negative_balance": True}
        )
        assert resp.status_code == 200
        assert resp.json()["block_negative_balance"] is True

    async def test_patch_multiple_fields(self, client: AsyncClient, db_session):
        """PATCH /api/settings/ deve atualizar múltiplos campos de uma vez."""
        headers, _ = await self._auth_headers(db_session, "patch_multi@example.com")
        resp = await client.patch(
            "/api/settings/",
            headers=headers,
            json={"alert_low_balance": False, "block_negative_balance": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["alert_low_balance"] is False
        assert data["block_negative_balance"] is True
        assert data["monthly_reset"] is True  # não alterado

    async def test_get_settings_requires_auth(self, client: AsyncClient, db_session):
        """GET /api/settings/ sem token deve retornar 403."""
        resp = await client.get("/api/settings/")
        assert resp.status_code == 403

    async def test_patch_settings_requires_auth(self, client: AsyncClient, db_session):
        """PATCH /api/settings/ sem token deve retornar 403."""
        resp = await client.patch("/api/settings/", json={"monthly_reset": False})
        assert resp.status_code == 403
