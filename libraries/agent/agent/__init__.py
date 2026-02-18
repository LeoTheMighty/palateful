"""Agent library for AI-powered meal suggestions in Palateful.

This library provides a LangGraph-based agent that generates personalized meal
suggestions based on the user's pantry, preferences, and dietary restrictions.

Main components:
- LLM providers: OpenAI, Anthropic, and Ollama support
- Tools: Pantry, recipe search, user preferences
- Agent graph: LangGraph state machine for suggestion workflow
- Runner: Execute the agent for a user
- Tasks: Celery tasks for background processing
"""

from agent.config import AgentSettings, settings
from agent.runner import run_daily_suggestions_for_all, run_suggestion_agent

__all__ = [
    "settings",
    "AgentSettings",
    "run_suggestion_agent",
    "run_daily_suggestions_for_all",
    # Tasks (lazy imports - celery only available in worker context)
    "AutoAgentTask",
    "DailySuggestionsTask",
    "ExpiringIngredientsSuggestionsTask",
    "register_agent_tasks",
    "trigger_user_suggestion",
    "trigger_daily_suggestions",
    "trigger_expiring_suggestions",
]


def __getattr__(name):
    """Lazy import for celery-dependent task symbols."""
    _task_names = {
        "AutoAgentTask",
        "DailySuggestionsTask",
        "ExpiringIngredientsSuggestionsTask",
        "register_agent_tasks",
        "trigger_daily_suggestions",
        "trigger_expiring_suggestions",
        "trigger_user_suggestion",
    }
    if name in _task_names:
        from agent import tasks
        return getattr(tasks, name)
    raise AttributeError(f"module 'agent' has no attribute {name!r}")
