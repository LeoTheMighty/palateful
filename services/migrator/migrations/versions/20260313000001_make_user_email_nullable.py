"""Make user email nullable for social providers that don't return email

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Make email nullable — Apple Sign In may not provide an email address.
    # NULL values don't violate unique constraints, so multiple users can
    # have NULL email without conflict.
    op.alter_column("users", "email", existing_type=sa.String(), nullable=True)

    # Convert any existing empty-string emails to NULL
    op.execute("UPDATE users SET email = NULL WHERE email = ''")


def downgrade() -> None:
    # Convert NULLs back to empty string before making non-nullable
    op.execute("UPDATE users SET email = '' WHERE email IS NULL")
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
