"""Add dev_requests — admin requests for a change to Palateful.

Revision ID: devrequests01
Revises: idupbookname1
Create Date: 2026-11-24

Workstream admin-request-intake (plan 1e84ad), phase 1 (arq101); PRD FR-1.

One table, created whole: the status CHECK lists all 13 FR-12 statuses and
the slice-2 source columns (`source`, `fault_signature`) exist from this
revision, so neither the widening nor slice 2 needs a second migration.
Slice 1 writes only `source = 'admin'` rows in `submitted`.

Every length limit is a CHECK as well as API validation (the API checks the
normalized value, so a well-formed request never trips one).

Indexes:
- `ix_dev_requests_status_created` — the operator's `poll` (non-terminal
  rows, oldest first).
- `ix_dev_requests_submitter` — per-submitter lookups and the rate-limit
  audit.
- `ux_dev_requests_open_fault_signature` — partial unique: at most one open
  row per fault signature (FR-20), enforced by the index so two racing
  `open-fault` calls cannot both insert.

Downgrade drops the table. That is safe until the first real request
exists and lossy after it; past that point fix forward.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "devrequests01"
down_revision: str | None = "idupbookname1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUSES = (
    "'submitted', 'received', 'accepted', 'declined', 'withdrawn', "
    "'scoping', 'designing', 'planning', 'building', 'waiting_on_leo', "
    "'shipped', 'stopped', 'reverted'"
)
_TERMINAL = "'declined', 'withdrawn', 'shipped', 'stopped', 'reverted'"


def upgrade() -> None:
    op.create_table(
        "dev_requests",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
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
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "submitter_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'admin'"),
        ),
        sa.Column("fault_signature", sa.String(64), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("done_when", sa.Text(), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column(
            "target",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'palateful'"),
        ),
        sa.Column("priority", sa.String(16), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'submitted'"),
        ),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("workstream", sa.String(128), nullable=True),
        sa.Column("spec_hash", sa.String(64), nullable=True),
        sa.Column(
            "pr_urls",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(title) BETWEEN 1 AND 120",
            name="ck_dev_requests_title_length",
        ),
        sa.CheckConstraint(
            "length(body) BETWEEN 1 AND 4000",
            name="ck_dev_requests_body_length",
        ),
        sa.CheckConstraint(
            "done_when IS NULL OR length(done_when) BETWEEN 1 AND 1000",
            name="ck_dev_requests_done_when_length",
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_dev_requests_content_sha256",
        ),
        sa.CheckConstraint(
            f"status IN ({_STATUSES})",
            name="ck_dev_requests_status",
        ),
        sa.CheckConstraint(
            "target = 'palateful'",
            name="ck_dev_requests_target",
        ),
        sa.CheckConstraint(
            "priority IS NULL OR priority IN ('low', 'normal', 'high')",
            name="ck_dev_requests_priority",
        ),
        sa.CheckConstraint(
            "source IN ('admin', 'fault')",
            name="ck_dev_requests_source",
        ),
        sa.CheckConstraint(
            "(source = 'fault') = (fault_signature IS NOT NULL)",
            name="ck_dev_requests_fault_signature",
        ),
    )
    op.create_index(
        "ix_dev_requests_status_created",
        "dev_requests",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_dev_requests_submitter",
        "dev_requests",
        ["submitter_id"],
    )
    op.create_index(
        "ux_dev_requests_open_fault_signature",
        "dev_requests",
        ["fault_signature"],
        unique=True,
        postgresql_where=sa.text(
            f"fault_signature IS NOT NULL AND status NOT IN ({_TERMINAL})"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_dev_requests_open_fault_signature", table_name="dev_requests"
    )
    op.drop_index("ix_dev_requests_submitter", table_name="dev_requests")
    op.drop_index("ix_dev_requests_status_created", table_name="dev_requests")
    op.drop_table("dev_requests")
