from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, UserRole
from src.repository.users import UserRepository
from src.schemas import UserCreate


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def user_repository(mock_session):
    return UserRepository(mock_session)


@pytest.fixture
def user():
    return User(
        id=1,
        username="testuser",
        email="testuser@example.com",
        hashed_password="hashed",
        confirmed=True,
        role=UserRole.USER,
    )


@pytest.mark.asyncio
async def test_get_user_by_id(user_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await user_repository.get_user_by_id(user_id=1)

    assert result is not None
    assert result.id == 1
    assert result.username == "testuser"


@pytest.mark.asyncio
async def test_get_user_by_username(user_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await user_repository.get_user_by_username(username="testuser")

    assert result is not None
    assert result.username == "testuser"


@pytest.mark.asyncio
async def test_get_user_by_email(user_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await user_repository.get_user_by_email(email="testuser@example.com")

    assert result is not None
    assert result.email == "testuser@example.com"


@pytest.mark.asyncio
async def test_create_user(user_repository, mock_session):
    body = UserCreate(
        username="newuser", email="newuser@example.com", password="hashedpass"
    )

    result = await user_repository.create_user(body=body, avatar="http://avatar")

    assert isinstance(result, User)
    assert result.username == "newuser"
    assert result.email == "newuser@example.com"
    assert result.avatar == "http://avatar"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_confirmed_email(user_repository, mock_session, user):
    user.confirmed = False
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    await user_repository.confirmed_email(email="testuser@example.com")

    assert user.confirmed is True
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_avatar_url(user_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await user_repository.update_avatar_url(
        email="testuser@example.com", url="http://new-avatar"
    )

    assert result.avatar == "http://new-avatar"
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_update_password(user_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await user_repository.update_password(
        email="testuser@example.com", hashed_password="new-hash"
    )

    assert result is not None
    assert result.hashed_password == "new-hash"
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_update_password_user_not_found(user_repository, mock_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await user_repository.update_password(
        email="missing@example.com", hashed_password="new-hash"
    )

    assert result is None
    mock_session.commit.assert_not_awaited()
