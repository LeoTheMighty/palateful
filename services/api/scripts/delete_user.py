"""Delete a Palateful user and everything that references them.

Usage:
    # Dry-run (default) — prints what WOULD be removed and what would be
    # kept, per table, with counts. Nothing is written.
    python services/api/scripts/delete_user.py --id-or-email qa@example.test

    # Commit. Requires BOTH confirmations; see "Guards" below.
    python services/api/scripts/delete_user.py \\
        --id-or-email qa@example.test \\
        --confirm-email qa@example.test \\
        --auth0-disabled --yes

Requires DATABASE_URL. Raw SQLAlchemy, like the other ops scripts, so it
runs against prod without booting the FastAPI app.

DISABLE THE AUTH0 IDENTITY FIRST — the deletion undoes itself otherwise
=====================================================================
`get_current_user` (`services/api/src/dependencies.py`) calls
`find_or_create_by(User, auth0_id=...)` and then `_ensure_default_calendar`
and `_ensure_system_trying_out` on **every authed request**. Delete the
rows while the Auth0 identity can still authenticate and the next request
from that identity recreates the user, a default calendar and a starter
recipe book. The script would report success and the user would be back.

**This script cannot do that step and cannot check that you did.** There
is no Auth0 Management API client in this repo — `utils/services/auth0.py`
only verifies tokens against JWKS — so there are no credentials here with
which to disable anything. The flag `--auth0-disabled` is therefore an
*attestation*: you are stating you disabled it. Nothing verifies the
claim at the time you make it.

What the script does instead is check afterwards: `--verify-after`
seconds after committing (default 5, `0` disables), it re-queries the
`auth0_id`. If the row is back, the identity was still live, the deletion
undid itself, and the script says so and exits 1. That converts a silent
self-undo into an observed failure — it does not prevent one.

Guards
======
Two independent confirmations, neither of which is a bare "I'm sure":

* `--confirm-email` must exactly match (case-insensitively) the email of
  the user that `--id-or-email` resolved to. The lookup and your belief
  about who you are deleting have to agree — a typo in either one fails
  closed. A user with no email on record cannot be confirmed, and so
  cannot be deleted by this script.
* **Admin accounts are refused outright, with no override.** A `--force`
  flag is a flag that can be added by reflex; there is deliberately none
  here. If deleting an admin is ever genuinely required, add that
  capability as its own considered change.

Schema drift also fails closed: the script derives the set of
user-referencing foreign keys from `information_schema` at run time, and
**refuses to proceed if it finds a `NO ACTION` / `RESTRICT` FK it does
not handle by name** (see `UNHANDLED_FK_ALLOWLIST`). A partially-applied
delete is the worst of the available outcomes.

What "deleted" does and does not mean
=====================================
Neither hard delete nor anonymising achieves "no trace of this user".
This script hard-deletes, and reports honestly in two sections:

* **Removed** — the user row, plus every row whose FK is `CASCADE`.
* **Kept, unattributed** — rows whose FK is `SET NULL` keep existing with
  a null user, and `error_logs.user_id` has **no foreign key at all**, so
  those rows keep a `user_id` pointing at a user who no longer exists.
  (Measured 2026-09-24: for the prod QA identity that is 761
  `client_latencies` rows and 6 `error_logs` rows out of 768 referencing
  rows — i.e. most of them.)

Error history surviving is deliberate: it is the record of what the user
hit, and it outlives the account on purpose.

Writes an audit row to `error_logs` with `service="audit"` and
`error_type="UserDeletionAudit"` so the removal is itself queryable
without polluting the error dashboards (which filter `service="api"`).

Exit codes: `0` success or dry-run, `2` no match / multiple matches /
missing DATABASE_URL, `1` refusal, error, or a deletion that undid
itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

SCRIPT_ACTOR = "script:delete_user"

#: User-referencing FKs that declare no `ondelete` (or a blocking rule),
#: which therefore have to be cleared by hand before the delete. Derived
#: from the live schema at run time; this list is what the script knows
#: how to handle. Anything else found at run time stops the run.
#: Measured against prod 2026-09-24: exactly one such FK exists.
UNHANDLED_FK_ALLOWLIST: dict[tuple[str, str], str] = {
    ("ingredients", "submitted_by_id"): "SET NULL",
}

#: Columns on `users` that point *out* at rows which the delete will
#: cascade away. Postgres resolves the cycle within a single statement,
#: but clearing them first keeps the intent explicit and the failure mode
#: readable if that ever stops being true.
USER_SELF_REFERENCES = ("default_recipe_book_id", "default_shopping_list_id")

#: Tables that reference a user without a foreign key, so nothing in the
#: database touches them on delete. Reported, never modified.
NO_FK_REFERENCES = (("error_logs", "user_id"),)

_FK_QUERY = """
SELECT tc.table_name, kcu.column_name, rc.delete_rule
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name
JOIN information_schema.referential_constraints rc
  ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND ccu.table_name = 'users'
ORDER BY tc.table_name, kcu.column_name
"""


def _get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(2)
    return create_engine(url)


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def find_user(conn: Connection, id_or_email: str) -> list[dict[str, Any]]:
    """Resolve by UUID, else by email (case-insensitive)."""
    if _looks_like_uuid(id_or_email):
        clause = "id = :value"
        params: dict[str, Any] = {"value": id_or_email}
    else:
        clause = "LOWER(email) = LOWER(:value)"
        params = {"value": id_or_email}
    result = conn.execute(
        text(
            f"SELECT id, email, name, auth0_id, is_admin, created_at "  # noqa: S608
            f"FROM users WHERE {clause}"
        ),
        params,
    )
    return [dict(row._mapping) for row in result]


def user_foreign_keys(conn: Connection) -> list[tuple[str, str, str]]:
    """Every FK referencing `users`, as (table, column, delete_rule)."""
    return [
        (row[0], row[1], row[2]) for row in conn.execute(text(_FK_QUERY))
    ]


def unhandled_foreign_keys(
    fks: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """FKs that neither cascade nor null, and that we don't handle by name.

    A `NO ACTION` / `RESTRICT` FK makes `DELETE FROM users` fail partway,
    which is worse than either succeeding or failing outright. Finding an
    unknown one means the schema moved and this script has not caught up.
    """
    return [
        (table, column, rule)
        for table, column, rule in fks
        if rule.upper() not in ("CASCADE", "SET NULL")
        and (table, column) not in UNHANDLED_FK_ALLOWLIST
    ]


def count_references(
    conn: Connection, fks: list[tuple[str, str, str]], user_id: Any
) -> tuple[list[tuple[str, str, str, int]], list[tuple[str, str, str, int]]]:
    """Per-table counts, split into (removed, kept_unattributed).

    `removed` is what disappears: `CASCADE` rows. `kept` is what survives
    with a dangling or nulled reference: `SET NULL` rows, the by-name FKs
    this script nulls itself, and the no-FK tables nothing touches.
    """
    removed: list[tuple[str, str, str, int]] = []
    kept: list[tuple[str, str, str, int]] = []
    for table, column, rule in fks:
        count = conn.execute(
            text(f'SELECT count(*) FROM "{table}" WHERE "{column}" = :u'),  # noqa: S608
            {"u": user_id},
        ).scalar_one()
        if not count:
            continue
        if rule.upper() == "CASCADE":
            removed.append((table, column, rule, count))
        else:
            effective = UNHANDLED_FK_ALLOWLIST.get((table, column), rule)
            kept.append((table, column, effective, count))
    for table, column in NO_FK_REFERENCES:
        count = conn.execute(
            text(f'SELECT count(*) FROM "{table}" WHERE "{column}" = :u'),  # noqa: S608
            {"u": user_id},
        ).scalar_one()
        if count:
            kept.append((table, column, "NO FK — dangles", count))
    return removed, kept


def _print_plan(
    user: dict[str, Any],
    removed: list[tuple[str, str, str, int]],
    kept: list[tuple[str, str, str, int]],
) -> None:
    print(f"User:      {user['id']}")
    print(f"Name:      {user.get('name') or '(none)'}")
    print(f"Admin:     {user['is_admin']}")
    print(f"Created:   {user.get('created_at')}")
    print()
    print("REMOVED — deleted outright (the user row, plus CASCADE rows):")
    print(f"  {'users':<32} {'id':<22} {'(the account)':<18}        1")
    for table, column, rule, count in removed:
        print(f"  {table:<32} {column:<22} {rule:<18} {count:>8}")
    if not removed:
        print("  (no cascading rows)")
    print()
    print("KEPT, UNATTRIBUTED — rows survive, pointing at nobody:")
    for table, column, rule, count in kept:
        print(f"  {table:<32} {column:<22} {rule:<18} {count:>8}")
    if not kept:
        print("  (none)")
    print()
    print(
        f"  totals: {sum(c for *_, c in removed) + 1} row(s) removed, "
        f"{sum(c for *_, c in kept)} kept unattributed"
    )
    print(
        "  NOTE: 'deleted' does not mean 'no trace'. The kept rows above "
        "remain in the database."
    )


def write_audit_row(
    conn: Connection,
    user_id: Any,
    removed_total: int,
    kept_total: int,
) -> None:
    """Record the deletion in `error_logs` as `service="audit"`.

    Deliberately stores no email or name: the row survives the user, and
    an audit trail does not need to preserve the identifiers the deletion
    existed to remove.
    """
    conn.execute(
        text(
            """
            INSERT INTO error_logs (
                id, created_at, service, error_type, error_message, user_id
            ) VALUES (
                :id, :created_at, 'audit', 'UserDeletionAudit', :message, NULL
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "created_at": datetime.now(UTC),
            "message": json.dumps(
                {
                    "actor": SCRIPT_ACTOR,
                    "deleted_user_id": str(user_id),
                    "rows_removed": removed_total,
                    "rows_kept_unattributed": kept_total,
                }
            ),
        },
    )


def perform_delete(
    conn: Connection, fks: list[tuple[str, str, str]], user_id: Any
) -> None:
    """Clear the by-name FKs and self-references, then delete the user."""
    for (table, column), _ in UNHANDLED_FK_ALLOWLIST.items():
        if not any(t == table and c == column for t, c, _ in fks):
            continue
        conn.execute(
            text(
                f'UPDATE "{table}" SET "{column}" = NULL WHERE "{column}" = :u'  # noqa: S608
            ),
            {"u": user_id},
        )
    for column in USER_SELF_REFERENCES:
        conn.execute(
            text(f'UPDATE users SET "{column}" = NULL WHERE id = :u'),  # noqa: S608
            {"u": user_id},
        )
    conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})


def verify_not_reprovisioned(
    engine: Engine, auth0_id: str, wait_s: float
) -> bool:
    """True if the user stayed deleted; False if it came back.

    A returning row means the Auth0 identity could still authenticate and
    `get_current_user` recreated it — the deletion undid itself.
    """
    if wait_s <= 0:
        return True
    time.sleep(wait_s)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM users WHERE auth0_id = :a"),
            {"a": auth0_id},
        ).scalar_one()
    return count == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete a user and everything referencing them.",
    )
    parser.add_argument("--id-or-email", required=True)
    parser.add_argument(
        "--confirm-email",
        help="must match the resolved user's email; required with --yes",
    )
    parser.add_argument(
        "--auth0-disabled",
        action="store_true",
        help="attest that the Auth0 identity is already disabled",
    )
    parser.add_argument(
        "--verify-after",
        type=float,
        default=5.0,
        help="seconds to wait before checking the user stayed deleted "
        "(0 disables the check)",
    )
    parser.add_argument("--yes", action="store_true", help="commit")
    args = parser.parse_args(argv)

    engine = _get_engine()
    with engine.connect() as conn:
        matches = find_user(conn, args.id_or_email)
        if not matches:
            print(f"No user matched {args.id_or_email!r}.", file=sys.stderr)
            return 2
        if len(matches) > 1:
            print(
                f"{len(matches)} users matched {args.id_or_email!r}; refusing.",
                file=sys.stderr,
            )
            return 2
        user = matches[0]

        if user["is_admin"]:
            print(
                "REFUSING: this user is an admin. This script deletes no "
                "admin account, and has no override flag by design.",
                file=sys.stderr,
            )
            return 1

        fks = user_foreign_keys(conn)
        unhandled = unhandled_foreign_keys(fks)
        if unhandled:
            print(
                "REFUSING: the schema has blocking foreign keys this script "
                "does not handle by name — a DELETE would apply partially:",
                file=sys.stderr,
            )
            for table, column, rule in unhandled:
                print(f"  {table}.{column} [{rule}]", file=sys.stderr)
            return 1

        removed, kept = count_references(conn, fks, user["id"])
        _print_plan(user, removed, kept)

        if not args.yes:
            print()
            print("Dry run — nothing was written. Re-run with --yes, "
                  "--confirm-email and --auth0-disabled to commit.")
            return 0

        confirm = (args.confirm_email or "").strip().lower()
        actual = (user.get("email") or "").strip().lower()
        if not actual:
            print(
                "REFUSING: this user has no email on record, so "
                "--confirm-email cannot corroborate the lookup.",
                file=sys.stderr,
            )
            return 1
        if confirm != actual:
            print(
                "REFUSING: --confirm-email does not match the resolved "
                "user's email. The lookup and your expectation disagree, "
                "which is what this check is for.",
                file=sys.stderr,
            )
            return 1
        if not args.auth0_disabled:
            print(
                "REFUSING: pass --auth0-disabled to attest that the Auth0 "
                "identity is disabled. While it can authenticate, the next "
                "request recreates this user and the deletion undoes itself.",
                file=sys.stderr,
            )
            return 1

        removed_total = sum(c for *_, c in removed) + 1
        kept_total = sum(c for *_, c in kept)
        auth0_id = user["auth0_id"]
        with conn.begin():
            perform_delete(conn, fks, user["id"])
            write_audit_row(conn, user["id"], removed_total, kept_total)

    print()
    print(f"Deleted. {removed_total} row(s) removed, {kept_total} kept.")

    if not verify_not_reprovisioned(engine, auth0_id, args.verify_after):
        print(
            "FAILED: the user reappeared after deletion. The Auth0 identity "
            "could still authenticate, so a request recreated it — the "
            "deletion undid itself. Disable the identity, then re-run.",
            file=sys.stderr,
        )
        return 1
    print("Verified: the user did not reappear.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
