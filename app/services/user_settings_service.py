from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings import UserSettings
from app.schemas.user_settings import UserSettingsUpdate


async def get_user_settings(db: AsyncSession, user_id: str) -> UserSettings | None:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_user_settings(
    db: AsyncSession, user_id: str, data: UserSettingsUpdate
) -> UserSettings | None:
    settings = await get_user_settings(db, user_id)
    if settings is None:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)
    return settings
