"""Add s3_key column + partial unique index to import_items.

Revision ID: sbf3s3keycol0
Revises: irrd2tlm0001
Create Date: 2026-04-18

Story sbf-3 of epic-share-backend-foundations. The presign flow
(sbf-2) mints keys like `imports/{user_id}/{uuid}.{ext}`; this column
is where `/import` stores the claimed key. The partial UNIQUE index
(`WHERE s3_key IS NOT NULL`) is the second line of defense against
replay — the first being the in-endpoint dedupe query. IntegrityError
on concurrent inserts maps back to `409 duplicate_import`.

Nullable because:
  * The legacy base64 path never sets s3_key.
  * The `url` / `text` paths never touch S3.
Partial index avoids bloating the index with millions of NULL entries
from the existing rows.

Down-migration drops the index then the column.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "sbf3s3keycol0"
down_revision: str | None = "irrd2tlm0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_items",
        sa.Column("s3_key", sa.Text(), nullable=True),
    )
    # Partial UNIQUE: enforces one row per S3 key, but only for rows
    # that actually have one. Legacy NULLs stay untouched.
    op.create_index(
        "ix_import_items_s3_key_unique",
        "import_items",
        ["s3_key"],
        unique=True,
        postgresql_where=sa.text("s3_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_items_s3_key_unique",
        table_name="import_items",
    )
    op.drop_column("import_items", "s3_key")
