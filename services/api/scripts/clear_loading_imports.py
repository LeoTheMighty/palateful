"""One-shot: delete import_jobs stuck in a loading state.

"Loading" = status in ('pending', 'processing'). Child import_items
cascade-delete via the relationship. Flip DRY_RUN to False to commit.
Writes one audit row to error_logs.
"""

from datetime import UTC, datetime

from sqlalchemy import text

DRY_RUN = True
LOADING_STATUSES = ("pending", "processing")
SCRIPT_ACTOR = "script:clear_loading_imports"

# `db` is injected by bin/prod-script's PRELUDE.
status_rows = db.execute(
    text(
        """
        SELECT status, COUNT(*) AS n
        FROM import_jobs
        GROUP BY status
        ORDER BY status
        """
    )
).all()
print("import_jobs by status:")
for row in status_rows:
    print(f"  {row.status:20s} {row.n}")

targets = db.execute(
    text(
        """
        SELECT id, status, source_type, source_filename, created_at
        FROM import_jobs
        WHERE status = ANY(:statuses)
        ORDER BY created_at DESC
        """
    ),
    {"statuses": list(LOADING_STATUSES)},
).all()

print(f"\nCandidate loading jobs ({len(targets)}):")
for row in targets:
    fname = row.source_filename or "-"
    print(f"  {row.id} {row.status:12s} {row.source_type:12s} {fname[:40]:40s} {row.created_at}")

if DRY_RUN:
    print("\nDRY-RUN: no changes written. Flip DRY_RUN=False to commit.")
else:
    if not targets:
        print("\nNothing to delete.")
    else:
        job_ids = [row.id for row in targets]
        items_deleted = db.execute(
            text("DELETE FROM import_items WHERE import_job_id = ANY(:ids)"),
            {"ids": job_ids},
        ).rowcount
        jobs_deleted = db.execute(
            text("DELETE FROM import_jobs WHERE id = ANY(:ids)"),
            {"ids": job_ids},
        ).rowcount
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
                "etype": "LoadingImportJobsPurge",
                "emsg": (
                    f"deleted {jobs_deleted} import_jobs + {items_deleted} import_items "
                    f"(statuses={list(LOADING_STATUSES)}) by {SCRIPT_ACTOR}"
                ),
                "svc": "audit",
            },
        )
        db.commit()
        print(f"\nDELETED {jobs_deleted} import_jobs and {items_deleted} import_items.")
