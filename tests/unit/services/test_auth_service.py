"""
Testes do Auth Service — BDD: token numérico 6 dígitos, salvar/validar token, get_current_user.
"""
import pytest

from app.services.auth_service import (
    generate_login_code,
    store_login_code,
    verify_login_code,
)
from app.services.user_service import create_user_with_settings
from app.services.jwt_service import create_token, decode_token


class TestAuthServiceLoginCode:
    """Cenários para código de login (6 dígitos, armazenar, validar)."""

    def test_generate_login_code_returns_six_digits(self):
        """Sistema deve gerar um token numérico de 6 dígitos."""
        code = generate_login_code()
        assert len(code) == 6
        assert code.isdigit()

    @pytest.mark.asyncio
    async def test_verify_login_code_succeeds_with_valid_stored_code(self, db_session):
        """Usuário autentica com token válido: sistema valida o token."""
        user = await create_user_with_settings(db_session, "auth@example.com")
        code = generate_login_code()
        await store_login_code(db_session, user.id, code)
        valid = await verify_login_code(db_session, user.id, code)
        assert valid is True

    @pytest.mark.asyncio
    async def test_verify_login_code_fails_with_wrong_code(self, db_session):
        """Usuário informa token incorreto: sistema exibe mensagem de token inválido."""
        user = await create_user_with_settings(db_session, "auth2@example.com")
        code = generate_login_code()
        await store_login_code(db_session, user.id, code)
        valid = await verify_login_code(db_session, user.id, "000000")
        assert valid is False

    @pytest.mark.asyncio
    async def test_verify_login_code_fails_after_code_used_once(self, db_session):
        """Token usado uma vez não pode ser reutilizado."""
        user = await create_user_with_settings(db_session, "auth3@example.com")
        code = generate_login_code()
        await store_login_code(db_session, user.id, code)
        first = await verify_login_code(db_session, user.id, code)
        assert first is True
        second = await verify_login_code(db_session, user.id, code)
        assert second is False
