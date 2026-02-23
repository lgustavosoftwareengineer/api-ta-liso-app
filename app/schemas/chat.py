from pydantic import BaseModel

from app.schemas.transaction import TransactionResponse


class ChatMessageRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    transaction: TransactionResponse | None = None
