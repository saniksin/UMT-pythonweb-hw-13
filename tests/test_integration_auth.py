from unittest.mock import Mock

import pytest
from sqlalchemy import select

from src.database.models import User
from src.services.auth import create_email_token, create_reset_password_token
from tests.conftest import TestingSessionLocal

user_data = {
    "username": "agent007",
    "email": "agent007@gmail.com",
    "password": "12345678",
}


def test_signup(client, monkeypatch):
    mock_send_email = Mock()
    monkeypatch.setattr("src.api.auth.send_verification_email", mock_send_email)
    response = client.post("api/auth/register", json=user_data)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["username"] == user_data["username"]
    assert data["email"] == user_data["email"]
    assert "hashed_password" not in data
    assert "avatar" in data
    assert data["role"] == "user"


def test_repeat_signup(client, monkeypatch):
    mock_send_email = Mock()
    monkeypatch.setattr("src.api.auth.send_verification_email", mock_send_email)
    response = client.post("api/auth/register", json=user_data)
    assert response.status_code == 409, response.text
    data = response.json()
    assert data["detail"] == "A user with this email already exists"


def test_not_confirmed_login(client):
    response = client.post(
        "api/auth/login",
        data={
            "username": user_data.get("username"),
            "password": user_data.get("password"),
        },
    )
    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Email address is not confirmed"


@pytest.mark.asyncio
async def test_login(client):
    async with TestingSessionLocal() as session:
        current_user = await session.execute(
            select(User).where(User.email == user_data.get("email"))
        )
        current_user = current_user.scalar_one_or_none()
        if current_user:
            current_user.confirmed = True
            await session.commit()

    response = client.post(
        "api/auth/login",
        data={
            "username": user_data.get("username"),
            "password": user_data.get("password"),
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_wrong_password_login(client):
    response = client.post(
        "api/auth/login",
        data={"username": user_data.get("username"), "password": "wrongpassword"},
    )
    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Invalid username or password"


def test_wrong_username_login(client):
    response = client.post(
        "api/auth/login",
        data={"username": "unknown_user", "password": user_data.get("password")},
    )
    assert response.status_code == 401, response.text
    data = response.json()
    assert data["detail"] == "Invalid username or password"


def test_validation_error_login(client):
    response = client.post(
        "api/auth/login", data={"password": user_data.get("password")}
    )
    assert response.status_code == 422, response.text
    data = response.json()
    assert "detail" in data


def test_refresh_token(client):
    login = client.post(
        "api/auth/login",
        data={
            "username": user_data.get("username"),
            "password": user_data.get("password"),
        },
    )
    refresh = login.json()["refresh_token"]

    response = client.post(
        "api/auth/refresh_token", json={"refresh_token": refresh}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_token_invalid(client):
    response = client.post(
        "api/auth/refresh_token", json={"refresh_token": "not-a-real-token"}
    )
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Invalid refresh token"


def test_reset_password_request(client, monkeypatch):
    mock_send_email = Mock()
    monkeypatch.setattr("src.api.auth.send_reset_password_email", mock_send_email)
    response = client.post(
        "api/auth/reset_password", json={"email": user_data.get("email")}
    )
    assert response.status_code == 200, response.text
    assert "message" in response.json()
    mock_send_email.assert_called_once()


def test_reset_password_confirm_and_login(client):
    token = create_reset_password_token({"sub": user_data.get("email")})
    new_password = "new-password-123"

    response = client.post(
        "api/auth/reset_password/confirm",
        json={"token": token, "new_password": new_password},
    )
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Password has been reset successfully"

    # The old password no longer works.
    old_login = client.post(
        "api/auth/login",
        data={
            "username": user_data.get("username"),
            "password": user_data.get("password"),
        },
    )
    assert old_login.status_code == 401, old_login.text

    # The new password works.
    new_login = client.post(
        "api/auth/login",
        data={"username": user_data.get("username"), "password": new_password},
    )
    assert new_login.status_code == 200, new_login.text


def test_reset_password_confirm_invalid_token(client):
    response = client.post(
        "api/auth/reset_password/confirm",
        json={"token": "broken-token", "new_password": "whatever123"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Invalid password reset token"


def test_reset_password_unknown_email(client):
    token = create_reset_password_token({"sub": "ghost@example.com"})
    response = client.post(
        "api/auth/reset_password/confirm",
        json={"token": token, "new_password": "whatever123"},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Password reset error"


rookie_data = {
    "username": "rookie",
    "email": "rookie@gmail.com",
    "password": "12345678",
}


def test_confirmed_email_flow(client, monkeypatch):
    monkeypatch.setattr("src.api.auth.send_verification_email", Mock())
    register = client.post("api/auth/register", json=rookie_data)
    assert register.status_code == 201, register.text

    token = create_email_token({"sub": rookie_data["email"]})
    response = client.get(f"api/auth/confirmed_email/{token}")
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Email confirmed successfully"

    # Confirming a second time is idempotent.
    again = client.get(f"api/auth/confirmed_email/{token}")
    assert again.status_code == 200, again.text
    assert again.json()["message"] == "Email already confirmed"


def test_confirmed_email_invalid_token(client):
    response = client.get("api/auth/confirmed_email/broken-token")
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Invalid email verification token"


def test_request_email_already_confirmed(client):
    response = client.post(
        "api/auth/request_email", json={"email": rookie_data["email"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Email already confirmed"


def test_request_email_unknown(client, monkeypatch):
    monkeypatch.setattr("src.api.auth.send_verification_email", Mock())
    response = client.post(
        "api/auth/request_email", json={"email": "nobody@example.com"}
    )
    assert response.status_code == 200, response.text
    assert "message" in response.json()
