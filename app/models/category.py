import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, func, Numeric, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(10), nullable=True)
    initial_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reset_month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reset_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="categories")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="category"
    )
    monthly_snapshots: Mapped[list["CategoryMonthlySnapshot"]] = relationship(
        "CategoryMonthlySnapshot", back_populates="category", cascade="all, delete-orphan"
    )
