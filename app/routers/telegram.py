"""Telegram webhook endpoint: receives updates and delegates to telegram_service."""
import logging

from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services import telegram_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telegram"])


async def _process_webhook_task(chat_id: int, text: str) -> None:
    """Run in background with its own DB session."""
    try:
        async with AsyncSessionLocal() as db:
            await telegram_service.handle_message(db, chat_id, text)
    except Exception as e:
        logger.exception("Telegram webhook task failed chat_id=%s text=%r: %s", chat_id, text, e)


@router.post("/webhooks/telegram", status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Telegram updates. Auth via X-Telegram-Bot-Api-Secret-Token; process in background."""
    settings = get_settings()
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not settings.telegram_webhook_secret or secret != settings.telegram_webhook_secret:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized"},
        )
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=status.HTTP_200_OK, content={})
    message = body.get("message")
    if not message or not isinstance(message, dict):
        return JSONResponse(status_code=status.HTTP_200_OK, content={})
    chat = message.get("chat")
    if not chat or not isinstance(chat, dict):
        return JSONResponse(status_code=status.HTTP_200_OK, content={})
    try:
        chat_id = int(chat.get("id"))
    except (TypeError, ValueError):
        return JSONResponse(status_code=status.HTTP_200_OK, content={})
    text = message.get("text")
    if not text or not isinstance(text, str):
        return JSONResponse(status_code=status.HTTP_200_OK, content={})
    logger.info("Telegram webhook: chat_id=%s text=%r", chat_id, text)
    background_tasks.add_task(_process_webhook_task, chat_id, text)
    return {}
