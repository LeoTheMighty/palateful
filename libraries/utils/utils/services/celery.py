import logging
import pkgutil
from types import ModuleType

from celery import Celery
from celery.signals import setup_logging
from utils.constants import (
    AWS_ENDPOINT_URL,
    AWS_REGION,
    CELERY_BROKER_URL,
    CELERY_QUEUE_PREFIX,
    LOGGING_LEVEL
)
from utils import tasks

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)

# Create Celery app
celery_app = Celery('tasks', broker=CELERY_BROKER_URL)

# Configure broker transport options for SQS
broker_transport_options = {
    'queue_name_prefix': CELERY_QUEUE_PREFIX,
    'region': AWS_REGION,
    'visibility_timeout': 3600,  # 1 hour
    'polling_interval': 1,
}

# Add LocalStack endpoint URL if configured (for local development)
if AWS_ENDPOINT_URL:
    broker_transport_options['endpoint_url'] = AWS_ENDPOINT_URL

celery_app.conf.broker_transport_options = broker_transport_options

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'shopping-list-deadline-reminders': {
        'task': 'shopping_list_deadline_reminder',
        'schedule': 900.0,  # Every 15 minutes
        'options': {'queue': 'celery'},
    },
}
celery_app.conf.timezone = 'UTC'


@setup_logging.connect
def config_loggers(*_args, **_kwargs):
    """Configures celery loggers with json format and catalyst id defined in main.py"""


def import_tasks(package: ModuleType = tasks):
    """Import all tasks in the given package"""
    logger.info("Importing task files from %s", package.__name__)
    for _loader, module_name, is_pkg in pkgutil.walk_packages(
        package.__path__,
        package.__name__ + '.'
    ):
        logger.info("Importing module: %s", module_name)
        __import__(module_name)
        if is_pkg:
            next_package = __import__(module_name, fromlist=["dummy"])
            import_tasks(next_package)  # Recursive call to handle sub-packages
