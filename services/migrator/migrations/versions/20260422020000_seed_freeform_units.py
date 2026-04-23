"""Seed 15 freeform-canonical rows into the `units` table.

Revision ID: erifrunits01
Revises: schdrem001
Create Date: 2026-04-22

Story eri-4a (epic-extractor-richer-ingredients).

The riip-3 "19 canonical tokens" prompt list (CANONICAL_UNIT_TOKENS in
`libraries/utils/utils/services/recipe_extractors/unit_prompt.py`) is
the *prompt vocabulary* — what we hint to the LLM. This migration
grows the *data-model vocabulary* — the `units` table — by 15 freeform
canonical rows so `unit_aliases.canonical_unit` FK stays intact when
eri-4b adds plural→singular aliases (stalks→stalk, cans→can, …).

Matches the pattern established by `pinch`/`dash`/`clove`/`slice` in
`20260418040000_create_unit_aliases.py`: `type="other"`,
`to_base_factor=1`, self-referential `base_unit`.

Note: `piece` is both added here as a canonical row AND already listed
as an alias (piece→each) from riip-1. Once this migration runs,
`normalize_unit_display("piece")` returns `"piece"` (canonical lookup
wins before alias lookup). eri-4b refreshes the alias map accordingly
(drops the stale piece→each / pieces→each entries).

Idempotent via `INSERT … ON CONFLICT (name) DO NOTHING` — safe to
re-run on a partially-applied DB.

Down-migration removes the 15 seeded rows **only if** no
`unit_aliases.canonical_unit` row and no live `recipe_ingredients.unit_display`
still references them. If references remain, down-migration errors out
(operator intervention required) — we don't silently orphan FK deps.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "erifrunits01"
down_revision: str | None = "schdrem001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 15 freeform canonical units. Kept in sync with:
#   - `_FREEFORM_ALLOWED` in unit_prompt.py (prompt hint list)
#   - the plural→singular aliases seeded in eri-4b
#
# (name, abbreviation, type, to_base_factor, base_unit)
_FREEFORM_UNITS: tuple[tuple[str, str, str, str, str], ...] = (
    ("stalk", "stalk", "other", "1", "stalk"),
    ("bunch", "bunch", "other", "1", "bunch"),
    ("sprig", "sprig", "other", "1", "sprig"),
    ("head", "head", "other", "1", "head"),
    ("can", "can", "other", "1", "can"),
    ("packet", "packet", "other", "1", "packet"),
    ("stick", "stick", "other", "1", "stick"),
    ("sheet", "sheet", "other", "1", "sheet"),
    ("strip", "strip", "other", "1", "strip"),
    ("piece", "piece", "other", "1", "piece"),
    ("sachet", "sachet", "other", "1", "sachet"),
    ("jar", "jar", "other", "1", "jar"),
    ("bottle", "bottle", "other", "1", "bottle"),
    ("bar", "bar", "other", "1", "bar"),
    ("drop", "drop", "other", "1", "drop"),
)


def upgrade() -> None:
    bind = op.get_bind()
    insert_sql = sa.text(
        "INSERT INTO units (id, name, abbreviation, type, to_base_factor, base_unit) "
        "VALUES (gen_random_uuid(), :name, :abbreviation, :type, :to_base_factor, :base_unit) "
        "ON CONFLICT (name) DO NOTHING"
    )
    for name, abbr, utype, to_base, base_unit in _FREEFORM_UNITS:
        bind.execute(
            insert_sql,
            {
                "name": name,
                "abbreviation": abbr,
                "type": utype,
                "to_base_factor": to_base,
                "base_unit": base_unit,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    names = [row[0] for row in _FREEFORM_UNITS]

    # Abort the down-migration if any live alias still points at one of
    # the freeform rows — otherwise the FK on `unit_aliases.canonical_unit`
    # (`ondelete=RESTRICT`) would bite us mid-drop.
    alias_refs = (
        bind.execute(
            sa.text(
                "SELECT DISTINCT canonical_unit FROM unit_aliases "
                "WHERE canonical_unit = ANY(:names)"
            ),
            {"names": names},
        )
        .scalars()
        .all()
    )
    if alias_refs:
        raise RuntimeError(
            "seed_freeform_units downgrade blocked: unit_aliases still references "
            f"{sorted(set(alias_refs))}. Remove those alias rows first "
            "(e.g. by downgrading eri-4b) and re-run."
        )

    delete_sql = sa.text("DELETE FROM units WHERE name = ANY(:names)")
    bind.execute(delete_sql, {"names": names})
