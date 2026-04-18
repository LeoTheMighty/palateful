"""Add calendars + calendar_users + calendar_id FKs on meal_events & rules.

Revision ID: c1a2l3d4r5s6
Revises: a1r2e3c4u5r6
Create Date: 2026-04-17

First-class Calendar container. Ships the backfill migration in a single
alembic revision:

1. Create calendars + calendar_users tables (with CHECK constraint on role
   and the partial unique index that DB-enforces "exactly one default per
   user").
2. Add nullable calendar_id FK to meal_events + meal_recurrence_rules.
3. Seed one default calendar per existing user ("My Calendar") + an owner
   calendar_users row per user.
4. Backfill meal_events.calendar_id and meal_recurrence_rules.calendar_id
   from the owner's default calendar.
5. Integrity check: abort if any rows remain NULL.
6. Tighten both FKs to NOT NULL.

Re-runnable: the partial unique index + ON CONFLICT on the seed step + the
"WHERE calendar_id IS NULL" filter on the backfill step make every step
idempotent.

Logged: row counts at each step are written to error_logs with
service="migrator" and error_type="CalendarBackfillStep" so a prod run is
observable without grepping container logs.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2l3d4r5s6"
down_revision: str | None = "a1r2e3c4u5r6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_CALENDAR_NAME = "My Calendar"


def _log_step(conn, step_name: str, **counts) -> None:
    """Record a migration step to error_logs for observability.

    service="migrator" keeps these rows out of api-error dashboards
    (which filter on service="api"). error_type="CalendarBackfillStep"
    namespaces this migration's rows.
    """
    counts_str = ", ".join(f"{k}={v}" for k, v in counts.items()) or "no counts"
    message = f"{step_name}: {counts_str}"
    conn.execute(
        sa.text(
            """
            INSERT INTO error_logs
                (id, created_at, updated_at,
                 error_type, error_message, service, user_id)
            VALUES
                (gen_random_uuid(), NOW(), NOW(),
                 'CalendarBackfillStep', :msg, 'migrator', NULL)
            """
        ),
        {"msg": message},
    )


def upgrade() -> None:
    conn = op.get_bind()

    # -------- Step 1: create tables --------
    op.create_table(
        "calendars",
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
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "is_shared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column(
            "owner_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_calendars_owner_id",
        "calendars",
        ["owner_id"],
    )
    # DB-enforced invariant: exactly one default calendar per user that is
    # not archived. Allows re-running the backfill seed idempotently via
    # ON CONFLICT DO NOTHING.
    op.create_index(
        "uq_calendars_owner_is_default_active",
        "calendars",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND archived_at IS NULL"),
    )

    op.create_table(
        "calendar_users",
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
        sa.Column("role", sa.String(16), nullable=False, server_default="editor"),
        sa.Column(
            "calendar_id",
            sa.UUID(),
            sa.ForeignKey("calendars.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "invited_by_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role IN ('owner', 'editor')",
            name="ck_calendar_users_role",
        ),
    )
    op.create_index(
        "ix_calendar_users_user_archived",
        "calendar_users",
        ["user_id", "archived_at"],
    )
    op.create_index(
        "ix_calendar_users_calendar_id",
        "calendar_users",
        ["calendar_id"],
    )

    # -------- Step 2: add nullable FKs --------
    op.add_column(
        "meal_events",
        sa.Column(
            "calendar_id",
            sa.UUID(),
            sa.ForeignKey("calendars.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_meal_events_calendar_id_scheduled_at",
        "meal_events",
        ["calendar_id", "scheduled_at"],
    )

    op.add_column(
        "meal_recurrence_rules",
        sa.Column(
            "calendar_id",
            sa.UUID(),
            sa.ForeignKey("calendars.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_meal_recurrence_rules_calendar_id",
        "meal_recurrence_rules",
        ["calendar_id"],
    )

    # -------- Step 3: seed default calendars --------
    # Use ON CONFLICT against the partial unique index so this is idempotent
    # even if the migration is re-run after a partial success.
    seed_calendars = conn.execute(
        sa.text(
            """
            INSERT INTO calendars
                (id, created_at, updated_at, name, is_default, owner_id)
            SELECT
                gen_random_uuid(), NOW(), NOW(), :name, true, u.id
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM calendars c
                WHERE c.owner_id = u.id
                  AND c.is_default = true
                  AND c.archived_at IS NULL
            )
            RETURNING id, owner_id
            """
        ),
        {"name": DEFAULT_CALENDAR_NAME},
    )
    seeded_rows = list(seed_calendars)
    calendars_seeded = len(seeded_rows)

    # Create owner memberships for every seeded default calendar.
    # LEFT JOIN filter makes this re-runnable — if a calendar_users row
    # already exists for (cal, user), skip.
    memberships_result = conn.execute(
        sa.text(
            """
            INSERT INTO calendar_users
                (created_at, updated_at, role, calendar_id, user_id)
            SELECT NOW(), NOW(), 'owner', c.id, c.owner_id
            FROM calendars c
            LEFT JOIN calendar_users cu
              ON cu.calendar_id = c.id AND cu.user_id = c.owner_id
            WHERE c.is_default = true
              AND c.archived_at IS NULL
              AND cu.user_id IS NULL
            RETURNING calendar_id
            """
        )
    )
    memberships_created = len(list(memberships_result))

    _log_step(
        conn,
        "seed_default_calendars",
        calendars_seeded=calendars_seeded,
        memberships_created=memberships_created,
    )

    # -------- Step 4: backfill FKs on meal_events + recurrence_rules --------
    events_updated_result = conn.execute(
        sa.text(
            """
            UPDATE meal_events
            SET calendar_id = c.id
            FROM calendars c
            WHERE meal_events.calendar_id IS NULL
              AND c.owner_id = meal_events.owner_id
              AND c.is_default = true
              AND c.archived_at IS NULL
            """
        )
    )
    events_updated = events_updated_result.rowcount or 0
    _log_step(conn, "backfill_meal_events", rows_updated=events_updated)

    rules_updated_result = conn.execute(
        sa.text(
            """
            UPDATE meal_recurrence_rules
            SET calendar_id = c.id
            FROM calendars c
            WHERE meal_recurrence_rules.calendar_id IS NULL
              AND c.owner_id = meal_recurrence_rules.owner_id
              AND c.is_default = true
              AND c.archived_at IS NULL
            """
        )
    )
    rules_updated = rules_updated_result.rowcount or 0
    _log_step(conn, "backfill_recurrence_rules", rows_updated=rules_updated)

    # -------- Step 5: integrity check --------
    null_events = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM meal_events WHERE calendar_id IS NULL"
        )
    ).scalar_one()
    null_rules = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM meal_recurrence_rules WHERE calendar_id IS NULL"
        )
    ).scalar_one()

    if null_events or null_rules:
        _log_step(
            conn,
            "integrity_check_failed",
            null_meal_events=null_events,
            null_recurrence_rules=null_rules,
        )
        raise RuntimeError(
            f"Backfill incomplete: meal_events NULL count={null_events}, "
            f"recurrence_rules NULL count={null_rules}. "
            "Aborting migration — no rows will be tightened to NOT NULL."
        )

    _log_step(
        conn,
        "integrity_check_passed",
        null_meal_events=null_events,
        null_recurrence_rules=null_rules,
    )

    # -------- Step 6: tighten to NOT NULL --------
    op.alter_column("meal_events", "calendar_id", nullable=False)
    op.alter_column("meal_recurrence_rules", "calendar_id", nullable=False)


def downgrade() -> None:
    # Drop indexes + columns on meal_events / meal_recurrence_rules.
    op.drop_index(
        "ix_meal_events_calendar_id_scheduled_at",
        table_name="meal_events",
    )
    op.drop_column("meal_events", "calendar_id")

    op.drop_index(
        "ix_meal_recurrence_rules_calendar_id",
        table_name="meal_recurrence_rules",
    )
    op.drop_column("meal_recurrence_rules", "calendar_id")

    # Drop calendar_users first (FK depends on calendars).
    op.drop_index(
        "ix_calendar_users_calendar_id",
        table_name="calendar_users",
    )
    op.drop_index(
        "ix_calendar_users_user_archived",
        table_name="calendar_users",
    )
    op.drop_table("calendar_users")

    # Drop calendars last.
    op.drop_index(
        "uq_calendars_owner_is_default_active",
        table_name="calendars",
    )
    op.drop_index(
        "ix_calendars_owner_id",
        table_name="calendars",
    )
    op.drop_table("calendars")
