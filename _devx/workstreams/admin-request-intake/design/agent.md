# Design — Admin Request Intake

<!-- Stage: Design. Gate: `devx gate coverage 1e84ad` (design mode — one
     tri-state row per G-/UC-/CAP-/FR- ID in prd/agent.md). Hard rule: don't
     plan here. No phases, no tasks — design is the approach, not the
     sequence. Citations are to palateful origin/main 80e5d005 unless they
     say otherwise; research answers are in design/research.md (RQn). -->

## Overview

- **Objective**: Give Palateful the request side of the admin-request
  pipeline: a place to store a request, a way for any admin to file one,
  and an operator-only channel the laptop bridge uses to see, adopt and
  track requests, without any submitter text reaching the laptop before
  Leo adopts it. Then extend the same channel to faults and to the row
  bookkeeping that routing needs.
- **Solution**: One new table whose model module owns the status set and
  the text normalization. One admin endpoint. `bin/prod-script` learns to
  forward arguments. Two self-contained operator scripts — one read-only,
  one write-only — speak a framed, versioned record protocol that survives
  the ECS-exec stream. A minimal web-admin form calls the endpoint. Faults
  and routing are new modes of the same two scripts, not new channels.

## Constraints

- **The laptop reaches the database only through `bin/prod-script`.** RDS is
  private (design PR #124 §1), and the bridge must not get an
  internet-reachable credential.
- **`bin/prod-script` ships one file and forwards nothing.** It takes only
  `$1` (`bin/prod-script:14`) and runs prelude + script through
  `python -u -c` (RQ6).
- **The stream is noisy.** stdout and stderr arrive merged through a TTY,
  CRLF, with keepalive escapes every 0.5 s (`bin/prod-script:85-95`) and
  banner lines; the exit code is aws's, not the script's (`:181-183`).
- **Prod has no `DATABASE_URL` variable.** Tasks get `DB_*`
  (`terraform/modules/ecs/main.tf:291-306`); `utils.constants` composes the
  URL (`libraries/utils/utils/constants.py:19-42`).
- **The script that runs is `origin/main`'s; the image that runs it may be
  older.** Deploys are automatic on merge now, but a failed or slow deploy
  still leaves the image behind `main`.
- **No `from __future__`** in scripts run by `bin/prod-script`
  (`docs/HELPFUL_SCRIPTS.md:20-22`).
- **API coverage is pinned at 100% branch over `src/`**
  (`services/api/pyproject.toml:34-43`); `scripts/` is outside it.
- **A single-file pytest run in `services/api` exits 1 when green**, because
  `addopts` carries `--cov` and `fail_under = 100` (measured 2026-11-24:
  `test_promote_admin_script.py`, 8 passed, exit 1; exit 0 with
  `--no-cov`).
- **Flutter has no RED registry.** `flutter-test` runs bare `flutter test`
  (`.github/workflows/ci.yml:399-401`; RQ14), so a failing app test cannot
  merge ahead of its code.
- **The admin panel is web-only** and gated to admins by the router
  (`app/lib/core/router/app_router.dart:225-227`, `:633-638`).
- **The repo is public.** No request or fault text in any commit.
- **The merge is the deploy.** `production` has 0 protection rules.

## Risks

- **Submitter text reaches the laptop before adoption** → `poll`, `metrics`
  and every refusal select and print no text column; errors are enum codes,
  never exception text → proven by E-2.
- **The containment check is blind** (it passes because it looks in the
  wrong place) → the same detector must find all three canaries in a
  successful `adopt`, and must fail on a record built with one → proven by
  E-2.
- **The ECS stream mangles records** → ASCII-only JSON, one `write` per line,
  an `end` record with a count; the eval's `aws` shim reproduces CRLF,
  merged escapes and banners → proven by E-1.
- **A script depends on library code the deployed image lacks** → the import
  allowlist (stdlib, SQLAlchemy, `utils.constants`) → proven by E-1.
- **Two bridge runs, or the bridge and a cancel, race on one row** →
  compare-and-set under a row lock, with an explicit `from` → proven by
  E-4.
- **An admin smuggles state through create** → `extra="forbid"`; the server
  sets status, source and submitter → proven by E-3.
- **Leo reads one thing and the agent reads another** → normalization plus a
  hash over every submitter field, re-checked at `adopt` and again at
  `→ accepted` → proven by E-5 and E-1.
- **Fault text carries attacker-chosen content** → only server-emitted
  services, only server-chosen fields, a route template instead of the
  path → proven by E-12.
- **A fault signature churns on every edit, so nothing ever dedupes** → no
  line numbers in the signature → proven by E-13.
- **Routing re-points a row it should not** → `move` is compare-and-set on
  the current workstream → proven by E-14.

## Trade-offs

- **Two scripts over one.** The read script contains no write SQL, so it can
  be audited as read-only by reading it; the cost is a ~25-line record
  emitter duplicated in both, held together by E-1 and E-2 parsing both
  with one consumer.
- **Self-contained scripts over a shared `utils` helper.** A shared module
  would be cleaner and breaks under the image-lag constraint. The cost is
  the content hash existing twice (the endpoint's helper and the read
  script); E-1 asserts that the two agree on the same row.
- **The full status set and the source columns in the first migration over
  one migration per slice.** One migration, and no deploy-ordering problem
  later; the cost is a CHECK that lists states slice 1 never writes.
- **Argument forwarding in `bin/prod-script` over environment variables or a
  generated script per call.** `docs/HELPFUL_SCRIPTS.md` claims ECS exec
  forwards the local environment, but nothing tests that, and the API
  container has no reason to inherit the laptop's shell. A generated script
  is a code-injection surface. Forwarding argv inside the base64 payload is
  backward compatible and testable locally.
- **Live-Postgres evals over SQL-text mocks.** The repo's script tests mock
  SQL text (`services/api/tests/test_promote_admin_script.py:37-68`), which
  cannot be written before the SQL exists and would pin an implementation
  rather than the contract. A throwaway database per test session costs
  under a second (RQ10).
- **`show` in a plain terminal over shipping the panel detail screen in
  slice 1.** Keeps the slice to one endpoint; the cost is that Leo reads
  requests at the laptop until the widening lands.
- **Compare-and-set with an explicit `from` over "set status".** Retries
  become no-ops, and a race becomes a loud `conflict` instead of a silent
  overwrite.
- **A partial unique index for "one open row per signature" over a check
  in the write script alone.** Two `open-fault` calls racing would both
  pass a read-then-insert check; the index makes the second insert fail,
  and the script reports the existing row.
- **Audit `user_id` = the submitter over the operator or null.** The
  operator is always Leo, so recording him adds nothing; the submitter is
  what `audit_errors.py` and `inspect_user_push.py` already filter by.
- **An adopted fault becomes a row over staying bridge-side.** Faults then
  share states, the panel and the signature index for routing; the cost is
  two nullable columns in slice 1's migration.

## Out of scope

- Everything in the PRD's Non-goals. Of note for design: the bridge, the
  router, devx split/combine, AWS-side fault sources, and `client` rows.

## Assumptions

- **ECS exec merges stderr into the stream through a TTY.** The shim
  reproduces the merged form; if prod turns out to separate them, the
  consumer rule (strip escapes, match the prefix) still holds. Revision
  trigger: a real `poll` run whose records fail to parse.
- **`aws ecs execute-command`'s exit code says nothing about the script.**
  The contract already ignores it.
- **The API container can enumerate its own routes for FR-18.** If
  importing the app inside the task is too heavy, a route-template list is
  generated at build time instead. Revision trigger: slice 2 design check.
- **Prod stack traces name container paths** (`/app/src/…` for the API,
  `site-packages/utils/…` for the library). Revision trigger: one
  read-only `bin/prod-script` look at real `stack_trace` values before slice
  2's frames mapping is written.
- **Admins stay a handful.** 5 creates per hour each is generous.

## Discarded considerations

- **`fetch_feedback.py` as the tap** — needs a direct `DATABASE_URL`, RDS is
  private, and it writes an audit row per run (design PR #124 §1).
- **An authenticated API path for the bridge** — a credential the internet
  can reach.
- **Reusing `user_feedbacks`** — mixed trust, wrong side effects, wrong
  status semantics (PR #124 §5).
- **Routing by an LLM reading the text** — breaks containment (PRD FR-21).
- **Environment-variable arguments** — unverified transport (Trade-offs).
- **A Flutter RED registry in this workstream** — real work in another
  surface; app expectations are tests-after instead.
- **Trusting `client` error rows as fault signals** — written through a
  user endpoint (`services/api/src/api/v1/user/record_client_error.py:63`).

## Wrap, don't duplicate

- Reuses:
  - `require_admin_async` (`services/api/src/dependencies.py:523-537`) for
    admin-only create.
  - `AsyncEndpoint`, `success`, `failure` (`utils.api.endpoint`; RQ3) and
    the `admin_router` (`services/api/src/routers/v1/admin_router.py:26`).
  - The in-memory rate-limit pattern
    (`services/api/src/api/v1/user/create_user_feedback.py:41-60`).
  - `Base` (`libraries/utils/utils/models/base.py:9-14`) and the
    package export list (`libraries/utils/utils/models/__init__.py:56`,
    `:108`).
  - The audit-row pattern of `promote_admin.py`
    (`services/api/scripts/promote_admin.py:75-110`): `service="audit"`
    rows in `error_logs`.
  - `bin/prod-script` itself, its prelude and its sentinel.
  - `utils.constants.DATABASE_URL` for the scripts' engine.
  - The dashboard tile and route pattern
    (`app/lib/features/admin/admin_dashboard_screen.dart:771-781`,
    `app/lib/core/router/app_router.dart:662-669`) and `_dio` admin calls
    (`app/lib/core/services/api_client.dart:1104`).
  - The RED registry (`tools/red-artifacts.txt`,
    `libraries/utils/utils/testing/red_registry.py:60-74`) and the
    `workstream-evals` runner (`devx.config.yaml` `projects:`).
- Adds:
  - `dev_requests` table, `DevRequest` model, its status set and its text
    normalization.
  - `POST /v1/admin/dev-requests` (and in the widening, list and cancel).
  - Argument forwarding in `bin/prod-script`.
  - `services/api/scripts/dev_requests_read.py` and
    `services/api/scripts/dev_requests_write.py`.
  - The "Request a change" screen (and in the widening, list and detail).
  - A test harness for the contract evals: a throwaway database, an `aws`
    shim, and a reference consumer.

## Design

### Architecture

| Component | New or existing | Path | Responsibility |
| --- | --- | --- | --- |
| `DevRequest` model + constants | new | `libraries/utils/utils/models/dev_request.py` | Table, CHECKs, `DEV_REQUEST_STATUSES`, `TERMINAL_STATUSES`, `normalize_request_text()`, `content_sha256()` |
| Migration | new | `services/migrator/migrations/versions/<ts>_add_dev_requests.py` | Creates the table; `down_revision` = the head at implementation time (`idupbookname1` today) |
| `CreateDevRequest` | new | `services/api/src/api/v1/admin/create_dev_request.py` | Validate, normalize, hash, rate-limit, insert |
| Admin route | existing file | `services/api/src/routers/v1/admin_router.py` | `@admin_router.post("/dev-requests")` |
| `bin/prod-script` | existing, changed | `bin/prod-script` | Forward `"$@"` after the script as `sys.argv[1:]` |
| Read script | new | `services/api/scripts/dev_requests_read.py` | `poll`, `adopt`, `show`, `metrics`; later `faults`, `fault-adopt` |
| Write script | new | `services/api/scripts/dev_requests_write.py` | `transition`; later the widening edges, `open-fault`, `move` |
| New-request screen | new | `app/lib/features/admin/admin_dev_request_new_screen.dart` | Form → create → show id8 |
| Dashboard tile + route | existing files | `admin_dashboard_screen.dart`, `app_router.dart`, `api_client.dart` | Entry, `/admin/dev-requests/new`, `createDevRequest()` |
| Widening endpoints and screens | new | see Widening surfaces | List, detail, cancel; panel list and detail |
| Bridge | external | `~/.claude/orchestrator` | Everything in PRD FR-13 |

How they compose for one request:

1. The form posts to the endpoint, which normalizes the three fields, hashes
   them, and inserts a `submitted` row.
2. The bridge runs `bin/prod-script dev_requests_read.py poll`. The read
   script opens its own engine from `utils.constants.DATABASE_URL`, selects
   only non-text columns, and prints `DEVREQ1` records and an `end`.
3. The bridge runs `dev_requests_write.py transition <id> submitted
   received`. The write script locks the row, checks the edge, updates it
   and inserts one audit row in one transaction.
4. On Leo's adopt, `adopt <id> <sha>` returns the text once; the bridge
   quarantines it and runs `transition … accepted --sha <sha>`, which
   re-checks the hash and the submitter before writing.

#### Failure handling

| Failure | Disposition |
| --- | --- |
| Table missing (script ahead of migration) | `end` with `ok: false`, `error: db_error`; no partial records |
| Any database exception | rollback; `db_error`; the exception text is never printed |
| Bad argument | `invalid_argument` before any query |
| Row not in `from` | `conflict`; nothing written |
| Edge not given to the bridge | `illegal_transition`; nothing written |
| Hash differs at `adopt` or `→ accepted` | `sha_mismatch`; nothing written |
| Submitter null or not admin at `adopt` or `→ accepted` | `submitter_revoked`; nothing written |
| Stream cut before `end` | consumer treats the run as failed; the write was atomic, so a retry is a no-op or `conflict` |
| Rate limit hit | 429 with `retry_after_s`, no row |

### Interfaces

The cross-repo contract is the PRD's (FR-5 to FR-13, FR-18 to FR-22); this
section adds only what the PRD leaves to design.

- **`bin/prod-script <script.py> [args…]`**: the local side JSON-encodes
  `"$@"` (after the script) and base64s it; the prelude's first statement
  sets `sys.argv = [<script path>] + json.loads(base64.b64decode(…))`,
  substituted like the sentinel placeholder. No arguments → `sys.argv =
  [<script path>]`; `argparse` then sees `[]`, as it does today.
- **Script CLI**: `argparse` subcommands (`poll`, `adopt`, `show`, `metrics`,
  later `faults`, `fault-adopt`; `transition`, later `open-fault`, `move`),
  each script exposing `main(argv: list[str] | None = None) -> int`, as
  `promote_admin.py` does (`:142`). `main` catches everything, so the
  `end` record is always the last line.
- **Record emitter** (in each script): `emit(kind, **fields)` writes
  `"DEVREQ1 " + json.dumps({"kind": kind, "v": 1, **fields},
  ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"` in one
  `sys.stdout.write`, then flushes; `end(ok, error)` counts what was
  emitted.
- **Model helpers**: `normalize_request_text(value: str) -> str` (NFKC,
  drop `Cc`/`Cf` except `\n`/`\t`, strip) and `content_sha256(title, body,
  done_when) -> str` (PRD FR-2's canonical JSON). The endpoint uses both;
  the read and write scripts carry their own copy of the hash (Trade-offs).
- **Endpoint**: `CreateDevRequest.Params` with `extra="forbid"`; field
  validators normalize and reject blank-after-normalization; length limits
  are checked on the normalized value, matching the CHECKs.
- **Panel**: `ApiClient.createDevRequest({title, body, doneWhen})` →
  `POST /v1/admin/dev-requests`; the screen maps 403/422/429 to messages.

### Data

`dev_requests`, per PRD FR-1, with:

- CHECKs: `length(title) BETWEEN 1 AND 120`, `length(body) BETWEEN 1 AND
  4000`, `done_when IS NULL OR length(done_when) BETWEEN 1 AND 1000`,
  `content_sha256 ~ '^[0-9a-f]{64}$'`, `status IN (…13…)`, `target =
  'palateful'`, `priority IS NULL OR priority IN ('low','normal','high')`,
  `source IN ('admin','fault')`, `(source = 'fault') = (fault_signature IS
  NOT NULL)`.
- Indexes: `(status, created_at)` for `poll`; `(submitter_id)`; a partial
  unique index on `fault_signature` where `status` is not terminal, so one
  signature has at most one open row (FR-20).
- `pr_urls` JSONB default `'[]'`; `updated_at` from `Base`; `adopted_at`,
  `synced_at` nullable.
- Retention: rows are kept. A deleted submitter nulls `submitter_id`.
- Audit rows: `error_logs` with `service="audit"`,
  `error_type="DevRequestTransition"` (later `DevRequestFaultOpen`,
  `DevRequestMove`), `user_id` = the submitter (null for faults),
  `error_message` = `"dev_request <id8>: <from> -> <to>[ reason=<code>]"`.

### Widening surfaces

The widening reuses the feedback inbox's shapes; only the differences are
listed.

- **List** (`services/api/src/api/v1/admin/list_dev_requests.py`, new):
  mirrors `ListFeedback` (`services/api/src/api/v1/admin/list_feedback.py:26-58`
  — count, then `created_at DESC`, bounded offset/limit) with a status
  filter whose `all` drops the filter. Items carry no `body` and no
  `done_when`; the response carries the server's `now`, so the panel's
  staleness hints do not depend on the device clock.
- **Detail** (`GET /v1/admin/dev-requests/{id}`, new): the one route that
  returns `body` and `done_when`, to admins only, rendered as plain `Text`.
  This is the panel read that replaces `show`.
- **Cancel** (`services/api/src/api/v1/admin/cancel_dev_request.py`, new):
  `UPDATE … SET status = 'withdrawn' WHERE id = :id AND submitter_id =
  :caller AND status IN ('submitted','received')`. Zero rows → 403 when the
  caller is not the submitter, 409 otherwise. It writes the same
  `DevRequestTransition` audit row the write script does. This is the only
  HTTP write besides create; E-3's route allowlist names exactly these
  routes.
- **Panel list and detail** (`app/lib/features/admin/admin_dev_requests_screen.dart`,
  `admin_dev_request_detail_screen.dart`, new): `AdminFeedbackScreen`'s
  filter chips, `RefreshIndicator` and `ListView.builder`
  (`app/lib/features/admin/admin_feedback_screen.dart:172`, `:232-234`),
  plus a status chip per row. The two staleness hints compare `created_at`
  and `synced_at` against the response's `now`.
- **Pipeline fields** (write script, FR-17): one dict maps each detail code
  to its template; `--pr` appends only if `pr_urls` does not already
  contain it (`NOT (pr_urls @> to_jsonb(ARRAY[:pr]))`); `--workstream`
  and `--spec-hash` are set only on `accepted` → `scoping` or by `move`.

### Verification harness

The P0 evals run the real code paths against a real Postgres, because the
contract is what they test.

- **Throwaway database.** `services/api/tests/devreq_harness.py` (new; not
  collected) creates `devreq_eval_<random>` from
  `DEVREQ_EVAL_ADMIN_URL` (default the local and CI server,
  `postgresql://postgres:postgres@localhost:5432/postgres`), creates
  `vector` and `pg_trgm`, runs `Base.metadata.create_all`, and drops it at
  session end. Measured: 51 tables in 0.56 s (RQ10).
- **`aws` shim.** A PATH-first `aws` that answers `ecs list-tasks` with a
  fake ARN and runs `ecs execute-command --command` locally, emitting a
  banner, merging stderr into stdout and converting to CRLF, so the real
  `bin/prod-script` and the real prelude run end to end.
- **Reference consumer.** The PRD FR-6 parsing rule in code, used by every
  eval, so all of them judge output the way the bridge must.
- **API under test.** `from main import app` with `get_async_database`
  bound to the throwaway database and `get_current_user_async` returning a
  real user row (RQ4).
- **Wrappers.** `evals/E-N_*.sh` run `poetry run pytest -o addopts=""
  -p no:cacheprovider <file>` (the coverage-exit constraint), refuse with
  `EVAL-TAMPERED` (exit 3) if the test file or harness differs from its
  pinned sha256, and map the result: all passed → 0; any failure → 1;
  any error, skip or collection problem → `EVAL-WRONG-REASON` (exit 3).
  Missing-feature checks live in test bodies, never in fixtures, so an
  unbuilt feature is a failure and a broken harness is an error.
- **Registry.** Every RED pytest file is registered in
  `tools/red-artifacts.txt` until its phase turns it green.

## Migration plan

- **Schema**: one Alembic revision adds `dev_requests`. CI's `run-migrator`
  runs before `deploy-services` (`.github/workflows/ci.yml:952`, `:1021`),
  so the endpoint never deploys ahead of its table. Downgrade drops the
  table; that is safe until the first real request exists, and lossy after.
- **`bin/prod-script`**: backward compatible; existing one-argument calls are
  unchanged.
- **Scripts ahead of schema**: if the bridge runs a script before the
  migration has deployed, every call ends `db_error` and the bridge changes
  nothing.
- **Panel**: web-only, deployed with `main`; no app-store release involved.
- **Faults and routing**: no schema change; new script modes only.

## Decision log

| Date | Decision | Record |
| --- | --- | --- |
| 2026-11-24 | Faults as slice 2; routing as signals plus `move` | [scope revision](../decisions/2026-11-24-scope-revision-faults-routing.md) |
| 2026-11-24 | Contract evals on live Postgres with sha-pinned wrappers | [eval harness](../decisions/2026-11-24-eval-harness.md) |

## Unresolved design questions

- How the read script gets route templates inside the API task (FR-18) —
  resolved by slice 2's design check; no P0 depends on it.
- The container-path to repo-path mapping for `frames` — resolved by one
  read-only look at prod `stack_trace` values before slice 2; no P0 depends
  on it.

## Glossary

- **Bridge** — the laptop's launchd listener in the orchestrator repo.
- **Operator channel** — `bin/prod-script`, runnable only with the laptop's
  AWS credentials.
- **id8** — the first 8 hex characters of a row's UUID.
- **Signature** — the hash that groups one kind of server error.
- **Quarantine** — the laptop file, outside every repo, that holds adopted
  text.
