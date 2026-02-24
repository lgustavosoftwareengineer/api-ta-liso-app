from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatHistoryResponse, ChatMessageRequest, ChatMessageResponse, ChatResponse, TransactionResponse
from app.services.auth_service import get_current_user
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.get("/", response_model=ChatHistoryResponse)
async def get_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await chat_service.list_history(db, current_user.id)
    return ChatHistoryResponse(
        messages=[ChatMessageResponse.model_validate(m) for m in messages]
    )


@router.post("/", response_model=ChatResponse)
async def chat(
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reply, transactionNullable, insufficient_balance = await chat_service.process_message(db, current_user.id, body.message)

    if transactionNullable is not None:
        return ChatResponse(
            reply=reply,
            transaction=TransactionResponse.model_validate(transactionNullable),
        )

    return ChatResponse(reply=reply, insufficient_balance=insufficient_balance)
    
