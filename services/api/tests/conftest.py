"""Test configuration for API service."""

import os
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, PropertyMock

import pytest

# Set test environment before any imports
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("AUTH0_DOMAIN", "test.auth0.com")
os.environ.setdefault("AUTH0_AUDIENCE", "https://api.palateful.test")
os.environ.setdefault("AUTH0_CLIENT_ID", "test_client_id")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "sqs://")

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Model-like objects for mocking database results
# ---------------------------------------------------------------------------

class MockModel:
    """Base mock model that supports attribute access."""

    def __init__(self, **kwargs):
        now = datetime.now(UTC)
        defaults = {
            "id": str(uuid.uuid4()),
            "created_at": now,
            "updated_at": now,
            "archived_at": None,
        }
        defaults.update(kwargs)
        for key, value in defaults.items():
            setattr(self, key, value)


class MockUser(MockModel):
    """Mock User model."""

    def __init__(self, **kwargs):
        defaults = {
            "auth0_id": f"auth0|{uuid.uuid4()}",
            "email": "test@example.com",
            "name": "Test User",
            "username": "testuser",
            "picture": None,
            "email_verified": True,
            "has_completed_onboarding": True,
            "default_recipe_book_id": None,
            "notification_preferences": {
                "push_enabled": True,
                "email_digest": "daily",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
                "timezone": "America/Denver",
            },
            "push_tokens": [],
            "username_changed_at": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockRecipeBook(MockModel):
    """Mock RecipeBook model."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Test Recipe Book",
            "description": "A test recipe book",
            "is_public": False,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockRecipeBookUser(MockModel):
    """Mock RecipeBookUser model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "recipe_book_id": str(uuid.uuid4()),
            "role": "owner",
            "invited_by_id": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockRecipe(MockModel):
    """Mock Recipe model."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Test Recipe",
            "description": "A test recipe",
            "instructions": "Step 1: Test",
            "servings": 4,
            "prep_time": 10,
            "cook_time": 20,
            "image_url": None,
            "source_url": None,
            "recipe_book_id": str(uuid.uuid4()),
            "embedding": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockIngredient(MockModel):
    """Mock Ingredient model."""

    def __init__(self, **kwargs):
        defaults = {
            "canonical_name": "flour",
            "aliases": [],
            "category": "baking",
            "flavor_profile": [],
            "default_unit": "g",
            "is_canonical": True,
            "pending_review": False,
            "image_url": None,
            "embedding": None,
            "submitted_by_id": None,
            "parent_id": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockRecipeIngredient(MockModel):
    """Mock RecipeIngredient model."""

    def __init__(self, **kwargs):
        from decimal import Decimal
        defaults = {
            "recipe_id": str(uuid.uuid4()),
            "ingredient_id": str(uuid.uuid4()),
            "quantity_display": Decimal("2.000"),
            "unit_display": "cups",
            "quantity_normalized": Decimal("240.000"),
            "unit_normalized": "g",
            "notes": None,
            "is_optional": False,
            "order_index": 0,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockFriendRequest(MockModel):
    """Mock FriendRequest model."""

    def __init__(self, **kwargs):
        defaults = {
            "from_user_id": str(uuid.uuid4()),
            "to_user_id": str(uuid.uuid4()),
            "status": "pending",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockFriendship(MockModel):
    """Mock Friendship model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "friend_id": str(uuid.uuid4()),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockMealEvent(MockModel):
    """Mock MealEvent model."""

    def __init__(self, **kwargs):
        defaults = {
            "title": "Test Dinner",
            "description": None,
            "meal_type": "dinner",
            "event_date": datetime.now(UTC).date(),
            "event_time": "18:00",
            "status": "planned",
            "recipe_id": None,
            "owner_id": str(uuid.uuid4()),
            "notify_before_minutes": 30,
            "recurrence_rule": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockMealEventParticipant(MockModel):
    """Mock MealEventParticipant model."""

    def __init__(self, **kwargs):
        defaults = {
            "meal_event_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "role": "host",
            "status": "accepted",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockShoppingList(MockModel):
    """Mock ShoppingList model."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Test Shopping List",
            "description": None,
            "status": "active",
            "owner_id": str(uuid.uuid4()),
            "share_code": None,
            "share_code_expires_at": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockShoppingListUser(MockModel):
    """Mock ShoppingListUser model."""

    def __init__(self, **kwargs):
        defaults = {
            "shopping_list_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "role": "owner",
            "notify_on_changes": True,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockShoppingListItem(MockModel):
    """Mock ShoppingListItem model."""

    def __init__(self, **kwargs):
        from decimal import Decimal
        defaults = {
            "shopping_list_id": str(uuid.uuid4()),
            "name": "Test Item",
            "quantity": Decimal("1"),
            "unit": "each",
            "category": None,
            "is_checked": False,
            "checked_by_id": None,
            "checked_at": None,
            "added_by_id": str(uuid.uuid4()),
            "assigned_to_id": None,
            "ingredient_id": None,
            "notes": None,
            "store_section": None,
            "sort_order": 0,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockActiveTimer(MockModel):
    """Mock ActiveTimer model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "label": "Test Timer",
            "duration_seconds": 300,
            "elapsed_seconds": 0,
            "status": "running",
            "started_at": datetime.now(UTC),
            "paused_at": None,
            "completed_at": None,
            "meal_event_id": None,
            "recipe_step_id": None,
            "notify_on_complete": True,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockInvitation(MockModel):
    """Mock Invitation model."""

    def __init__(self, **kwargs):
        defaults = {
            "from_user_id": str(uuid.uuid4()),
            "to_user_id": None,
            "to_email": "invitee@example.com",
            "resource_type": "recipe_book",
            "resource_id": str(uuid.uuid4()),
            "role": "editor",
            "status": "pending",
            "message": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockInviteLink(MockModel):
    """Mock InviteLink model."""

    def __init__(self, **kwargs):
        defaults = {
            "token": str(uuid.uuid4()),
            "resource_type": "recipe_book",
            "resource_id": str(uuid.uuid4()),
            "role": "viewer",
            "created_by_id": str(uuid.uuid4()),
            "is_active": True,
            "expires_at": None,
            "max_uses": None,
            "use_count": 0,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockImportJob(MockModel):
    """Mock ImportJob model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "recipe_book_id": str(uuid.uuid4()),
            "source_type": "url",
            "status": "pending",
            "total_items": 1,
            "processed_items": 0,
            "succeeded_items": 0,
            "failed_items": 0,
            "pending_review_items": 0,
            "ai_cost_usd": 0.0,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockImportItem(MockModel):
    """Mock ImportItem model."""

    def __init__(self, **kwargs):
        defaults = {
            "import_job_id": str(uuid.uuid4()),
            "source_url": "https://example.com/recipe",
            "status": "pending",
            "raw_data": None,
            "parsed_recipe": None,
            "user_edits": None,
            "error_message": None,
            "ai_cost_usd": 0.0,
            "needs_review": False,
            "recipe_name": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockParserJob(MockModel):
    """Mock ParserJob model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "s3_key": "uploads/test.jpg",
            "output_s3_key": "results/test.json",
            "status": "pending",
            "batch_job_id": None,
            "result": None,
            "error_message": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


# ---------------------------------------------------------------------------
# Mock query builder to simulate SQLAlchemy Query objects
# ---------------------------------------------------------------------------

class MockQuery:
    """Mock SQLAlchemy query that supports chaining."""

    def __init__(self, items=None):
        self._items = items or []

    def filter(self, *args, **kwargs):
        return self

    def where(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def outerjoin(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, n):
        return self

    def limit(self, n):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None

    def count(self):
        return len(self._items)

    def scalar(self):
        if self._items:
            return self._items[0]
        return None

    def one_or_none(self):
        return self._items[0] if self._items else None

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return self

    def update(self, values, **kwargs):
        pass

    def delete(self, **kwargs):
        pass


class MockExecuteResult:
    """Mock result from db.execute()."""

    def __init__(self, items=None):
        self._items = items or []

    def scalar(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items

    def __iter__(self):
        return iter(self._items)


# ---------------------------------------------------------------------------
# Mock Database class
# ---------------------------------------------------------------------------

class MockDatabase:
    """Mock Database that can be configured per-test."""

    def __init__(self):
        self.db = MagicMock()
        self._find_by_results = {}
        self._where_results = {}

        # Default db.query returns empty MockQuery
        self.db.query.return_value = MockQuery()
        self.db.execute.return_value = MockExecuteResult()
        self.db.commit = MagicMock()
        self.db.flush = MagicMock()
        self.db.refresh = MagicMock()
        self.db.add = MagicMock()

    def find_by(self, model_class, **kwargs):
        """Mock find_by - returns configured result or None."""
        key = (model_class.__name__, tuple(sorted(kwargs.items())))
        if key in self._find_by_results:
            return self._find_by_results[key]
        # Also check by model name alone for simpler configs
        simple_key = model_class.__name__
        if simple_key in self._find_by_results:
            return self._find_by_results[simple_key]
        return None

    def set_find_by(self, model_class, result, **kwargs):
        """Configure a find_by return value."""
        if kwargs:
            key = (model_class.__name__, tuple(sorted(kwargs.items())))
        else:
            key = model_class.__name__
        self._find_by_results[key] = result

    def find_or_create_by(self, model_class, defaults=None, **kwargs):
        """Mock find_or_create_by."""
        result = self.find_by(model_class, **kwargs)
        if result:
            return result
        # Create a new instance
        all_attrs = {**(defaults or {}), **kwargs}
        return model_class(**all_attrs) if hasattr(model_class, '__call__') else MockModel(**all_attrs)

    def where(self, model, **kwargs):
        """Mock where - returns MockQuery with configured results."""
        key = model.__name__
        items = self._where_results.get(key, [])
        return MockQuery(items)

    def set_where(self, model_class, items):
        """Configure a where return value."""
        self._where_results[model_class.__name__] = items

    def create(self, model):
        """Mock create."""
        if not hasattr(model, 'id') or model.id is None:
            model.id = str(uuid.uuid4())
        if not hasattr(model, 'created_at') or model.created_at is None:
            model.created_at = datetime.now(UTC)
        if not hasattr(model, 'updated_at') or model.updated_at is None:
            model.updated_at = datetime.now(UTC)
        return model

    def create_all(self, models):
        """Mock create_all."""
        for m in models:
            self.create(m)
        return models

    def update(self, model, **kwargs):
        """Mock update."""
        for key, value in kwargs.items():
            setattr(model, key, value)
        model.updated_at = datetime.now(UTC)
        return model

    def delete(self, model):
        """Mock delete."""
        return model

    def save(self, model):
        """Mock save."""
        return self.create(model)

    def close(self):
        """Mock close."""
        pass

    def lock(self, key):
        """Mock lock."""
        return MagicMock(__enter__=MagicMock(), __exit__=MagicMock())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Create a fresh MockDatabase for each test."""
    return MockDatabase()


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    return MockUser()


@pytest.fixture
def client(mock_db, mock_user):
    """Create a TestClient with mocked dependencies."""
    from main import app
    from dependencies import get_database, get_current_user

    def override_get_database():
        return mock_db

    def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_db):
    """Create a TestClient with only database mocked (no auth override)."""
    from main import app
    from dependencies import get_database

    def override_get_database():
        return mock_db

    app.dependency_overrides[get_database] = override_get_database

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
