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

from agent.config import settings, AgentSettings
from agent.runner import run_suggestion_agent, run_daily_suggestions_for_all
from agent.tasks import (
    AutoAgentTask,
    DailySuggestionsTask,
    ExpiringIngredientsSuggestionsTask,
    register_agent_tasks,
    trigger_user_suggestion,
    trigger_daily_suggestions,
    trigger_expiring_suggestions,
)

__all__ = [
    "settings",
    "AgentSettings",
    "run_suggestion_agent",
    "run_daily_suggestions_for_all",
    # Tasks
    "AutoAgentTask",
    "DailySuggestionsTask",
    "ExpiringIngredientsSuggestionsTask",
    "register_agent_tasks",
    "trigger_user_suggestion",
    "trigger_daily_suggestions",
    "trigger_expiring_suggestions",
]
