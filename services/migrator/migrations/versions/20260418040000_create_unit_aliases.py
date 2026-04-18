"""Create unit_aliases table + seed canonical units and freeform aliases.

Revision ID: r1i2i3p4u01
Revises: a1h2r3a4r5c1
Create Date: 2026-04-18

Story riip-1. Adds the freeform-unit → canonical-token lookup that powers
`normalize_unit_display` (riip-2 wires it into every write path). The
`units` table itself was created in the initial migration but never seeded
on its own (the application only stores `unit_display` strings); this
migration seeds the rows we need so the new `unit_aliases.canonical_unit`
FK to `units.name` is satisfied.

Pre-conditions:
- `units.name` already has a UNIQUE constraint (initial migration) — the
  FK target requires it.
- Seeds use `INSERT … ON CONFLICT DO NOTHING` so re-running on a
  partially-applied DB is safe.

Down: drop `unit_aliases`. Leave the seeded `units` rows in place — they
may be referenced by live `recipe_ingredients.unit_display` strings, and
down-migrations should not orphan that data.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r1i2i3p4u01"
down_revision: str | None = "a1h2r3a4r5c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Canonical tokens — kept in sync with the extractor prompt token list
# (riip-3) and the Flutter `kCuratedUnits` array.
#
# (name, abbreviation, type, to_base_factor, base_unit)
_CANONICAL_UNITS: tuple[tuple[str, str, str, str, str], ...] = (
    # Volume (base ml)
    ("tsp", "tsp", "volume", "4.929", "ml"),
    ("tbsp", "tbsp", "volume", "14.787", "ml"),
    ("cup", "cup", "volume", "236.588", "ml"),
    ("fl oz", "fl oz", "volume", "29.574", "ml"),
    ("ml", "ml", "volume", "1", "ml"),
    ("l", "l", "volume", "1000", "ml"),
    ("pint", "pt", "volume", "473.176", "ml"),
    ("quart", "qt", "volume", "946.353", "ml"),
    ("gallon", "gal", "volume", "3785.41", "ml"),
    # Weight (base g)
    ("g", "g", "weight", "1", "g"),
    ("kg", "kg", "weight", "1000", "g"),
    ("mg", "mg", "weight", "0.001", "g"),
    ("oz", "oz", "weight", "28.3495", "g"),
    ("lb", "lb", "weight", "453.592", "g"),
    # Count / other (non-convertible)
    ("each", "each", "count", "1", "each"),
    ("pinch", "pinch", "other", "1", "pinch"),
    ("dash", "dash", "other", "1", "dash"),
    ("clove", "clove", "other", "1", "clove"),
    ("slice", "slice", "other", "1", "slice"),
)


# alias → canonical_unit. ≥40 entries covering volume/weight/count
# full-words, plurals, and common typos.
_ALIASES: tuple[tuple[str, str], ...] = (
    # Volume full names + plurals
    ("tablespoon", "tbsp"),
    ("tablespoons", "tbsp"),
    ("teaspoon", "tsp"),
    ("teaspoons", "tsp"),
    ("cups", "cup"),
    ("c", "cup"),
    ("fluid ounce", "fl oz"),
    ("fluid ounces", "fl oz"),
    ("fluid_ounce", "fl oz"),
    ("floz", "fl oz"),
    ("milliliter", "ml"),
    ("milliliters", "ml"),
    ("millilitre", "ml"),
    ("millilitres", "ml"),
    ("liter", "l"),
    ("liters", "l"),
    ("litre", "l"),
    ("litres", "l"),
    ("gallons", "gallon"),
    ("gal", "gallon"),
    ("quarts", "quart"),
    ("qt", "quart"),
    ("pints", "pint"),
    ("pt", "pint"),
    # Weight full names + plurals
    ("gram", "g"),
    ("grams", "g"),
    ("kilogram", "kg"),
    ("kilograms", "kg"),
    ("kilo", "kg"),
    ("kilos", "kg"),
    ("pound", "lb"),
    ("pounds", "lb"),
    ("lbs", "lb"),
    ("ounce", "oz"),
    ("ounces", "oz"),
    ("milligram", "mg"),
    ("milligrams", "mg"),
    # Count + other plurals + alts
    ("cloves", "clove"),
    ("slices", "slice"),
    ("pinches", "pinch"),
    ("dashes", "dash"),
    ("ea", "each"),
    ("piece", "each"),
    ("pieces", "each"),
    # Common typos / abbreviations
    ("tbsps", "tbsp"),
    ("tsps", "tsp"),
    ("tblsp", "tbsp"),
    ("teasp", "tsp"),
    ("tblspn", "tbsp"),
)


def _seed_units(bind) -> None:
    """Idempotently insert the canonical unit rows referenced by the FK."""
    insert_sql = sa.text(
        "INSERT INTO units (id, name, abbreviation, type, to_base_factor, base_unit) "
        "VALUES (gen_random_uuid(), :name, :abbreviation, :type, :to_base_factor, :base_unit) "
        "ON CONFLICT (name) DO NOTHING"
    )
    for name, abbr, utype, to_base, base_unit in _CANONICAL_UNITS:
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


def _assert_units_present(bind) -> None:
    """Fail loudly if a canonical unit is missing after seeding."""
    canonical_names = sorted({c[0] for c in _CANONICAL_UNITS})
    found = (
        bind.execute(
            sa.text("SELECT name FROM units WHERE name = ANY(:names)"),
            {"names": canonical_names},
        )
        .scalars()
        .all()
    )
    missing = sorted(set(canonical_names) - set(found))
    if missing:
        raise RuntimeError(
            "unit_aliases migration: expected canonical units missing from "
            f"`units` table after seed: {missing}"
        )


def _seed_aliases(bind) -> None:
    """Idempotently insert alias → canonical rows."""
    insert_sql = sa.text(
        "INSERT INTO unit_aliases (alias, canonical_unit) "
        "VALUES (:alias, :canonical) "
        "ON CONFLICT (alias) DO NOTHING"
    )
    for alias, canonical in _ALIASES:
        bind.execute(insert_sql, {"alias": alias, "canonical": canonical})


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Seed canonical units the FK will point at.
    _seed_units(bind)

    # 2. Pre-condition: every canonical_unit referenced by the alias seed
    #    must exist in `units` before we add the FK.
    _assert_units_present(bind)

    # 3. Create the unit_aliases table. Mirrors `JoinsBase` columns
    #    (created_at, updated_at, archived_at) so the SQLAlchemy model
    #    and the DB schema stay in lock-step (and `alembic check`
    #    doesn't flag drift).
    op.create_table(
        "unit_aliases",
        sa.Column("alias", sa.String(80), primary_key=True),
        sa.Column(
            "canonical_unit",
            sa.String(32),
            sa.ForeignKey("units.name", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # 4. Seed alias rows.
    _seed_aliases(bind)


def downgrade() -> None:
    op.drop_table("unit_aliases")
