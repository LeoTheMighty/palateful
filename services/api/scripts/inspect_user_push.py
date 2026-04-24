"""Inspect a user's push-notification state for debugging.

Prints everything the admin push-health endpoint would return, plus the
raw push-token list and recent audit rows — useful when the admin
endpoint itself is broken (stale deploy, 404 on route) or when you need
the full token values, not just prefixes.

Usage:
    # By email (case-insensitive).
    DATABASE_URL=<prod-url> python services/api/scripts/inspect_user_push.py \\
        --id-or-email leonid@ac93.org

    # By UUID.
    DATABASE_URL=<prod-url> python services/api/scripts/inspect_user_push.py \\
        --id-or-email 34589ac4-f6ef-4adf-9b3b-299084cbc947

    # Include full push tokens (default: only 8-char prefixes).
    DATABASE_URL=<prod-url> python services/api/scripts/inspect_user_push.py \\
        --id-or-email leonid@ac93.org --show-full-tokens

    # Recent push-related error rows (default 10, max 50).
    DATABASE_URL=<prod-url> python services/api/scripts/inspect_user_push.py \\
        --id-or-email leonid@ac93.org --error-limit 25

Requires DATABASE_URL in the environment. Uses raw SQL so the script
runs against prod without booting the FastAPI app. Read-only — no
mutations, no audit row. Can also be run via `bin/prod-script` (the
prelude will create a db session but this script sets up its own
engine from DATABASE_URL, so the prelude variables are ignored).

Exit codes:
    0 — user found, diagnostic printed
    1 — DB / runtime error
    2 — no user matched --id-or-email
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_TOKEN_PREFIX_LEN = 8


def _get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)
    return create_engine(url)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Inspect a user's push-notification state. Read-only.",
    )
    p.add_argument(
        "--id-or-email",
        required=True,
        help="Target user UUID or email (case-insensitive email match).",
    )
    p.add_argument(
        "--error-limit",
        type=int,
        default=10,
        help="Max recent push_notifications error rows to show. Default 10, max 50.",
    )
    p.add_argument(
        "--show-full-tokens",
        action="store_true",
        help="Print full FCM tokens instead of 8-char prefixes.",
    )
    args = p.parse_args(argv)
    if args.error_limit < 1 or args.error_limit > 50:
        print("ERROR: --error-limit must be between 1 and 50.", file=sys.stderr)
        sys.exit(1)
    return args


def _resolve_user(engine: Engine, raw: str) -> dict[str, Any] | None:
    """Return the matched user row as a dict, or None.

    Mirrors `_resolve_target` in get_push_health.py: UUID first, then
    case-insensitive email.
    """
    cols = (
        "id, email, auth0_id, is_admin, "
        "notification_permission_status, notification_preferences, "
        "push_tokens, created_at"
    )
    raw = raw.strip()

    try:
        uid = uuid.UUID(raw)
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {cols} FROM users WHERE id = :id"),
                {"id": str(uid)},
            ).mappings().one_or_none()
        if row is not None:
            return dict(row)
    except (ValueError, TypeError):
        pass

    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT {cols} FROM users "
                "WHERE lower(email) = lower(:email) "
                "LIMIT 2"
            ),
            {"email": raw},
        ).mappings().all()
    if len(row) == 0:
        return None
    if len(row) > 1:
        print(
            f"ERROR: multiple users matched email={raw!r}. "
            "Disambiguate with a UUID.",
            file=sys.stderr,
        )
        sys.exit(1)
    return dict(row[0])


def _recent_errors(
    engine: Engine, user_id: Any, limit: int
) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT created_at, error_type, error_message, request_id "
                "FROM error_logs "
                "WHERE user_id = :uid AND service = 'push_notifications' "
                "ORDER BY created_at DESC "
                "LIMIT :lim"
            ),
            {"uid": str(user_id), "lim": limit},
        ).mappings().all()
    return [dict(r) for r in rows]


def _recent_audit(
    engine: Engine, user_id: Any, limit: int = 10
) -> list[dict[str, Any]]:
    """Admin audit rows targeting this user (AdminTestPushAudit, AdminPushHealthCheck)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT created_at, error_type, error_message "
                "FROM error_logs "
                "WHERE user_id = :uid AND service = 'audit' "
                "ORDER BY created_at DESC "
                "LIMIT :lim"
            ),
            {"uid": str(user_id), "lim": limit},
        ).mappings().all()
    return [dict(r) for r in rows]


def _format_token(token: str, show_full: bool) -> str:
    if show_full:
        return token
    if len(token) <= _TOKEN_PREFIX_LEN:
        return token
    return f"{token[:_TOKEN_PREFIX_LEN]}…"


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    engine = _get_engine()

    try:
        user = _resolve_user(engine, args.id_or_email)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: DB query failed: {e}", file=sys.stderr)
        return 1

    if user is None:
        print(f"No user matched: {args.id_or_email!r}", file=sys.stderr)
        return 2

    tokens = list(user.get("push_tokens") or [])
    errors = _recent_errors(engine, user["id"], args.error_limit)
    audit = _recent_audit(engine, user["id"], limit=10)

    out = {
        "user_id": str(user["id"]),
        "email": user["email"],
        "auth0_id": user["auth0_id"],
        "is_admin": bool(user["is_admin"]),
        "created_at": _iso(user["created_at"]),
        "notification_permission_status": user["notification_permission_status"],
        "notification_preferences": user["notification_preferences"],
        "push_tokens_count": len(tokens),
        "push_tokens": [
            _format_token(t, args.show_full_tokens) for t in tokens
        ],
        "recent_push_errors": [
            {
                "timestamp": _iso(r["created_at"]),
                "error_type": r["error_type"],
                "error_message": (r["error_message"] or "")[:500],
                "request_id": r["request_id"],
            }
            for r in errors
        ],
        "recent_push_errors_count": len(errors),
        "recent_admin_audit": [
            {
                "timestamp": _iso(r["created_at"]),
                "error_type": r["error_type"],
                "error_message": (r["error_message"] or "")[:500],
            }
            for r in audit
        ],
    }

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
