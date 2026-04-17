"""Quick audit of rows in the ``error_logs`` table.

Intended to be run via ``bin/prod-script`` so that ``db`` and the
``ErrorLog`` model are preloaded by the prelude:

    bin/prod-script scripts/python/audit_errors.py

By default prints, for the last 24h:
  - total error_logs rows (split by service)
  - top error_types, with counts and a sample message
  - most recent rows (error_type, status_code, path, created_at)

For each top error_type we also print the most recent stack trace
(tail-truncated) so the actual call site is visible without a second
round-trip.

Tunables via env vars (set them in your local shell before calling
``bin/prod-script``):
  AUDIT_HOURS          window in hours (default 24)
  AUDIT_TOP            top-N error_types (default 10)
  AUDIT_RECENT         recent N rows (default 15)
  AUDIT_TRACE_LINES    stack-trace tail size per error_type (default 25, 0 to hide)
  AUDIT_INCLUDE_AUDIT  set to 1 to include service=audit rows

Note: bin/prod-script forwards env into the container via ECS exec, so
tunables must be exported in your local shell.

IMPORTANT: do not use ``from __future__`` imports — bin/prod-script
concatenates this file onto a PRELUDE, so any ``__future__`` import
would no longer be at the top of the module.
"""

import os
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import func

HOURS = int(os.environ.get("AUDIT_HOURS", "24"))
INCLUDE_AUDIT = os.environ.get("AUDIT_INCLUDE_AUDIT", "").lower() in ("1", "true", "yes")
TOP_N = int(os.environ.get("AUDIT_TOP", "10"))
RECENT_N = int(os.environ.get("AUDIT_RECENT", "15"))
TRACE_LINES = int(os.environ.get("AUDIT_TRACE_LINES", "25"))

since = datetime.now(UTC) - timedelta(hours=HOURS)

print(f"=== error_logs audit — last {HOURS}h (since {since.isoformat()}) ===")

rows = (
    db.query(ErrorLog.service, func.count(ErrorLog.id))  # noqa: F821
    .filter(ErrorLog.created_at >= since)  # noqa: F821
    .group_by(ErrorLog.service)  # noqa: F821
    .all()
)
total = sum(c for _, c in rows)
print(f"\nTotal rows: {total}")
for service, count in sorted(rows, key=lambda r: -r[1]):
    print(f"  {service:<10} {count}")

q = db.query(ErrorLog).filter(ErrorLog.created_at >= since)  # noqa: F821
if not INCLUDE_AUDIT:
    q = q.filter(ErrorLog.service != "audit")  # noqa: F821

errors = q.order_by(ErrorLog.created_at.desc()).all()  # noqa: F821

print(f"\nErrors (service!=audit): {len(errors)}")

if errors:
    by_type = Counter(e.error_type for e in errors)
    # errors is ordered desc by created_at, so the first one per type is
    # the most recent — use it for both the sample message and stack trace.
    sample_msg = {}
    sample_trace = {}
    sample_request_id = {}
    for e in errors:
        if e.error_type not in sample_msg:
            sample_msg[e.error_type] = e.error_message or ""
            sample_trace[e.error_type] = e.stack_trace or ""
            sample_request_id[e.error_type] = e.request_id or ""

    print(f"\nTop {TOP_N} error_types:")
    for etype, count in by_type.most_common(TOP_N):
        sample = sample_msg[etype][:120].replace("\n", " ")
        req_id = sample_request_id[etype] or "-"
        print(f"  {count:>5}  {etype}   [latest request_id={req_id}]")
        print(f"         | {sample}")
        trace = sample_trace[etype]
        if TRACE_LINES > 0 and trace:
            lines = trace.rstrip().splitlines()
            tail = lines[-TRACE_LINES:]
            truncated = len(lines) > TRACE_LINES
            print(f"         | stack_trace (tail {len(tail)} of {len(lines)} lines):")
            if truncated:
                print("         |   ... (older frames truncated)")
            for line in tail:
                print(f"         |   {line}")

    print(f"\nMost recent {RECENT_N}:")
    for e in errors[:RECENT_N]:
        path = (e.path or "")[:40]
        msg = (e.error_message or "")[:80].replace("\n", " ")
        ts = e.created_at.isoformat(timespec="seconds") if e.created_at else "?"
        print(
            f"  {ts}  {e.service:<8}  "
            f"{str(e.status_code or '-'):<4}  "
            f"{(e.method or '-'):<5}  {path:<40}  "
            f"{e.error_type}: {msg}"
        )
else:
    print("  (no errors in window)")
