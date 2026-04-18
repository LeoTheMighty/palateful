"""Add last_retry_at + awaiting_review_reason columns to import_items.

Revision ID: irrd1fields0
Revises: r1i2i3p4u01
Create Date: 2026-04-18

Story irrd-1. Surfaces two fields the API already knows it wants but
never had:

  * `last_retry_at` — stamped by the retry endpoint on dispatch; lets the
    Flutter caret expansion render "Retried 2 times · last at 3m ago"
    without pulling the full audit log. Historical retried rows
    (retry_count > 0) intentionally keep NULL — the field is best-effort
    forward-looking.
  * `awaiting_review_reason` — the rule path that routed the item into
    `awaiting_review` (low_confidence / unmatched_ingredients /
    missing_title / manual). Stored as a plain VARCHAR rather than a PG
    enum so adding a new reason later is a code-only change. CHECK
    constraint keeps the value set bounded.

Down-migration drops both columns cleanly.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "irrd1fields0"
down_revision: str | None = "r1i2i3p4u01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_AWAITING_REVIEW_REASONS = (
    "low_confidence",
    "unmatched_ingredients",
    "missing_title",
    "manual",
)


def upgrade() -> None:
    op.add_column(
        "import_items",
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "import_items",
        sa.Column("awaiting_review_reason", sa.String(32), nullable=True),
    )
    reasons = ", ".join(f"'{r}'" for r in _AWAITING_REVIEW_REASONS)
    op.create_check_constraint(
        "ck_import_items_awaiting_review_reason",
        "import_items",
        f"awaiting_review_reason IS NULL "
        f"OR awaiting_review_reason IN ({reasons})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_import_items_awaiting_review_reason",
        "import_items",
        type_="check",
    )
    op.drop_column("import_items", "awaiting_review_reason")
    op.drop_column("import_items", "last_retry_at")
