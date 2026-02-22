"""
Testes do User Service — BDD: Login (criar usuário ao solicitar código), usuário por id/email.
"""
from sqlalchemy import select

import pytest

from app.models.user_settings import UserSettings
from app.services.user_service import (
    get_user_by_id,
    get_user_by_email,
    create_user_with_settings,
)


@pytest.mark.asyncio
class TestUserService:
    """Cenários para busca e criação de usuário."""

    async def test_get_user_by_id_returns_none_when_not_found(self, db_session):
        """Busca por id inexistente retorna None."""
        user = await get_user_by_id(db_session, "id-inexistente")
        assert user is None

    async def test_get_user_by_email_returns_none_when_not_found(self, db_session):
        """Busca por email inexistente retorna None."""
        user = await get_user_by_email(db_session, "naoexiste@example.com")
        assert user is None

    async def test_create_user_with_settings_creates_user_and_settings(self, db_session):
        """Cria usuário e suas configurações padrão (UserSettings)."""
        user = await create_user_with_settings(db_session, "novo@example.com")
        assert user.id is not None
        assert user.email == "novo@example.com"
        # Verifica UserSettings via query para evitar lazy load fora do contexto async
        result = await db_session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings = result.scalar_one_or_none()
        assert settings is not None
        assert settings.user_id == user.id

    async def test_get_user_by_id_returns_user_after_create(self, db_session):
        """Busca por id retorna o usuário criado."""
        user = await create_user_with_settings(db_session, "getbyid@example.com")
        found = await get_user_by_id(db_session, user.id)
        assert found is not None
        assert found.id == user.id
        assert found.email == user.email

    async def test_get_user_by_email_returns_user_after_create(self, db_session):
        """Busca por email retorna o usuário criado."""
        email = "getbyemail@example.com"
        await create_user_with_settings(db_session, email)
        found = await get_user_by_email(db_session, email)
        assert found is not None
        assert found.email == email
