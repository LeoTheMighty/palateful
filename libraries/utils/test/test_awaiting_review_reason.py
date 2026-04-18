"""Tests verifying each awaiting_review routing path stamps the right
`awaiting_review_reason` on import_items (irrd-1 AC7 + AC11).

The value drives the 1-word reason chip on collapsed yellow rows in the
Imports tab (irrd-6). It has to reflect the rule path that actually
flipped the item into awaiting_review so Leo can skip the caret
expansion on obviously-action items.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_item(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        import_job_id=uuid.uuid4(),
        status="matching",
        last_successful_stage="extracted",
        parsed_recipe=None,
        raw_data={},
        source_type="url",
        source_url=None,
        ai_cost_cents=0,
        error_message=None,
        error_code=None,
        retry_count=0,
        awaiting_review_reason=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_database(item):
    database = MagicMock()

    def find_by(model, **_kwargs):
        from utils.models.import_item import ImportItem as _II
        from utils.models.import_job import ImportJob as _IJ

        if model is _II:
            return item
        if model is _IJ:
            return SimpleNamespace(
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
    database.db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
        ("awaiting_review", 1)
    ]
    database.db.commit = MagicMock()
    return database


def _run_match(item, match_side_effect):
    from utils.tasks.import_tasks.match_ingredients_task import (
        MatchIngredientsTask,
    )

    task = MatchIngredientsTask()
    task.database = _make_database(item)
    task._match_ingredient = MagicMock(  # type: ignore[method-assign]
        side_effect=match_side_effect
    )
    task._dispatch_create_task = MagicMock()  # type: ignore[method-assign]

    with patch("utils.services.activity_service.create_activity"):
        task.execute(str(item.id))


def test_unmatched_ingredient_sets_unmatched_reason():
    """Any needs_review ingredient without a matched_ingredient_id routes
    to `unmatched_ingredients` — the strongest actionable signal."""
    item = _make_item(
        parsed_recipe={
            "name": "Cake",
            "ingredients": [
                {"text": "2 cups flour"},
                {"text": "totally made-up herb"},
            ],
        }
    )

    match_results = iter(
        [
            {
                "ingredient_id": str(uuid.uuid4()),
                "confidence": 1.0,
                "match_type": "exact",
                "needs_review": False,
            },
            {
                "ingredient_id": None,
                "confidence": 0.0,
                "match_type": "none",
                "needs_review": True,
            },
        ]
    )
    _run_match(item, lambda *_a, **_kw: next(match_results))

    assert item.status == "awaiting_review"
    assert item.awaiting_review_reason == "unmatched_ingredients"


def test_low_confidence_match_sets_low_confidence_reason():
    """Needs_review with an existing match but low confidence routes to
    `low_confidence`."""
    item = _make_item(
        parsed_recipe={
            "name": "Pie",
            "ingredients": [{"text": "sugar"}],
        }
    )
    _run_match(
        item,
        lambda *_a, **_kw: {
            "ingredient_id": str(uuid.uuid4()),
            "confidence": 0.6,
            "match_type": "fuzzy",
            "needs_review": True,
        },
    )

    assert item.status == "awaiting_review"
    assert item.awaiting_review_reason == "low_confidence"


def test_missing_title_beats_match_issues():
    """A missing recipe name routes to `missing_title` regardless of the
    match outcome — the recipe is literally unnamed and that's the first
    thing to fix."""
    item = _make_item(
        parsed_recipe={
            # No "name" / "title" key at all.
            "ingredients": [{"text": "flour"}],
        }
    )
    _run_match(
        item,
        lambda *_a, **_kw: {
            "ingredient_id": str(uuid.uuid4()),
            "confidence": 1.0,
            "match_type": "exact",
            "needs_review": False,
        },
    )

    assert item.status == "awaiting_review"
    assert item.awaiting_review_reason == "missing_title"


def test_missing_title_wins_over_unmatched():
    """Priority check: missing_title > unmatched_ingredients."""
    item = _make_item(
        parsed_recipe={
            "name": "   ",  # whitespace-only counts as missing
            "ingredients": [{"text": "mystery"}],
        }
    )
    _run_match(
        item,
        lambda *_a, **_kw: {
            "ingredient_id": None,
            "confidence": 0.0,
            "match_type": "none",
            "needs_review": True,
        },
    )

    assert item.awaiting_review_reason == "missing_title"


def test_happy_path_clears_reason():
    """All high-confidence matches → approved, reason must be None (not
    stale from a prior routing)."""
    item = _make_item(
        parsed_recipe={
            "name": "Bread",
            "ingredients": [{"text": "flour"}],
        },
        awaiting_review_reason="low_confidence",  # stale prior value
    )
    _run_match(
        item,
        lambda *_a, **_kw: {
            "ingredient_id": str(uuid.uuid4()),
            "confidence": 1.0,
            "match_type": "exact",
            "needs_review": False,
        },
    )

    assert item.status == "approved"
    assert item.awaiting_review_reason is None
