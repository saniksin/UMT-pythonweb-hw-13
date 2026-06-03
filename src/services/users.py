from libgravatar import Gravatar
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.repository.users import UserRepository
from src.schemas import UserCreate


class UserService:
    """Business-logic layer for users."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service with a database session.

        :param db: An open async SQLAlchemy session.
        :type db: AsyncSession
        """
        self.repository = UserRepository(db)

    async def create_user(self, body: UserCreate) -> User:
        """Create a new user, attaching a gravatar avatar when possible.

        :param body: Registration payload (password must already be hashed).
        :type body: UserCreate
        :return: The freshly created user.
        :rtype: User
        """
        avatar: str | None = None
        try:
            avatar = Gravatar(body.email).get_image()
        except Exception:
            avatar = None
        return await self.repository.create_user(body, avatar=avatar)

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Return the user with the given id (or ``None``)."""
        return await self.repository.get_user_by_id(user_id)

    async def get_user_by_username(self, username: str) -> User | None:
        """Return the user with the given username (or ``None``)."""
        return await self.repository.get_user_by_username(username)

    async def get_user_by_email(self, email: str) -> User | None:
        """Return the user with the given email (or ``None``)."""
        return await self.repository.get_user_by_email(email)

    async def confirmed_email(self, email: str) -> None:
        """Mark the user with ``email`` as confirmed."""
        await self.repository.confirmed_email(email)

    async def update_avatar_url(self, email: str, url: str) -> User:
        """Persist a new avatar URL for the user with ``email``."""
        return await self.repository.update_avatar_url(email, url)

    async def update_password(self, email: str, hashed_password: str) -> User | None:
        """Persist a new password hash for the user with ``email``.

        :param email: The user's email.
        :type email: str
        :param hashed_password: The new bcrypt password hash.
        :type hashed_password: str
        :return: The updated user, or ``None`` if no such user exists.
        :rtype: User | None
        """
        return await self.repository.update_password(email, hashed_password)
