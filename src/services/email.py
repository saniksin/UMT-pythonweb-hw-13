from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import EmailStr

from src.conf.config import config
from src.services.auth import create_email_token, create_reset_password_token

_conf = ConnectionConfig(
    MAIL_USERNAME=config.MAIL_USERNAME,
    MAIL_PASSWORD=config.MAIL_PASSWORD,
    MAIL_FROM=config.MAIL_FROM,
    MAIL_PORT=config.MAIL_PORT,
    MAIL_SERVER=config.MAIL_SERVER,
    MAIL_FROM_NAME=config.MAIL_FROM_NAME,
    MAIL_STARTTLS=config.MAIL_STARTTLS,
    MAIL_SSL_TLS=config.MAIL_SSL_TLS,
    USE_CREDENTIALS=config.USE_CREDENTIALS,
    VALIDATE_CERTS=config.VALIDATE_CERTS,
    TEMPLATE_FOLDER=Path(__file__).parent / "templates",
)


async def send_verification_email(email: EmailStr, username: str, host: str) -> None:
    """Render the verification template and dispatch it to the user.

    :param email: Recipient address.
    :type email: EmailStr
    :param username: Recipient username (shown in the template).
    :type username: str
    :param host: Base URL of the application (used to build the link).
    :type host: str
    """
    try:
        token = create_email_token({"sub": email})
        message = MessageSchema(
            subject="Confirm your email — Contacts API",
            recipients=[email],
            template_body={"host": host, "username": username, "token": token},
            subtype=MessageType.html,
        )
        fm = FastMail(_conf)
        await fm.send_message(message, template_name="verify_email.html")
    except ConnectionErrors as err:
        print(f"[email] failed to send verification mail: {err}")


async def send_reset_password_email(
    email: EmailStr, username: str, host: str
) -> None:
    """Render the password-reset template and dispatch it to the user.

    :param email: Recipient address.
    :type email: EmailStr
    :param username: Recipient username (shown in the template).
    :type username: str
    :param host: Base URL of the application (used to build the link).
    :type host: str
    """
    try:
        token = create_reset_password_token({"sub": email})
        message = MessageSchema(
            subject="Reset your password — Contacts API",
            recipients=[email],
            template_body={"host": host, "username": username, "token": token},
            subtype=MessageType.html,
        )
        fm = FastMail(_conf)
        await fm.send_message(message, template_name="reset_password.html")
    except ConnectionErrors as err:
        print(f"[email] failed to send reset-password mail: {err}")
