"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Auth0 Configuration
    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_client_id: str = ""

    # Database
    database_url: str = ""

    # Redis (optional for MVP)
    redis_url: str = ""

    # CORS Origins
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "https://*.ngrok-free.app",
        "https://*.ngrok.io",
    ]

    # Environment
    environment: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
