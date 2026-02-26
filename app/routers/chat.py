from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.category import CategoryResponse
from app.schemas.chat import ChatHistoryResponse, ChatMessageRequest, ChatMessageResponse, ChatResponse, TransactionResponse
from app.schemas.chat_result import ChatProcessResult
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
    result: ChatProcessResult = await chat_service.process_message(db, current_user.id, body.message)

    return ChatResponse(
        reply=result.reply,
        action=result.action,
        transaction=TransactionResponse.model_validate(result.transaction) if result.transaction else None,
        insufficient_balance=result.insufficient_balance,
        categories=[CategoryResponse.model_validate(c) for c in result.categories] if result.categories else None,
        category=CategoryResponse.model_validate(result.category) if result.category else None,
        transactions=[TransactionResponse.model_validate(t) for t in result.transactions] if result.transactions else None,
    )
