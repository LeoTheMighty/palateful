"""Add client_latencies table for client-side performance telemetry.

Revision ID: cla1aclilat01
Revises: erifraliases01
Create Date: 2026-04-23

Story cla-1a (epic-perf-client-analytics). Mirrors the shape of
`request_latencies` (obs-latency-1) plus the platform/route/extra
fields needed to slice client-emitted samples by iOS / Android / Web
and by event type (route-paint, app-start, network, frame-jank,
MetricKit, JankStats, web Navigation Timing).

Schema notes:
- `extra jsonb` is NOT NULL with a `'{}'::jsonb` server default —
  aggregations can assume the column is always present. MetricKit +
  JankStats + Navigation Timing raw payloads land here so new fields
  can be surfaced later without another migration.
- CHECK constraints on `type` and `platform` act as a cheap
  server-side whitelist. Keep these in sync with
  `CLIENT_LATENCY_TYPES` / `CLIENT_LATENCY_PLATFORMS` in
  `libraries/utils/utils/models/client_latency.py` and the Flutter
  enum in `app/lib/core/services/client_latency_ingest.dart`.
- `user_id` is SET NULL on user delete AND nullable at insert time
  (anonymous pre-login cold-start events, locked 2026-04-23 in the
  epic's user-locked answer to the anonymous-ingest question).
- Indexes match the three hot-path slicing keys plus a
  retention-sweep index. `route` index is partial
  (WHERE route IS NOT NULL) because app_start / MetricKit rows carry
  no route and would waste index space.

Chains after `erifraliases01` (eri-4b freeform-unit aliases) so
alembic keeps a single linear head across parallel-epic PRs.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "cla1aclilat01"
down_revision: str | None = "erifraliases01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPE_VALUES = (
    "app_start",
    "route_paint",
    "network_request",
    "frame_jank_p95",
    "metrickit_daily",
    "jankstats_daily",
    "web_navigation",
    "first_paint",
    "first_contentful_paint",
)

_PLATFORM_VALUES = ("ios", "android", "web")


def _check_in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    op.create_table(
        "client_latencies",
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("app_version", sa.String(32), nullable=False),
        sa.Column("route", sa.String(256), nullable=True),
        sa.Column("endpoint", sa.String(256), nullable=True),
        sa.Column("metric_name", sa.String(64), nullable=True),
        sa.Column("device_class", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(
            _check_in("type", _TYPE_VALUES),
            name="ck_client_latencies_type",
        ),
        sa.CheckConstraint(
            _check_in("platform", _PLATFORM_VALUES),
            name="ck_client_latencies_platform",
        ),
    )

    # Partial index — only rows carrying a route. app_start / MetricKit
    # / JankStats rows are route-less and would bloat the index.
    op.create_index(
        "ix_client_latencies_created_route",
        "client_latencies",
        [sa.text("created_at DESC"), "route"],
        postgresql_where=sa.text("route IS NOT NULL"),
    )
    op.create_index(
        "ix_client_latencies_created_platform",
        "client_latencies",
        [sa.text("created_at DESC"), "platform"],
    )
    op.create_index(
        "ix_client_latencies_created_type",
        "client_latencies",
        [sa.text("created_at DESC"), "type"],
    )
    op.create_index(
        "ix_client_latencies_created",
        "client_latencies",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_latencies_created", table_name="client_latencies"
    )
    op.drop_index(
        "ix_client_latencies_created_type", table_name="client_latencies"
    )
    op.drop_index(
        "ix_client_latencies_created_platform", table_name="client_latencies"
    )
    op.drop_index(
        "ix_client_latencies_created_route", table_name="client_latencies"
    )
    op.drop_table("client_latencies")
