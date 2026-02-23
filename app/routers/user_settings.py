from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user_settings import UserSettingsUpdate, UserSettingsResponse
from app.services.auth_service import get_current_user
from app.services import user_settings_service

router = APIRouter(tags=["settings"])


@router.get("/", response_model=UserSettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await user_settings_service.get_user_settings(db, current_user.id)
    if settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configurações não encontradas")
    return settings


@router.patch("/", response_model=UserSettingsResponse)
async def update_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await user_settings_service.update_user_settings(db, current_user.id, body)
    if settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configurações não encontradas")
    return settings
