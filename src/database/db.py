import contextlib

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.conf.config import config


class DatabaseSessionManager:
    """Owns the async engine and hands out short-lived sessions."""

    def __init__(self, url: str) -> None:
        """Create the async engine and session factory for ``url``.

        :param url: Async SQLAlchemy DSN.
        :type url: str
        """
        self._engine: AsyncEngine | None = create_async_engine(url)
        self._session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            autoflush=False, autocommit=False, bind=self._engine
        )

    @contextlib.asynccontextmanager
    async def session(self):
        """Yield a session, rolling back on error and always closing it.

        :raises RuntimeError: If the session factory is not initialized.
        :raises SQLAlchemyError: Re-raised after rollback on a database error.
        :return: An async context manager yielding an :class:`AsyncSession`.
        """
        if self._session_maker is None:
            raise RuntimeError("Database session is not initialized")
        session = self._session_maker()
        try:
            yield session
        except SQLAlchemyError:
            await session.rollback()
            raise
        finally:
            await session.close()


sessionmanager = DatabaseSessionManager(config.DB_URL)


async def get_db():
    """FastAPI dependency that yields a database session per request.

    :return: An async generator yielding an :class:`AsyncSession`.
    """
    async with sessionmanager.session() as session:
        yield session
