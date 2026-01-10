import logging
import pkgutil
from types import ModuleType

from celery import Celery
from celery.signals import setup_logging
from hal_utils.constants import (
    CELERY_BROKER_URL,
    CELERY_QUEUE_PREFIX,
    LOGGING_LEVEL
)
from hal_utils import tasks

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)

# Create Celery app
celery_app = Celery('tasks', broker=CELERY_BROKER_URL)
celery_app.conf.broker_transport_options = {
    'queue_name_prefix': CELERY_QUEUE_PREFIX
}


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
