from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.schemas import UserCreate


class UserRepository:
    """Data-access layer for the User entity."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        :param session: An open async SQLAlchemy session.
        :type session: AsyncSession
        """
        self.db = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Fetch a user by primary key.

        :param user_id: The user's id.
        :type user_id: int
        :return: The user, or ``None`` if not found.
        :rtype: User | None
        """
        stmt = select(User).filter_by(id=user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        """Fetch a user by username.

        :param username: The user's username.
        :type username: str
        :return: The user, or ``None`` if not found.
        :rtype: User | None
        """
        stmt = select(User).filter_by(username=username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Fetch a user by email.

        :param email: The user's email.
        :type email: str
        :return: The user, or ``None`` if not found.
        :rtype: User | None
        """
        stmt = select(User).filter_by(email=email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, body: UserCreate, avatar: str | None = None) -> User:
        """Persist a new user.

        :param body: Registration payload (password must already be hashed).
        :type body: UserCreate
        :param avatar: Optional avatar URL (e.g. a gravatar link).
        :type avatar: str | None
        :return: The freshly created user.
        :rtype: User
        """
        user = User(
            username=body.username,
            email=body.email,
            hashed_password=body.password,
            avatar=avatar,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def confirmed_email(self, email: str) -> None:
        """Mark the user with ``email`` as having a confirmed address.

        :param email: The user's email.
        :type email: str
        """
        user = await self.get_user_by_email(email)
        if user is None:
            return
        user.confirmed = True
        await self.db.commit()

    async def update_avatar_url(self, email: str, url: str) -> User:
        """Update a user's avatar URL.

        :param email: The user's email.
        :type email: str
        :param url: The new avatar URL.
        :type url: str
        :return: The updated user.
        :rtype: User
        """
        user = await self.get_user_by_email(email)
        user.avatar = url
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_password(self, email: str, hashed_password: str) -> User | None:
        """Replace a user's password hash (used by the reset-password flow).

        :param email: The user's email.
        :type email: str
        :param hashed_password: The new bcrypt password hash.
        :type hashed_password: str
        :return: The updated user, or ``None`` if no such user exists.
        :rtype: User | None
        """
        user = await self.get_user_by_email(email)
        if user is None:
            return None
        user.hashed_password = hashed_password
        await self.db.commit()
        await self.db.refresh(user)
        return user
