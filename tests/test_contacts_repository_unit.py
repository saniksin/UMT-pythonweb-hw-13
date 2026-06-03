from datetime import date

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.repository.contacts import ContactRepository
from src.schemas import ContactCreate, ContactUpdate


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def contact_repository(mock_session):
    return ContactRepository(mock_session)


@pytest.fixture
def user():
    return User(id=1, username="testuser")


def _contact(**overrides):
    data = dict(
        id=1,
        first_name="Tony",
        last_name="Stark",
        email="tony@stark.io",
        phone="+380501112233",
        birthday=date(1970, 5, 29),
        user_id=1,
    )
    data.update(overrides)
    return Contact(**data)


@pytest.mark.asyncio
async def test_get_contacts(contact_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [_contact()]
    mock_session.execute = AsyncMock(return_value=mock_result)

    contacts = await contact_repository.get_contacts(user=user, skip=0, limit=10)

    assert len(contacts) == 1
    assert contacts[0].first_name == "Tony"


@pytest.mark.asyncio
async def test_get_contacts_with_filters(contact_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [_contact()]
    mock_session.execute = AsyncMock(return_value=mock_result)

    contacts = await contact_repository.get_contacts(
        user=user, skip=0, limit=10, first_name="Tony", last_name="Stark", email="tony"
    )

    assert len(contacts) == 1
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_contact_by_id(contact_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = _contact()
    mock_session.execute = AsyncMock(return_value=mock_result)

    contact = await contact_repository.get_contact_by_id(contact_id=1, user=user)

    assert contact is not None
    assert contact.id == 1
    assert contact.email == "tony@stark.io"


@pytest.mark.asyncio
async def test_create_contact(contact_repository, mock_session, user):
    body = ContactCreate(
        first_name="Peter",
        last_name="Parker",
        email="peter@bugle.com",
        phone="+380509998877",
        birthday=date(2001, 8, 10),
    )

    result = await contact_repository.create_contact(body=body, user=user)

    assert isinstance(result, Contact)
    assert result.first_name == "Peter"
    assert result.user_id == user.id
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_update_contact(contact_repository, mock_session, user):
    existing = _contact()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute = AsyncMock(return_value=mock_result)

    body = ContactUpdate(
        first_name="Anthony",
        last_name="Stark",
        email="tony@stark.io",
        phone="+380501112233",
        birthday=date(1970, 5, 29),
    )

    result = await contact_repository.update_contact(
        contact_id=1, body=body, user=user
    )

    assert result is not None
    assert result.first_name == "Anthony"
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(existing)


@pytest.mark.asyncio
async def test_update_contact_not_found(contact_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    body = ContactUpdate(
        first_name="X",
        last_name="Y",
        email="x@y.io",
        phone="+380500000000",
        birthday=date(1990, 1, 1),
    )

    result = await contact_repository.update_contact(
        contact_id=999, body=body, user=user
    )

    assert result is None
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_contact(contact_repository, mock_session, user):
    existing = _contact()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await contact_repository.remove_contact(contact_id=1, user=user)

    assert result is not None
    assert result.id == 1
    mock_session.delete.assert_awaited_once_with(existing)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_contact_not_found(contact_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await contact_repository.remove_contact(contact_id=999, user=user)

    assert result is None
    mock_session.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_upcoming_birthdays(contact_repository, mock_session, user):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [_contact()]
    mock_session.execute = AsyncMock(return_value=mock_result)

    contacts = await contact_repository.get_upcoming_birthdays(user=user, days=7)

    assert isinstance(contacts, list)
    mock_session.execute.assert_awaited_once()
