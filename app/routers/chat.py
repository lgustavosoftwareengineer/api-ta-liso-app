from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageRequest, ChatResponse
from app.services.auth_service import get_current_user
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reply, transaction = await chat_service.process_message(db, current_user.id, body.message)
    return ChatResponse(reply=reply, transaction=transaction)
