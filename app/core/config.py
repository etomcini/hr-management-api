from enum import StrEnum

from pydantic import EmailStr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: Environment = Environment.DEVELOPMENT
    docs_enabled: bool = True

    # Database
    database_url: str

    # Authentication
    jwt_secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_min: int = 10

    refresh_access_token_expire_days: int = 7

    default_role: str = "employee"

    # Email
    mail_server: str
    mail_port: int
    mail_username: str
    mail_password: SecretStr
    mail_from_email: EmailStr
    mail_from_name: str = "HR App"
    mail_start_tls: bool = True

    # Password reset
    frontend_url: str
    password_reset_token_expire_minutes: int = 30


settings = Settings()  # Loaded from .env file
