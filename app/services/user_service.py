from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_settings import UserSettings


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Busca usuário por id."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Busca usuário por email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, user_id: str, name: str) -> User | None:
    """Atualiza o nome do usuário."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None
    user.name = name
    await db.commit()
    await db.refresh(user)
    return user


async def create_user_with_settings(db: AsyncSession, email: str) -> User:
    """Cria usuário e suas configurações padrão."""
    user = User(email=email)
    db.add(user)
    await db.flush()

    user_settings = UserSettings(user_id=user.id)
    db.add(user_settings)
    await db.commit()
    await db.refresh(user)
    return user
