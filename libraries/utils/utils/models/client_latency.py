"""ClientLatency model — one row per client-emitted performance sample.

Mirrors the `request_latencies` shape plus the platform/route/extra
fields needed to split samples across iOS / Android / Web and across
client event types (route-paint, app-start, network, frame-jank,
MetricKit, JankStats, web Navigation Timing). Written by the
synchronous bulk-insert in `POST /v1/client-latencies`
(`services/api/src/api/v1/client_latency/ingest.py`, cla-1b) and
pruned nightly by the `cleanup_latency_samples` task (30 day
retention — same as server-side).

`extra` (jsonb) is NOT NULL with a `'{}'::jsonb` server default so
downstream aggregations can assume the column is always present, even
for event types that ship no platform-specific payload (e.g.
`app_start`). MetricKit + JankStats + Navigation Timing all land the
full raw payload here so we can query new fields later without a
migration.

Check constraints on `type` and `platform` act as a cheap server-side
whitelist — the client can't invent new categories without a matching
migration, and accidental typos fail fast at insert time.
"""

import uuid

from sqlalchemy import (
    UUID,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from utils.models.base import Base

# Whitelist of event types emitted by the client. Keep in sync with
# the CHECK constraint in the migration
# (`20260423010000_add_client_latencies_table.py`) and the Flutter
# `ClientLatencyEvent` enum in
# `app/lib/core/services/client_latency_ingest.dart`.
CLIENT_LATENCY_TYPES = (
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

# Whitelist of platform strings. Add new platforms here + in the
# migration CHECK + in the Flutter enum together.
CLIENT_LATENCY_PLATFORMS = ("ios", "android", "web")


class ClientLatency(Base):
    """Append-only client-side performance sample.

    `route` is nullable because cold-start + MetricKit events do not
    carry one. `endpoint` is nullable because only `network_request`
    events carry one. `metric_name` is nullable and reserved for
    metric-style events (e.g. `jankstats_daily` payload keys) that
    don't map cleanly to a route or endpoint.

    `user_id` is SET NULL on user delete (samples survive offboarding
    without dangling FK violations) AND NULL is an accepted value at
    insert time (anonymous pre-login cold-start events — per the
    2026-04-23 user-lock decision in `epic-perf-client-analytics.md`).
    """

    __tablename__ = "client_latencies"

    # id, created_at, updated_at, archived_at inherited from Base

    type: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)

    route: Mapped[str | None] = mapped_column(String(256), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(256), nullable=True)
    metric_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_class: Mapped[str | None] = mapped_column(String(64), nullable=True)

    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    extra: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ("
            + ", ".join(f"'{t}'" for t in CLIENT_LATENCY_TYPES)
            + ")",
            name="ck_client_latencies_type",
        ),
        CheckConstraint(
            "platform IN ("
            + ", ".join(f"'{p}'" for p in CLIENT_LATENCY_PLATFORMS)
            + ")",
            name="ck_client_latencies_platform",
        ),
        # Partial index — route is nullable; only index rows that
        # carry one (app_start + MetricKit rows would waste space).
        Index(
            "ix_client_latencies_created_route",
            text("created_at DESC"),
            "route",
            postgresql_where=text("route IS NOT NULL"),
        ),
        # Compound on (created_at, platform) — platform is always set.
        Index(
            "ix_client_latencies_created_platform",
            text("created_at DESC"),
            "platform",
        ),
        # Compound on (created_at, type) — type is always set.
        Index(
            "ix_client_latencies_created_type",
            text("created_at DESC"),
            "type",
        ),
        # Retention / prune sweep.
        Index(
            "ix_client_latencies_created",
            text("created_at DESC"),
        ),
    )
