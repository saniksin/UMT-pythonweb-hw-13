from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration.

    Values are read from (in order of priority):
        1. real environment variables (``DB_URL=...``)
        2. the ``.env`` file at the project root
        3. the defaults declared below

    Secrets (JWT, SMTP, Cloudinary) have no defaults — the app refuses to
    start until they are provided via the environment.
    """

    # ── Application ───────────────────────────────────────────────────────────
    APP_HOST: str = Field(default="127.0.0.1")
    APP_PORT: int = Field(default=8000)

    # ── Database ──────────────────────────────────────────────────────────────
    DB_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/contacts_app",
        description="Async SQLAlchemy DSN for PostgreSQL",
    )

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET: str = Field(description="Secret used to sign access / email JWTs")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_SECONDS: int = Field(default=3600)
    JWT_REFRESH_EXPIRATION_SECONDS: int = Field(
        default=604800, description="Lifetime of a refresh token (default 7 days)"
    )

    # ── Redis (current-user cache) ──────────────────────────────────────────────
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str | None = Field(default=None)
    REDIS_DB: int = Field(default=0)
    REDIS_USER_TTL: int = Field(
        default=900, description="How long (seconds) a cached user lives in Redis"
    )

    # ── SMTP / FastAPI-Mail ───────────────────────────────────────────────────
    MAIL_USERNAME: EmailStr
    MAIL_PASSWORD: str
    MAIL_FROM: EmailStr
    MAIL_PORT: int = Field(default=465)
    MAIL_SERVER: str = Field(default="smtp.gmail.com")
    MAIL_FROM_NAME: str = Field(default="Contacts API")
    MAIL_STARTTLS: bool = Field(default=False)
    MAIL_SSL_TLS: bool = Field(default=True)
    USE_CREDENTIALS: bool = Field(default=True)
    VALIDATE_CERTS: bool = Field(default=True)

    # ── Cloudinary ────────────────────────────────────────────────────────────
    CLD_NAME: str
    CLD_API_KEY: str
    CLD_API_SECRET: str

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed origins (or '*')",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @property
    def cors_origins_list(self) -> list[str]:
        raw = self.CORS_ORIGINS.strip()
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


config = Settings()
