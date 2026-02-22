from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    icon: str | None = None
    initial_amount: Decimal


class CategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    initial_amount: Decimal | None = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    icon: str | None
    initial_amount: Decimal
    current_balance: Decimal
    reset_month: int | None
    reset_year: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
