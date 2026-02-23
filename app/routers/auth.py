from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import RequestLoginCode, VerifyLoginCode, TokenResponse
from app.services.auth_service import request_login_code, authenticate

router = APIRouter(tags=["auth"])


@router.post("/request-code", status_code=status.HTTP_204_NO_CONTENT)
async def request_code(body: RequestLoginCode, db: AsyncSession = Depends(get_db)):
    await request_login_code(db, body.email)


@router.post("/verify-code", response_model=TokenResponse)
async def verify_code(body: VerifyLoginCode, db: AsyncSession = Depends(get_db)):
    try:
        token = await authenticate(db, body.email, body.code)
        return TokenResponse(access_token=token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
