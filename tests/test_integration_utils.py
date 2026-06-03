from unittest.mock import AsyncMock, MagicMock

from main import app
from src.database.db import get_db


def test_healthchecker(client):
    response = client.get("/api/healthchecker")
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Welcome to Contacts API!"


def test_healthchecker_db_misconfigured(client):
    """When the DB returns nothing, the route reports a 500."""

    async def override_get_db():
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        yield session

    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/healthchecker")
        assert response.status_code == 500, response.text
        assert response.json()["detail"] == "Database is not configured correctly"
    finally:
        app.dependency_overrides[get_db] = original


def test_healthchecker_db_unreachable(client):
    """When the DB query raises, the route reports a 500."""

    async def override_get_db():
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("connection error"))
        yield session

    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/healthchecker")
        assert response.status_code == 500, response.text
        assert response.json()["detail"] == "Error connecting to the database"
    finally:
        app.dependency_overrides[get_db] = original
