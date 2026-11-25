# Claude Code Reference

> **IMPORTANT:** ALWAYS use `npx nx` commands whenever possible instead of direct commands.

## Project Overview

Palateful is an NX monorepo with Python microservices (FastAPI) and Flutter mobile frontend. This is a kitchen management app with AI-powered recipe and ingredient features.

## Key References

- **`docs/`** - Feature/design docs (MVP, import pipeline, shared shopping cart, calendar, invitations, search, recipe experience, deployment, eval). Source of truth for schema and endpoints is the code itself (`services/api/src/db/models/`, `services/api/src/routers/`).
- **`_bmad-output/planning-artifacts/epics.md`** - Current roadmap and epic status — **primary source for what to do next**
- **`_bmad-output/planning-artifacts/architecture.md`** - Current system architecture
- **`ANDROID.md`** - Play Store release runbook (single operator, Day 1 signup → Day 3 first tag). See `epic-android-play-console-launch` for epic-level context.
- **`app/lib/core/state/README.md`** - MutationBus convention (emit/subscribe patterns, coalescer recipe, WS-lowering recipe). Ships the `mutationFailureCopy` map, the `showMutationFailureSnackbar` helper, and the `pumpWithMutation` test helper used by every reactivity regression test.
- **`tools/no-silent-catch-check.sh`** - CI grep guard that blocks PRs where a feature-service catch block silently swallows an exception. Allowlist in `tools/silent-catch-allowlist.txt` (format: `file:lineno:rationale`, reviewer sign-off required).
- **`tools/red-artifacts.txt`** - Registry of tests-first RED artifacts merged to `main` ahead of their implementation. A RED artifact **may** merge, but it **must** be registered here in the same commit, or it turns the shared `ci.yml / test` gate red for every unrelated PR until the workstream lands (format: `path:story-hash:rationale`). Registered files are dropped from default pytest collection by a `collect_ignore` conftest in their test root (reference: `libraries/utils/test/conftest.py`); run them with `PYTEST_RUN_RED=1`. **The commit that turns the artifact GREEN must delete its entry** — a stale entry means the story shipped with its own acceptance test not running.

## Project Structure

```
palateful/
├── services/           # Python microservices (api, migrator, parser, worker)
├── libraries/          # Shared Python libraries (utils, test_helper)
├── docs/               # Documentation
├── terraform/          # AWS infrastructure
├── archive/            # Original Next.js implementation (reference)
└── scripts/            # Utility scripts
```

## Development Commands

```bash
# Build Docker images
npx nx run api:docker-build
npx nx run migrator:docker-build

# Start all services (primary dev workflow)
docker compose up

# Run migrations (with migrate profile)
docker compose --profile migrate up migrator

# Install dependencies (when needed)
npx nx run api:install
npx nx run migrator:install

# Generate lock files
npx nx run-many -t lock

# Run migrations locally (requires DATABASE_URL)
npx nx run migrator:migrate

# Lint/Test
npx nx run api:lint
npx nx run api:test
```

## Technology Stack

- **API**: FastAPI, SQLAlchemy 2.0 async, PostgreSQL 16 with pgvector
- **Auth**: Auth0 with JWT
- **AI**: OpenAI (gpt-4o-mini), HunyuanOCR for image processing
- **Infrastructure**: AWS (ECS Fargate, RDS, API Gateway, Lambda)
- **Package Manager**: Poetry (Python), Yarn (Node/NX)

## Environment Variables

See `.env.example` for required configuration. Key vars:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_CLIENT_ID` - Auth0 config
- `OPENAI_API_KEY` - OpenAI API key

## Ops Scripts

Scripts in `services/api/scripts/` are one-off ops tools that talk directly
to the database via `DATABASE_URL`. They do not require the FastAPI app to
be running. Every mutation writes an audit row to `error_logs` with
`service="audit"` so the change is queryable without polluting error
dashboards (which filter on `service="api"`).

### `promote_admin.py` — grant/revoke admin by email

```bash
# Dry-run (default): prints target user + planned change, no writes.
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email leonid@ac93.org

# Commit the promotion.
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email leonid@ac93.org --yes

# Revoke admin (mistake recovery or offboarding).
DATABASE_URL=<prod-url> python services/api/scripts/promote_admin.py \
    --email someone@example.com --demote --yes
```

Exit codes: `0` success / no-op, `2` no match or multiple matches, `1`
other errors. Script is idempotent: re-running in the target state is a
no-op.

### `fetch_feedback.py` — export user feedback rows

```bash
# Default — last 7 days of unread feedback as CSV to stdout.
DATABASE_URL=<prod-url> python services/api/scripts/fetch_feedback.py \
    > /tmp/feedback.csv

# Last 30 days, all statuses, JSON-lines.
DATABASE_URL=<prod-url> python services/api/scripts/fetch_feedback.py \
    --since 30d --status all --format json > /tmp/feedback.jsonl

# Everything ever, tab-separated.
DATABASE_URL=<prod-url> python services/api/scripts/fetch_feedback.py \
    --since all --status all --format tsv > /tmp/feedback.tsv
```

Flags:
- `--since` — `7d` / `30d` / `90d` / `all` (default: `7d`)
- `--status` — `unread` / `read` / `archived` / `all` (default: `unread`)
- `--format` — `csv` / `tsv` / `json` (default: `csv`)

Streams rows to stdout; memory stays bounded at any window size. Writes
one audit row to `error_logs` at end-of-run (`service="audit"`,
`error_type="FeedbackExport"`) with the filter args + row count.
Read-only — no mutations — so no `--yes` flag is needed.

Exit codes: `0` success (rows emitted), `2` no matching rows
(informational, not a failure), `1` DB / other errors.

### `inspect_user_push.py` — dump a user's push-notification state

```bash
# By email (case-insensitive).
DATABASE_URL=<prod-url> python services/api/scripts/inspect_user_push.py \
    --id-or-email leonid@ac93.org

# By UUID.
DATABASE_URL=<prod-url> python services/api/scripts/inspect_user_push.py \
    --id-or-email 34589ac4-f6ef-4adf-9b3b-299084cbc947

# Full FCM tokens (default is 8-char prefixes).
DATABASE_URL=<prod-url> python services/api/scripts/inspect_user_push.py \
    --id-or-email leonid@ac93.org --show-full-tokens
```

Prints (as JSON) the user's `push_tokens` list, `notification_permission_status`,
`notification_preferences`, recent `service="push_notifications"` error
rows, and recent `service="audit"` admin-action rows for the user.
Mirrors the admin `GET /v1/admin/notifications/health/...` endpoint but
works even when the endpoint isn't deployed or is broken.

Flags:
- `--id-or-email` (required) — UUID or email (case-insensitive).
- `--error-limit` — max recent error rows (default 10, max 50).
- `--show-full-tokens` — print full FCM tokens, not prefixes.

Read-only — no mutations, no audit row written. Safe to run freely.

Exit codes: `0` success, `2` no user matched, `1` DB / runtime error.

### `analyze_latency.py` — surface slow endpoints + tasks

```bash
# Default — top-15 endpoints + tasks by p95 over the last 24h (table).
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py

# Pin a CSV baseline before any perf change lands.
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --top 15 --format csv > /tmp/baseline.csv

# Hunt for regressions (recent 24h p95 > 1.5x 7-to-30d baseline p95).
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --format table

# Drill into low-traffic endpoints (no noise floor).
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section endpoints --window 1h --min-samples 0 --top 100
```

Flags: `--window {1h|24h|7d|all}` (default `24h`), `--top <int>` clamped
to `[1,100]` (default `15`), `--format {table|csv|json}` (default
`table`), `--regression-hunt` (implies `--section endpoints`),
`--min-samples <int>` (default `5`; `0` disables), `--section
{endpoints|tasks|both}` (default `both`). Default sort: **p95 desc**.

Read-only — no mutations, no audit row. See `docs/PERFORMANCE_OPS.md`
for baseline-capture / post-upgrade diff recipes.

Exit codes: `0` rows emitted, `2` empty (informational), `1` DB /
runtime error.

### `audit_errors.py` — surface common errors from `error_logs`

Two modes: **aggregate** (triage — "what's on fire?") and **drill**
(debug — "what do I need to fix?"). Always triage first to find the
noisy groups, then drill into one at a time.

**Aggregate mode** (default):

```bash
# Top-20 (service, error_type) groups over the last 24h.
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py

# Last hour, all services including audit rows, JSON-lines.
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --window 1h --include-audit --format json

# Drill into one service, last 7 days, keep only groups with >= 5 hits.
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --service api --window 7d --min-samples 5 --top 50

# CSV snapshot for diffing against a future run.
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --window 7d --format csv > /tmp/errors-baseline.csv
```

Aggregate output includes, per group, the most-recent non-null sample
of `status_code`, `method`, `path`, `request_id`, `user_id`,
`error_code`, `stage`, `import_item_id`, and `error_message` — enough
correlation handles to hop straight into CloudWatch (`bin/prod-logs`)
or into `--drill` without a second query.

**Drill mode** (`--drill SERVICE:ERROR_TYPE`):

```bash
# Last 20 full rows for api:ValueError over 24h (vertical per-row dump,
# includes stack_trace, request_id, user_id, error_code, import_item_id).
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --drill api:ValueError

# JSON-lines — easiest format when stack traces are multiline.
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --drill api:ValueError --format json --top 50

# Any error_type for one service (empty error_type after the colon).
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --drill push_notifications: --window 7d

# Wider window, big batch for offline triage.
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --drill worker:CreateRecipeTask --window 30d --top 100 --format json \
    > /tmp/recipe-task-failures.jsonl
```

Drill mode emits individual rows, most-recent first, with every
column from the `ErrorLog` model: `id`, `created_at`, `service`,
`error_type`, `error_code`, `status_code`, `method`, `path`,
`request_id`, `user_id`, `import_item_id`, `stage`, `error_message`,
**`stack_trace`**. `--service`, `--include-audit`, and `--min-samples`
are ignored in drill mode (the drill key encodes the service, and
aggregation doesn't apply).

Flags: `--window {1h|24h|7d|30d|all}` (default `24h`), `--top <int>`
clamped to `[1,200]` (default `20`), `--format {table|csv|json}`
(default `table`), `--service <name>` (aggregate only; omit for all
non-audit services), `--include-audit` (aggregate only; include
`service='audit'` rows — excluded by default because those are
admin-action trails), `--min-samples <int>` (aggregate only; default
`1`), `--drill SERVICE:ERROR_TYPE` (switch to drill mode; empty
error_type matches any). Default sort (aggregate): **count desc,
then last_seen desc**. Default sort (drill): **created_at desc**.

Read-only — no mutations, no audit row. Safe to run freely.

Exit codes: `0` rows emitted, `2` empty (informational), `1` DB /
runtime error, or malformed `--drill`.

**What this table does not contain.** A count of zero or one here means
*nothing reached this table*, not *nothing happened*. Telling those apart
takes reading `endpoint.py` and `main.py:166`, not another query: the 4xx
audit writer fires only for an `APIException` raised **inside an endpoint
body**, so every dependency-raised auth failure — expired or invalid token —
is absent by construction. Measured 2026-09-22: `service='api'` had **one row
in the life of the deployment**. The client's view of the same failure lives
in Crashlytics, not here, and `service='client'` rows are only the subset of
failures that held a usable token to send the report with. For the auth class
the two views are disjoint, not complementary — the failures that matter most
are the ones that could not authenticate a report of themselves. Tracked by
`audit4xx1`.

### `delete_user.py` — remove a user and everything referencing them

```bash
# Dry-run (default): prints what WOULD be removed and what would be kept,
# per table, with counts. Nothing is written.
DATABASE_URL=<prod-url> python services/api/scripts/delete_user.py \
    --id-or-email qa@example.test

# Commit. Both confirmations are required, and neither is a bare "yes".
DATABASE_URL=<prod-url> python services/api/scripts/delete_user.py \
    --id-or-email qa@example.test --confirm-email qa@example.test \
    --auth0-disabled --yes
```

**Disable the Auth0 identity FIRST.** `get_current_user` re-provisions on
every authed request (`find_or_create_by` + default calendar + starter
book), so deleting the rows while the identity can still authenticate
recreates the user on the next request. The script **cannot** do this or
check that you did — there is no Auth0 Management API client in the repo,
only JWKS verification — so `--auth0-disabled` is an attestation, not a
verification. What it does do is re-query `--verify-after` seconds later
(default 5) and exit 1 if the user came back.

**"Deleted" does not mean "no trace", and the gap is most of the data.**
Measured against the prod QA identity 2026-09-24: **768 referencing rows,
of which 761 are `client_latencies` on a `SET NULL` FK** — those survive,
unattributed — plus 6 `error_logs` rows, which have **no foreign key at
all** and keep pointing at a user who no longer exists. Removing a test
user therefore does **not** remove the test data it generated. Anyone
sizing prod QA volume should know that before running walkthroughs, not
after. The dry-run prints "removed" and "kept, unattributed" separately
for this reason.

Guards, both deliberate: a second, **different** identifier must agree
with the lookup — `--confirm-email` normally, or `--confirm-name` when
the user has **no email on record** — so a typo in either fails closed.
(Corrected 2026-09-24: the null-email case was originally refused
outright as a deliberate edge case, and the one prod test identity is
exactly that case, so the guard refused the only operation it was built
for. A blank is never accepted as a match; `--confirm-user-id` is
deliberately not offered, because repeating the id the lookup used
guards against mistyping it once but not against pasting the wrong id
twice.) And **admin accounts are refused outright with no override** — a
`--force` flag is one that gets added by reflex. Schema drift also fails
closed: the script reads the FK graph from `information_schema` at run
time and refuses if it finds a blocking FK it does not handle by name
(measured: exactly one, `ingredients.submitted_by_id`).

Writes an audit row (`service="audit"`, `error_type="UserDeletionAudit"`)
carrying the user id and row counts — deliberately not the email or name,
since the row outlives the user.

Exit codes: `0` success or dry-run, `2` no match / multiple matches, `1`
refusal, error, or a deletion that undid itself.

### `qa_cleanup.py` — delete selected QA-owned content (never a user)

```bash
# Dry-run (default): proves each target is in scope, prints, writes nothing.
DATABASE_URL=<prod-url> python services/api/scripts/qa_cleanup.py \
    --id-or-email qa@example.test --confirm-email qa@example.test \
    --recipe <uuid> --ingredient <uuid>

# Commit.
DATABASE_URL=<prod-url> python services/api/scripts/qa_cleanup.py \
    --id-or-email qa@example.test --confirm-email qa@example.test \
    --recipe <uuid> --ingredient <uuid> --yes
```

**Separate from `delete_user.py` on purpose.** This script is the one
intended to hold a *standing* permission grant, and a standing grant takes
the blast radius of the largest thing the granted script can do. This one
**cannot delete a user at all**; `delete_user.py` can, so it keeps needing
per-case approval.

**Safe by construction, not by care.** Every target is an explicit row id
that must prove it is in scope before anything is written:

1. **Owned, and owned only by them** — a recipe's book must be owned by the
   confirmed user *and* have no other members. Recipes carry no user FK:
   ownership runs `recipes.recipe_book_id` → `recipe_book_users(role='owner')`,
   and books are shareable, so "they own it" alone would delete content other
   members can see.
2. **Unreferenced** — an `ingredients` row is deletable only when nothing
   references it, re-checked **inside the transaction, after** the owned
   deletes. That ordering is what lets a row referenced only by the user's
   own deleted recipe qualify while a row someone else uses never can.

Rule 2 exists because ingredient rows are **not owned**: measured
2026-09-24, both junk `mashed bananas` rows had `submitted_by_id = NULL`,
and 51 of 130 ingredient rows have no submitter. User-scoping cannot reach
them, and name-matching them would be an unscoped delete wearing a
QA-cleanup label. Rule 2 assumes `ingredients` is a bag of display names
rather than a shared catalogue (`utils/models/ingredient.py`); if that
changes, `test_ingredients_are_not_a_shared_catalogue` fails rather than
the script silently widening.

Same guards as `delete_user.py`: a second, different identifier must
agree with the lookup (`--confirm-email`, or `--confirm-name` when the
user has no email), and **admin accounts are refused outright with no
override**.

Writes an audit row (`service="audit"`, `error_type="QaCleanupAudit"`).

Exit codes: `0` success or dry-run, `2` no match / multiple matches, `1`
refusal or an out-of-scope target.

<!-- devx:start -->
# CLAUDE.md — Agent context for this project

This block is managed by `/devx-init`. Hand-edits inside the markers will
trigger an INTERVIEW.md merge-conflict entry on the next `/devx-init` run;
add your own context **outside** the markers (above or below).

## What this project is

Kitchen-management app with AI-powered recipe, pantry, and meal-planning features.

## Strategic axes

| Axis | Setting |
|---|---|
| `mode` | **YOLO** |
| `project.shape` | **mature-refactor-and-add** |
| `thoroughness` | **send-it** |

Source of truth: `devx.config.yaml`. Don't add one-off mode-aware logic
without updating `docs/MODES.md` first.

## Backlog files

| File | Written by | Read by |
|---|---|---|
| `DEV.md` | `/devx-plan`, `/devx`, ManageAgent | `/devx`, `/devx-test` |
| `PLAN.md` | `/devx-plan`, ManageAgent | `/devx-plan`, you |
| `TEST.md` | `/devx`, `/devx-test`, FocusAgent | `/devx-test` |
| `DEBUG.md` | any agent (CI red, flake, regression) | `/devx-debug` |
| `FOCUS.md` | FocusAgent, you | `/devx-plan`, `/devx-debug` |
| `INTERVIEW.md` | any agent blocked on a human decision | you |
| `MANUAL.md` | any agent when action requires a human | you |
| `LESSONS.md` | LearnAgent, you (`--add`) | ManageAgent, you, mobile |

INTERVIEW = decisions you must make. MANUAL = actions you must take. Don't
conflate.

## Spec file convention

```
<type>/<type>-<hash>-<timestamp>-<slug>.md
```

Frontmatter carries `hash`, `type`, `created`, `title`, `from:`, `spawned:`,
`status`, `owner`, `branch`. Body has Goal, Acceptance criteria, Technical
notes, Status log (append-only). The Status log is the request history —
where a thing came from, where it went.

## Working agreements

- **Don't duplicate business logic.** Wrap existing endpoints, tools,
  utilities.
- **One commit per story / sub-task.** Atomic, reviewable.
- **Fix forward.** If review finds issues, fix them in the same item; don't
  open follow-ups for in-scope work.
- **Status log is append-only.** Add lines; don't rewrite history.
- **Worktrees are isolation, not staging.** Don't run a non-`/devx` flow
  inside a worktree; don't share a worktree across agents.
<!-- devx:end -->
