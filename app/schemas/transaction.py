from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    category_id: str | None = None
    description: str
    amount: Decimal


class TransactionUpdate(BaseModel):
    category_id: str | None = None
    description: str | None = None
    amount: Decimal | None = None


class TransactionResponse(BaseModel):
    id: str
    category_id: str | None
    description: str
    amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}
