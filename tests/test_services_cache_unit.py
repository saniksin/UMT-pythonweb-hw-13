import pickle

from unittest.mock import AsyncMock, patch

import pytest

from src.database.models import User, UserRole
from src.services import cache


def _user():
    return User(
        id=1,
        username="cached",
        email="cached@example.com",
        hashed_password="hash",
        confirmed=True,
        role=UserRole.USER,
    )


@pytest.mark.asyncio
async def test_get_cached_user_hit():
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=pickle.dumps(_user()))
    with patch("src.services.cache.get_redis", return_value=fake_redis):
        result = await cache.get_cached_user("cached")

    assert result is not None
    assert result.username == "cached"


@pytest.mark.asyncio
async def test_get_cached_user_miss():
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=None)
    with patch("src.services.cache.get_redis", return_value=fake_redis):
        result = await cache.get_cached_user("cached")

    assert result is None


@pytest.mark.asyncio
async def test_get_cached_user_handles_redis_error():
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(side_effect=Exception("redis down"))
    with patch("src.services.cache.get_redis", return_value=fake_redis):
        result = await cache.get_cached_user("cached")

    assert result is None


@pytest.mark.asyncio
async def test_get_cached_user_handles_corrupted_payload():
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=b"not-a-valid-pickle")
    with patch("src.services.cache.get_redis", return_value=fake_redis):
        result = await cache.get_cached_user("cached")

    assert result is None


@pytest.mark.asyncio
async def test_cache_user():
    fake_redis = AsyncMock()
    fake_redis.set = AsyncMock()
    with patch("src.services.cache.get_redis", return_value=fake_redis):
        await cache.cache_user(_user())

    fake_redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_user_handles_redis_error():
    fake_redis = AsyncMock()
    fake_redis.set = AsyncMock(side_effect=Exception("redis down"))
    with patch("src.services.cache.get_redis", return_value=fake_redis):
        await cache.cache_user(_user())  # must not raise


@pytest.mark.asyncio
async def test_invalidate_user():
    fake_redis = AsyncMock()
    fake_redis.delete = AsyncMock()
    with patch("src.services.cache.get_redis", return_value=fake_redis):
        await cache.invalidate_user("cached")

    fake_redis.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalidate_user_handles_redis_error():
    fake_redis = AsyncMock()
    fake_redis.delete = AsyncMock(side_effect=Exception("redis down"))
    with patch("src.services.cache.get_redis", return_value=fake_redis):
        await cache.invalidate_user("cached")  # must not raise


def test_get_redis_returns_singleton():
    cache._redis = None
    first = cache.get_redis()
    second = cache.get_redis()
    assert first is second
    cache._redis = None
