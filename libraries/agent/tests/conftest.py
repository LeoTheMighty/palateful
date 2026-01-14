"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.id = "test-user-id"
    user.email = "test@example.com"
    user.name = "Test User"
    user.notification_preferences = {
        "push_enabled": True,
        "email_digest": "daily",
        "timezone": "America/Denver",
    }
    user.push_tokens = []
    return user


@pytest.fixture
def sample_pantry_items():
    """Create sample pantry items."""
    return [
        {
            "ingredient_name": "chicken breast",
            "category": "protein",
            "quantity": 2,
            "unit": "lb",
            "expires_at": None,
            "days_until_expiry": None,
        },
        {
            "ingredient_name": "tomato",
            "category": "produce",
            "quantity": 4,
            "unit": "count",
            "expires_at": "2025-01-20T00:00:00",
            "days_until_expiry": 3,
            "expiring_soon": True,
        },
        {
            "ingredient_name": "pasta",
            "category": "grains",
            "quantity": 1,
            "unit": "lb",
            "expires_at": None,
            "days_until_expiry": None,
        },
    ]


@pytest.fixture
def sample_suggestion_state(sample_pantry_items):
    """Create a sample suggestion state."""
    return {
        "user_id": "test-user-id",
        "trigger_type": "daily",
        "trigger_context": {},
        "pantry_items": sample_pantry_items,
        "user_preferences": {
            "dietary_restrictions": [],
            "cuisine_preferences": ["Italian", "Mexican"],
        },
        "expiring_items": [
            item for item in sample_pantry_items if item.get("expiring_soon")
        ],
        "matched_recipes": [],
        "suggestions": [],
        "messages": [],
        "current_step": "context_fetched",
        "error": None,
        "created_suggestion_ids": [],
        "notifications_sent": 0,
    }
