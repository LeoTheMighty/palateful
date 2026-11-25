# Helpful Scripts

Catalog of one-off ops scripts for quick audits and manual interventions
against Palateful's production database/services. All of them run
against the live DB, so read the section on each before copy-pasting.

## Runners

- **`bin/prod-script <path.py> [args…]`** — runs a local Python file inside
  the prod API ECS task via `aws ecs execute-command`. The prelude preloads
  `db`, `database`, and every SQLAlchemy model + enum, so scripts can
  reference `ErrorLog`, `User`, etc. directly with no imports. Arguments
  after the script reach it as `sys.argv[1:]` (see below). Output streams
  back to your terminal.
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
  environment). Nothing tests that claim; prefer arguments for a new
  script, which are tested end to end.
- Do **not** rebind `sys` or `time` at any level of a script (e.g.
  `from datetime import time`). The prelude's keepalive thread reads both
  for the life of the process; rebinding one kills it, and Session Manager
  then cuts the stream after ~1 s of silence. This fails only in prod.
  Guarded for the dev-request scripts by
  `services/api/tests/test_dev_requests_channel.py`.
- Take the database URL from `utils.constants.DATABASE_URL`, never
  `os.environ["DATABASE_URL"]`: prod tasks set only `DB_HOST`/`DB_PORT`/
  `DB_NAME`/`DB_USERNAME`/`DB_PASSWORD`/`DB_SSLMODE`, which
  `utils.constants` composes. A script reading the variable directly
  passes locally and fails in prod.

### bin/prod-script arguments

```bash
bin/prod-script services/api/scripts/dev_requests_read.py adopt <id> <sha256>
```

`sys.argv` inside the task is `[<script path>, args…]`; with no arguments it
is `[<script path>]`, so `argparse` sees `[]` as before. Arguments are an
instruction that runs with prod credentials, so they cross as **data**:
JSON-encoded, base64'd into the same payload as the script, and decoded by
the prelude. None is ever interpolated into the shell command or into Python
source; `$(…)`, backticks, quotes and `;` arrive verbatim and run nothing.

Refused locally (exit 1, `aws` never called), naming the argument's
position but never its value:

- an argument that is not valid UTF-8;
- one containing a control or format character (Unicode `Cc`/`Cf`:
  newline, tab, CR, ESC, zero-width, bidi override);
- an argument list that encodes to more than 4096 bytes.

Arguments are ids, hashes and enum codes; none needs any of those. Base64 is
not encryption: anything that records the `--command` string, or reads the
local process list, sees the arguments. **Never pass a secret or request
text as an argument.** Calls with arguments need `python3` on the local
`PATH` (the encoder); calls without do not.

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

## Operator channel — dev requests

Two scripts speak the `DEVREQ1` record protocol to the orchestrator bridge
(workstream `admin-request-intake`, PRD FR-5…FR-13). They run standalone
against `utils.constants.DATABASE_URL` or, as the bridge runs them, through
`bin/prod-script`. Both import only stdlib, SQLAlchemy and
`utils.constants`, because the bridge runs `origin/main`'s copy against
whatever image is deployed.

**Output.** Every machine-readable line is `DEVREQ1 ` plus one ASCII-only
JSON object; every run ends with exactly one
`{"kind":"end","v":1,"ok":…,"count":…,"error":…}`. A consumer strips CSI
escapes and trailing `\r`, keeps only `^DEVREQ1 (\{.*\})$` lines, and treats
the run as failed unless there is exactly one `end`, last, with a matching
`count` and `ok: true`. The process exit code (`0` ok, `1` otherwise) is
not part of the contract — under `bin/prod-script` it is `aws`'s. Errors are
enum codes, never exception text.

### `services/api/scripts/dev_requests_read.py` — read-only

Every query runs in `SET TRANSACTION READ ONLY` (Postgres refuses a write),
with `statement_timeout` 15 s and `lock_timeout` 5 s. No audit row.
Nothing is printed until the transaction has closed.

```bash
# Open (non-terminal) rows: ids, hashes, statuses. No title/body/done-when.
bin/prod-script services/api/scripts/dev_requests_read.py poll
# Counts and lags: total, by_status, received_lag_s_p50/max,
# stale_undecided (undecided > 7 days), accepted_without_audit.
bin/prod-script services/api/scripts/dev_requests_read.py metrics
# The text, once, for adoption: only when the row is submitted/received,
# stored hash == recomputed hash == <sha256>, and the submitter is a
# current admin.
bin/prod-script services/api/scripts/dev_requests_read.py adopt <id> <sha256>
# A human reading a request. NEVER inside an LLM session.
bin/prod-script services/api/scripts/dev_requests_read.py show <id>
```

`poll` and `metrics` select no text column. `show` prints plain text under a
banner, prefixes every text line with `  | ` and escapes control/format
characters, so request text can neither pass for a `DEVREQ1` record nor
drive the terminal; it also says whether the stored hash still matches.

Error codes: `invalid_argument` (any argument outside the grammar; checked
before connecting), `not_found`, `wrong_status`, `sha_mismatch`,
`submitter_revoked` (adopt), `db_error` (any database failure, including a
table that is not migrated yet), `internal_error` (anything else).

### `services/api/scripts/dev_requests_write.py` — the only writer of bridge-owned statuses

```bash
bin/prod-script services/api/scripts/dev_requests_write.py \
    transition <id> <from> <to> [--sha <hex64>] [--reason <code>]
```

| Edge | Arguments |
|---|---|
| `submitted` → `received` | none |
| `submitted`/`received` → `accepted` | `--sha` (re-checked; stamps `adopted_at`) |
| `submitted`/`received` → `declined` | `--reason duplicate\|wont_do\|unclear\|unsafe` |
| `submitted`/`received` → `withdrawn` | `--reason submitter_revoked` |

Every other edge is `illegal_transition` (the widening edges until arq106).
`<id>` is a canonical lowercase UUID; a repeated, abbreviated or
inapplicable option is `invalid_argument`. All of that is decided before
connecting. Then, in one transaction with the row locked: already at `<to>`
→ `changed: false`, nothing written (for `accepted`, only with the same
hash); at `<from>` → applied, with exactly one audit row
(`service="audit"`, `error_type="DevRequestTransition"`,
`"dev_request <id8>: <from> -> <to>[ reason=<code>]"`, `user_id` = the
submitter); anywhere else → `conflict`. A row lock held elsewhere ends
`db_error` after 5 s rather than queueing. Output:
`{"kind":"transition","id","id8","from","to","changed"}`, printed only after
commit.

Error codes: `invalid_argument`, `illegal_transition`, `not_found`,
`conflict`, `sha_mismatch`, `submitter_revoked`, `db_error`,
`internal_error`.

Tests: the locked evals `_devx/workstreams/admin-request-intake/evals/E-1`,
`E-2`, `E-4` (run through their wrappers), plus
`services/api/tests/test_dev_requests_channel.py` and
`test_dev_requests_scripts.py`. They need a reachable Postgres
(`docker compose up -d db`).

## Adding a new script

- If it runs inside the prod container (uses `db`/models), put it in
  `scripts/python/` and run via `bin/prod-script`.
- If it manages its own SQLAlchemy engine and can run locally against
  `DATABASE_URL`, put it in `services/api/scripts/`.
- For any mutation, follow the dry-run-by-default + audit-row pattern
  from `promote_admin.py`.
- Keep scripts self-contained: a single file, stdlib + sqlalchemy
  only, with a docstring that shows usage examples.
