import logging
import os
import tomllib
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("orion.config")


def get_pyproject_version() -> str:
    """Dynamically read project version from pyproject.toml."""
    try:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "1.0.0")
    except (OSError, tomllib.TOMLDecodeError, KeyError):
        return "1.0.0"
    return "1.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    ENVIRONMENT: str = Field(default="development", validation_alias="ENVIRONMENT")
    PROJECT_NAME: str = Field(default="ORION - KSM AIoT API", validation_alias="PROJECT_NAME")
    VERSION: str = get_pyproject_version()
    API_V1_STR: str = Field(default="/orion/api/v1", validation_alias="API_V1_STR")

    DATABASE_HOST: str = Field(default="localhost", validation_alias="PGHOST")
    DATABASE_PORT: int = Field(default=5432, validation_alias="PGPORT")
    DATABASE_USER: str = Field(default="orion_dev_user", validation_alias="PGUSER")
    DATABASE_PASSWORD: str = Field(default="orion_dev_password", validation_alias="PGPASSWORD")
    DATABASE_NAME: str = Field(default="orion_dev_db", validation_alias="PGDATABASE")

    RAW_DATABASE_URL: str | None = Field(default=None, validation_alias="DATABASE_URL")

    UPLOAD_DIR: str = Field(default="uploads", validation_alias="UPLOAD_DIR")
    MAX_UPLOAD_SIZE: int = Field(default=2 * 1024 * 1024, validation_alias="MAX_UPLOAD_SIZE")  # 2MB

    # Security & Tokens: Short-lived access tokens (30 mins) + 7 days refresh
    SECRET_KEY: str = Field(
        default="orion-secret-key-ksm-aiot-upnvj-2026-supersecure-enterprise-jwt",
        validation_alias="JWT_SECRET",
    )
    ALGORITHM: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # Allowed CORS Origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:80",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    DEBUG: bool = Field(default=True, validation_alias="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @property
    def JWT_SECRET(self) -> str:
        return self.SECRET_KEY

    @property
    def JWT_ALGORITHM(self) -> str:
        return self.ALGORITHM

    @property
    def PGHOST(self) -> str:
        return self.DATABASE_HOST

    @property
    def PGPORT(self) -> int:
        return self.DATABASE_PORT

    @property
    def PGUSER(self) -> str:
        return self.DATABASE_USER

    @property
    def PGPASSWORD(self) -> str:
        return self.DATABASE_PASSWORD

    @property
    def PGDATABASE(self) -> str:
        return self.DATABASE_NAME

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        if self.RAW_DATABASE_URL:
            return self.RAW_DATABASE_URL
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    def get_database_url(self) -> str:
        return self.DATABASE_URL

    def get_allowed_origins(self) -> list[str]:
        """Return restrictive CORS origins for production, or allow configured for dev."""
        if self.ENVIRONMENT.lower() == "production":
            # In production, filter out wildcard
            return [o for o in self.CORS_ORIGINS if o != "*"]
        return self.CORS_ORIGINS


settings = Settings()

if settings.ENVIRONMENT.lower() == "production" and "supersecure" in settings.SECRET_KEY:
    logger.warning("PERINGATAN KEAMANAN: SECRET_KEY masih menggunakan default nilai development pada production!")
