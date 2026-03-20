"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic import field_validator
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

    # CORS Origins — exact origins only (Starlette does not support wildcards).
    # Ngrok tunnels are covered by allow_origin_regex in main.py.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Regex pattern for additional allowed origins (e.g. ngrok tunnels in dev)
    cors_origin_regex: str = r"https://.*\.ngrok(?:-free)?\.(?:app|io)"

    # Environment
    environment: str = "development"

    # AWS / Parser — default suffix matches environment so dev/prod stay separated
    aws_region: str = "us-east-1"
    parser_inputs_bucket: str = ""
    parser_outputs_bucket: str = ""
    batch_job_queue: str = ""
    batch_job_definition: str = ""

    @field_validator("auth0_domain", "auth0_audience", "database_url")
    @classmethod
    def require_non_empty(cls, v: str, info) -> str:
        if not v:
            raise ValueError(
                f"{info.field_name} is required — set it via the {info.field_name.upper()} environment variable"
            )
        return v

    def model_post_init(self, __context) -> None:
        """Derive AWS resource names from environment when not explicitly set."""
        env = self.environment
        if not self.parser_inputs_bucket:
            object.__setattr__(self, "parser_inputs_bucket", f"palateful-parser-inputs-{env}")
        if not self.parser_outputs_bucket:
            object.__setattr__(self, "parser_outputs_bucket", f"palateful-parser-outputs-{env}")
        if not self.batch_job_queue:
            object.__setattr__(self, "batch_job_queue", f"palateful-parser-queue-{env}")
        if not self.batch_job_definition:
            object.__setattr__(self, "batch_job_definition", f"palateful-parser-job-{env}")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
