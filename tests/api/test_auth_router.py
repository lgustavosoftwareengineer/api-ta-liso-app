"""
Testes do Auth Router (controllers) — BDD: Login sem senha via e-mail.
Solicitar código com e-mail válido/inválido, validar token, acessar rota protegida sem auth.
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.user_service import create_user_with_settings
from app.services.auth_service import store_login_code, generate_login_code
from app.services.jwt_service import create_token


@pytest.mark.asyncio
class TestAuthRouter:
    """Cenários de login e proteção de rotas."""

    async def test_request_code_valid_email_returns_204_and_sends_email(
        self, client: AsyncClient, db_session
    ):
        """Usuário solicita código com e-mail válido: 204, token gerado e enviado por e-mail."""
        with patch("app.services.email.send_login_code", new_callable=AsyncMock) as mock_send:
            resp = await client.post(
                "/api/auth/request-code",
                json={"email": "valido@example.com"},
            )
            assert resp.status_code == 204
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert args[0] == "valido@example.com"
            assert len(args[1]) == 6
            assert args[1].isdigit()

    async def test_request_code_invalid_email_returns_422(self, client: AsyncClient):
        """Usuário informa e-mail com formato inválido: sistema exibe erro, não envia e-mail."""
        with patch("app.services.email.send_login_code", new_callable=AsyncMock) as mock_send:
            resp = await client.post(
                "/api/auth/request-code",
                json={"email": "joaoemail.com"},
            )
            assert resp.status_code == 422
            mock_send.assert_not_called()

    async def test_verify_code_valid_returns_jwt(self, client: AsyncClient, db_session):
        """Usuário autentica com token válido: sistema valida e gera JWT de sessão."""
        user = await create_user_with_settings(db_session, "verify@example.com")
        code = generate_login_code()
        await store_login_code(db_session, user.id, code)
        resp = await client.post(
            "/api/auth/verify-code",
            json={"email": "verify@example.com", "code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data.get("token_type") == "bearer"
        # Decode and check sub
        from app.services.jwt_service import decode_token
        user_id = decode_token(data["access_token"])
        assert user_id == user.id

    async def test_verify_code_invalid_returns_401(self, client: AsyncClient, db_session):
        """Usuário informa token incorreto: sistema exibe mensagem de token inválido."""
        user = await create_user_with_settings(db_session, "invalid@example.com")
        await store_login_code(db_session, user.id, generate_login_code())
        resp = await client.post(
            "/api/auth/verify-code",
            json={"email": "invalid@example.com", "code": "000000"},
        )
        assert resp.status_code == 401
        assert "inválido" in resp.json().get("detail", "").lower() or "expirado" in resp.json().get("detail", "").lower()

    async def test_verify_code_unknown_email_returns_401(self, client: AsyncClient):
        """E-mail que nunca solicitou código: 401."""
        resp = await client.post(
            "/api/auth/verify-code",
            json={"email": "naoexiste@example.com", "code": "123456"},
        )
        assert resp.status_code == 401

    async def test_protected_route_without_auth_returns_401(
        self, client: AsyncClient
    ):
        """Usuário tenta acessar tela protegida sem autenticação: 401 ou 403."""
        resp = await client.get("/api/categories/")
        # HTTPBearer retorna 403 quando não envia header; 401 quando token inválido
        assert resp.status_code in (401, 403)

    async def test_protected_route_with_valid_jwt_returns_200(
        self, client: AsyncClient, db_session
    ):
        """Usuário autenticado acessa rota protegida: 200."""
        user = await create_user_with_settings(db_session, "protected@example.com")
        token = create_token(user.id)
        resp = await client.get(
            "/api/categories/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
