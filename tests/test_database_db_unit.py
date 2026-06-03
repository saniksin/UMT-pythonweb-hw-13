import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.database import db as db_module
from src.database.db import DatabaseSessionManager

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.mark.asyncio
async def test_session_yields_session():
    manager = DatabaseSessionManager(SQLITE_URL)
    async with manager.session() as session:
        assert session is not None


@pytest.mark.asyncio
async def test_session_rolls_back_on_sqlalchemy_error():
    manager = DatabaseSessionManager(SQLITE_URL)
    with pytest.raises(SQLAlchemyError):
        async with manager.session():
            raise SQLAlchemyError("boom")


@pytest.mark.asyncio
async def test_session_raises_when_not_initialized():
    manager = DatabaseSessionManager(SQLITE_URL)
    manager._session_maker = None
    with pytest.raises(RuntimeError):
        async with manager.session():
            pass


@pytest.mark.asyncio
async def test_get_db_yields_session(monkeypatch):
    manager = DatabaseSessionManager(SQLITE_URL)
    monkeypatch.setattr(db_module, "sessionmanager", manager)

    gen = db_module.get_db()
    session = await gen.__anext__()
    assert session is not None
    await gen.aclose()
