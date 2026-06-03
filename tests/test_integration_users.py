from unittest.mock import patch

import pytest

from src.database.models import User, UserRole
from src.services.auth import Hash, create_access_token
from tests.conftest import TestingSessionLocal, test_user


def test_get_me(client, get_token):
    headers = {"Authorization": f"Bearer {get_token}"}
    response = client.get("api/users/me", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["username"] == test_user["username"]
    assert data["email"] == test_user["email"]
    assert data["role"] == "admin"
    assert "avatar" in data


def test_get_me_without_token(client):
    response = client.get("api/users/me")
    assert response.status_code == 401, response.text


@patch("src.services.upload_file.UploadFileService.upload_file")
def test_update_avatar_admin(mock_upload_file, client, get_token):
    fake_url = "http://example.com/avatar.jpg"
    mock_upload_file.return_value = fake_url

    headers = {"Authorization": f"Bearer {get_token}"}
    file_data = {"file": ("avatar.jpg", b"fake image content", "image/jpeg")}

    response = client.patch("/api/users/avatar", headers=headers, files=file_data)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["username"] == test_user["username"]
    assert data["avatar"] == fake_url
    mock_upload_file.assert_called_once()


@pytest.mark.asyncio
async def test_update_avatar_forbidden_for_regular_user(client):
    # Seed a regular (non-admin) user directly in the test database.
    async with TestingSessionLocal() as session:
        regular = User(
            username="regular_joe",
            email="joe@example.com",
            hashed_password=Hash().get_password_hash("12345678"),
            confirmed=True,
            role=UserRole.USER,
        )
        session.add(regular)
        await session.commit()

    token = await create_access_token(data={"sub": "regular_joe"})
    headers = {"Authorization": f"Bearer {token}"}
    file_data = {"file": ("avatar.jpg", b"fake image content", "image/jpeg")}

    response = client.patch("/api/users/avatar", headers=headers, files=file_data)
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Insufficient access rights"
