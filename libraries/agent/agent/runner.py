"""Agent runner for executing suggestion workflows."""

import logging
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from agent.graph.state import SuggestionState
from agent.graph.graph import create_suggestion_graph
from agent.config import settings

logger = logging.getLogger(__name__)

# Lazy initialization of engine and session factory
_engine = None
_session_factory = None


def _get_session_factory():
    """Lazily create the session factory."""
    global _engine, _session_factory

    if _session_factory is None:
        _engine = create_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
        _session_factory = sessionmaker(
            _engine,
            class_=Session,
            expire_on_commit=False,
        )

    return _session_factory


def run_suggestion_agent(
    user_id: str,
    trigger_type: str = "daily",
    context: dict[str, Any] | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """
    Run the suggestion agent for a user.

    Args:
        user_id: ID of the user to generate suggestions for
        trigger_type: Type of trigger ("daily", "pantry_update", "expiring")
        context: Additional context for the trigger
        db: Optional database session to use (creates one if not provided)

    Returns:
        Final state from the agent workflow
    """
    logger.info(f"Starting suggestion agent for user {user_id}, trigger: {trigger_type}")

    # Create initial state
    initial_state: SuggestionState = {
        "user_id": user_id,
        "trigger_type": trigger_type,
        "trigger_context": context or {},
        "pantry_items": [],
        "user_preferences": {},
        "expiring_items": [],
        "matched_recipes": [],
        "suggestions": [],
        "messages": [],
        "current_step": "started",
        "error": None,
        "created_suggestion_ids": [],
        "notifications_sent": 0,
    }

    # Create graph
    graph = create_suggestion_graph()

    # Use provided db session or create a new one
    if db is not None:
        return _execute_graph(graph, initial_state, db)
    else:
        session_factory = _get_session_factory()
        with session_factory() as session:
            return _execute_graph(graph, initial_state, session)


def _execute_graph(
    graph,
    initial_state: SuggestionState,
    db: Session,
) -> dict[str, Any]:
    """Execute the graph nodes with error handling."""
    try:
        # Execute nodes manually since we need to pass db session
        # In a full LangGraph setup, we'd use a custom runnable

        # Step 1: Fetch context
        context_result = graph.nodes["fetch_context"](initial_state, db)
        state = {**initial_state, **context_result}

        # Step 2: Generate suggestions
        suggestions_result = graph.nodes["generate_suggestions"](state, db)
        state = {**state, **suggestions_result}

        # Step 3: Create notifications
        notifications_result = graph.nodes["create_notifications"](state, db)
        state = {**state, **notifications_result}

        logger.info(
            f"Agent completed for user {initial_state['user_id']}: "
            f"{len(state.get('created_suggestion_ids', []))} suggestions, "
            f"{state.get('notifications_sent', 0)} notifications"
        )

        return state

    except Exception as e:
        logger.error(f"Agent error for user {initial_state['user_id']}: {e}")

        # Run error handler
        error_state = {**initial_state, "error": str(e)}
        error_result = graph.nodes["handle_error"](error_state, db)

        return {**error_state, **error_result}


def run_daily_suggestions_for_all(db: Session | None = None) -> dict[str, int]:
    """
    Run daily suggestions for all users with notifications enabled.

    This is called by the Celery scheduled task.

    Args:
        db: Optional database session to use

    Returns:
        Dict with success and error counts
    """
    from utils.models import User

    logger.info("Starting daily suggestions for all users")

    def _run_for_all(session: Session) -> dict[str, int]:
        # Get all users with push notifications enabled
        query = select(User).where(
            User.notification_preferences["push_enabled"].as_boolean() == True  # noqa: E712
        )
        result = session.execute(query)
        users = result.scalars().all()

        logger.info(f"Found {len(users)} users for daily suggestions")

        success_count = 0
        error_count = 0

        for user in users:
            try:
                run_suggestion_agent(
                    user_id=str(user.id),
                    trigger_type="daily",
                    db=session,
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Error generating suggestions for user {user.id}: {e}")
                error_count += 1

        logger.info(
            f"Daily suggestions complete: {success_count} success, {error_count} errors"
        )

        return {"success": success_count, "errors": error_count}

    if db is not None:
        return _run_for_all(db)
    else:
        session_factory = _get_session_factory()
        with session_factory() as session:
            return _run_for_all(session)
