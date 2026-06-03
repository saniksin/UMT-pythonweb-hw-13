from unittest.mock import AsyncMock, patch

import pytest
from fastapi_mail.errors import ConnectionErrors

from src.services import email


@pytest.mark.asyncio
async def test_send_verification_email():
    with patch("src.services.email.FastMail") as mock_fastmail:
        instance = mock_fastmail.return_value
        instance.send_message = AsyncMock()

        await email.send_verification_email(
            "user@example.com", "user", "http://testserver/"
        )

        instance.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_reset_password_email():
    with patch("src.services.email.FastMail") as mock_fastmail:
        instance = mock_fastmail.return_value
        instance.send_message = AsyncMock()

        await email.send_reset_password_email(
            "user@example.com", "user", "http://testserver/"
        )

        instance.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_verification_email_handles_connection_error():
    with patch("src.services.email.FastMail") as mock_fastmail:
        instance = mock_fastmail.return_value
        instance.send_message = AsyncMock(side_effect=ConnectionErrors("smtp down"))

        # The helper swallows connection errors instead of propagating them.
        await email.send_verification_email(
            "user@example.com", "user", "http://testserver/"
        )


@pytest.mark.asyncio
async def test_send_reset_password_email_handles_connection_error():
    with patch("src.services.email.FastMail") as mock_fastmail:
        instance = mock_fastmail.return_value
        instance.send_message = AsyncMock(side_effect=ConnectionErrors("smtp down"))

        await email.send_reset_password_email(
            "user@example.com", "user", "http://testserver/"
        )
