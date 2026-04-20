"""Round-trip riip-2 verification: every live write path normalizes units.

These tests exercise the *normalization seam* in each write path — the
single point where a freeform unit string crosses into a persisted
column. We use a stub `normalize_unit_display` so tests are deterministic
without a real DB; the assertions verify that:

  1. Each path *calls* `normalize_unit_display` for every unit it
     persists.
  2. Snapshot writes do NOT call it (history preserved).
  3. The persisted token is the canonical one returned by the
     normalizer, not the raw input.

Live paths covered:
  - extract_recipe_task._serialize_recipe (parsed_recipe → JSONB)
  - extract_recipe_task._parse_raw_ingredients (spreadsheet path)
  - create_recipe_task._create_recipe_ingredient (RecipeIngredient row)

API-side write paths (create_recipe / update_recipe / restore_recipe_version
/ fork_recipe / update_import_item) live in `services/api/tests/`; the
integration there is exercised by the existing endpoint test suites.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.tasks.import_tasks import extract_recipe_task as ext_mod


def _stub_normalizer(monkeypatch, module, *, mapping=None) -> list[tuple]:
    """Replace `module.normalize_unit_display` with a recording stub.

    Returns the call log so the test can assert on raw inputs the path
    fed to the normalizer.
    """
    calls: list[tuple] = []
    mapping = mapping or {"tablespoon": "tbsp", "grams": "g"}

    def stub(raw, _session, context=None):
        calls.append((raw, context))
        if raw is None:
            return None
        return mapping.get(raw, raw)

    monkeypatch.setattr(module, "normalize_unit_display", stub)
    return calls


# ---------------------------------------------------------------------------
# extract_recipe_task._serialize_recipe — parsed_recipe JSONB write
# ---------------------------------------------------------------------------


def test_serialize_recipe_normalizes_each_ingredient_unit(monkeypatch):
    calls = _stub_normalizer(monkeypatch, ext_mod)

    fake_recipe = SimpleNamespace(
        name="X",
        description=None,
        ingredients=[
            SimpleNamespace(
                text="2 tablespoons butter",
                quantity=2,
                unit="tablespoon",
                name="butter",
                notes=None,
                is_optional=False,
            ),
            SimpleNamespace(
                text="100 grams flour",
                quantity=100,
                unit="grams",
                name="flour",
                notes=None,
                is_optional=False,
            ),
        ],
        steps=None,
        instructions=None,
        servings=2,
        prep_time_minutes=None,
        cook_time_minutes=None,
        total_time_minutes=None,
        image_url=None,
        source_url=None,
        author=None,
        cuisine=None,
        category=None,
        keywords=None,
        primary_vibe=None,
        secondary_vibe=None,
    )

    out = ext_mod._serialize_recipe(fake_recipe, "ai", session=MagicMock())  # noqa: SLF001

    assert out["ingredients"][0]["unit"] == "tbsp"
    assert out["ingredients"][1]["unit"] == "g"
    # Both raw inputs flowed through the normalizer.
    raws = [c[0] for c in calls]
    assert "tablespoon" in raws
    assert "grams" in raws
    # Context names the call site so audit grep can target it.
    contexts = [c[1] for c in calls if c[1]]
    assert all(c.get("path") == "extract_recipe_task" for c in contexts)


# ---------------------------------------------------------------------------
# extract_recipe_task._parse_raw_ingredients — spreadsheet path
# ---------------------------------------------------------------------------


def test_parse_raw_ingredients_normalizes_unit_per_row(monkeypatch):
    calls = _stub_normalizer(monkeypatch, ext_mod)

    fake_database = SimpleNamespace(db=MagicMock())
    task = ext_mod.ExtractRecipeTask()
    task.database = fake_database
    task.user_id = None

    raw = [
        {"text": "2 tablespoons butter", "quantity": 2, "unit": "tablespoon", "name": "butter"},
        {"text": "100 grams flour", "quantity": 100, "unit": "grams", "name": "flour"},
        # String entries take the legacy path — no unit field, no normalize call for them.
        "1 cup sugar",
    ]
    out = task._parse_raw_ingredients(raw)  # noqa: SLF001
    units = [item.get("unit") for item in out if "unit" in item]
    assert "tbsp" in units
    assert "g" in units
    raws = [c[0] for c in calls]
    assert "tablespoon" in raws
    assert "grams" in raws


# ---------------------------------------------------------------------------
# create_recipe_task._create_recipe_ingredient — RecipeIngredient row
# ---------------------------------------------------------------------------


def test_create_recipe_task_normalizes_unit_display(monkeypatch):
    """Units coming through ing_data get coerced before persist."""
    from utils.tasks.import_tasks import create_recipe_task as cr_mod

    calls = _stub_normalizer(monkeypatch, cr_mod)

    # Stub the Ingredient constructor so the test doesn't need a real DB
    # session. Post-epic-ingredients-string-simplification the task
    # instantiates a fresh Ingredient row per name and flushes it.
    def _fake_ingredient(**kwargs):
        inst = SimpleNamespace(id="ing-id-1", **kwargs)
        return inst

    monkeypatch.setattr(cr_mod, "Ingredient", _fake_ingredient)

    captured: list = []

    class _FakeDatabase:
        db = MagicMock()

        def find_by(self, *_args, **_kwargs):
            return None

        def create(self, model):
            captured.append(model)
            return model

    task = cr_mod.CreateRecipeTask()
    task.database = _FakeDatabase()
    task.user_id = None

    fake_recipe = SimpleNamespace(id="recipe-id-1")
    ing_data = {
        "quantity": 2,
        "unit": "tablespoon",
        "notes": None,
        "is_optional": False,
        "name": "butter",
    }
    task._create_recipe_ingredient(fake_recipe, ing_data, 0)  # noqa: SLF001

    assert captured, "expected one RecipeIngredient persisted"
    persisted = captured[-1]
    assert persisted.unit_display == "tbsp"
    assert ("tablespoon", {"path": "create_recipe_task"}) in calls


# ---------------------------------------------------------------------------
# Cross-path parametrization — single happy-path table verifies coercion.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_unit, expected_unit",
    [
        ("tablespoon", "tbsp"),
        ("grams", "g"),
        ("tbsp", "tbsp"),  # already canonical
        ("", ""),  # empty preserved
        (None, None),  # None preserved
    ],
)
def test_serialize_recipe_unit_table(monkeypatch, raw_unit, expected_unit):
    """Single happy-path matrix for the serializer normalization."""
    _stub_normalizer(monkeypatch, ext_mod)

    fake_recipe = SimpleNamespace(
        name="X",
        description=None,
        ingredients=[
            SimpleNamespace(
                text="x",
                quantity=1,
                unit=raw_unit,
                name="butter",
                notes=None,
                is_optional=False,
            ),
        ],
        steps=None,
        instructions=None,
        servings=1,
        prep_time_minutes=None,
        cook_time_minutes=None,
        total_time_minutes=None,
        image_url=None,
        source_url=None,
        author=None,
        cuisine=None,
        category=None,
        keywords=None,
        primary_vibe=None,
        secondary_vibe=None,
    )
    out = ext_mod._serialize_recipe(fake_recipe, "ai", session=MagicMock())  # noqa: SLF001
    assert out["ingredients"][0]["unit"] == expected_unit


# ---------------------------------------------------------------------------
# Snapshot rule — _create_version_snapshot is API-side; we don't test here,
# but assert the documented invariant holds at the source level.
# ---------------------------------------------------------------------------


def test_snapshot_path_does_not_import_normalize_unit_display():
    """Sanity check: update_recipe.py's snapshot helper reads `ri.unit_display`
    directly and never routes through normalize_unit_display. Done as a
    grep so renaming is loud."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / (
        "services/api/src/api/v1/recipe/update_recipe.py"
    )
    text = src.read_text()
    snapshot_block_start = text.index("def _create_version_snapshot")
    next_def = text.find("    def ", snapshot_block_start + 1)
    snapshot_block_end = next_def if next_def != -1 else len(text)
    snapshot_text = text[snapshot_block_start:snapshot_block_end]
    assert "normalize_unit_display" not in snapshot_text, (
        "Snapshots must preserve historical units verbatim — do not normalize."
    )
