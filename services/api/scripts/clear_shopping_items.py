"""One-shot: delete every row from shopping_list_items.

Leaves shopping_lists, shopping_list_users, and reminder-state rows
intact. shopping_list_events rows are orphaned (they only carry
item_id inside JSONB event_data — no FK), so history remains but
references stale items; acceptable for a solo-user cleanup.

Runs inside the prod ECS task via bin/prod-script. Flip DRY_RUN to
False to commit. Writes one audit row to error_logs.
"""

from datetime import UTC, datetime

from sqlalchemy import text

DRY_RUN = True
SCRIPT_ACTOR = "script:clear_shopping_items"

# `db` is injected by bin/prod-script's PRELUDE.
before = db.execute(text("SELECT COUNT(*) FROM shopping_list_items")).scalar()
lists = db.execute(text("SELECT COUNT(*) FROM shopping_lists")).scalar()

print(f"shopping_list_items rows: {before}")
print(f"shopping_lists rows (untouched): {lists}")

if DRY_RUN:
    print("DRY-RUN: no changes written. Flip DRY_RUN=False to commit.")
else:
    deleted = db.execute(text("DELETE FROM shopping_list_items")).rowcount
    db.execute(
        text(
            """
            INSERT INTO error_logs (
                id, created_at, updated_at,
                error_type, error_message, service
            ) VALUES (
                gen_random_uuid(), :now, :now,
                :etype, :emsg, :svc
            )
            """
        ),
        {
            "now": datetime.now(UTC),
            "etype": "ShoppingListItemsPurge",
            "emsg": f"deleted {deleted} shopping_list_items rows by {SCRIPT_ACTOR}",
            "svc": "audit",
        },
    )
    db.commit()
    after = db.execute(text("SELECT COUNT(*) FROM shopping_list_items")).scalar()
    print(f"DELETED {deleted} rows. Remaining: {after}")
