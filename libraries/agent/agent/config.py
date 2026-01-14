"""Configuration settings for the Agent library."""

from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Agent library settings."""

    # Database
    database_url: str = "postgresql://localhost:5432/palateful"

    # LLM Providers
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Agent Configuration
    agent_default_provider: str = "openai"  # "openai" | "anthropic" | "ollama"
    agent_model: str = "gpt-4o-mini"
    agent_temperature: float = 0.7

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # Service
    debug: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = AgentSettings()
