"""Add friends and social system

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add username field to users table
    op.add_column(
        "users",
        sa.Column("username", sa.String(20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("username_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # 2. Create friend_requests table
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("from_user_id", sa.UUID(), nullable=False),
        sa.Column("to_user_id", sa.UUID(), nullable=False),
        sa.Column("message", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["from_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["to_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "from_user_id", "to_user_id", name="uq_friend_requests_users"
        ),
    )
    op.create_index(
        "ix_friend_requests_from_user", "friend_requests", ["from_user_id"]
    )
    op.create_index(
        "ix_friend_requests_to_user_status",
        "friend_requests",
        ["to_user_id", "status"],
    )

    # 3. Create friendships table (bidirectional)
    op.create_table(
        "friendships",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("friend_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "friend_id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["friend_id"], ["users.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_friendships_user", "friendships", ["user_id"])


def downgrade() -> None:
    # Drop friendships table
    op.drop_index("ix_friendships_user", table_name="friendships")
    op.drop_table("friendships")

    # Drop friend_requests table
    op.drop_index("ix_friend_requests_to_user_status", table_name="friend_requests")
    op.drop_index("ix_friend_requests_from_user", table_name="friend_requests")
    op.drop_table("friend_requests")

    # Drop username columns from users
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username_changed_at")
    op.drop_column("users", "username")
