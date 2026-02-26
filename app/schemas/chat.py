from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.category import CategoryResponse
from app.schemas.transaction import TransactionResponse


class ChatMessageRequest(BaseModel):
    message: str


class InsufficientBalanceDetail(BaseModel):
    available: Decimal
    requested: Decimal
    message: str


class ChatResponse(BaseModel):
    reply: str
    action: str | None = None
    transaction: TransactionResponse | None = None
    insufficient_balance: InsufficientBalanceDetail | None = None
    categories: list[CategoryResponse] | None = None
    category: CategoryResponse | None = None
    transactions: list[TransactionResponse] | None = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    transaction_id: str | None = None
    category_id: str | None = None
    balance_available: Decimal | None = None
    balance_requested: Decimal | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]
