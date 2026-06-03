from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.database.models import UserRole


# ──────────────────────────────────────────────────────────────────────────────
# Contact schemas
# ──────────────────────────────────────────────────────────────────────────────


class ContactBase(BaseModel):
    """Shared contact fields used both for creating and updating contacts."""

    first_name: str = Field(min_length=1, max_length=50, examples=["Tony"])
    last_name: str = Field(min_length=1, max_length=50, examples=["Stark"])
    email: EmailStr = Field(max_length=150, examples=["tony@stark.industries"])
    phone: str = Field(min_length=3, max_length=30, examples=["+380501112233"])
    birthday: date = Field(examples=["1970-05-29"])
    additional_data: str | None = Field(
        default=None,
        max_length=500,
        examples=["Genius, billionaire, playboy, philanthropist"],
    )


class ContactCreate(ContactBase):
    """Schema used when creating a contact."""


class ContactUpdate(ContactBase):
    """Schema used for full updates of a contact."""


class ContactResponse(ContactBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────────────────────────────────────
# User schemas
# ──────────────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """Payload for new-account registration."""

    username: str = Field(min_length=3, max_length=50, examples=["tony_stark"])
    email: EmailStr = Field(max_length=150, examples=["tony@stark.industries"])
    password: str = Field(min_length=6, max_length=128, examples=["s3cret123"])


class UserResponse(BaseModel):
    """Public projection of a User (what we send back to clients)."""

    id: int
    username: str
    email: EmailStr
    avatar: str | None = None
    confirmed: bool
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────────────────────────────────────
# Auth schemas
# ──────────────────────────────────────────────────────────────────────────────


class Token(BaseModel):
    """Pair of JWT tokens issued on a successful login / refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Payload carrying a refresh token to mint a fresh pair of tokens."""

    refresh_token: str


class RequestEmail(BaseModel):
    """Payload for re-requesting a verification email."""

    email: EmailStr


class PasswordResetRequest(BaseModel):
    """Payload that starts the password-reset flow (send the reset email)."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Payload that finishes the password-reset flow with a new password."""

    token: str
    new_password: str = Field(min_length=6, max_length=128, examples=["n3wpass123"])
