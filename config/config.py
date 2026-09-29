import logging
import tomllib
from pathlib import Path

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("orion.config")

# Public development default; the app refuses to start in production with it (see validate_production_security)
DEV_DEFAULT_JWT_SECRET = "orion-secret-key-ksm-aiot-upnvj-2026-supersecure-enterprise-jwt"  # nosec B105 - public dev default, rejected in production
MIN_JWT_SECRET_LENGTH = 32
ALLOWED_JWT_ALGORITHMS = ("HS256", "HS384", "HS512")


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
    # Staged uploads never saved into a record are purged after this many hours
    STAGED_UPLOAD_TTL_HOURS: int = Field(default=24, validation_alias="STAGED_UPLOAD_TTL_HOURS")
    # Number of reverse proxies in front of the API that append to X-Forwarded-For (e.g. cloudflared/nginx = 1).
    # 0 = trust only the socket peer address.
    TRUSTED_PROXY_HOPS: int = Field(default=1, ge=0, validation_alias="TRUSTED_PROXY_HOPS")
    # Initial password for login accounts created by the Excel import. Unset = random, unusable until reset.
    IMPORT_DEFAULT_PASSWORD: str | None = Field(default=None, validation_alias="IMPORT_DEFAULT_PASSWORD")

    # Security & Tokens: Short-lived access tokens (30 mins) + 7 days refresh
    SECRET_KEY: str = Field(default=DEV_DEFAULT_JWT_SECRET, validation_alias="JWT_SECRET")
    ALGORITHM: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")

    SUPERADMIN_NIM: str = Field(validation_alias="SUPERADMIN_NIM")
    SUPERADMIN_NAME: str = Field(validation_alias="SUPERADMIN_NAME")
    SUPERADMIN_EMAIL: str = Field(validation_alias="SUPERADMIN_EMAIL")
    SUPERADMIN_PW: str = Field(validation_alias="SUPERADMIN_PW")

    # Allowed CORS Origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:80",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    CORS_ORIGIN_REGEX: str | None = Field(
        default=r"^https:\/\/.*\.trycloudflare\.com$",
        validation_alias="CORS_ORIGIN_REGEX",
    )
    # Off unless explicitly enabled: DEBUG exposes exception details in API errors and runs the dev seeder
    DEBUG: bool = Field(default=False, validation_alias="DEBUG")
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

    def get_allowed_origin_regex(self) -> str | None:
        """Return CORS origin regex, or None in production unless explicitly configured."""
        if self.ENVIRONMENT.lower() == "production" and self.CORS_ORIGIN_REGEX == r"^https:\/\/.*\.trycloudflare\.com$":
            return None
        return self.CORS_ORIGIN_REGEX

    @field_validator("ALGORITHM")
    def validate_jwt_algorithm(cls, v):
        # An env value like "none" would make PyJWT accept unsigned tokens
        if v not in ALLOWED_JWT_ALGORITHMS:
            raise ValueError(f"JWT_ALGORITHM must be one of {', '.join(ALLOWED_JWT_ALGORITHMS)}")
        return v

    @field_validator("SUPERADMIN_NIM", "SUPERADMIN_NAME", "SUPERADMIN_EMAIL", "SUPERADMIN_PW")
    def validate_superadmin_fields(cls, v):
        if not v:
            raise ValueError("Superadmin fields cannot be empty")
        return v


def validate_production_security(cfg: Settings) -> None:
    """Fail closed on insecure production configuration instead of only logging a warning."""
    if cfg.ENVIRONMENT.lower() != "production":
        return
    if cfg.SECRET_KEY == DEV_DEFAULT_JWT_SECRET or len(cfg.SECRET_KEY) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(
            "JWT_SECRET must be set to a random value of at least "
            f"{MIN_JWT_SECRET_LENGTH} characters in production (generate with: openssl rand -hex 32)."
        )
    if cfg.DEBUG:
        logger.warning("DEBUG=True is ignored in production (it would expose exception details).")
        cfg.DEBUG = False


settings = Settings()
validate_production_security(settings)
