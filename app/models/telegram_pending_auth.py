from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TelegramPendingAuth(Base):
    __tablename__ = "telegram_pending_auth"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
