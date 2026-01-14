"""Celery worker entry point."""

from utils.services.celery import celery_app, import_tasks

# Import all tasks from utils.tasks package
import_tasks()

# Register agent tasks
from agent import register_agent_tasks
register_agent_tasks()

# Re-export celery_app for the worker command
app = celery_app
