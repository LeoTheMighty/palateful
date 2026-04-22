"""Add idempotency_key column + partial unique index to import_jobs.

Revision ID: impjobidemp001
Revises: afh2seeallidx1
Create Date: 2026-04-21

The Share Extension (iOS) and the Flutter reconciler both POST
`/v1/recipe-books/{book}/import` with the same `idempotency_key` when a
share hasn't been confirmed yet: the extension submits once when the
user taps Save, and the reconciler re-submits the persisted pending
record on every app resume as a backstop. Before this column existed
the backend ignored the key entirely, so a single share produced
duplicate ImportJobs (up to 4 in the wild — extension + cold-boot +
resume + late URLSession callback).

`idempotency_key` is a client-generated UUID-shaped string; we don't
parse it, just use it as an opaque replay token. Partial UNIQUE on
`(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL` scopes
the constraint to one user so different users can't collide, and keeps
the legacy rows (no key) out of the index.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "impjobidemp001"
down_revision: str | None = "afh2seeallidx1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_jobs",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_import_jobs_user_idempotency_key_unique",
        "import_jobs",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_jobs_user_idempotency_key_unique",
        table_name="import_jobs",
    )
    op.drop_column("import_jobs", "idempotency_key")
