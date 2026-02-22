import random
import string
from datetime import datetime, timezone, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.login_token import LoginToken
from app.models.user import User
from app.services.jwt_service import decode_token
from app.services.user_service import get_user_by_id
from app.services.monthly_reset_service import ensure_monthly_reset

settings = get_settings()
bearer_scheme = HTTPBearer()


def generate_login_code() -> str:
    """Gera código numérico de 6 dígitos para login."""
    return "".join(random.choices(string.digits, k=6))


async def store_login_code(db: AsyncSession, user_id: str, code: str) -> None:
    """Armazena o código de login com TTL."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.login_token_ttl_seconds
    )
    token = LoginToken(user_id=user_id, token=code, expires_at=expires_at)
    db.add(token)
    await db.commit()


async def verify_login_code(db: AsyncSession, user_id: str, code: str) -> bool:
    """Valida o código de login e marca como usado."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(LoginToken).where(
            LoginToken.user_id == user_id,
            LoginToken.token == code,
            LoginToken.expires_at > now,
            LoginToken.used == False,  # noqa: E712
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        return False

    token.used = True
    await db.commit()
    return True


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: valida o JWT e retorna o usuário autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_token(credentials.credentials)
    if user_id is None:
        raise credentials_exception

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    # Lazy reset: no primeiro acesso do mês, snapshot + reset de categorias (se config ativa)
    await ensure_monthly_reset(db, user.id)

    return user
