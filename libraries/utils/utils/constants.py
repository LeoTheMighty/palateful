import logging
import os

ENVIRONMENT = os.environ.get("ENVIRONMENT")

# Logging level - can be DEBUG, INFO, WARNING, ERROR, CRITICAL
_logging_level_str = os.environ.get("LOGGING_LEVEL", "INFO").upper()
LOGGING_LEVEL = getattr(logging, _logging_level_str, logging.INFO)

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL")
CELERY_QUEUE_PREFIX = os.environ.get("CELERY_QUEUE_PREFIX", "palateful-")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")  # For LocalStack
DATABASE_URL = os.environ.get("DATABASE_URL")
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW", "20"))

# Auth0 configuration
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE", "")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "")

# Generic task constants (used by utils.tasks.task.BaseTask)
EXPONENTIAL_BACKOFF_FACTOR = float(os.environ.get("EXPONENTIAL_BACKOFF_FACTOR", "2.0"))
MIN_BATCH_SIZE = int(os.environ.get("MIN_BATCH_SIZE", "2"))  # Minimum chunk size
MAX_BATCH_SIZE = int(os.environ.get("MAX_BATCH_SIZE", "10"))  # Maximum chunk size
MAX_TASK_COUNTDOWN = int(os.environ.get("MAX_TASK_COUNTDOWN", "30"))  # Maximum task countdown
