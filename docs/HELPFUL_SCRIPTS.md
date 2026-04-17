# Helpful Scripts

Catalog of one-off ops scripts for quick audits and manual interventions
against Palateful's production database/services. All of them run
against the live DB, so read the section on each before copy-pasting.

## Runners

- **`bin/prod-script <path.py>`** — runs a local Python file inside the
  prod API ECS task via `aws ecs execute-command`. The prelude preloads
  `db`, `database`, and every SQLAlchemy model + enum, so scripts can
  reference `ErrorLog`, `User`, etc. directly with no imports. Output
  streams back to your terminal.
- **`bin/prod-console`** — same context but interactive (REPL).
- **`bin/prod-logs`** — tail/query CloudWatch logs.
- **Local, direct-to-DB**: set `DATABASE_URL=<prod-url>` and run
  `python scripts/python/...` when the script uses raw SQLAlchemy
  (e.g. `services/api/scripts/promote_admin.py`).

### bin/prod-script gotchas

- `aws --cask session-manager-plugin` must be installed.
- Do **not** use `from __future__` imports in scripts — the prelude is
  concatenated above your code, so `__future__` would no longer be on
  line 1.
- Scripts should be **read-only by default**. If a script mutates,
  follow the `promote_admin.py` pattern: dry-run unless `--yes`, and
  write an audit row to `error_logs` with `service="audit"`.
- Tunables via env vars must be **exported in your local shell**
  before calling `bin/prod-script` (ECS exec forwards the inherited
  environment).

## Common audits

### Error landscape — `scripts/python/audit_errors.py`

Summarizes the `error_logs` table: per-service row count, top error
types with sample messages, and the most recent N rows. Good first
stop after a deploy or a user-reported issue.

```bash
# Default: last 24h.
bin/prod-script scripts/python/audit_errors.py

# Widen the window.
AUDIT_HOURS=168 bin/prod-script scripts/python/audit_errors.py

# Include the audit-trail rows (promote_admin writes, etc.).
AUDIT_INCLUDE_AUDIT=1 bin/prod-script scripts/python/audit_errors.py

# Show more error types / more recent rows.
AUDIT_TOP=20 AUDIT_RECENT=30 \
  bin/prod-script scripts/python/audit_errors.py

# Longer stack-trace tail per error_type (or 0 to hide traces).
AUDIT_TRACE_LINES=60 bin/prod-script scripts/python/audit_errors.py
```

Output sections:

1. **Total rows** — by `service` column (api, audit, worker, parser).
2. **Top error_types** — grouped counts, sample message, latest
   `request_id`, and the tail of the most recent stack trace per type.
3. **Most recent** — one row per error, with timestamp, status code,
   method, path, and truncated message.

Rows with `service="audit"` are excluded from the "real errors" views
by default — that namespace is for script-authored audit trails (see
`promote_admin.py`), not application errors.

## Common mutations

### Grant/revoke admin — `services/api/scripts/promote_admin.py`

Runs locally against `DATABASE_URL` (not via `bin/prod-script` — it
boots its own engine). Dry-run unless `--yes`, writes an audit row.

```bash
# Dry-run: print target user + planned change.
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email someone@example.com

# Commit the promotion.
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email someone@example.com --yes

# Revoke.
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email someone@example.com --demote --yes
```

Exit codes: `0` success/no-op, `2` no match or multiple matches, `1`
other errors. Idempotent.

## Adding a new script

- If it runs inside the prod container (uses `db`/models), put it in
  `scripts/python/` and run via `bin/prod-script`.
- If it manages its own SQLAlchemy engine and can run locally against
  `DATABASE_URL`, put it in `services/api/scripts/`.
- For any mutation, follow the dry-run-by-default + audit-row pattern
  from `promote_admin.py`.
- Keep scripts self-contained: a single file, stdlib + sqlalchemy
  only, with a docstring that shows usage examples.
