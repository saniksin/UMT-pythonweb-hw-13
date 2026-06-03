from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import config
from src.database.db import get_db
from src.database.models import User, UserRole
from src.services.cache import cache_user, get_cached_user
from src.services.users import UserService


class Hash:
    """Wrapper around passlib's bcrypt context."""

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Return ``True`` if ``plain_password`` matches the stored hash.

        :param plain_password: The password supplied by the user.
        :type plain_password: str
        :param hashed_password: The bcrypt hash stored in the database.
        :type hashed_password: str
        :return: Whether the password is correct.
        :rtype: bool
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a plain-text password with bcrypt.

        :param password: The password to hash.
        :type password: str
        :return: The bcrypt hash.
        :rtype: str
        """
        return self.pwd_context.hash(password)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _create_token(data: dict[str, Any], scope: str, expires_seconds: int) -> str:
    """Encode a JWT carrying ``scope`` and an expiry ``expires_seconds`` away.

    :param data: Claims to embed (typically ``{"sub": ...}``).
    :type data: dict
    :param scope: Token scope (``access_token``, ``refresh_token`` ...).
    :type scope: str
    :param expires_seconds: Token lifetime in seconds.
    :type expires_seconds: int
    :return: The signed JWT.
    :rtype: str
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    to_encode.update(
        {"iat": now, "exp": now + timedelta(seconds=expires_seconds), "scope": scope}
    )
    return jwt.encode(to_encode, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


async def create_access_token(
    data: dict[str, Any], expires_delta: int | None = None
) -> str:
    """Create a short-lived JWT used to authenticate API calls.

    :param data: Claims to embed (``{"sub": username}``).
    :type data: dict
    :param expires_delta: Optional override for the lifetime in seconds.
    :type expires_delta: int | None
    :return: The signed access token.
    :rtype: str
    """
    expires = expires_delta if expires_delta is not None else config.JWT_EXPIRATION_SECONDS
    return _create_token(data, "access_token", expires)


async def create_refresh_token(
    data: dict[str, Any], expires_delta: int | None = None
) -> str:
    """Create a long-lived JWT used to mint new access tokens.

    :param data: Claims to embed (``{"sub": username}``).
    :type data: dict
    :param expires_delta: Optional override for the lifetime in seconds.
    :type expires_delta: int | None
    :return: The signed refresh token.
    :rtype: str
    """
    expires = (
        expires_delta
        if expires_delta is not None
        else config.JWT_REFRESH_EXPIRATION_SECONDS
    )
    return _create_token(data, "refresh_token", expires)


async def decode_refresh_token(token: str) -> str:
    """Validate a refresh token and return the username it carries.

    :param token: The refresh token to decode.
    :type token: str
    :raises HTTPException: 401 if the token is invalid or has the wrong scope.
    :return: The username (``sub`` claim).
    :rtype: str
    """
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
        )
        if payload.get("scope") != "refresh_token":
            raise JWTError("Invalid token scope")
        username = payload.get("sub")
        if username is None:
            raise JWTError("Missing subject in token")
        return username
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc


def create_email_token(data: dict[str, Any]) -> str:
    """Create a long-lived JWT used to verify a user's email address.

    :param data: Claims to embed (``{"sub": email}``).
    :type data: dict
    :return: The signed email-verification token.
    :rtype: str
    """
    return _create_token(data, "email_token", 7 * 24 * 60 * 60)


def create_reset_password_token(data: dict[str, Any]) -> str:
    """Create a short-lived JWT used to reset a forgotten password.

    :param data: Claims to embed (``{"sub": email}``).
    :type data: dict
    :return: The signed password-reset token (valid for one hour).
    :rtype: str
    """
    return _create_token(data, "reset_password", 60 * 60)


async def get_email_from_token(token: str) -> str:
    """Decode an email-verification token and return the email it carries.

    :param token: The email-verification token.
    :type token: str
    :raises HTTPException: 422 if the token is invalid or has the wrong scope.
    :return: The email address (``sub`` claim).
    :rtype: str
    """
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
        )
        if payload.get("scope") != "email_token":
            raise JWTError("Invalid token scope")
        email = payload.get("sub")
        if email is None:
            raise JWTError("Missing email in token")
        return email
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email verification token",
        ) from exc


async def get_email_from_reset_token(token: str) -> str:
    """Decode a password-reset token and return the email it carries.

    :param token: The password-reset token.
    :type token: str
    :raises HTTPException: 422 if the token is invalid or has the wrong scope.
    :return: The email address (``sub`` claim).
    :rtype: str
    """
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
        )
        if payload.get("scope") != "reset_password":
            raise JWTError("Invalid token scope")
        email = payload.get("sub")
        if email is None:
            raise JWTError("Missing email in token")
        return email
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid password reset token",
        ) from exc


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency that resolves the currently authenticated user.

    The user is first looked up in Redis; on a cache miss the database is
    queried and the result is cached for subsequent requests.

    :param token: The bearer access token (injected by FastAPI).
    :type token: str
    :param db: The database session (injected by FastAPI).
    :type db: AsyncSession
    :raises HTTPException: 401 if the token or the user is invalid.
    :return: The authenticated user.
    :rtype: User
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
        )
        if payload.get("scope") != "access_token":
            raise credentials_exception
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    cached_user = await get_cached_user(username)
    if cached_user is not None:
        return cached_user

    user_service = UserService(db)
    user = await user_service.get_user_by_username(username)
    if user is None:
        raise credentials_exception

    await cache_user(user)
    return user


def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that only lets administrators through.

    :param user: The authenticated user (injected by :func:`get_current_user`).
    :type user: User
    :raises HTTPException: 403 if the user is not an administrator.
    :return: The authenticated administrator.
    :rtype: User
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient access rights",
        )
    return user
