from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import RequestLoginCode, VerifyLoginCode, TokenResponse
from app.services.auth_service import (
    generate_login_code,
    store_login_code,
    verify_login_code,
)
from app.services.email import send_login_code
from app.services.jwt_service import create_token
from app.services.user_service import create_user_with_settings, get_user_by_email

router = APIRouter(tags=["auth"])


@router.post("/request-code", status_code=status.HTTP_204_NO_CONTENT)
async def request_code(body: RequestLoginCode, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, body.email)
    if user is None:
        user = await create_user_with_settings(db, body.email)

    code = generate_login_code()
    await store_login_code(db, user.id, code)
    await send_login_code(body.email, code)


@router.post("/verify-code", response_model=TokenResponse)
async def verify_code(body: VerifyLoginCode, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, body.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código inválido ou expirado",
        )

    valid = await verify_login_code(db, user.id, body.code)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código inválido ou expirado",
        )

    return TokenResponse(access_token=create_token(user.id))
