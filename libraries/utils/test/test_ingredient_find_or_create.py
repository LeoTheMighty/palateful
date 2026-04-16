"""Tests for ingredient find-or-create behavior in import tasks.

Verifies that match_ingredients_task (Tier 4) and create_recipe_task (safety net)
use database.find_or_create_by instead of raw create, preventing unique constraint
violations on concurrent imports.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_item(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        import_job_id=uuid.uuid4(),
        status="pending",
        last_successful_stage=None,
        parsed_recipe=None,
        user_edits=None,
        created_recipe_id=None,
        raw_data={"text": "some text"},
        source_type="photo",
        source_url=None,
        ai_cost_cents=0,
        error_message=None,
        error_code=None,
        retry_count=0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_database(item, job=None):
    database = MagicMock()

    def find_by(model, **_kwargs):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ
        if model is _II:
            return item
        if model is _IJ:
            return job or SimpleNamespace(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                total_items=1,
                processed_items=0,
                failed_items=0,
                succeeded_items=0,
                pending_review_items=0,
                status="processing",
                total_ai_cost_cents=0,
            )
        return None

    database.find_by.side_effect = find_by
    database.db = MagicMock()
    database.db.query.return_value.filter.return_value.first.return_value = None
    database.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        ("matching", 1)
    ]
    database.db.execute.return_value.first.return_value = None
    database.db.commit = MagicMock()

    created_ingredient = SimpleNamespace(
        id=uuid.uuid4(),
        canonical_name="test ingredient",
        is_canonical=False,
        pending_review=True,
    )
    database.find_or_create_by.return_value = created_ingredient
    database.create.return_value = created_ingredient

    return database, created_ingredient


# ------------------------------------------------------------------
# match_ingredients_task: Tier 4 uses find_or_create_by
# ------------------------------------------------------------------


def test_match_task_tier4_uses_find_or_create_by():
    """Tier 4 (no match) must call find_or_create_by, not raw create."""
    from utils.models.ingredient import Ingredient
    from utils.tasks.import_tasks.match_ingredients_task import MatchIngredientsTask

    task = MatchIngredientsTask()
    item = _make_item(
        parsed_recipe={
            "ingredients": [{"text": "salt"}],
            "name": "Simple Recipe",
        }
    )
    database, created_ingredient = _make_database(item)
    task.database = database
    task.user_id = uuid.uuid4()

    task._check_cached_match = MagicMock(return_value=None)
    task._exact_match = MagicMock(return_value=None)
    task._fuzzy_match = MagicMock(return_value=None)
    task._cache_match = MagicMock()
    task._dispatch_create_task = MagicMock()

    with patch("utils.services.activity_service.create_activity"):
        task.execute(str(item.id))

    database.find_or_create_by.assert_called_once()
    call_args = database.find_or_create_by.call_args
    assert call_args[0][0] is Ingredient
    assert call_args[1]["canonical_name"] == "salt"
    assert call_args[1]["defaults"]["is_canonical"] is False
    assert call_args[1]["defaults"]["pending_review"] is True
    assert call_args[1]["defaults"]["submitted_by_id"] == task.user_id

    database.create.assert_not_called()


def test_match_task_tier4_returns_correct_ingredient_id():
    """Tier 4 must use the ingredient returned by find_or_create_by."""
    from utils.tasks.import_tasks.match_ingredients_task import MatchIngredientsTask

    task = MatchIngredientsTask()
    item = _make_item(
        parsed_recipe={
            "ingredients": [{"text": "pepper"}],
            "name": "Pepper Recipe",
        }
    )
    database, created_ingredient = _make_database(item)
    task.database = database
    task.user_id = uuid.uuid4()

    task._check_cached_match = MagicMock(return_value=None)
    task._exact_match = MagicMock(return_value=None)
    task._fuzzy_match = MagicMock(return_value=None)
    task._cache_match = MagicMock()
    task._dispatch_create_task = MagicMock()

    with patch("utils.services.activity_service.create_activity"):
        task.execute(str(item.id))

    cache_call = task._cache_match.call_args
    assert cache_call[0][1] == str(created_ingredient.id)

    matched_id = item.parsed_recipe["ingredients"][0]["matched_ingredient_id"]
    assert matched_id == str(created_ingredient.id)


def test_match_task_tier4_concurrent_returns_existing():
    """When find_or_create_by returns an existing ingredient (concurrent create),
    the task uses it without error."""
    from utils.tasks.import_tasks.match_ingredients_task import MatchIngredientsTask

    task = MatchIngredientsTask()
    existing_ingredient = SimpleNamespace(
        id=uuid.uuid4(),
        canonical_name="salt",
        is_canonical=True,
        pending_review=False,
    )

    item = _make_item(
        parsed_recipe={
            "ingredients": [{"text": "salt"}],
            "name": "Salt Recipe",
        }
    )
    database, _ = _make_database(item)
    database.find_or_create_by.return_value = existing_ingredient
    task.database = database
    task.user_id = uuid.uuid4()

    task._check_cached_match = MagicMock(return_value=None)
    task._exact_match = MagicMock(return_value=None)
    task._fuzzy_match = MagicMock(return_value=None)
    task._cache_match = MagicMock()
    task._dispatch_create_task = MagicMock()

    with patch("utils.services.activity_service.create_activity"):
        result = task.execute(str(item.id))

    assert result["data"]["status"] == "approved"
    matched_id = item.parsed_recipe["ingredients"][0]["matched_ingredient_id"]
    assert matched_id == str(existing_ingredient.id)


# ------------------------------------------------------------------
# create_recipe_task: safety net uses find_or_create_by
# ------------------------------------------------------------------


def test_create_recipe_task_safety_net_uses_find_or_create_by():
    """Safety-net path (no matched_ingredient_id) must call find_or_create_by."""
    from utils.models.ingredient import Ingredient
    from utils.tasks.import_tasks.create_recipe_task import CreateRecipeTask

    task = CreateRecipeTask()

    job = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        recipe_book_id=uuid.uuid4(),
        total_items=1,
        processed_items=0,
        failed_items=0,
        succeeded_items=0,
        pending_review_items=0,
        status="processing",
    )

    item = _make_item(
        status="approved",
        import_job_id=job.id,
        parsed_recipe={
            "name": "Test Recipe",
            "ingredients": [{"text": "Flour", "quantity": 2, "unit": "cups"}],
            "steps": [{"order": 1, "instruction": "Mix"}],
        },
    )

    database = MagicMock()

    created_ingredient = SimpleNamespace(id=uuid.uuid4())
    database.find_or_create_by.return_value = created_ingredient

    created_recipe = SimpleNamespace(id=uuid.uuid4())
    database.create.return_value = created_recipe
    database.db = MagicMock()
    database.db.refresh = MagicMock()

    def find_by(model, **kwargs):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ
        if model is _II:
            return item
        if model is _IJ:
            return job
        return None

    database.find_by.side_effect = find_by
    database.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        ("completed", 1)
    ]

    task.database = database
    task.user_id = uuid.uuid4()

    with patch("utils.services.activity_service.create_activity"):
        task.execute(str(item.id))

    database.find_or_create_by.assert_called_once()
    call_args = database.find_or_create_by.call_args
    assert call_args[0][0] is Ingredient
    assert call_args[1]["canonical_name"] == "flour"
    assert call_args[1]["defaults"]["is_canonical"] is False
    assert call_args[1]["defaults"]["pending_review"] is True


def test_create_recipe_task_safety_net_normalizes_name():
    """Safety-net path must lowercase + strip the ingredient name."""
    from utils.tasks.import_tasks.create_recipe_task import CreateRecipeTask

    task = CreateRecipeTask()

    job = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        recipe_book_id=uuid.uuid4(),
        total_items=1,
        processed_items=0,
        failed_items=0,
        succeeded_items=0,
        pending_review_items=0,
        status="processing",
    )

    item = _make_item(
        status="approved",
        import_job_id=job.id,
        parsed_recipe={
            "name": "Test Recipe",
            "ingredients": [{"text": "  Brown Sugar  ", "quantity": 1, "unit": "cup"}],
            "steps": [{"order": 1, "instruction": "Mix"}],
        },
    )

    database = MagicMock()
    created_ingredient = SimpleNamespace(id=uuid.uuid4())
    database.find_or_create_by.return_value = created_ingredient

    created_recipe = SimpleNamespace(id=uuid.uuid4())
    database.create.return_value = created_recipe
    database.db = MagicMock()
    database.db.refresh = MagicMock()

    def find_by(model, **kwargs):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ
        if model is _II:
            return item
        if model is _IJ:
            return job
        return None

    database.find_by.side_effect = find_by
    database.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        ("completed", 1)
    ]

    task.database = database
    task.user_id = uuid.uuid4()

    with patch("utils.services.activity_service.create_activity"):
        task.execute(str(item.id))

    call_args = database.find_or_create_by.call_args
    assert call_args[1]["canonical_name"] == "brown sugar"
