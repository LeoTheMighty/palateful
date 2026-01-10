"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/palateful"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth0
    auth0_domain: str = ""
    auth0_client_id: str = ""
    auth0_audience: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Application
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]


settings = Settings()
