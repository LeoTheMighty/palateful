"""Seed plural→singular aliases for the eri-4a freeform units.

Revision ID: erifraliases01
Revises: erifrunits01
Create Date: 2026-04-22

Story eri-4b (epic-extractor-richer-ingredients).

Chains after eri-4a: now that `stalk`, `bunch`, `can`, `head`, etc. are
canonical rows in `units`, the plural forms (`stalks`, `bunches`, …)
FK-safely point at them. Without these aliases, the softened prompt
rule (eri-1) could emit "stalks" and `normalize_unit_display` would
miss, write a UnitAliasMiss audit row, and the ingredient row would
persist `unit="stalks"` (lowercased/trimmed but not canonicalized).

Also reconciles the `piece`/`pieces` collision: riip-1 seeded
`piece→each` and `pieces→each`. Now that `piece` is canonical
(eri-4a), we drop those stale aliases and add `pieces→piece`. The
backend cache refreshes on process restart; the Flutter client picks
up the new aliases via its live fetch in `SessionAliasMap.init()` on
next cold-start (no app reinstall required).

Idempotent — INSERT uses `ON CONFLICT DO NOTHING`; DELETE is a no-op
when the stale rows are already gone.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "erifraliases01"
down_revision: str | None = "erifrunits01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 15 plural → singular aliases. Canonical targets must exist in `units`
# (seeded by eri-4a, revision `erifrunits01`).
_FREEFORM_ALIASES: tuple[tuple[str, str], ...] = (
    ("stalks", "stalk"),
    ("bunches", "bunch"),
    ("sprigs", "sprig"),
    ("heads", "head"),
    ("cans", "can"),
    ("packets", "packet"),
    ("packs", "packet"),
    ("sticks", "stick"),
    ("sheets", "sheet"),
    ("strips", "strip"),
    ("pieces", "piece"),
    ("sachets", "sachet"),
    ("jars", "jar"),
    ("bottles", "bottle"),
    ("bars", "bar"),
    ("drops", "drop"),
)


# Stale aliases from riip-1 now rendered obsolete because their
# canonical targets changed meaning:
#   piece / pieces used to map to `each`; they now map to `piece`
#   (canonical in its own right after eri-4a).
_STALE_ALIASES: tuple[tuple[str, str], ...] = (
    ("piece", "each"),
    ("pieces", "each"),
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Drop the riip-1 aliases whose canonical target is wrong now.
    #    Restricted to the exact (alias, canonical_unit) pair so we
    #    never touch an alias the user intentionally rebound.
    delete_sql = sa.text(
        "DELETE FROM unit_aliases "
        "WHERE alias = :alias AND canonical_unit = :canonical"
    )
    for alias, canonical in _STALE_ALIASES:
        bind.execute(delete_sql, {"alias": alias, "canonical": canonical})

    # 2. Seed the 15 plural→singular freeform aliases.
    insert_sql = sa.text(
        "INSERT INTO unit_aliases (alias, canonical_unit) "
        "VALUES (:alias, :canonical) "
        "ON CONFLICT (alias) DO NOTHING"
    )
    for alias, canonical in _FREEFORM_ALIASES:
        bind.execute(insert_sql, {"alias": alias, "canonical": canonical})


def downgrade() -> None:
    bind = op.get_bind()

    # Reverse step 2: remove the 15 freeform aliases.
    # Match exact pair so we never yank an alias a human intentionally
    # rebound to something else.
    delete_alias_sql = sa.text(
        "DELETE FROM unit_aliases "
        "WHERE alias = :alias AND canonical_unit = :canonical"
    )
    for alias, canonical in _FREEFORM_ALIASES:
        bind.execute(delete_alias_sql, {"alias": alias, "canonical": canonical})

    # Reverse step 1: put the riip-1 aliases back where they were. Uses
    # ON CONFLICT DO NOTHING in case the operator already re-seeded
    # them manually.
    restore_sql = sa.text(
        "INSERT INTO unit_aliases (alias, canonical_unit) "
        "VALUES (:alias, :canonical) "
        "ON CONFLICT (alias) DO NOTHING"
    )
    for alias, canonical in _STALE_ALIASES:
        bind.execute(restore_sql, {"alias": alias, "canonical": canonical})
