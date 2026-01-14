"""Configuration settings for the ingredient scraper."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    usda_api_key: str | None = None
    openai_api_key: str | None = None

    # Scraper settings
    scraper_cache_dir: Path = Path("./cache")
    scraper_output_dir: Path = Path("./output")
    scraper_rate_limit_per_second: float = 2.0
    scraper_max_retries: int = 3
    scraper_timeout_seconds: int = 30

    # Pipeline settings
    dedup_similarity_threshold: float = 0.90
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 100

    # OpenAI settings for substitution generation
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 1000
    substitution_batch_size: int = 20

    # Target counts
    target_ingredient_count: int = 5000


settings = Settings()
