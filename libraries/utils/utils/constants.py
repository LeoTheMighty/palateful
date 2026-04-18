import logging
import os
from urllib.parse import quote

ENVIRONMENT = os.environ.get("ENVIRONMENT")

# Logging level - can be DEBUG, INFO, WARNING, ERROR, CRITICAL
_logging_level_str = os.environ.get("LOGGING_LEVEL", "INFO").upper()
LOGGING_LEVEL = getattr(logging, _logging_level_str, logging.INFO)

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL")
CELERY_QUEUE_PREFIX = os.environ.get("CELERY_QUEUE_PREFIX", "palateful-")
CELERY_POLLING_INTERVAL = int(os.environ.get("CELERY_POLLING_INTERVAL", "1"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")  # For LocalStack


def _build_database_url() -> str | None:
    """Construct DATABASE_URL.

    Prefer component env vars (DB_HOST, DB_PORT, DB_NAME, DB_USERNAME,
    DB_PASSWORD, DB_SSLMODE) when all the required ones are present — ECS
    tasks in prod get DB_PASSWORD pulled straight from the RDS-managed
    Secrets Manager secret, which eliminates the drift vector we hit
    when the URL was kept in a separately-maintained secret. Fall back
    to DATABASE_URL verbatim so local docker-compose and CI keep working
    unchanged.
    """
    host = os.environ.get("DB_HOST")
    user = os.environ.get("DB_USERNAME")
    pwd = os.environ.get("DB_PASSWORD")
    name = os.environ.get("DB_NAME")
    if host and user and pwd and name:
        port = os.environ.get("DB_PORT", "5432")
        sslmode = os.environ.get("DB_SSLMODE")
        query = f"?sslmode={sslmode}" if sslmode else ""
        return f"postgresql://{user}:{quote(pwd, safe='')}@{host}:{port}/{name}{query}"
    return os.environ.get("DATABASE_URL")


DATABASE_URL = _build_database_url()
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW", "20"))

# AWS Parser / Batch settings (used by worker tasks)
PARSER_INPUTS_BUCKET = os.environ.get("PARSER_INPUTS_BUCKET", "")
PARSER_OUTPUTS_BUCKET = os.environ.get("PARSER_OUTPUTS_BUCKET", "")
# sbf-1 / sbf-3. Bucket that holds raw share-extension uploads
# (imports/{user_id}/{uuid}.{ext}) and the ffmpeg-extracted audio
# (sbf-4). Mirrors PARSER_INPUTS_BUCKET but lifecycle-scoped shorter.
S3_IMPORTS_BUCKET = os.environ.get("S3_IMPORTS_BUCKET", "")
BATCH_JOB_QUEUE = os.environ.get("BATCH_JOB_QUEUE", "")
BATCH_JOB_DEFINITION = os.environ.get("BATCH_JOB_DEFINITION", "")

# Auth0 configuration
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE", "")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "")

# Valid recipe vibe categories
VALID_VIBES = [
    "light_fresh",
    "hearty",
    "comfort",
    "energizing",
    "carb_load",
    "indulgent",
    "warming",
]

VIBE_OPTIONS = [
    {"id": "light_fresh", "name": "Light & Fresh", "color": "#A8D8A8"},
    {"id": "hearty", "name": "Hearty & Filling", "color": "#D4A853"},
    {"id": "comfort", "name": "Comfort", "color": "#CB8B73"},
    {"id": "energizing", "name": "Energizing", "color": "#8FA882"},
    {"id": "carb_load", "name": "Carb-Load", "color": "#C8A96E"},
    {"id": "indulgent", "name": "Indulgent", "color": "#8B6B8B"},
    {"id": "warming", "name": "Warming", "color": "#A0522D"},
]

# Generic task constants (used by utils.tasks.task.BaseTask)
EXPONENTIAL_BACKOFF_FACTOR = float(os.environ.get("EXPONENTIAL_BACKOFF_FACTOR", "2.0"))
MIN_BATCH_SIZE = int(os.environ.get("MIN_BATCH_SIZE", "2"))  # Minimum chunk size
MAX_BATCH_SIZE = int(os.environ.get("MAX_BATCH_SIZE", "10"))  # Maximum chunk size
MAX_TASK_COUNTDOWN = int(os.environ.get("MAX_TASK_COUNTDOWN", "30"))  # Maximum task countdown

# Stuck-import sweeper (used by sweep_stuck_imports_task)
STUCK_IMPORT_JOB_TIMEOUT_MINUTES = int(
    os.environ.get("STUCK_IMPORT_JOB_TIMEOUT_MINUTES", "10")
)
STUCK_IMPORT_SWEEPER_INTERVAL_SECONDS = int(
    os.environ.get("STUCK_IMPORT_SWEEPER_INTERVAL_SECONDS", "120")
)

# Pipeline stage markers (written by each task on successful stage completion,
# read by the retry endpoint to resume from the next stage). STAGE_CREATED is
# a telemetry-only token (irrd-2) — the terminal stage from the caret
# expansion's timeline view, never written to `import_items.last_successful_stage`.
STAGE_PARSED = "parsed"
STAGE_EXTRACTED = "extracted"
STAGE_MATCHED = "matched"
STAGE_CREATED = "created"
