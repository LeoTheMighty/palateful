"""Add collaboration system (invitations, invite links, activities)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New tables ---

    # Create invitations table
    op.create_table(
        "invitations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("from_user_id", sa.UUID(), nullable=False),
        sa.Column("to_user_id", sa.UUID(), nullable=True),
        sa.Column("to_email", sa.String(255), nullable=True),
        sa.Column("resource_type", sa.String(30), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("role_offered", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("message", sa.String(200), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_invitations_resource", "invitations", ["resource_type", "resource_id"]
    )
    op.create_index("ix_invitations_to_user_id", "invitations", ["to_user_id"])
    op.create_index("ix_invitations_from_user_id", "invitations", ["from_user_id"])

    # Create invite_links table
    op.create_table(
        "invite_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(20), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("resource_type", sa.String(30), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("role_offered", sa.String(20), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", name="uq_invite_links_token"),
    )

    # Create activities table
    op.create_table(
        "activities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("resource_type", sa.String(30), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=True),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_activities_resource_created",
        "activities",
        ["resource_type", "resource_id", "created_at"],
    )

    # --- Alter existing tables ---

    # Add invited_by_id to recipe_book_users
    op.add_column(
        "recipe_book_users",
        sa.Column("invited_by_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_recipe_book_users_invited_by",
        "recipe_book_users",
        "users",
        ["invited_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add invited_by_id to pantry_users
    op.add_column(
        "pantry_users",
        sa.Column("invited_by_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pantry_users_invited_by",
        "pantry_users",
        "users",
        ["invited_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add invited_by_id to shopping_list_users
    op.add_column(
        "shopping_list_users",
        sa.Column("invited_by_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_shopping_list_users_invited_by",
        "shopping_list_users",
        "users",
        ["invited_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add invited_by_id to meal_event_participants
    op.add_column(
        "meal_event_participants",
        sa.Column("invited_by_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_meal_event_participants_invited_by",
        "meal_event_participants",
        "users",
        ["invited_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add collaboration columns to notifications
    op.add_column(
        "notifications",
        sa.Column("source_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("resource_type", sa.String(30), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("resource_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("invitation_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("cta_action", sa.String(255), nullable=True),
    )
    op.create_foreign_key(
        "fk_notifications_source_user",
        "notifications",
        "users",
        ["source_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_notifications_invitation",
        "notifications",
        "invitations",
        ["invitation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # --- Revert notification changes ---
    op.drop_constraint("fk_notifications_invitation", "notifications", type_="foreignkey")
    op.drop_constraint("fk_notifications_source_user", "notifications", type_="foreignkey")
    op.drop_column("notifications", "cta_action")
    op.drop_column("notifications", "invitation_id")
    op.drop_column("notifications", "resource_id")
    op.drop_column("notifications", "resource_type")
    op.drop_column("notifications", "source_user_id")

    # --- Revert invited_by_id additions ---
    op.drop_constraint(
        "fk_meal_event_participants_invited_by",
        "meal_event_participants",
        type_="foreignkey",
    )
    op.drop_column("meal_event_participants", "invited_by_id")

    op.drop_constraint(
        "fk_shopping_list_users_invited_by",
        "shopping_list_users",
        type_="foreignkey",
    )
    op.drop_column("shopping_list_users", "invited_by_id")

    op.drop_constraint("fk_pantry_users_invited_by", "pantry_users", type_="foreignkey")
    op.drop_column("pantry_users", "invited_by_id")

    op.drop_constraint(
        "fk_recipe_book_users_invited_by", "recipe_book_users", type_="foreignkey"
    )
    op.drop_column("recipe_book_users", "invited_by_id")

    # --- Drop new tables ---
    op.drop_index("ix_activities_resource_created", table_name="activities")
    op.drop_table("activities")

    op.drop_table("invite_links")

    op.drop_index("ix_invitations_from_user_id", table_name="invitations")
    op.drop_index("ix_invitations_to_user_id", table_name="invitations")
    op.drop_index("ix_invitations_resource", table_name="invitations")
    op.drop_table("invitations")
