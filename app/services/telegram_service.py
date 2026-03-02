"""Telegram bot integration: webhook handling, registration flow, and message formatting."""
import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.telegram_pending_auth import TelegramPendingAuth
from app.models.telegram_user import TelegramUser
from app.models.user import User
from app.schemas.chat_result import ChatProcessResult
from app.services import auth_service
from app.services import chat_service
from app.services.user_service import get_user_by_email

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

COMMANDS_HELP = (
    "📋 Comandos disponíveis:\n\n"
    "/gasto <valor> <descrição> <categoria>\n"
    "  Ex: /gasto 35 Almoço Alimentação\n\n"
    "/categorias — Ver categorias e saldos\n\n"
    "/gastos — Últimas transações\n"
    "/gastos hoje — Gastos de hoje\n"
    "/gastos semana — Últimos 7 dias\n"
    "/gastos mes — Mês atual\n\n"
    "/ajuda — Esta mensagem\n\n"
    "💬 Você também pode escrever naturalmente, tipo:\n"
    "\"Gastei 50 reais no mercado, Alimentação\""
)

_GASTOS_FILTER_PHRASES = {
    "hoje": "listar transações hoje",
    "semana": "listar transações semana",
    "mes": "listar transações mes",
}


async def send_message(chat_id: int, text: str) -> None:
    """Send a text message to a Telegram chat via Bot API."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not set; skipping send_message (chat_id=%s). "
            "Check env/Secret Manager key TELEGRAM_BOT_TOKEN.",
            chat_id,
        )
        return
    url = f"{TELEGRAM_API_BASE}/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url,
                json={"chat_id": chat_id, "text": text},
                timeout=10.0,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            logger.exception("Telegram sendMessage failed: %s", e)
            raise


async def get_user_by_telegram_chat_id(
    db: AsyncSession, chat_id: int
) -> User | None:
    """Return the User linked to this telegram_chat_id, or None."""
    result = await db.execute(
        select(TelegramUser)
        .where(TelegramUser.telegram_chat_id == chat_id)
        .options(selectinload(TelegramUser.user))
    )
    tu = result.scalar_one_or_none()
    if tu is None:
        return None
    return tu.user


async def get_pending_auth(
    db: AsyncSession, chat_id: int
) -> TelegramPendingAuth | None:
    """Return pending auth record for this chat_id, or None."""
    result = await db.execute(
        select(TelegramPendingAuth).where(
            TelegramPendingAuth.telegram_chat_id == chat_id
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_pending_auth(
    db: AsyncSession, chat_id: int, email: str
) -> TelegramPendingAuth:
    """Insert or update pending auth for this chat_id with the given email."""
    pending = await get_pending_auth(db, chat_id)
    if pending is None:
        pending = TelegramPendingAuth(telegram_chat_id=chat_id, email=email.strip())
        db.add(pending)
    else:
        pending.email = email.strip()
    await db.commit()
    await db.refresh(pending)
    return pending


async def complete_registration(db: AsyncSession, chat_id: int) -> None:
    """Create TelegramUser for the pending auth and remove the pending record."""
    pending = await get_pending_auth(db, chat_id)
    if pending is None:
        return
    user = await get_user_by_email(db, pending.email)
    if user is None:
        return
    db.add(TelegramUser(user_id=user.id, telegram_chat_id=chat_id))
    await db.delete(pending)
    await db.commit()


def _looks_like_code(text: str) -> bool:
    """True if text looks like a 6-digit login code."""
    return bool(re.fullmatch(r"\d{6}", text.strip()))


def format_reply(result: ChatProcessResult) -> str:
    """Format ChatProcessResult as Telegram-friendly text."""
    if result.insufficient_balance:
        d = result.insufficient_balance
        return (
            "❌ Saldo insuficiente\n"
            f"Disponível: R$ {d.available:.2f} | Solicitado: R$ {d.requested:.2f}"
        )
    if result.action == "list_categories" and result.categories:
        lines = [
            f"• {c.icon or '📦'} {c.name} — R$ {c.current_balance:.2f} / R$ {c.initial_amount:.2f}"
            for c in result.categories
        ]
        return "📦 Suas categorias:\n" + "\n".join(lines)
    if result.action == "create_transaction" and result.transaction:
        return "✅ " + result.reply
    if result.action == "list_transactions" and result.reply:
        return "📋 " + result.reply
    return result.reply


async def handle_registration_step(
    db: AsyncSession, chat_id: int, text: str
) -> str:
    """Handle one step of registration (email or code). Returns reply text."""
    pending = await get_pending_auth(db, chat_id)
    if pending is None:
        return "Por favor, envie o e-mail cadastrado no Tá Liso para continuar."
    email = pending.email
    if _looks_like_code(text):
        code = text.strip()
        try:
            await auth_service.authenticate(db, email, code)
            await complete_registration(db, chat_id)
            return "Conta vinculada com sucesso. Agora você pode registrar gastos e ver categorias por aqui."
        except ValueError:
            return "Código inválido ou expirado. Verifique o e-mail e tente novamente."
    if EMAIL_REGEX.match(text.strip()):
        try:
            await auth_service.request_login_code(db, text.strip())
            await get_or_create_pending_auth(db, chat_id, text.strip())
            return "Enviamos um código de 6 dígitos para o seu e-mail. Digite o código aqui para vincular a conta."
        except Exception as e:
            logger.exception("request_login_code failed: %s", e)
            return "Não foi possível enviar o código. Tente novamente mais tarde."
    return "Por favor, envie o e-mail cadastrado no Tá Liso ou o código de 6 dígitos que enviamos."


async def _handle_command(db: AsyncSession, user_id: str, text: str) -> str:
    """Handle slash commands for registered users. Returns reply text."""
    parts = text.strip().split()
    cmd = parts[0].lower()

    if cmd in ("/start", "/ajuda"):
        return COMMANDS_HELP

    if cmd == "/categorias":
        result = await chat_service.process_message(db, user_id, "listar categorias")
        return format_reply(result)

    if cmd == "/gastos":
        filter_word = parts[1].lower() if len(parts) > 1 else ""
        phrase = _GASTOS_FILTER_PHRASES.get(filter_word, "listar transações")
        result = await chat_service.process_message(db, user_id, phrase)
        return format_reply(result)

    if cmd == "/gasto":
        if len(parts) < 4:
            return (
                "Uso: /gasto <valor> <descrição> <categoria>\n"
                "Exemplo: /gasto 35 Almoço Alimentação"
            )
        amount = parts[1]
        category = parts[-1]
        description = " ".join(parts[2:-1])
        phrase = f"registrar gasto de R${amount} em {description} na categoria {category}"
        result = await chat_service.process_message(db, user_id, phrase)
        return format_reply(result)

    # Comando desconhecido — passa ao chat_service como linguagem natural
    result = await chat_service.process_message(db, user_id, text)
    return format_reply(result)


async def handle_message(db: AsyncSession, chat_id: int, text: str) -> None:
    """Main entry: route to registration or chat_service, then send reply."""
    user = await get_user_by_telegram_chat_id(db, chat_id)
    if user is not None:
        if text.startswith("/"):
            reply_text = await _handle_command(db, user.id, text)
        else:
            result = await chat_service.process_message(db, user.id, text)
            reply_text = format_reply(result)
        await send_message(chat_id, reply_text)
        return
    pending = await get_pending_auth(db, chat_id)
    if pending is not None:
        reply_text = await handle_registration_step(db, chat_id, text)
        await send_message(chat_id, reply_text)
        return
    if EMAIL_REGEX.match(text.strip()):
        try:
            await auth_service.request_login_code(db, text.strip())
            await get_or_create_pending_auth(db, chat_id, text.strip())
            await send_message(
                chat_id,
                "Enviamos um código de 6 dígitos para o seu e-mail. Digite o código aqui para vincular a conta.",
            )
        except Exception as e:
            logger.exception("request_login_code failed: %s", e)
            await send_message(
                chat_id,
                "Não foi possível enviar o código. Tente novamente mais tarde.",
            )
    else:
        await send_message(
            chat_id,
            "Olá! Para usar o Tá Liso pelo Telegram, envie o e-mail cadastrado no app para vincular sua conta.",
        )
