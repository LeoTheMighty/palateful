"""Promote or demote a Palateful user to/from admin by email.

Usage:
    # Dry-run (default) — prints target user record and planned change.
    python services/api/scripts/promote_admin.py --email leonid@ac93.org

    # Commit the promotion.
    python services/api/scripts/promote_admin.py --email leonid@ac93.org --yes

    # Demote a user.
    python services/api/scripts/promote_admin.py --email someone@example.com --demote --yes

Requires DATABASE_URL to be set in the environment. Uses raw SQLAlchemy
so the script can run against prod without booting the FastAPI app.

Writes an audit row to the error_logs table on every successful mutation
with service="audit" and error_type="AdminRoleChangeAudit" so the event
is queryable but doesn't pollute the error-service dashboards (which
filter to service="api").
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

SCRIPT_ACTOR = "script:promote_admin"


def _get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(2)
    return create_engine(url)


def _find_user_by_email(conn: Connection, email: str) -> list[dict[str, Any]]:
    result = conn.execute(
        text(
            """
            SELECT id, email, name, created_at, is_admin
            FROM users
            WHERE email = :email
            """
        ),
        {"email": email},
    )
    return [dict(row._mapping) for row in result]


def _update_is_admin(conn: Connection, user_id: Any, new_value: bool) -> None:
    conn.execute(
        text(
            """
            UPDATE users
            SET is_admin = :value, updated_at = :now
            WHERE id = :id
            """
        ),
        {
            "value": new_value,
            "now": datetime.now(UTC),
            "id": user_id,
        },
    )


def _write_audit_row(
    conn: Connection,
    target_user_id: Any,
    target_email: str,
    before: bool,
    after: bool,
) -> None:
    """Write a durable audit row to error_logs.

    service="audit" keeps it out of api-service error dashboards;
    error_type="AdminRoleChangeAudit" is the namespace for this kind.
    """
    message = (
        f"is_admin {before} -> {after} for {target_email} "
        f"(user_id={target_user_id}) by {SCRIPT_ACTOR}"
    )
    conn.execute(
        text(
            """
            INSERT INTO error_logs (
                id, created_at, updated_at,
                error_type, error_message, service, user_id
            ) VALUES (
                gen_random_uuid(), :now, :now,
                :etype, :emsg, :svc, :uid
            )
            """
        ),
        {
            "now": datetime.now(UTC),
            "etype": "AdminRoleChangeAudit",
            "emsg": message,
            "svc": "audit",
            "uid": target_user_id,
        },
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Promote/demote a Palateful user to/from admin by email.",
    )
    p.add_argument("--email", required=True, help="Target user email (exact match).")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--promote",
        dest="action",
        action="store_const",
        const="promote",
        help="Grant admin (default).",
    )
    mode.add_argument(
        "--demote",
        dest="action",
        action="store_const",
        const="demote",
        help="Revoke admin.",
    )
    p.set_defaults(action="promote")
    p.add_argument(
        "--yes",
        action="store_true",
        help="Commit the change. Default is dry-run.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    engine = _get_engine()
    with engine.connect() as conn:
        matches = _find_user_by_email(conn, args.email)

        if len(matches) == 0:
            print(f"ERROR: no user with email={args.email}", file=sys.stderr)
            return 2
        if len(matches) > 1:
            print(
                f"ERROR: {len(matches)} users matched email={args.email}; "
                "email is expected to be unique. Aborting.",
                file=sys.stderr,
            )
            return 2

        user = matches[0]
        target_state = args.action == "promote"
        current_state = bool(user["is_admin"])

        print("Target user:")
        print(f"  id          : {user['id']}")
        print(f"  email       : {user['email']}")
        print(f"  name        : {user['name']}")
        print(f"  created_at  : {user['created_at']}")
        print(f"  is_admin    : {current_state}")
        print(f"  action      : {args.action}  (would set is_admin={target_state})")

        if current_state == target_state:
            label = "admin" if target_state else "not admin"
            print(f"NO-OP: already {label}")
            return 0

        if not args.yes:
            print("DRY-RUN: no changes written. Re-run with --yes to commit.")
            return 0

        # --yes: commit the change atomically with the audit row.
        with conn.begin():
            _update_is_admin(conn, user["id"], target_state)
            _write_audit_row(
                conn,
                target_user_id=user["id"],
                target_email=str(user["email"]),
                before=current_state,
                after=target_state,
            )

        verb = "PROMOTE_ADMIN" if target_state else "DEMOTE_ADMIN"
        print(
            f"{verb} user_id={user['id']} email={user['email']} "
            f"before={current_state} after={target_state} actor={SCRIPT_ACTOR}"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
