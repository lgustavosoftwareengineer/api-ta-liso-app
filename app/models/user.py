from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.telegram_user import TelegramUser

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    categories: Mapped[list["Category"]] = relationship(
        "Category", back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )
    login_tokens: Mapped[list["LoginToken"]] = relationship(
        "LoginToken", back_populates="user", cascade="all, delete-orphan"
    )
    settings: Mapped["UserSettings"] = relationship(
        "UserSettings", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="user", cascade="all, delete-orphan"
    )
    telegram_user: Mapped[Optional["TelegramUser"]] = relationship(
        "TelegramUser", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
