"""Test configuration for API service."""

import os
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterator
from unittest.mock import MagicMock

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


# Pre-warm the unit-alias cache so tests don't try to hit a real DB on
# the first `normalize_unit_display` call. With sync mocks the lazy-init
# happened to no-op cleanly (MagicMock's `execute(...).scalars().all()`
# returned a usable empty list); with async mocks the same lazy-init
# fires `mock_async_db.db.execute` (an `AsyncMock`) synchronously and
# crashes on `.scalars()` of a coroutine. Forcing `_cache_initialized=True`
# with empty sets makes `_ensure_cache` a no-op and `normalize_unit_display`
# returns inputs as-is — sufficient for handler tests that don't assert
# on canonical unit translation.
def _prewarm_unit_alias_cache_for_tests() -> None:
    from utils.services.units import normalize as _normalize

    _normalize._cache_initialized = True
    if not _normalize._canonical_units:
        _normalize._canonical_units = set()
    if not _normalize._alias_map:
        _normalize._alias_map = {}


_prewarm_unit_alias_cache_for_tests()


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

    def is_archived(self) -> bool:
        return self.archived_at is not None


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
            "is_admin": False,
            "default_recipe_book_id": None,
            "previous_recipe_book_id": None,
            "default_shopping_list_id": None,
            "previous_shopping_list_id": None,
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
            "is_shared": False,
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
            "tags": [],
            "recipe_book_id": str(uuid.uuid4()),
            "embedding": None,
            "forked_from_recipe_id": None,
            "forked_from_book_id": None,
            "forked_from_recipe_name": None,
            "forked_from_book_name": None,
            "primary_vibe": None,
            "secondary_vibe": None,
            "inferred_fields": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockIngredient(MockModel):
    """Mock Ingredient model."""

    def __init__(self, **kwargs):
        defaults = {
            "canonical_name": "flour",
            "flavor_profile": [],
            "default_unit": "g",
            "image_url": None,
            "submitted_by_id": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockRecipeIngredient(MockModel):
    """Mock RecipeIngredient model.

    The real RecipeIngredient is a join table with a composite PK
    (recipe_id, ingredient_id) and no `id` column. The base MockModel
    sets `id` by default, so strip it here — otherwise production code
    that accidentally reads `ri.id` passes tests but raises
    AttributeError in prod.
    """

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
        if "id" not in kwargs:
            try:
                delattr(self, "id")
            except AttributeError:
                pass


class MockRecipeStep(MockModel):
    """Mock RecipeStep model."""

    def __init__(self, **kwargs):
        defaults = {
            "recipe_id": str(uuid.uuid4()),
            "step_number": 1,
            "instruction": "Test step",
            "active_time_minutes": None,
            "timers": None,
            "wait_time_minutes": None,
            "wait_type": None,
            "can_prep_ahead": False,
            "is_optional": False,
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
            "message": None,
            "from_user": None,
            "to_user": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockFriendship(MockModel):
    """Mock Friendship model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "friend_id": str(uuid.uuid4()),
            "friend": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockCalendar(MockModel):
    """Mock Calendar model."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "My Calendar",
            "description": None,
            "is_default": True,
            "is_shared": False,
            "color": None,
            "owner_id": str(uuid.uuid4()),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockCalendarUser(MockModel):
    """Mock CalendarUser model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "calendar_id": str(uuid.uuid4()),
            "role": "owner",
            "invited_by_id": None,
            "last_opened_at": None,
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
            "scheduled_at": datetime.now(UTC),
            "status": "planned",
            "recipe_id": None,
            "recipe": None,
            "meal_id": None,
            "meal": None,
            "owner_id": str(uuid.uuid4()),
            "calendar_id": str(uuid.uuid4()),
            "pantry_id": None,
            "notify_prep_start": True,
            "prep_start_offset_minutes": 60,
            "notify_cook_start": True,
            "cook_start_offset_minutes": 30,
            "meal_reminder_time": None,
            "last_reminder_sent_at": None,
            "is_shared": False,
            "is_recurring": False,
            "recurrence_rule": None,
            "recurrence_end_date": None,
            "parent_event_id": None,
            "recurrence_rule_id": None,
            "participants": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    @property
    def reminder_time(self):
        """Mirror the real model's `reminder_time` property so endpoint
        response builders that call it work in tests without hitting the
        real SQLAlchemy model."""
        from utils.models.meal_event import MEAL_SLOT_DEFAULT_TIMES
        if self.meal_reminder_time is not None:
            return self.meal_reminder_time
        return MEAL_SLOT_DEFAULT_TIMES.get(
            self.meal_type, MEAL_SLOT_DEFAULT_TIMES["lunch"]
        )


class MockMealEventParticipant(MockModel):
    """Mock MealEventParticipant model."""

    def __init__(self, **kwargs):
        defaults = {
            "meal_event_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "role": "host",
            "status": "accepted",
            "assigned_tasks": [],
            "user": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockShoppingList(MockModel):
    """Mock ShoppingList model."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "Test Shopping List",
            "status": "pending",
            "owner_id": str(uuid.uuid4()),
            "is_shared": False,
            "share_code": None,
            "meal_event_id": None,
            "pantry_id": None,
            "default_deadline": None,
            "sort_by": "deadline",
            "auto_populate_from_calendar": True,
            "items": [],
            "members": [],
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
            "last_seen_at": None,
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
            "checked_by_user_id": None,
            "checked_at": None,
            "added_by_user_id": None,
            "assigned_to_user_id": None,
            "ingredient_id": None,
            "recipe_id": None,
            "notes": None,
            "store_section": None,
            "store_order": None,
            "sort_order": 0,
            "due_at": None,
            "meal_event_id": None,
            "due_reason": None,
            "priority": 3,
            "already_have_quantity": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockPantry(MockModel):
    """Mock Pantry model."""

    def __init__(self, **kwargs):
        defaults = {
            "name": "My Pantry",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockPantryUser(MockModel):
    """Mock PantryUser model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "pantry_id": str(uuid.uuid4()),
            "role": "owner",
            "invited_by_id": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockPantryIngredientEvent(MockModel):
    """Mock PantryIngredientEvent audit row."""

    def __init__(self, **kwargs):
        from decimal import Decimal
        defaults = {
            "pantry_id": str(uuid.uuid4()),
            "ingredient_id": str(uuid.uuid4()),
            "event_type": "decrement",
            "delta_quantity": Decimal("0.000"),
            "source_meal_event_id": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockPantryIngredient(MockModel):
    """Mock PantryIngredient model."""

    def __init__(self, **kwargs):
        from decimal import Decimal
        defaults = {
            "pantry_id": str(uuid.uuid4()),
            "ingredient_id": str(uuid.uuid4()),
            "quantity_display": Decimal("1.000"),
            "unit_display": "each",
            "quantity_normalized": Decimal("1.000"),
            "unit_normalized": "each",
            "storage_location": None,
            "expires_at": None,
            "ingredient": None,
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
            "status": "running",
            "started_at": datetime.now(UTC),
            "paused_at": None,
            "elapsed_when_paused": 0,
            "notify_on_complete": True,
            "notification_sent": False,
            "remaining_seconds": 300,
            "is_expired": False,
            "meal_event_id": None,
            "recipe_step_id": None,
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
            "role_offered": "editor",
            "status": "pending",
            "message": None,
            "expires_at": None,
            "responded_at": None,
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
            "role_offered": "viewer",
            "created_by_id": str(uuid.uuid4()),
            "created_by": None,
            "is_active": True,
            "expires_at": None,
            "max_uses": None,
            "use_count": 0,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockRecipeVersion(MockModel):
    """Mock RecipeVersion model."""

    def __init__(self, **kwargs):
        defaults = {
            "recipe_id": str(uuid.uuid4()),
            "version_number": 1,
            "snapshot": {"name": "Old Name", "ingredients": [], "steps": []},
            "changed_fields": ["name"],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockRecipeNote(MockModel):
    """Mock RecipeNote model."""

    def __init__(self, **kwargs):
        defaults = {
            "recipe_id": str(uuid.uuid4()),
            "body": "A test note",
            "created_by": str(uuid.uuid4()),
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockUserFavorite(MockModel):
    """Mock UserFavorite model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "recipe_id": str(uuid.uuid4()),
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
            "source_filename": None,
            "status": "pending",
            "total_items": 1,
            "processed_items": 0,
            "succeeded_items": 0,
            "failed_items": 0,
            "pending_review_items": 0,
            "total_ai_cost_cents": 0,
            "started_at": None,
            "completed_at": None,
            "dismissed_at": None,
            "error_message": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockImportItem(MockModel):
    """Mock ImportItem model."""

    def __init__(self, **kwargs):
        defaults = {
            "import_job_id": str(uuid.uuid4()),
            "source_type": "url",
            "source_url": "https://example.com/recipe",
            "source_reference": None,
            "status": "pending",
            "raw_data": {},
            "parsed_recipe": None,
            "error_message": None,
            "error_code": None,
            "ai_cost_cents": 0,
            "needs_review": False,
            "recipe_name": None,
            "retry_count": 0,
            "last_successful_stage": None,
            "last_retry_at": None,
            "awaiting_review_reason": None,
            "dismissed_at": None,
            "s3_key": None,
            "created_recipe_id": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockParserJob(MockModel):
    """Mock ParserJob model."""

    def __init__(self, **kwargs):
        defaults = {
            "user_id": str(uuid.uuid4()),
            "input_s3_key": "uploads/test.jpg",
            "output_s3_key": "results/test.json",
            "status": "pending",
            "batch_job_id": None,
            "extracted_text": None,
            "error_message": None,
            "completed_at": None,
            "import_job_id": None,
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

    def distinct(self, *args, **kwargs):
        return self

    def subquery(self):
        return MagicMock()

    def options(self, *args, **kwargs):
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

    def unique(self):
        return self

    def update(self, values, **kwargs):
        pass

    def delete(self, **kwargs):
        pass

    def in_(self, *args, **kwargs):
        return True

    def with_for_update(self, *args, **kwargs):
        return self


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

    def scalar_one(self):
        if not self._items:
            from sqlalchemy.exc import NoResultFound

            raise NoResultFound
        return self._items[0]

    def first(self):
        return self._items[0] if self._items else None

    def one_or_none(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items

    def unique(self):
        return self

    def __iter__(self):
        return iter(self._items)


# ---------------------------------------------------------------------------
# Helper to apply SQLAlchemy column defaults (simulating DB behavior)
# ---------------------------------------------------------------------------

def _apply_column_defaults(obj):
    """Apply SQLAlchemy column defaults to a model instance."""
    if getattr(obj, 'id', None) is None:
        obj.id = str(uuid.uuid4())
    if getattr(obj, 'created_at', None) is None:
        obj.created_at = datetime.now(UTC)
    if getattr(obj, 'updated_at', None) is None:
        obj.updated_at = datetime.now(UTC)
    try:
        from sqlalchemy import inspect as sa_inspect
        mapper = sa_inspect(type(obj))
        for attr in mapper.column_attrs:
            col = attr.columns[0]
            val = getattr(obj, attr.key, None)
            if val is None and col.default is not None:
                default = col.default
                if default.is_scalar:
                    setattr(obj, attr.key, default.arg)
                elif default.is_callable:
                    try:
                        setattr(obj, attr.key, default.arg(None))
                    except TypeError:
                        try:
                            setattr(obj, attr.key, default.arg())
                        except Exception:
                            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Query-count test helper (pbq-0)
# ---------------------------------------------------------------------------


@dataclass
class QueryCounter:
    """Tallies DB-interaction calls observed on a `MockDatabase` inside a
    `count_queries()` block.

    Because the API test suite mocks the session, these counts measure
    invocations of mock methods rather than real SQL round-trips — good
    enough for regressioning N+1 patterns whose extra hits show up as
    explicit `db.query(...)` / `db.execute(...)` repetitions inside a
    handler (e.g. `_readable_book_ids` called per meal). Relationship-
    attribute lazy loads do NOT surface here; pair the count with a
    `selectinload` spy when the fix is an eager-load.

    `query_args` captures the positional args passed to every
    `db.query(...)` call during the block, so tests can assert how many
    times a particular model was queried (e.g. `RecipeBookUser`).
    """

    select: int = 0
    insert: int = 0
    update: int = 0
    delete: int = 0
    query_args: list[tuple[Any, ...]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.select + self.insert + self.update + self.delete

    def query_count_for(self, model) -> int:
        """Number of `db.query(...)` calls whose first arg is `model`.

        Matches either the model class itself or a column attribute of
        it (`RecipeBookUser.recipe_book_id` maps to `RecipeBookUser`).
        """
        target = getattr(model, "__name__", None) or repr(model)
        count = 0
        for args in self.query_args:
            if not args:
                continue
            first = args[0]
            first_name = getattr(first, "__name__", None)
            if first_name == target:
                count += 1
                continue
            owner = getattr(first, "class_", None) or getattr(first, "parent", None)
            owner_name = getattr(owner, "__name__", None)
            if owner_name == target:
                count += 1
        return count


def _classify_sql(statement: str) -> str:
    """Map a SQL statement's leading keyword to a counter category.

    Used by `count_queries`'s `before_cursor_execute` listener path
    (aam-4). `WITH` falls into `select` because every CTE we issue ends
    in a SELECT; explicit RETURNING on INSERT/UPDATE/DELETE is still
    classified by the leading verb. Unknown verbs fall through to
    `select` rather than dropping silently — the worst outcome is a
    lightly-inflated select count, never a missed regression.
    """
    if not statement:
        return "select"
    head = statement.lstrip().split(None, 1)[0].lower()
    if head in ("insert",):
        return "insert"
    if head in ("update",):
        return "update"
    if head in ("delete",):
        return "delete"
    return "select"


def _attach_engine_listeners(counter: "QueryCounter"):
    """Register `before_cursor_execute` on the sync + async engines.

    Returns a cleanup callable that removes every listener on exit. Both
    engines are optional — when `DATABASE_URL` (or `ASYNC_DATABASE_URL`)
    is unset the matching engine is `None` and we just skip it. The
    async engine's underlying sync engine (`engine.sync_engine`) is the
    one that fires DB-API events, so we attach there.
    """
    from sqlalchemy import event

    try:
        from utils.services.database import async_db_engine, db_engine
    except Exception:  # pragma: no cover  (import failure ≠ test scope)
        return lambda: None

    listeners = []

    def _make_listener():
        def _on_execute(conn, cursor, statement, params, context, executemany):
            cat = _classify_sql(statement)
            setattr(counter, cat, getattr(counter, cat) + 1)
        return _on_execute

    if db_engine is not None:
        lst = _make_listener()
        event.listen(db_engine, "before_cursor_execute", lst)
        listeners.append((db_engine, lst))

    if async_db_engine is not None:
        lst = _make_listener()
        event.listen(async_db_engine.sync_engine, "before_cursor_execute", lst)
        listeners.append((async_db_engine.sync_engine, lst))

    def _cleanup():
        for target, lst in listeners:
            event.remove(target, "before_cursor_execute", lst)

    return _cleanup


@contextmanager
def count_queries(
    mock_db: "MockDatabase | None" = None,
) -> Iterator[QueryCounter]:
    """Measure DB-interaction calls within the block.

    Two pathways feed the same `QueryCounter`, so the same helper is
    usable from sync mock-based tests AND async real-engine tests
    (aam-4). The QueryCounter public surface (`.total/.select/.insert/
    .update/.delete/.query_args`) is unchanged — every existing `pbq-*`
    assertion keeps running as-is.

    1. **Mock-db wrap (legacy path).** When `mock_db` is a
       `MockDatabase`, increments come from the mock layer's
       `db.query`, `db.execute`, `db.add`, `db.delete` call_counts plus
       the high-level helpers (`find_by`, `where`, `create`, etc.).

    2. **Engine event listener (new path).** A `before_cursor_execute`
       listener attaches to whichever real engines exist (sync
       `db_engine` and async `async_db_engine`) and classifies the
       statement into select/insert/update/delete. This is what
       async-handler tests against a real test DB use.

    Both pathways always run inside the block; in mock-only tests the
    engines are `None` (DATABASE_URL is empty in the API test env), so
    the listener path no-ops. In real-engine tests `mock_db` is `None`
    and only the listener fires. Hybrid tests (rare) get an additive
    count.

    Typical usage (sync mock)::

        with count_queries(mock_db) as qc:
            response = client.get("/v1/meals?scope=home")
        assert qc.select <= 3
        assert qc.query_count_for(RecipeBookUser) == 1

    Typical usage (real-engine async)::

        async with count_queries() as qc, AsyncClient(...) as ac:
            await ac.get("/v1/meals/..."): ...

        assert qc.select <= 3
    """
    counter = QueryCounter()

    legacy_cleanup = None
    helper = None
    before_query = before_execute = before_add = before_sess_delete = 0

    if mock_db is not None:
        before_query = mock_db.db.query.call_count
        before_execute = mock_db.db.execute.call_count
        before_add = mock_db.db.add.call_count
        before_sess_delete = mock_db.db.delete.call_count

        # Intentionally NOT wrapping `save` — `MockDatabase.save` delegates
        # to `self.create`, which is already instrumented. Wrapping both
        # would double-count an insert whenever a test calls `save()`.
        orig_find_by = mock_db.find_by
        orig_where = mock_db.where
        orig_create = mock_db.create
        orig_create_all = mock_db.create_all
        orig_update = mock_db.update
        orig_delete = mock_db.delete

        helper = {
            "find_by": 0,
            "where": 0,
            "create": 0,
            "create_all": 0,
            "update": 0,
            "delete": 0,
        }

        def _wrap(name, orig):
            def wrapped(*args, **kwargs):
                helper[name] += 1
                return orig(*args, **kwargs)
            return wrapped

        mock_db.find_by = _wrap("find_by", orig_find_by)
        mock_db.where = _wrap("where", orig_where)
        mock_db.create = _wrap("create", orig_create)
        mock_db.create_all = _wrap("create_all", orig_create_all)
        mock_db.update = _wrap("update", orig_update)
        mock_db.delete = _wrap("delete", orig_delete)

        def _restore_mock():
            mock_db.find_by = orig_find_by
            mock_db.where = orig_where
            mock_db.create = orig_create
            mock_db.create_all = orig_create_all
            mock_db.update = orig_update
            mock_db.delete = orig_delete

        legacy_cleanup = _restore_mock

    detach_engine_listeners = _attach_engine_listeners(counter)

    try:
        yield counter
    finally:
        if mock_db is not None and helper is not None:
            counter.select += (
                (mock_db.db.query.call_count - before_query)
                + (mock_db.db.execute.call_count - before_execute)
                + helper["find_by"]
                + helper["where"]
            )
            counter.insert += (
                (mock_db.db.add.call_count - before_add)
                + helper["create"]
                + helper["create_all"]
            )
            counter.update += helper["update"]
            counter.delete += (
                (mock_db.db.delete.call_count - before_sess_delete)
                + helper["delete"]
            )
            counter.query_args = [
                tuple(call.args)
                for call in mock_db.db.query.call_args_list[before_query:]
            ]

        if legacy_cleanup is not None:
            legacy_cleanup()
        detach_engine_listeners()


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
        self.db.refresh = MagicMock(side_effect=_apply_column_defaults)
        self.db.add = MagicMock()
        self.db.delete = MagicMock()

    def find_by(self, model_class, **kwargs):
        """Mock find_by - returns configured result or None.

        Special case: CalendarUser defaults to an owner membership for
        the queried (user_id, calendar_id) when no explicit mapping is
        set. Post-cal-found-2 most tests that exercise meal_event /
        recurrence_rule handlers depend on calendar membership — having
        the default be "allowed" keeps the patch surface tiny. Tests
        that need access denied override via
        `set_find_by(CalendarUser, None, user_id=..., calendar_id=...)`.
        """
        key = (model_class.__name__, tuple(sorted(kwargs.items())))
        if key in self._find_by_results:
            return self._find_by_results[key]
        # Also check by model name alone for simpler configs
        simple_key = model_class.__name__
        if simple_key in self._find_by_results:
            return self._find_by_results[simple_key]
        if model_class.__name__ == "CalendarUser":
            user_id = kwargs.get("user_id")
            calendar_id = kwargs.get("calendar_id")
            if user_id is not None and calendar_id is not None:
                return MockCalendarUser(
                    user_id=user_id, calendar_id=calendar_id, role="owner"
                )
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
        """Mock create - applies column defaults like a real DB would."""
        _apply_column_defaults(model)
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
def client(mock_db, mock_async_db, mock_user):
    """Create a TestClient with mocked dependencies.

    aam-10: also overrides async deps (`get_async_database` +
    `get_current_user_async`) so sync-style tests can exercise async
    routers without rewriting. Tests whose handler code hits async DB
    paths need to pre-configure `mock_async_db` (not `mock_db`).
    """
    from main import app
    from dependencies import (
        get_async_database,
        get_current_user,
        get_current_user_async,
        get_database,
    )

    def override_get_database():
        return mock_db

    async def override_get_async_database():
        yield mock_async_db

    def override_get_current_user():
        return mock_user

    async def override_get_current_user_async():
        return mock_user

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[get_async_database] = override_get_async_database
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_user_async] = (
        override_get_current_user_async
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_db, mock_async_db):
    """Create a TestClient with only the database deps mocked (no auth override).

    aam-10: also overrides `get_async_database` so unauth'd async handlers
    (e.g. `GET /v1/meals/public/{token}`) get the `MockAsyncDatabase`
    instead of trying to instantiate the real `AsyncDatabase` (which
    would crash because `DATABASE_URL` is empty in the API test env).
    """
    from main import app
    from dependencies import get_async_database, get_database

    def override_get_database():
        return mock_db

    async def override_get_async_database():
        yield mock_async_db

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[get_async_database] = override_get_async_database

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Async fixtures (aam-4)
# ---------------------------------------------------------------------------


class MockAsyncDatabase:
    """Async mirror of `MockDatabase`.

    Phase 3 stories convert handlers from `Endpoint` to `AsyncEndpoint`
    and switch the dep from `get_database` → `get_async_database`. Tests
    for those handlers override the async dep to return an instance of
    this class. Behavior parity with `MockDatabase` so per-domain test
    conversion is mostly s/`def`/`async def`/ + s/`mock_db`/`mock_async_db`/.

    The session double exposes async write methods (`commit`, `flush`,
    `refresh`, `delete`, `add`, `add_all`) so handlers can `await
    self.db.db.commit()` without crashing. Read paths return the same
    `MockExecuteResult` the sync mock does — the API of `result.scalars()`
    / `.all()` / `.scalar_one_or_none()` works the same on sync and async
    sessions, so handler code that's been converted to `await
    self.db.db.execute(stmt)` reads the result identically.
    """

    def __init__(self):
        from unittest.mock import AsyncMock

        self.db = MagicMock()
        self._find_by_results = {}
        self._where_results = {}

        self.db.execute = AsyncMock(return_value=MockExecuteResult())
        self.db.commit = AsyncMock()
        self.db.flush = AsyncMock()
        self.db.refresh = AsyncMock(side_effect=_apply_column_defaults)
        self.db.add = MagicMock()
        self.db.add_all = MagicMock()
        self.db.delete = AsyncMock()
        self.db.close = AsyncMock()

    async def find_by(self, model_class, **kwargs):
        """Async mirror of MockDatabase.find_by — same lookup semantics."""
        key = (model_class.__name__, tuple(sorted(kwargs.items())))
        if key in self._find_by_results:
            return self._find_by_results[key]
        simple_key = model_class.__name__
        if simple_key in self._find_by_results:
            return self._find_by_results[simple_key]
        if model_class.__name__ == "CalendarUser":
            user_id = kwargs.get("user_id")
            calendar_id = kwargs.get("calendar_id")
            if user_id is not None and calendar_id is not None:
                return MockCalendarUser(
                    user_id=user_id, calendar_id=calendar_id, role="owner"
                )
        return None

    def set_find_by(self, model_class, result, **kwargs):
        if kwargs:
            key = (model_class.__name__, tuple(sorted(kwargs.items())))
        else:
            key = model_class.__name__
        self._find_by_results[key] = result

    async def find_or_create_by(self, model_class, defaults=None, **kwargs):
        result = await self.find_by(model_class, **kwargs)
        if result:
            return result
        all_attrs = {**(defaults or {}), **kwargs}
        return (
            model_class(**all_attrs)
            if hasattr(model_class, "__call__")
            else MockModel(**all_attrs)
        )

    def where(self, model, **kwargs):
        """Sync builder (chainable) — terminals are `await`able.

        Mirrors `AsyncDatabase.where` (returns an `AsyncQuery`-like
        object). The terminal coroutines preserve the same return-types
        the sync `MockQuery` exposes so handler code asserting on
        `.first()` / `.all()` / `.count()` works without rewrites.

        Falls back to `_find_by_results` when no explicit `set_where`
        registration exists: lets tests mock a single entity with
        `set_find_by(Model, obj, id=...)` and have both
        `find_by(Model, id=...)` and
        `where(Model, id=...).options(...).first()` return it. The
        real `AsyncDatabase.find_by` is a thin wrapper over
        `where().first()`, so this fallback keeps parity with
        production semantics.
        """
        key = model.__name__
        items = self._where_results.get(key)
        if items is None and kwargs:
            key_with_args = (key, tuple(sorted(kwargs.items())))
            fallback = self._find_by_results.get(key_with_args)
            if fallback is None:
                fallback = self._find_by_results.get(key)
            if fallback is not None:
                items = [fallback]
        if items is None:
            items = []
        return _MockAsyncQuery(items)

    def set_where(self, model_class, items):
        self._where_results[model_class.__name__] = items

    async def create(self, model):
        _apply_column_defaults(model)
        return model

    async def create_all(self, models):
        for m in models:
            await self.create(m)
        return models

    async def update(self, model, **kwargs):
        for key, value in kwargs.items():
            setattr(model, key, value)
        model.updated_at = datetime.now(UTC)
        return model

    async def update_all(self, models, **kwargs):
        for model in models:
            await self.update(model, **kwargs)
        return models

    async def delete(self, model):
        return model

    async def save(self, model):
        return await self.create(model)

    async def save_all(self, models):
        for m in models:
            await self.create(m)
        return models

    async def bulk_update(self, model_class, filters, **kwargs):
        return None

    async def find_and_bulk_update(
        self, model_class, updates, include_archived=False, **filters
    ):
        return None

    async def delete_by(self, model_class, filters):
        return None

    async def close(self):
        pass

    def lock(self, key):
        """Returns a no-op async context manager."""

        class _NoopLock:
            async def __aenter__(self_inner):
                return True

            async def __aexit__(self_inner, *a):
                return None

        return _NoopLock()


class _MockAsyncQuery:
    """Async-terminal mirror of `MockQuery` returned by MockAsyncDatabase.where."""

    def __init__(self, items=None):
        self._items = items or []

    def filter(self, *a, **k):
        return self

    def filter_by(self, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        return self

    def offset(self, n):
        return self

    def options(self, *a, **k):
        return self

    async def all(self):
        return self._items

    async def first(self):
        return self._items[0] if self._items else None

    async def one_or_none(self):
        return self._items[0] if self._items else None

    async def one(self):
        if not self._items:
            from sqlalchemy.exc import NoResultFound

            raise NoResultFound
        return self._items[0]

    async def count(self):
        return len(self._items)


@pytest.fixture
def mock_async_db():
    """Create a fresh MockAsyncDatabase for each test."""
    return MockAsyncDatabase()


@pytest.fixture
async def async_client(mock_db, mock_async_db, mock_user):
    """Create an httpx.AsyncClient backed by ASGITransport on the API app.

    Mirrors the sync `client` fixture: overrides the async DB dep with
    `MockAsyncDatabase` and the auth dep with the same `mock_user`.
    Also overrides the SYNC `get_database` with a sync `MockDatabase`
    so a request that lands on a not-yet-converted handler during the
    dual-dispatch window doesn't try to instantiate the real
    `Database()` (which would crash because `DATABASE_URL` is empty in
    the API test env).

    The fixture is `async def` and yields an `httpx.AsyncClient`, so
    usage is::

        async def test_something(async_client):
            response = await async_client.get("/v1/health")
    """
    from httpx import ASGITransport, AsyncClient

    from dependencies import (
        get_async_database,
        get_current_user,
        get_current_user_async,
        get_database,
    )
    from main import app

    def _override_get_database():
        return mock_db  # sync MockDatabase for any sync handler still present

    async def _override_get_async_database():
        yield mock_async_db

    def _override_get_current_user():
        return mock_user

    async def _override_get_current_user_async():
        return mock_user

    app.dependency_overrides[get_database] = _override_get_database
    app.dependency_overrides[get_async_database] = _override_get_async_database
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_current_user_async] = (
        _override_get_current_user_async
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
