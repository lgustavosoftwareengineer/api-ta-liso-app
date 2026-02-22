import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, func, Numeric, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CategoryMonthlySnapshot(Base):
    __tablename__ = "category_monthly_snapshots"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    category_id: Mapped[str] = mapped_column(
        String, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    initial_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_spent: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    final_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    category: Mapped["Category"] = relationship(
        "Category", back_populates="monthly_snapshots"
    )
