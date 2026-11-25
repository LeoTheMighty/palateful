<!-- refined: critique 2026-11-24 (lenses: pm, architect, dev, qa; run by the authoring session — no subagents available) -->
# Plan — Admin Request Intake

<!-- Stage: Plan. Gate: `devx gate coverage 1e84ad` (plan mode — one row per
     E-id; P0 floor: every P0 expectation `full` and naming a runnable
     artifact). Sizing rule: a phase is one cohesive concern with a
     verifiable exit, sized to land as a single reviewable PR. One phase ≙
     one dev spec ≙ one PR. Profile: plan.phase_appetite = coarse. -->

<!-- Leo's breakdown: a thin vertical slice first — one request row, one
     endpoint, one poll, one adopt — proving the whole path; then widen
     along the design's six-phase shape (model+migration, endpoints,
     prod-scripts, panel, bridge, wiring); then faults and routing.
     Phases 1–3 are the slice. 4–6 are the widening. 7–8 are slice 2. The
     bridge and wiring halves of every stage are external gates. -->

## Current state

- No request storage. `user_feedbacks` is user feedback
  (`libraries/utils/utils/models/user_feedback.py:16-18`); `Suggestion` is
  AI meal suggestions.
- `bin/prod-script` runs one local file inside the API task and forwards no
  arguments (`bin/prod-script:14`).
- `services/api/scripts/` holds one-off ops scripts with an audit-row
  pattern (`services/api/scripts/promote_admin.py:75-110`); none speaks a
  machine protocol.
- The web admin dashboard has a feedback tile and inbox
  (`app/lib/features/admin/admin_dashboard_screen.dart:771-781`).
- The bridge does not exist (orchestrator repo, external).

## Desired state

- An admin files a request in the panel; the bridge sees its id and hash
  within one poll; Leo adopts it at the laptop; the text crosses once; the
  row reads `accepted`. (Phases 1–3 plus the bridge.)
- Admins list, read and cancel their requests; the bridge writes pipeline
  progress back. (Phases 4–6.)
- Server faults arrive as bounded, text-free signals; an adopted fault is a
  tracked row; rows follow their work between workstreams. (Phases 7–8.)

## What we're NOT doing

- Anything in `~/.claude/orchestrator` or in devx (external gates below).
- Auto-adopt, auto-merge, panel approval, a CI request guard, identity
  separation.
- Fault signals from `client` rows or from AWS-side sources.
- Any change to `user_feedbacks`, `Suggestion`, or the feedback inbox.
- A Flutter RED registry.

## Risks

**Riskiest phase: Phase 2.** It changes `bin/prod-script`, which every ops
session on this machine uses, and it is the first code whose writes reach
production through the operator channel. Its contract is also the one the
bridge is built against, so a mistake there propagates to another repo.

**What this order exposes.** Phase 1 deploys an endpoint any admin can call
before anything reads its rows, and Phase 3 puts a form in front of admins.
If Phase 3 deploys before the bridge listens, requests pile up `submitted`
with no one told; the "not picked up" hint does not exist until Phase 5. So
Phase 3 merges only after the bridge is installed (External gates).

| Risk | Phase | Blast radius | Rollback |
|---|---|---|---|
| `bin/prod-script` argument change breaks an existing ops call | 2 | med — every ops session | Revert the PR: the change is additive and the old one-argument path is unchanged; E-1 checks a no-argument call |
| A contract mistake ships to the bridge | 2 | med — another repo built on it | Fix forward under `DEVREQ1` if additive; a breaking fix moves both sides to `DEVREQ2` (FR-13.10) |
| Migration lands, then needs reshaping after real rows exist | 1 | low | Before the first real request: revert (downgrade drops the table). After: a forward migration only — not revert-safe |
| Form deploys before the bridge listens | 3 | low — requests wait unseen | Hold the merge on the external gate; revert is safe |
| Rows written by the bridge outlive a revert of the script that wrote them | 6, 8 | low | Revert the code; rows stay valid under the full status CHECK. Not a schema change, so no data migration |
| Live-DB evals flake on a slow CI database | 1, 2 | low | The harness creates its own database; a flake is an error, which the wrapper reports as a wrong reason, never as green |
| The bridge runs `origin/main` scripts against an older image | 2, 6, 7, 8 | low | Scripts import nothing new (E-1); a missing table or column ends `db_error`, and the bridge changes nothing |

## Expectation coverage

| E-id | Priority | Verified in phase | Validation type | Eval artifact | Coverage |
|---|---|---|---|---|---|
| E-1 | P0 | 2 | tests-first | `_devx/workstreams/admin-request-intake/evals/E-1_full_path.sh` | full |
| E-2 | P0 | 2 | tests-first | `_devx/workstreams/admin-request-intake/evals/E-2_containment_canary.sh` | full |
| E-3 | P0 | 1 | tests-first | `_devx/workstreams/admin-request-intake/evals/E-3_operator_only.sh` | full |
| E-4 | P0 | 2 | tests-first | `_devx/workstreams/admin-request-intake/evals/E-4_transitions.sh` | full |
| E-5 | P0 | 1 | tests-first | `_devx/workstreams/admin-request-intake/evals/E-5_normalization.sh` | full |
| E-6 | P1 | 1 | tests-after | `services/api/tests/test_dev_requests_rate_limit.py` | full |
| E-7 | P1 | 3 | tests-after | `app/test/features/admin/admin_dev_request_new_screen_test.dart` | full |
| E-8 | P1 | 3 | human | `_devx/workstreams/admin-request-intake/evals/E-8_live_walkthrough.md` | full |
| E-9 | P2 | 4 | tests-after | `services/api/tests/test_dev_requests_list_cancel.py` | full |
| E-10 | P2 | 5 | tests-after | `app/test/features/admin/admin_dev_requests_list_screen_test.dart` | full |
| E-11 | P2 | 6 | tests-after | `services/api/tests/test_dev_requests_pipeline_fields.py` | full |
| E-12 | P1 | 7 | tests-after | `services/api/tests/test_dev_requests_faults.py` | full |
| E-13 | P2 | 7 | tests-after | `services/api/tests/test_dev_requests_fault_signature.py` | full |
| E-14 | P2 | 8 | tests-after | `services/api/tests/test_dev_requests_routing_writes.py` | full |

E-1 also passes only once Phase 1 is in, since it starts at the create
endpoint; it is listed at Phase 2, where it first can.

## Phase checklist

- [ ] Phase 1: Request storage and the create endpoint (dev spec: arq101)
- [ ] Phase 2: Operator channel — prod-script arguments, read and write scripts (dev spec: arq102)
- [ ] Phase 3: Request-a-change form in the admin panel (dev spec: arq103)
- [ ] Phase 4: List, detail and cancel endpoints (dev spec: arq104)
- [ ] Phase 5: Panel list and detail screens (dev spec: arq105)
- [ ] Phase 6: Pipeline progress fields in the write script (dev spec: arq106)
- [ ] Phase 7: Fault signals — faults and fault-adopt modes (dev spec: arq107)
- [ ] Phase 8: Adopted faults as rows, and routing moves (dev spec: arq108)
**External gates (orchestrator bridge and router, devx split/combine — other repos, O-5):**

- **X-1 — bridge, slice 1** (`~/.claude/orchestrator`). Poll, acknowledge,
  adopt, decline and withdraw exactly as PRD FR-13 says; the launchd plist,
  the `AGENTS` entry, a `render` case for `palateful_request` records, and
  the wake rule that asks Leo. Built against PRD FR-5…FR-13 at this
  workstream's `origin/main`. **Phase 3 merges only after X-1 is
  installed.** The E-8 live walkthrough runs only after X-1 and Phases 1–3
  are deployed. **Phase 4, Phase 5 and Phase 6 start only after E-8 passes**
  — Leo's sequencing: the slice works live, then widen.
- **X-2 — bridge, widening** (`~/.claude/orchestrator`). Derive pipeline
  state from devx outputs at `origin/main`, post `devx: hold` on every PR a
  request produces, handle a submitter revoked after adoption, detect
  stalls. Consumes Phase 6's arguments; nothing in Palateful waits on it,
  but G-5 is measured only once it runs.
- **X-3 — bridge, faults** (`~/.claude/orchestrator`). Poll `faults`, raise
  one event per new signature or doubling, cap questions to Leo at 5 a day,
  collect AWS-side sources. **Phase 7 starts only after Phase 6 has landed
  and X-2 runs;** Phase 7's modes are exercised live only by X-3.
- **X-4 — router** (`~/.claude/orchestrator`). Fit / create proposals from
  PRD FR-21's signals, confirmed by Leo at adoption. **Phase 8's `move` is
  exercised live only by X-4.**
- **X-5 — split and combine primitives** (devx repo; in flight in its own
  session). May land as "prepare both children, inherit no gate verdict, a
  human partitions the expectations". PRD FR-22 needs only a partition of
  row moves, so that outcome suffices; its cost is that every split waits
  on Leo and both children re-run their gates. Blocks no Palateful phase.

## Execution graph

<!-- Gate 3 FAILs a cycle, a phase set ≠ the checklist, or two unordered
     phases changing one file (per their **Files**) without a waiver.
     Emission sets `blocked_by` from `depends_on`. External gates are not
     edges here; they are prose above. -->

```yaml
phases:
  - { id: 1, depends_on: [] }
  - { id: 2, depends_on: [1] }
  - { id: 3, depends_on: [1], parallel_safe: true }
  - { id: 4, depends_on: [2, 3] }
  - { id: 5, depends_on: [4] }
  - { id: 6, depends_on: [2, 3], parallel_safe: true }
  - { id: 7, depends_on: [6] }
  - { id: 8, depends_on: [7] }
waivers: []
```

## Phases

### 1. Phase: Request storage and the create endpoint

**Overview**: The table, the model and its helpers, and `POST
/v1/admin/dev-requests`. First, because every other phase reads or writes
this row. Slice.

**Files**:
- `libraries/utils/utils/models/dev_request.py` — new: `DevRequest`, the
  13 statuses, terminal set, `normalize_request_text()`, `content_sha256()`.
- `libraries/utils/utils/models/__init__.py` — export `DevRequest`.
- `services/migrator/migrations/versions/<ts>_add_dev_requests.py` — new:
  the table with every CHECK and index in design § Data; `down_revision` =
  the head when the phase starts (`idupbookname1` today).
- `services/api/src/api/v1/admin/create_dev_request.py` — new:
  `CreateDevRequest`, strict params, rate limit.
- `services/api/src/api/v1/admin/__init__.py` — export it.
- `services/api/src/routers/v1/admin_router.py` — `POST /dev-requests`.
- `services/api/tests/test_dev_requests_rate_limit.py` — new (E-6).
- `services/api/tests/test_dev_request_model.py` — new: in-process tests
  that hold `src/` at 100% branch coverage.
- `tools/red-artifacts.txt` — delete the E-3 and E-5 entries.

**Context**:
- PRD FR-1…FR-4; design § Data, § Interfaces (Endpoint, Model helpers).
- Rate-limit pattern: `services/api/src/api/v1/user/create_user_feedback.py:41-60`.
- The status CHECK lists all 13 statuses and the source columns exist from
  this migration (design Trade-offs).
- The E-3 and E-5 evals need a reachable Postgres: `docker compose up -d db`
  locally; CI's `test` job provides one at `localhost:5432`.
- The eval wrappers pin the sha256 of the pytest files and harness they
  run. Make the code pass them; if an eval is genuinely wrong, that is
  `devx revise`, not an edit.

**Verification plan**:
- Type: tests-first
- Success criteria:
  - `bash _devx/workstreams/admin-request-intake/evals/E-3_operator_only.sh`
    and `…/E-5_normalization.sh` exit 0.
  - `npx nx run api:test` green at 100% coverage; `npx nx run api:lint`
    clean; CI's `migrate-test` applies the migration.
  - `tools/red-artifacts.txt` no longer lists the E-3 or E-5 files.

**Tasks**:
- [ ] T1.1 Model, constants and helpers — files: `libraries/utils/utils/models/dev_request.py`, `libraries/utils/utils/models/__init__.py`
- [ ] T1.2 Migration — files: `services/migrator/migrations/versions/<ts>_add_dev_requests.py`
- [ ] T1.3 Endpoint, export and route — files: `services/api/src/api/v1/admin/create_dev_request.py`, `services/api/src/api/v1/admin/__init__.py`, `services/api/src/routers/v1/admin_router.py`
- [ ] T1.4 Rate-limit and coverage tests; turn E-3 and E-5 green; delete their registry entries

### 2. Phase: Operator channel — prod-script arguments, read and write scripts

**Overview**: Argument forwarding in `bin/prod-script`, and the two scripts
that speak `DEVREQ1`: `poll`, `adopt`, `show`, `metrics`, and `transition`
for the seven slice edges. This is the contract the bridge is built
against. Slice; riskiest phase.

**Files**:
- `bin/prod-script` — forward arguments after the script as `sys.argv[1:]`.
- `services/api/scripts/dev_requests_read.py` — new.
- `services/api/scripts/dev_requests_write.py` — new.
- `docs/HELPFUL_SCRIPTS.md` — document both scripts and the argument form.
- `CLAUDE.md` — Ops Scripts entries for both scripts (outside the devx
  markers).
- `tools/red-artifacts.txt` — delete the E-1, E-2 and E-4 entries.

**Context**:
- PRD FR-5…FR-13; design § Interfaces, § Failure handling, § Verification
  harness.
- Import allowlist: standard library, SQLAlchemy, `utils.constants` (PRD
  FR-7).
- No `from __future__` (`docs/HELPFUL_SCRIPTS.md:20-22`).
- Widening edges stay `illegal_transition` until Phase 6.
- Same eval rules as Phase 1: a reachable Postgres, and no edits to the
  pinned eval files.

**Verification plan**:
- Type: tests-first
- Success criteria:
  - `bash _devx/workstreams/admin-request-intake/evals/E-1_full_path.sh`,
    `…/E-2_containment_canary.sh` and `…/E-4_transitions.sh` exit 0.
  - One read-only `bin/prod-script services/api/scripts/dev_requests_read.py poll`
    against production after deploy ends with `ok: true` (run by Leo from
    a plain terminal).
  - `tools/red-artifacts.txt` no longer lists the E-1, E-2 or E-4 files.

**Tasks**:
- [ ] T2.1 Argument forwarding — files: `bin/prod-script`
- [ ] T2.2 Read script: `poll`, `adopt`, `show`, `metrics` — files: `services/api/scripts/dev_requests_read.py`
- [ ] T2.3 Write script: `transition` with the slice edges — files: `services/api/scripts/dev_requests_write.py`
- [ ] T2.4 Docs — files: `docs/HELPFUL_SCRIPTS.md`, `CLAUDE.md`
- [ ] T2.5 Turn E-1, E-2, E-4 green; delete their registry entries; run the production `poll` check

### 3. Phase: Request-a-change form in the admin panel

**Overview**: A dashboard tile and a form that calls the create endpoint
and shows the id8. Last in the slice, and held until the bridge listens.
Slice.

**Files**:
- `app/lib/features/admin/admin_dev_request_new_screen.dart` — new.
- `app/lib/features/admin/admin_dashboard_screen.dart` — a "Request a
  change" tile, patterned on `_buildFeedbackTile`.
- `app/lib/core/router/app_router.dart` — `/admin/dev-requests/new`.
- `app/lib/core/services/api_client.dart` — `createDevRequest()`.
- `app/test/features/admin/admin_dev_request_new_screen_test.dart` — new
  (E-7).

**Context**:
- PRD FR-14; design § Interfaces (Panel).
- The admin area is web-only and redirects non-admins
  (`app/lib/core/router/app_router.dart:225-227`, `:633-638`).

**Verification plan**:
- Type: tests-after (E-7), then human (E-8)
- Success criteria:
  - `flutter test test/features/admin/admin_dev_request_new_screen_test.dart`
    passes in `app/`; `flutter analyze` clean.
  - E-8's walkthrough (`evals/E-8_live_walkthrough.md`) passes in
    production, after X-1.

**Tasks**:
- [ ] T3.1 API client call — files: `app/lib/core/services/api_client.dart`
- [ ] T3.2 Screen and route — files: `app/lib/features/admin/admin_dev_request_new_screen.dart`, `app/lib/core/router/app_router.dart`
- [ ] T3.3 Dashboard tile — files: `app/lib/features/admin/admin_dashboard_screen.dart`
- [ ] T3.4 Widget tests (E-7) — files: `app/test/features/admin/admin_dev_request_new_screen_test.dart`
- [ ] T3.5 After X-1: run the E-8 walkthrough and record it

### 4. Phase: List, detail and cancel endpoints

**Overview**: `GET /v1/admin/dev-requests`, `GET …/{id}`, `POST
…/{id}/cancel`. Widening; starts after E-8 passes.

**Files**:
- `services/api/src/api/v1/admin/list_dev_requests.py` — new.
- `services/api/src/api/v1/admin/get_dev_request.py` — new.
- `services/api/src/api/v1/admin/cancel_dev_request.py` — new.
- `services/api/src/api/v1/admin/__init__.py` — exports.
- `services/api/src/routers/v1/admin_router.py` — three routes.
- `services/api/tests/test_dev_requests_list_cancel.py` — new (E-9).

**Context**:
- PRD FR-15; design § Widening surfaces. `ListFeedback`
  (`services/api/src/api/v1/admin/list_feedback.py:26-58`) is the shape.
- E-3's route allowlist already names these three routes.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - E-9 passes; E-3 still exits 0; `npx nx run api:test` green at 100%.

**Tasks**:
- [ ] T4.1 List and detail — files: `services/api/src/api/v1/admin/list_dev_requests.py`, `services/api/src/api/v1/admin/get_dev_request.py`
- [ ] T4.2 Cancel with its audit row — files: `services/api/src/api/v1/admin/cancel_dev_request.py`
- [ ] T4.3 Exports, routes, tests — files: `services/api/src/api/v1/admin/__init__.py`, `services/api/src/routers/v1/admin_router.py`, `services/api/tests/test_dev_requests_list_cancel.py`

### 5. Phase: Panel list and detail screens

**Overview**: The admin list with status chips and staleness hints, and the
detail screen that replaces `show` as Leo's reading surface. Widening.

**Files**:
- `app/lib/features/admin/admin_dev_requests_screen.dart` — new.
- `app/lib/features/admin/admin_dev_request_detail_screen.dart` — new.
- `app/lib/features/admin/admin_dashboard_screen.dart` — the tile opens the
  list.
- `app/lib/core/router/app_router.dart` — list and detail routes.
- `app/lib/core/services/api_client.dart` — list, detail, cancel calls.
- `app/test/features/admin/admin_dev_requests_list_screen_test.dart` — new
  (E-10).

**Context**:
- PRD FR-16; design § Widening surfaces. `AdminFeedbackScreen`
  (`app/lib/features/admin/admin_feedback_screen.dart:172`, `:232-234`) is
  the shape. Hints compare against the response's `now`.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - E-10 passes; `flutter analyze` clean.

**Tasks**:
- [ ] T5.1 API client calls — files: `app/lib/core/services/api_client.dart`
- [ ] T5.2 List screen with chips and hints — files: `app/lib/features/admin/admin_dev_requests_screen.dart`
- [ ] T5.3 Detail screen with cancel — files: `app/lib/features/admin/admin_dev_request_detail_screen.dart`
- [ ] T5.4 Routes, tile, tests — files: `app/lib/core/router/app_router.dart`, `app/lib/features/admin/admin_dashboard_screen.dart`, `app/test/features/admin/admin_dev_requests_list_screen_test.dart`

### 6. Phase: Pipeline progress fields in the write script

**Overview**: The widening edges of FR-12 and their FR-17 arguments, so the
bridge can write scoping … shipped and "waiting on Leo" with a reason.
Widening.

**Files**:
- `services/api/scripts/dev_requests_write.py` — widening edges,
  `--workstream`, `--spec-hash`, `--pr`, `--detail`/`--gate`/`--count`.
- `services/api/tests/test_dev_requests_pipeline_fields.py` — new (E-11).
- `docs/HELPFUL_SCRIPTS.md` — the new arguments.

**Context**:
- PRD FR-12, FR-17; design § Widening surfaces (Pipeline fields).
- Consumed by X-2.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - E-11 passes; E-4 still exits 0 (it samples only edges no phase
    legalizes).

**Tasks**:
- [ ] T6.1 Widening edges and arguments — files: `services/api/scripts/dev_requests_write.py`
- [ ] T6.2 Detail-code templates and PR append-once
- [ ] T6.3 Tests and docs — files: `services/api/tests/test_dev_requests_pipeline_fields.py`, `docs/HELPFUL_SCRIPTS.md`

### 7. Phase: Fault signals — faults and fault-adopt modes

**Overview**: Server-side `error_logs` grouped by signature, capped at 50
plus overflow, with no caller-written text; and the one call that returns
a fault's samples at adoption. Slice 2.

**Files**:
- `services/api/scripts/dev_requests_read.py` — `faults`, `fault-adopt`.
- `services/api/tests/test_dev_requests_faults.py` — new (E-12).
- `services/api/tests/test_dev_requests_fault_signature.py` — new (E-13).
- `docs/HELPFUL_SCRIPTS.md` — the two modes.

**Context**:
- PRD FR-18, FR-19; design § Assumptions (route templates, container
  paths) and § Unresolved design questions — both are settled at the start
  of this phase, by one read-only `bin/prod-script` look at real
  `stack_trace` values and a check of whether the task can enumerate its
  routes.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - E-12 and E-13 pass; E-2 still exits 0.

**Tasks**:
- [ ] T7.1 Settle route-template source and frame mapping (read-only prod look)
- [ ] T7.2 `faults` with signature, cap and overflow — files: `services/api/scripts/dev_requests_read.py`
- [ ] T7.3 `fault-adopt`
- [ ] T7.4 Tests and docs — files: `services/api/tests/test_dev_requests_faults.py`, `services/api/tests/test_dev_requests_fault_signature.py`, `docs/HELPFUL_SCRIPTS.md`

### 8. Phase: Adopted faults as rows, and routing moves

**Overview**: `open-fault` (one open row per signature) and `move` (a row
follows its work), plus the two `metrics` fields routing is measured by.
Slice 2, with routing.

**Files**:
- `services/api/scripts/dev_requests_write.py` — `open-fault`, `move`.
- `services/api/scripts/dev_requests_read.py` — `metrics` gains
  `faults_open`, `signatures_multi_workstream`.
- `services/api/tests/test_dev_requests_routing_writes.py` — new (E-14).
- `docs/HELPFUL_SCRIPTS.md` — the two writes.

**Context**:
- PRD FR-20, FR-22; design § Data (partial unique index).
- Exercised live by X-3 and X-4; a devx split that only prepares children
  still works through `move` (X-5).

**Verification plan**:
- Type: tests-after
- Success criteria:
  - E-14 passes; E-1, E-2 and E-4 still exit 0.

**Tasks**:
- [ ] T8.1 `open-fault` — files: `services/api/scripts/dev_requests_write.py`
- [ ] T8.2 `move`
- [ ] T8.3 `metrics` fields — files: `services/api/scripts/dev_requests_read.py`
- [ ] T8.4 Tests and docs — files: `services/api/tests/test_dev_requests_routing_writes.py`, `docs/HELPFUL_SCRIPTS.md`
