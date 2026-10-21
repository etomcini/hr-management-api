from enum import StrEnum

from pydantic import EmailStr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Settings(BaseSettings):
    app_env: Environment = Environment.DEVELOPMENT

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
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

    # RabbitMQ
    rabbitmq_user: str
    rabbitmq_password: SecretStr
    rabbitmq_vhost: str = "hr_app"
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672

    # Password reset
    frontend_url: str
    password_reset_token_expire_minutes: int = 30

    # Password-change rate limiting
    password_change_max_per_hour: int = 4
    password_change_window_minutes: int = 60


settings = Settings()  # Loaded from .env file
