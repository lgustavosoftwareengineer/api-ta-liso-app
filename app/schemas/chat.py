from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.transaction import TransactionResponse


class ChatMessageRequest(BaseModel):
    message: str


class InsufficientBalanceDetail(BaseModel):
    available: Decimal
    requested: Decimal
    message: str


class ChatResponse(BaseModel):
    reply: str
    transaction: TransactionResponse | None = None
    insufficient_balance: InsufficientBalanceDetail | None = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    transaction_id: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]
