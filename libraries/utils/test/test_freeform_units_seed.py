"""eri-4a: pin the 15 freeform-canonical rows seeded into `units` against
the prompt vocabulary so they cannot drift.

The migration (``services/migrator/migrations/versions/
20260422020000_seed_freeform_units.py``) inserts 15 rows into the
``units`` table. Those rows MUST exactly match the ``_FREEFORM_ALLOWED``
tuple in ``unit_prompt.py`` — otherwise the LLM can emit a word we
don't have a canonical row for, and ``unit_aliases.canonical_unit``
FK coverage starts slipping.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from utils.services.recipe_extractors.unit_prompt import _FREEFORM_ALLOWED

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MIGRATION_PATH = (
    _REPO_ROOT
    / "services/migrator/migrations/versions/"
    "20260422020000_seed_freeform_units.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("seed_freeform_units", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_freeform_seed_names_match_prompt_allowlist():
    module = _load_migration_module()
    seeded_names = {entry[0] for entry in module._FREEFORM_UNITS}
    prompt_allowed = set(_FREEFORM_ALLOWED)
    assert seeded_names == prompt_allowed, (
        "Freeform units seed and prompt _FREEFORM_ALLOWED are out of sync. "
        f"only-in-seed={seeded_names - prompt_allowed}, "
        f"only-in-prompt={prompt_allowed - seeded_names}"
    )


def test_freeform_seed_has_exactly_fifteen_rows():
    module = _load_migration_module()
    assert len(module._FREEFORM_UNITS) == 15


def test_freeform_seed_type_and_factor_match_pinch_dash_pattern():
    """Matches the `pinch`/`dash`/`clove`/`slice` pattern in
    `20260418040000_create_unit_aliases.py`: `type="other"`, factor=1,
    base_unit=self.
    """
    module = _load_migration_module()
    for name, abbr, utype, to_base, base_unit in module._FREEFORM_UNITS:
        assert utype == "other", f"{name}: expected type='other', got {utype!r}"
        assert to_base == "1", f"{name}: expected to_base_factor='1', got {to_base!r}"
        assert base_unit == name, f"{name}: expected base_unit self-reference"
        # Abbreviation default = name for freeform count units.
        assert abbr == name


def test_freeform_seed_revision_chains_from_schdrem001():
    module = _load_migration_module()
    assert module.revision == "erifrunits01"
    assert module.down_revision == "schdrem001"


def test_migration_file_uses_on_conflict_do_nothing():
    """Idempotency guard — re-running on a partially-applied DB must
    be a no-op, not a constraint violation."""
    text = _MIGRATION_PATH.read_text()
    assert re.search(r"ON CONFLICT\s*\(name\)\s*DO NOTHING", text), (
        "seed_freeform_units must use ON CONFLICT DO NOTHING for idempotency"
    )
