"""Tests for Telegram webhook and registration flow."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTelegramWebhook:
    """Webhook endpoint: auth and payload handling."""

    async def test_webhook_401_without_secret(self, client: AsyncClient):
        """Missing X-Telegram-Bot-Api-Secret-Token returns 401."""
        resp = await client.post(
            "/webhooks/telegram",
            json={"update_id": 1, "message": {"chat": {"id": 123}, "text": "oi"}},
        )
        assert resp.status_code == 401

    async def test_webhook_401_wrong_secret(self, client: AsyncClient):
        """Wrong secret returns 401."""
        resp = await client.post(
            "/webhooks/telegram",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            json={"update_id": 1, "message": {"chat": {"id": 123}, "text": "oi"}},
        )
        assert resp.status_code == 401

    async def test_webhook_200_valid_body_schedules_task(self, client: AsyncClient):
        """Valid secret and body returns 200 and schedules handle_message."""
        with patch(
            "app.services.telegram_service.handle_message",
            new_callable=AsyncMock,
        ) as mock_handle:
            resp = await client.post(
                "/webhooks/telegram",
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
                json={
                    "update_id": 1,
                    "message": {
                        "chat": {"id": 12345},
                        "text": "gastei 10 no café",
                    },
                },
            )
            assert resp.status_code == 200
            assert resp.json() == {}
        # Background task runs after response; give it a moment
        mock_handle.assert_called_once()
        call_args = mock_handle.call_args
        assert call_args[0][1] == 12345
        assert call_args[0][2] == "gastei 10 no café"

    async def test_webhook_200_no_message_text(self, client: AsyncClient):
        """Body without message.text returns 200 and does not process."""
        resp = await client.post(
            "/webhooks/telegram",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
            json={"update_id": 1, "message": {"chat": {"id": 999}}},
        )
        assert resp.status_code == 200
        assert resp.json() == {}

    async def test_webhook_200_no_message(self, client: AsyncClient):
        """Body without message returns 200."""
        resp = await client.post(
            "/webhooks/telegram",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
            json={"update_id": 1},
        )
        assert resp.status_code == 200
