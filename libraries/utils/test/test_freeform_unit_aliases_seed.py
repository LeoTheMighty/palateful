"""eri-4b: pin the 15 plural→singular aliases + the piece/pieces reconciliation.

Matches the shape used for the freeform units seed test (eri-4a) — this
is a static-file test that does not touch the DB.
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
    "20260422030000_seed_freeform_unit_aliases.py"
)


def _load():
    spec = importlib.util.spec_from_file_location(
        "seed_freeform_unit_aliases", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alias_seed_has_sixteen_rows():
    """15 plural→singular + `packs→packet` (the one non-plural extra)."""
    module = _load()
    assert len(module._FREEFORM_ALIASES) == 16


def test_every_alias_target_is_a_seeded_freeform_canonical():
    """Every canonical target MUST be one of the eri-4a freeform
    rows — otherwise the FK on unit_aliases.canonical_unit is broken."""
    module = _load()
    targets = {canonical for _, canonical in module._FREEFORM_ALIASES}
    allowed = set(_FREEFORM_ALLOWED)
    missing = targets - allowed
    assert not missing, (
        f"eri-4b aliases reference canonical units not in eri-4a seed: {missing}"
    )


def test_plural_singular_pairs_are_lowercase_and_nontrivial():
    module = _load()
    for alias, canonical in module._FREEFORM_ALIASES:
        assert alias == alias.lower(), f"alias {alias!r} not lowercase"
        assert canonical == canonical.lower(), f"canonical {canonical!r} not lowercase"
        assert alias != canonical, f"degenerate alias {alias!r}={canonical!r}"


def test_stale_piece_aliases_get_dropped():
    module = _load()
    assert ("piece", "each") in module._STALE_ALIASES
    assert ("pieces", "each") in module._STALE_ALIASES


def test_pieces_points_to_piece_not_each():
    """The reconciled alias: pieces no longer normalizes to `each`."""
    module = _load()
    pieces_pairs = [
        (a, c) for a, c in module._FREEFORM_ALIASES if a == "pieces"
    ]
    assert pieces_pairs == [("pieces", "piece")]


def test_migration_revision_chains_from_eri_4a():
    module = _load()
    assert module.revision == "erifraliases01"
    assert module.down_revision == "erifrunits01"


def test_migration_uses_on_conflict_do_nothing_for_inserts():
    text = _MIGRATION_PATH.read_text()
    # Both the upgrade insert and the downgrade restore use the same
    # idempotency guard.
    matches = re.findall(r"ON CONFLICT\s*\(alias\)\s*DO NOTHING", text)
    assert len(matches) >= 2


def test_downgrade_restores_stale_aliases():
    """Rollback restores the piece/pieces→each pairs so pre-ERI state
    is recoverable."""
    text = _MIGRATION_PATH.read_text()
    assert "_STALE_ALIASES" in text
    downgrade_block = text.split("def downgrade()")[1]
    assert "INSERT INTO unit_aliases" in downgrade_block
    assert "_STALE_ALIASES" in downgrade_block


def test_packs_normalizes_to_packet():
    module = _load()
    pairs = dict(module._FREEFORM_ALIASES)
    assert pairs.get("packs") == "packet"


def test_all_15_singular_targets_have_at_least_one_alias():
    module = _load()
    targets = {canonical for _, canonical in module._FREEFORM_ALIASES}
    assert targets == set(_FREEFORM_ALLOWED), (
        f"Missing alias coverage for: {set(_FREEFORM_ALLOWED) - targets}"
    )
