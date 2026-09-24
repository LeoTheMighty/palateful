"""Delete selected content belonging to one QA user — never the user.

Usage:
    # Dry-run (default): resolve the targets, prove each is in scope,
    # print what would go. Nothing is written.
    python services/api/scripts/qa_cleanup.py \\
        --id-or-email qa@example.test --confirm-email qa@example.test \\
        --recipe <uuid> --recipe <uuid> --ingredient <uuid>

    # Commit.
    python services/api/scripts/qa_cleanup.py \\
        --id-or-email qa@example.test --confirm-email qa@example.test \\
        --recipe <uuid> --ingredient <uuid> --yes

Requires DATABASE_URL. Raw SQLAlchemy, like the other ops scripts.

Why this is a separate script from `delete_user.py`
===================================================
This one is intended to hold a **standing** permission grant, and a
standing grant takes the blast radius of the largest thing the granted
script can do — not the smallest. So this script **cannot delete a user**
at all, and gains nothing by being asked to. `delete_user.py` can, and
therefore keeps needing per-case approval.

Safe by construction, not by care
=================================
Every target is passed as an explicit row id and must prove it is in
scope before anything is written. There are exactly two ways to qualify:

1. **Owned, and owned only by them** — for a recipe, its book is owned
   by the confirmed QA user *and* has no other members. Recipes have no
   user FK at all: ownership runs `recipes.recipe_book_id` →
   `recipe_book_users(role='owner')`, and a book can be **shared**. A
   plain "the QA user owns it" test would delete content another member
   can see, which is exactly what scoping is supposed to prevent.
2. **Unreferenced** — for `ingredients` only: the row is referenced by
   nothing at commit time, checked inside the same transaction as the
   delete.

Rule 2 exists because ingredient rows are **not owned**: measured in prod
2026-09-24, both junk `mashed bananas` rows carried
`submitted_by_id = NULL`, and 51 of 130 ingredient rows have no submitter
at all. So user-scoping cannot reach them, and name-matching them would
be an unscoped delete wearing a QA-cleanup label — it could reach another
user's data, which is the thing the scoping exists to prevent.

Under rule 2 an ingredient row used by anyone else's recipe can never be
deleted, whatever ids are passed. That is the property the standing grant
rests on. It also fixes the ordering: the banana rows qualify only
*after* the junk recipes that referenced them are gone, which is why both
kinds of target are handled in one transaction, recipes first.

**What rule 2 assumes.** `ingredients` is a bag of display names, not a
shared catalogue: per `utils/models/ingredient.py`, every write path
creates a fresh row per parsed name, with no canonicalization and no
cross-recipe matching. If that ever changes, "referenced by nothing"
stops being sufficient — `test_ingredients_are_not_a_shared_catalogue`
pins it so the change fails loudly instead of silently widening this
script's reach.

Guards, identical in spirit to `delete_user.py`:
`--confirm-email` must match the resolved user's email, and **admin
accounts are refused outright with no override**.

Writes an audit row (`service="audit"`,
`error_type="QaCleanupAudit"`).

Exit codes: `0` success or dry-run, `2` no match / multiple matches /
missing DATABASE_URL, `1` refusal or an out-of-scope target.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

SCRIPT_ACTOR = "script:qa_cleanup"

#: Tables this script may delete from. Deliberately a short allowlist: a
#: tool holding a standing grant should not be able to reach a table
#: nobody vetted. Ownership is NOT a column here — see `recipe_in_scope`.
OWNED_TABLES: tuple[str, ...] = ("recipes",)

#: Tables deletable only when nothing references them (rule 2), mapped to
#: the referencing (table, column) pairs that must all be empty.
UNREFERENCED_TABLES: dict[str, tuple[tuple[str, str], ...]] = {
    "ingredients": (
        ("recipe_ingredients", "ingredient_id"),
        ("pantry_ingredients", "ingredient_id"),
        ("shopping_list_items", "ingredient_id"),
    ),
}


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
    clause = (
        "id = :value" if _looks_like_uuid(id_or_email)
        else "LOWER(email) = LOWER(:value)"
    )
    result = conn.execute(
        text(  # noqa: S608
            f"SELECT id, email, name, is_admin FROM users WHERE {clause}"
        ),
        {"value": id_or_email},
    )
    return [dict(row._mapping) for row in result]


def recipe_in_scope(
    conn: Connection, recipe_id: str, user_id: Any
) -> tuple[bool, str]:
    """Is this recipe the confirmed user's alone? Returns (ok, reason).

    Recipes carry no user FK. Ownership runs through the book:
    `recipes.recipe_book_id` -> `recipe_book_users(role='owner')`. Books
    are shareable, so ownership alone is not enough — a shared book's
    recipe is visible to other members, and deleting it would reach
    outside the scope this script's standing permission is granted on.
    Both conditions are required.
    """
    book = conn.execute(
        text("SELECT recipe_book_id FROM recipes WHERE id = :r"),
        {"r": recipe_id},
    ).scalar()
    if book is None:
        return False, "no such recipe"
    owns = conn.execute(
        text(
            "SELECT count(*) FROM recipe_book_users "
            "WHERE recipe_book_id = :b AND user_id = :u AND role = 'owner'"
        ),
        {"b": book, "u": user_id},
    ).scalar_one()
    if not owns:
        return False, f"book {book} is not owned by this user"
    others = conn.execute(
        text(
            "SELECT count(*) FROM recipe_book_users "
            "WHERE recipe_book_id = :b AND user_id <> :u"
        ),
        {"b": book, "u": user_id},
    ).scalar_one()
    if others:
        return False, (
            f"book {book} has {others} other member(s) — deleting this "
            f"recipe would remove content they can see"
        )
    return True, "sole owner of its book"


def references_to(
    conn: Connection, table: str, row_id: str
) -> list[tuple[str, int]]:
    """Non-zero references to `row_id`, as (referencing_table, count)."""
    found = []
    for ref_table, ref_column in UNREFERENCED_TABLES[table]:
        count = conn.execute(
            text(  # noqa: S608
                f'SELECT count(*) FROM "{ref_table}" WHERE "{ref_column}" = :r'
            ),
            {"r": row_id},
        ).scalar_one()
        if count:
            found.append((ref_table, count))
    return found


def write_audit_row(
    conn: Connection, user_id: Any, deleted: dict[str, list[str]]
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO error_logs (
                id, created_at, service, error_type, error_message, user_id
            ) VALUES (
                :id, :created_at, 'audit', 'QaCleanupAudit', :message, :user_id
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "created_at": datetime.now(UTC),
            "user_id": user_id,
            "message": json.dumps(
                {
                    "actor": SCRIPT_ACTOR,
                    "scoped_to_user_id": str(user_id),
                    "deleted": {k: len(v) for k, v in deleted.items()},
                    "ids": {k: [str(i) for i in v] for k, v in deleted.items()},
                }
            ),
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete selected QA-owned content. Never deletes a user.",
    )
    parser.add_argument("--id-or-email", required=True)
    parser.add_argument("--confirm-email", required=True)
    parser.add_argument(
        "--recipe", action="append", default=[], metavar="UUID",
        help="a recipe row id owned by the confirmed user (repeatable)",
    )
    parser.add_argument(
        "--ingredient", action="append", default=[], metavar="UUID",
        help="an ingredient row id; deleted only if unreferenced at commit "
        "time (repeatable)",
    )
    parser.add_argument("--yes", action="store_true", help="commit")
    args = parser.parse_args(argv)

    if not args.recipe and not args.ingredient:
        print("Nothing to do: pass --recipe and/or --ingredient.")
        return 0

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
                "REFUSING: this user is an admin. This script touches no "
                "admin account, and has no override flag by design.",
                file=sys.stderr,
            )
            return 1

        actual = (user.get("email") or "").strip().lower()
        if not actual or actual != args.confirm_email.strip().lower():
            print(
                "REFUSING: --confirm-email does not match the resolved "
                "user's email. The lookup and your expectation disagree.",
                file=sys.stderr,
            )
            return 1

        print(f"Scoped to user: {user['id']}")
        print()

        # --- prove every target is in scope, before writing anything ---
        out_of_scope: list[str] = []
        print("OWNED — deleted because they belong to this user:")
        for row_id in args.recipe:
            ok, reason = recipe_in_scope(conn, row_id, user["id"])
            if ok:
                print(f"  recipes            {row_id}  ({reason})")
            else:
                out_of_scope.append(f"recipes {row_id}: {reason}")
        if not args.recipe:
            print("  (none)")

        print()
        print("UNREFERENCED — deleted only if nothing points at them:")
        for row_id in args.ingredient:
            refs = references_to(conn, "ingredients", row_id)
            if refs:
                detail = ", ".join(f"{t}={n}" for t, n in refs)
                print(f"  ingredients        {row_id}  BLOCKED ({detail})")
                if not args.recipe:
                    out_of_scope.append(
                        f"ingredients {row_id}: still referenced ({detail})"
                    )
                else:
                    print(
                        "    ^ may qualify once the recipes above are "
                        "deleted; re-checked inside the transaction."
                    )
            else:
                print(f"  ingredients        {row_id}")
        if not args.ingredient:
            print("  (none)")

        if out_of_scope:
            print()
            print("REFUSING — out of scope:", file=sys.stderr)
            for line in out_of_scope:
                print(f"  {line}", file=sys.stderr)
            return 1

        if not args.yes:
            print()
            print("Dry run — nothing was written. Re-run with --yes to commit.")
            return 0

        deleted: dict[str, list[str]] = {"recipes": [], "ingredients": []}
        with conn.begin():
            for row_id in args.recipe:
                ok, reason = recipe_in_scope(conn, row_id, user["id"])
                if not ok:
                    print(
                        f"REFUSING: recipes {row_id} — {reason} (changed "
                        f"since the check); rolling back.",
                        file=sys.stderr,
                    )
                    raise SystemExit(1)
                conn.execute(
                    text("DELETE FROM recipes WHERE id = :r"), {"r": row_id}
                )
                deleted["recipes"].append(row_id)

            # Re-checked here, inside the transaction and AFTER the owned
            # deletions: that ordering is what lets a row referenced only
            # by this user's deleted content qualify, while a row someone
            # else references still cannot.
            for row_id in args.ingredient:
                refs = references_to(conn, "ingredients", row_id)
                if refs:
                    detail = ", ".join(f"{t}={n}" for t, n in refs)
                    print(
                        f"REFUSING: ingredients {row_id} is still referenced "
                        f"({detail}); rolling back.",
                        file=sys.stderr,
                    )
                    raise SystemExit(1)
                conn.execute(
                    text("DELETE FROM ingredients WHERE id = :r"),
                    {"r": row_id},
                )
                deleted["ingredients"].append(row_id)

            write_audit_row(conn, user["id"], deleted)

    print()
    print(
        f"Deleted {len(deleted['recipes'])} recipe(s), "
        f"{len(deleted['ingredients'])} ingredient(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
