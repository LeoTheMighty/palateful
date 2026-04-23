"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings
from utils.constants import DATABASE_URL as _UTILS_DATABASE_URL


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Auth0 Configuration
    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_client_id: str = ""

    # Database — defaults to utils.constants.DATABASE_URL, which builds
    # the URL from DB_HOST/DB_USERNAME/DB_PASSWORD/etc components when
    # those are set (prod path) and otherwise falls back to the raw
    # DATABASE_URL env var (local dev / tests).
    database_url: str = _UTILS_DATABASE_URL or ""

    # Redis (optional for MVP)
    redis_url: str = ""

    # CORS Origins — exact origins only (Starlette does not support wildcards).
    # Ngrok tunnels are covered by allow_origin_regex in main.py.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # Regex pattern for additional allowed origins (e.g. localhost Flutter app, ngrok tunnels in dev)
    cors_origin_regex: str = r"(https?://localhost(:\d+)?|https?://127\.0\.0\.1(:\d+)?|https://.*\.ngrok(?:-free)?\.(?:app|io))"

    # E2E testing bypass — when true, a fixed test token skips Auth0 validation
    e2e_test_mode: bool = False

    # Environment
    environment: str = "dev"

    # AI Chat
    ai_chat_monthly_token_cap: int = 500_000

    # AWS / Parser — default suffix matches environment so dev/prod stay separated
    aws_region: str = "us-east-1"
    parser_inputs_bucket: str = ""
    parser_outputs_bucket: str = ""
    s3_imports_bucket: str = ""
    batch_job_queue: str = ""
    batch_job_definition: str = ""

    # Self URL used by the Batch container to POST completion callbacks.
    # Set via API_BASE_URL env var on the ECS task. Empty in dev/local, in which
    # case CreateParserBatch falls back to polling-only mode.
    api_base_url: str = ""

    # Client-latency ingest kill-switch — served to clients via
    # `GET /v1/flags/perf` (cla-1c). Flutter fetches on startup, caches
    # for 5 min, defaults-on on fetch error. Flip `CLIENT_LATENCY_INGEST_ENABLED`
    # to `false` on the ECS task-def to shed all client-latency writes
    # without a client rebuild. `CLIENT_LATENCY_SAMPLING_RATE` (0.0..1.0)
    # is a softer lever — clients sample events before enqueue at that
    # rate. Default: everything on, 100% sampled.
    client_latency_ingest_enabled: bool = True
    client_latency_sampling_rate: float = 1.0

    @field_validator("client_latency_sampling_rate")
    @classmethod
    def _sampling_rate_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(
                "client_latency_sampling_rate must be in [0.0, 1.0]"
            )
        return v

    @field_validator("auth0_domain", "auth0_audience", "database_url")
    @classmethod
    def require_non_empty(cls, v: str, info) -> str:
        if not v:
            raise ValueError(
                f"{info.field_name} is required — set it via the {info.field_name.upper()} environment variable"
            )
        return v

    def model_post_init(self, __context) -> None:
        """Derive AWS resource names from environment when not explicitly set.

        `.strip()` is intentional: an unbound shell-style substitution
        (e.g. Terraform emitting `S3_IMPORTS_BUCKET=` or a whitespace-only
        value) should fall through to the env-derived default, not
        propagate an invalid bucket name into boto3 calls.
        """
        env = self.environment
        if not self.parser_inputs_bucket.strip():
            object.__setattr__(self, "parser_inputs_bucket", f"palateful-parser-inputs-{env}")
        if not self.parser_outputs_bucket.strip():
            object.__setattr__(self, "parser_outputs_bucket", f"palateful-parser-outputs-{env}")
        if not self.s3_imports_bucket.strip():
            object.__setattr__(self, "s3_imports_bucket", f"palateful-imports-{env}")
        if not self.batch_job_queue.strip():
            object.__setattr__(self, "batch_job_queue", f"palateful-parser-queue-{env}")
        if not self.batch_job_definition.strip():
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
