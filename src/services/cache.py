"""Redis-backed cache for the currently authenticated user.

Caching the user lets :func:`src.services.auth.get_current_user` skip a
database round-trip on every authenticated request. All Redis calls are
wrapped in ``try/except`` so the API keeps working (falling back to the
database) even when Redis is temporarily unavailable.
"""

import pickle

from redis.asyncio import Redis

from src.conf.config import config
from src.database.models import User

_redis: Redis | None = None


def get_redis() -> Redis:
    """Return a lazily-created async Redis client.

    :return: A shared :class:`redis.asyncio.Redis` connection.
    :rtype: Redis
    """
    global _redis
    if _redis is None:
        _redis = Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            password=config.REDIS_PASSWORD,
            db=config.REDIS_DB,
        )
    return _redis


def _user_key(username: str) -> str:
    """Build the Redis key under which a user is cached."""
    return f"user:{username}"


async def get_cached_user(username: str) -> User | None:
    """Fetch a cached user by username.

    :param username: The username to look up.
    :type username: str
    :return: The cached :class:`User`, or ``None`` on a cache miss / error.
    :rtype: User | None
    """
    try:
        raw = await get_redis().get(_user_key(username))
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return pickle.loads(raw)
    except Exception:
        return None


async def cache_user(user: User) -> None:
    """Store a user in the cache with the configured TTL.

    :param user: The user to cache.
    :type user: User
    """
    try:
        await get_redis().set(
            _user_key(user.username),
            pickle.dumps(user),
            ex=config.REDIS_USER_TTL,
        )
    except Exception:
        pass


async def invalidate_user(username: str) -> None:
    """Drop a user from the cache (call after any change to the user row).

    :param username: The username whose cache entry must be removed.
    :type username: str
    """
    try:
        await get_redis().delete(_user_key(username))
    except Exception:
        pass
