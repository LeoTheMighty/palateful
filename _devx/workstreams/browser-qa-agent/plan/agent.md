<!-- refined: critique 2026-07-27 (lenses: pm, architect, dev, qa) -->
# Plan — Browser QA Agent

<!-- Stage: Plan. Gate: `devx gate coverage 41ee13` (plan mode — one row per
     E-id; P0 floor: every P0 expectation `full` and naming a runnable
     artifact). Sizing rule: a phase is one cohesive concern with a
     verifiable exit, sized to land as a single reviewable PR. Default to
     more, smaller phases. One phase ≙ one dev spec ≙ one PR ≙ one tour. -->

## Current state

- `devx.config.yaml` has **no `projects:` block** — `devx gate evals`
  resolves zero runners; every P0 in every workstream auto-fails. Its `qa:`
  block claims `browser_harness: playwright` /
  `scripted_test_runner: playwright`; playwright is installed nowhere.
- Gen-2 e2e harness is dormant-but-intact: 7 numbered flows in
  `app/integration_test/0*_test.dart` plus one un-numbered flow
  (`meals_home_promotion_flow_test.dart`, hmp-5 — same posture, excluded
  from `run_all.sh`'s glob only by its name), driver
  `app/test_driver/integration_test.dart`, runner
  `services/e2e/scripts/run_all.sh` (chromedriver autostart, inter-test
  `pkill -f flutter_tools_chrome_device` flake mitigation, pass/fail
  summary), nx targets in `services/e2e/project.json` (`test`,
  `test-single`, `test-headless`, `stack-up`, `stack-down`). But
  `e2e:test` runs `run_all.sh` bare — no stack lifecycle — and the stack
  has two latent defects: `docker-compose.e2e.yml` sets `E2E_TEST_MODE`
  but not `ENVIRONMENT` (the bypass gate at
  `services/api/src/dependencies.py:109` requires
  `environment in ("development","test")` while `config.py` defaults to
  `"dev"`), and `migrator-test` migrates `…/test`
  (`docker-compose.yml:53`) while the api points at `…/palateful`
  (`docker-compose.yml:87`).
- **A third latent defect (found at plan critique)**: no drive invocation
  sets `API_BASE_URL`, and `app/lib/core/config/environment.dart` defaults
  it to `https://api.palateful.app` — a "local" e2e run compiles a build
  that talks to the **production API** with the fixed e2e token. Every
  browser-build launch in this plan carries
  `--dart-define=API_BASE_URL=http://localhost:8000` (the established
  local convention, `bin/prod-web-deploy:17`).
- Gen-1 Maestro (`services/e2e/flows/`, `services/e2e/config.yaml`) is
  abandoned; `services/e2e/README.md` still describes it, and
  `services/e2e/NEXT_STEPS.md` documents the pre-wrapper manual lifecycle.
- No QA-walkthrough template exists; 228 hand-rolled walkthroughs in
  `_bmad-output/implementation-artifacts/` across three drifting formats,
  production stopped 2026-05-03.
- `/devx-test` is routed in prose (`skills/devx.md:566` seam) but the skill
  does not exist (devx O-4 slot, `~/personal/devx/v2/07-decisions.md:86-92`).
- `qa.browser_harness` schema enum upstream is
  `[playwright, cypress, none]` —
  but note: config-schema validation is currently **documentation-only**
  (`loadValidatedConfig` has zero callers in `~/personal/devx/src`;
  consumer repos don't receive `_devx/config-schema.json`; cfg203
  mutual-exclusivity is likewise documented, unenforced). The enum
  extension still ships (it documents supported drivers and future-proofs
  the wiring), but nothing mechanically blocks the config flip.
- Framework QA.md (2026-04-23) bans browser-MCP for QA wholesale; the
  narrow attended carve-out is locked locally in
  `decisions/2026-07-27-hybrid-qa-driver.md` but not yet propagated (FR-7).

## Desired state

- `devx gate evals 41ee13 --dry-run` resolves every artifact of this (and
  any subsequent) workstream to a `projects:` runner; the `qa:` block names
  only installed tools (`claude-in-chrome` exploratory,
  `flutter-drive` scripted).
- `npx nx run e2e:test` is one-command green: stack-up (with working
  `E2E_MODE` bypass + isolated `test` DB) → wait-healthy → all 8 flows
  (7 numbered + the renamed hmp-5 flow) via flutter drive against the
  **local** API, with one targeted `AppConnectionException` retry →
  teardown-in-trap → exit 0 iff all pass; green on two consecutive runs.
  Gen-1 archived to `archive/e2e-maestro/`; README describes only the live
  path.
- `_devx/templates/engine/qa-walkthrough.md` ships in the devx package and
  installs here; `/devx` emits + executes
  `test/test-<hash>-qa-walkthrough.md` for user-visible stories (authored
  at /devx Phase 5 where evidence is freshest, committed with the story at
  Phase 6 — supersedes the PRD's "Phase 6 emits" phrasing).
- `/devx-test` exists upstream (O-4 filled), installs here, and has
  completed ≥1 attended pass on the recipe-import journey with findings
  routed FOCUS.md/DEBUG.md, cumulative same-day spend ≤ $1 (G-5 is a
  per-day cap; the skill enforces it, not just reports it).
- The browser-flow eval convention is documented
  (`_devx/workstreams/browser-qa-agent/evals/README.md`) and proven by a
  demonstration flow, with the `INFRA:` sentinel discipline guarding
  wrong-reason RED.
- QA.md §Layer 2 carries the attended carve-out; OPEN_QUESTIONS and O-4
  point at the shipped skill.
- `/devx-test --persona <name>` seeds a pass from
  `focus-group/personas/persona-<name>.md` and annotates findings.

## What we're NOT doing

- CI wiring of the e2e suite (`.github/workflows/ci.yml` keeps
  `--exclude=e2e`).
- Fixing gen-1 Maestro flows (archived verbatim, not repaired).
- Running `app/integration_test/perf_audit/` in the e2e suite (perf
  tooling, stays out of the flow glob).
- Unattended/scheduled QA, subprocess browser-use, separate API keys.
- Mobile-native device QA; any run against https://palateful.app —
  including implicitly: every browser build this plan launches pins
  `API_BASE_URL` to localhost.
- Changes to devx **gate/eval engine code** (`gate-evals.ts` et al.) or to
  `services/eval/`. (The `devx next` decision table in
  `src/lib/next/decide.ts` gains one row — that is FR-5 scope, not an
  engine change.)
- G-4's second half — the first *real* browser-flow expectation on a
  UI-touching workstream — lands in that subsequent workstream, not here.
  This workstream ships the convention + demonstration (E-5); the handoff
  is deliberate.
- Ongoing "every story emits a walkthrough" enforcement — E-3 proves the
  mechanism on one story; durable compliance rides on the `/devx` skill
  wiring (T3.2), not on a recurring check here.

## RED-stage prerequisites

Two bootstrap facts found at critique change what RED must do (they are
recorded here because RED consumes this plan):

1. **The `projects:` block is a RED prerequisite, not Phase 1 work.** Dev
   specs are only emitted when `devx gate evals` PASSes, and without the
   block every P0 resolves `not-run (no runner)` → FAIL
   (`gate-evals.ts:380-386,296-300`). So the RED stage commits
   `devx.config.yaml`'s `projects:` block (and the `run-eval.sh`
   dispatcher below) *before* running the gate. The `qa:` block keeps
   lying until Phase 1 — that keeps `e1` failing for the right reason.
2. **All six eval artifacts are authored at RED, at the exact Verified-by
   paths** (4 `.sh` + stubs for E-4/E-6 `.md`) — the RED contract; phases
   only *re-run* their artifact and watch it go green, never author it.
   `e3`/`e5` legitimately exit 1 at RED (template absent / demo+README
   absent).
3. **Wrong-reason guard (`INFRA:` sentinel).** The gate treats *any*
   nonzero exit as `right-reason` (`gate-evals.ts:408-414`) — exit 2 is
   mechanically indistinguishable. Convention: every infra-failure path
   prints a line starting `INFRA:` before exiting 2; the RED step that
   reads `evals/RED-report.md` failure quotes MUST reject the gate if any
   quote contains `INFRA:` and fix the infra first.

Runner table committed at RED (deviations from the design table are
critique-driven and noted):

| name | path | test | note |
|---|---|---|---|
| `api` | `services/api` | `poetry run pytest` | |
| `app` | `app` | `flutter test` | |
| `e2e` | `services/e2e` | `bash scripts/e2e_lifecycle.sh` | wrapper, not bare `run_all.sh` — `/devx` local CI runs project `test` on touched paths, and the bare runner assumes a running stack |
| `workstream-evals` | `_devx/workstreams` | `bash run-eval.sh` | dispatcher, not bare `bash` — bare `bash` invoked with no artifact (as `/devx` local CI does) reads stdin |

`_devx/workstreams/run-eval.sh` (committed at RED): no args → print skip
notice, exit 0; one arg → `exec bash "$1"`. Gate command for this
workstream's evals becomes `bash run-eval.sh browser-qa-agent/evals/<f>.sh`
with cwd `_devx/workstreams` (artifact paths are runner-relative,
`gate-evals.ts:390-394`), so eval scripts self-locate the repo root via
`git rev-parse --show-toplevel`. The `devx` CLI is a global bin — scripts
invoke it directly.

**E-1 eval mechanics** (threshold's intent, asserted positively): the
dry-run emits JSON (`planned[{eId, artifact, command}]`, `deferred[]` —
the prose verdict strings never appear in dry-run output,
`~/personal/devx/src/commands/gate.ts:437-452`), so
`e1_runner_resolution.sh` parses it and asserts: every `planned` entry has
a non-null `command`, `planned + deferred` counts equal 6, and
`grep -c playwright devx.config.yaml` = 0. This satisfies "zero
`not-run (no runner)`" a fortiori.

**E-5 artifact shape**: `e5_red_browser_flow.sh` (the Verified-by) is a
*wrapper* that asserts the convention exists and works: (a)
`evals/README.md` documents the convention (required sections present),
(b) `evals/demo_browser_flow.sh` exists and is right-reason-shaped — the
wrapper runs it and expects exit 1 with the asserted-behavior banner (or
exit 2 + `INFRA:` when the stack is down, which the wrapper reports and
propagates as its own `INFRA:` exit 2). The demo flow itself targets a
deliberately unbuilt behavior, stays red by design, and is **not** a
Verified-by artifact — it is the reference implementation the next
workstream copies. At RED, `e5` exits 1 (README + demo absent) →
right-reason recorded for E-5 in `RED-report.md`, satisfying the
threshold's first clause; Phase 5 makes it green.

## Expectation coverage

| E-id | Priority | Verified in phase | Validation type | Eval artifact | Coverage |
|---|---|---|---|---|---|
| E-1 | P0 | 1 | tests-first | `_devx/workstreams/browser-qa-agent/evals/e1_runner_resolution.sh` | full |
| E-2 | P0 | 2 | tests-first | `_devx/workstreams/browser-qa-agent/evals/e2_e2e_one_command.sh` | full |
| E-3 | P1 | 6 (template lands in 3) | tests-first | `_devx/workstreams/browser-qa-agent/evals/e3_walkthrough_emission.sh` | full |
| E-4 | P1 | 6 | human | `_devx/workstreams/browser-qa-agent/evals/E-4_devx_test_pass.md` | full |
| E-5 | P1 | 5 | tests-first | `_devx/workstreams/browser-qa-agent/evals/e5_red_browser_flow.sh` | full |
| E-6 | P2 | 7 | human | `_devx/workstreams/browser-qa-agent/evals/E-6_persona_pass.md` | full |

P0 floor: E-1 and E-2 are `full` with runnable `.sh` artifacts resolved by
the `workstream-evals` runner committed at RED. All artifacts are authored
at RED (see prerequisites above); "Verified in phase" = where each goes
green. E-4/E-6 are attended-by-design (human validation type, P1/P2 —
deferral-legal at RED, executed in phases 6/7).

## Phase checklist

- [ ] Phase 1: Config truth — `qa:` correction + runner resolution green *(G-1, due 2026-08-15)*
- [ ] Phase 2: E2E revival — one-command green *(G-2, due 2026-08-15)*
- [ ] Phase 3: Upstream story-derived QA — template, emission wiring, schema enum *(feeds G-3)*
- [ ] Phase 4: Upstream attended layer — `/devx-test` + routing + QA.md carve-out *(feeds G-5)*
- [ ] Phase 5: Palateful adoption — install, `qa:` flip, browser-flow eval convention *(G-3 due 2026-08-31; E-5/G-4 demonstration)*
- [ ] Phase 6: First attended pass — walkthrough emission + recipe-import journey *(G-3/G-5 proof; before 2026-09-15; needs Leo attended)*
- [ ] Phase 7: Persona-seeded passes *(no deadline; PRD-gated behind Phase 6)*

Dependency shape: 1 ∥ 2 ∥ 3 (disjoint files/repos); 4 after 3 (same-repo
sequencing; single version bump at end of 4); 5 after 1–4; 6 after 5
(attended); 7 after 6 (PRD's FR-8 precondition). G-4's deadline
(2026-09-15) is discharged here only as far as the convention +
demonstration; the "real expectation" half is handed to the next
UI-touching workstream (see scope fence).

## Phases

### 1. Phase: Config truth — `qa:` correction + runner resolution green

**Overview**: With the `projects:` block already landed at RED, this phase
makes the `qa:` block stop lying and turns E-1 green. `browser_harness`
flips to `none` (truthful today, legal under the current upstream enum) —
the final `claude-in-chrome` value waits for Phase 3's enum extension and
lands in Phase 5. Two-step flip kept deliberately even though schema
validation is currently unenforced (see Current state): the enum is the
documented driver contract, and the conservative ordering costs nothing.

**Files**:
- `devx.config.yaml` — set `qa.browser_harness: none`,
  `qa.scripted_test_runner: flutter-drive`.

**Context**:
- Resolution is longest-prefix on `path` with cwd = the runner's `path`
  (`~/personal/devx/src/lib/engine/gate-evals.ts:144-165,389-394`); the
  runner table + dispatcher landed at RED (see prerequisites).
- `projects:` is mutually exclusive with `stack:` per cfg203 —
  documented, currently unenforced (`config-validate.ts` has no such
  logic and no callers); palateful has neither block, so moot either way.
- `qa.scripted_test_runner` is a free string; `browser_harness` is the
  constrained enum — hence the two-step flip.

**Verification plan**:
- Type: tests-first
- Success criteria:
  - `bash run-eval.sh browser-qa-agent/evals/e1_runner_resolution.sh`
    (cwd `_devx/workstreams`) exits 0 — i.e. dry-run JSON shows 6/6
    expectations with a non-null command or a legal deferral, and
    `grep -c playwright devx.config.yaml` prints `0`.
  - `devx config get qa.browser_harness` prints `none`;
    `devx config get qa.scripted_test_runner` prints `flutter-drive`.

**Tasks**:
- [ ] T1.1 Flip `qa:` to interim-truthful values (`none` /
  `flutter-drive`) — files: `devx.config.yaml`
- [ ] T1.2 Re-run `e1_runner_resolution.sh` (authored at RED — never
  re-author); watch it go green; paste output as evidence

### 2. Phase: E2E revival — one-command green

**Overview**: Make `npx nx run e2e:test` the full lifecycle and fix the
three stack defects that keep the harness dormant or dangerous: the
dormant bypass (`ENVIRONMENT`), the DB mismatch (`DATABASE_URL`), and the
**prod-API default** (`API_BASE_URL`). Bring the hmp-5 flow into the
numbered population. Independent of Phase 1 (disjoint files) —
parallel-safe.

**Files**:
- `docker-compose.e2e.yml` — api overlay gains `ENVIRONMENT: development`
  (arms the bypass gate at `services/api/src/dependencies.py:109`) and
  `DATABASE_URL: postgresql://postgres:postgres@db:5432/test` (matches
  `migrator-test`'s target, isolates e2e writes from dev data; no SQL seed
  needed — the bypass lazy-seeds via `find_or_create_by`,
  `services/api/src/dependencies.py:108-110`; compose-merge lets the
  overlay value win).
- `services/e2e/scripts/run_all.sh` —
  (a) add `--dart-define=API_BASE_URL=http://localhost:8000` to the drive
  invocation (without it the build targets prod,
  `app/lib/core/config/environment.dart:9-12`);
  (b) fail-fast chromedriver presence check with a
  `brew install chromedriver` hint;
  (c) exactly one retry per test on the `AppConnectionException`
  signature — this requires capturing drive output
  (`tee` to a temp log; exit code via `PIPESTATUS` under the existing
  `set -uo pipefail`) while still streaming it, and the retry MUST repeat
  the `pkill -f flutter_tools_chrome_device` + sleep reset first
  (`run_all.sh:58-60`) — retrying against the same stale Chrome device
  adds nothing (`services/e2e/NEXT_STEPS.md:69`).
- `app/integration_test/08_meals_home_promotion_test.dart` — renamed from
  `meals_home_promotion_flow_test.dart` (git mv, no content change):
  joins the `0*` glob, making E-2's "every flow" wording true; population
  becomes 8.
- `services/e2e/scripts/e2e_lifecycle.sh` (new) — up → poll
  `localhost:8000` healthy → `run_all.sh` → down in a `trap` so teardown
  survives failure; exit nonzero iff any flow failed. Also the `e2e`
  project's `test` command (runner table at RED already points here).
- `services/e2e/project.json` — `test` target points at the lifecycle
  wrapper; `test-single` / `test-headless` gain the
  `API_BASE_URL=http://localhost:8000` define;
  `stack-up`/`stack-down` retained.
- `archive/e2e-maestro/` — gen-1 `services/e2e/flows/` + `config.yaml`
  moved verbatim (`storage.archive_path`; `archive/` is tracked — the
  managed gitignore block covers only `.worktrees/`/`.devx-cache/`).
- `services/e2e/README.md` — rewritten: live path only (stack, one-command
  run, single-test drive, flake note, chromedriver prereq, the
  `API_BASE_URL` gotcha).
- `services/e2e/NEXT_STEPS.md` — retired alongside gen-1 (its manual
  stack-up→test→down recipe double-runs the lifecycle after the repoint;
  fold anything still-true into README, archive the rest).

**Context**:
- The flow population is `run_all.sh`'s glob
  (`integration_test/0*_test.dart`) — after the rename it is 8 files;
  `perf_audit/` stays excluded by construction (subdirectory). The E-2
  eval asserts pass count == glob count (`ls app/integration_test/0*_test.dart | wc -l`),
  so a silently dropped or added flow fails the eval rather than hiding
  under a `≥` bar.
- Retry is targeted, not blanket: blanket retries mask real regressions;
  zero retries fails the two-consecutive-runs bar on known infra flake
  (design Trade-offs).
- `run_all.sh`'s own EXIT trap (chromedriver kill, `run_all.sh:26`) is
  process-local — it composes with the wrapper's compose-down trap; both
  fire.
- E-2 eval (`e2_e2e_one_command.sh`, authored at RED) runs
  `npx nx run e2e:test` twice back-to-back, asserts both exit 0 and pass
  count == glob count both times; prints `INFRA:` + exits 2 when
  Docker/chromedriver are absent (sentinel discipline, see RED-stage
  prerequisites).

**Verification plan**:
- Type: tests-first
- Success criteria:
  - `bash run-eval.sh browser-qa-agent/evals/e2_e2e_one_command.sh`
    exits 0 (two consecutive green suite runs, 8/8 each).
  - Manual trap spot-check (run once, evidence pasted): start a run,
    `docker kill palateful-api` mid-suite, then confirm the wrapper exits
    nonzero and `docker compose -f docker-compose.yml -f docker-compose.e2e.yml ps -q`
    prints nothing (teardown fired).
  - `services/e2e/flows/` no longer exists; `archive/e2e-maestro/flows/`
    does; `README.md` mentions neither Maestro nor `--flow=` syntax.

**Tasks**:
- [ ] T2.1 Fix the api overlay env (`ENVIRONMENT`, `DATABASE_URL`) —
  files: `docker-compose.e2e.yml`
- [ ] T2.2 `run_all.sh`: local `API_BASE_URL` define, chromedriver
  fail-fast, one targeted retry (output capture + pkill reset per
  Context) — files: `services/e2e/scripts/run_all.sh`
- [ ] T2.3 Rename the hmp-5 flow into the glob — files:
  `app/integration_test/08_meals_home_promotion_test.dart`
- [ ] T2.4 Author the lifecycle wrapper + repoint `e2e:test` + add
  `API_BASE_URL` to `test-single`/`test-headless` — files:
  `services/e2e/scripts/e2e_lifecycle.sh`, `services/e2e/project.json`
- [ ] T2.5 Archive gen-1 + NEXT_STEPS; rewrite README — files:
  `archive/e2e-maestro/`, `services/e2e/README.md`,
  `services/e2e/NEXT_STEPS.md`
- [ ] T2.6 Re-run `e2_e2e_one_command.sh` → green; run the trap
  spot-check; paste both as evidence

### 3. Phase: Upstream story-derived QA — template, emission wiring, schema enum

**Overview**: First devx-repo phase (direct commits to main, user
decision). Ships everything palateful's adoption needs that is *not* the
attended skill: the walkthrough template, the `/devx` emission wiring, and
the `browser_harness` enum extension. No version bump yet — that closes
Phase 4 so consumers install once.

**Files** (all `~/personal/devx`):
- `_devx/templates/engine/qa-walkthrough.md` (new) — skeleton from the
  ifh-1 hybrid generation
  (`_bmad-output/implementation-artifacts/ifh-1-qa-walkthrough.md` in
  palateful): header + scope blockquote → `## Pre-flight` runnable block →
  `## Manual checks` numbered behavioral assertions (fenced runnable block
  + expected output + invariant, each tagged `machine` or `human`) →
  `## Regressions to watch` → `## Post-merge follow-ups`.
- `.claude/commands/devx.md` + `skills/devx.md` mirror — Phase 5 (local CI
  validation) gains the emission step: for stories with user-visible
  surfaces, author `test/test-<hash>-qa-walkthrough.md` from the template,
  execute every `machine` item inline (evidence pasted, boxes checked),
  leave `human` items unchecked with a one-line "how to verify", append a
  TEST.md entry; file commits with the story in Phase 6. (PRD FR-4 says
  "`/devx` Phase 6 emits" — superseded: *author at Phase 5 where evidence
  is freshest, commit at Phase 6*; design §Architecture pt 3 is the
  authority.)
- `_devx/config-schema.json` — `qa.browser_harness` enum gains
  `claude-in-chrome`; its schema test updated alongside.

**Context**:
- Files with the `<!-- devx-skill v… -->` header are overwritten on
  version change; the packaged `templatesRoot` ships engine templates
  (`~/personal/devx/src/lib/init-skills.ts`,
  `src/commands/init.ts:77-78,156`) — this is why nothing here is authored
  in palateful.
- Verified this stage: `writeEngineTemplates`
  (`~/personal/devx/src/lib/init-write.ts:883-928`) writes any missing
  template file and is called from both the fresh-scaffold orchestrator
  (`init-orchestrator.ts:280`) and the upgrade path
  (`init-upgrade.ts:688`) — net-new `qa-walkthrough.md` installs on
  `devx init` upgrade; no palateful-side fallback commit needed. Caveat
  (same code path): templates are write-if-absent *forever* — later
  upstream revisions of `qa-walkthrough.md` will NOT auto-propagate to
  consumers; revisions need a manual copy or an upstream engine change
  (out of scope here).
- Skills are mirrored `.claude/commands/` → `skills/` via
  `npm run sync:skills` (`scripts/sync-skills.mjs`).

**Verification plan**:
- Type: tests-after
- Success criteria:
  - devx repo suite green (`npm test` there) including the extended enum
    test.
  - `qa-walkthrough.md` present under the packaged
    `_devx/templates/engine/`.
  - The schema test asserts `claude-in-chrome` accepted AND a bogus value
    rejected (enum still meaningful).
  - `skills/devx.md` mirror byte-matches `.claude/commands/devx.md` after
    `npm run sync:skills`.

**Tasks**:
- [ ] T3.1 Author `qa-walkthrough.md` template from the ifh-1 skeleton —
  files: `~/personal/devx/_devx/templates/engine/qa-walkthrough.md`
- [ ] T3.2 Wire emission into `/devx` Phase 5 + resync mirror — files:
  `~/personal/devx/.claude/commands/devx.md`,
  `~/personal/devx/skills/devx.md`
- [ ] T3.3 Extend the `browser_harness` enum + its test — files:
  `~/personal/devx/_devx/config-schema.json`, schema test
- [ ] T3.4 Run devx suite; commit(s) to devx main

### 4. Phase: Upstream attended layer — `/devx-test` + routing + QA.md carve-out

**Overview**: Fill the O-4 slot: the attended exploratory skill, its
dispatcher routing, its `devx next` nudge, and the FR-7 decision
propagation. Closes with the devx version bump so Phase 5 installs
everything in one upgrade.

**Files** (all `~/personal/devx`):
- `.claude/commands/devx-test.md` (new) + `skills/devx-test.md` mirror —
  protocol per design: resolve target (surface | story hash → walkthrough
  | TEST.md top) → preconditions (Claude-in-Chrome connected via
  `tabs_context`; local web build at `localhost:8888` running with
  `--dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000`,
  offer the launch command if absent) → drive journeys, one surface per
  invocation → route findings (UX friction → FOCUS.md; reproducible bugs →
  DEBUG.md with repro line; harness crashes → DEBUG.md against devx per
  `docs/QA.md:129-133`) → **enforce the cost cap**: G-5 is $1/*day*, so
  the skill body states the daily budget, checks for a same-day prior
  pass (its own report lines in FOCUS.md/DEBUG.md are the record), warns
  + requires explicit user confirmation before a second same-day
  invocation, and reports cumulative same-day spend at the end of every
  pass.
- `.claude/commands/devx.md` + mirror — routing mention at the seam
  already named (`skills/devx.md:566`).
- `src/lib/next/decide.ts` + its table test — new row: TEST.md has
  unclaimed walkthrough entries → suggest `/devx-test`; placement settled
  by first-match-wins ordering + the existing test (design's second
  unresolved question — resolved here mechanically).
- `docs/QA.md` — §Layer 2 line 53: blanket ❌ becomes "❌ for
  unattended/automated; ✅ for user-attended on-demand passes"; cadence
  cap ($1/day, line 206) unchanged.
- `docs/OPEN_QUESTIONS.md:148-155` — addendum pointing at the revision.
- `v2/07-decisions.md:86-92` — O-4 updated to point at the shipped skill.
- `package.json` — version bump (this is what makes `devx init` in
  palateful treat headered skills as stale and install the new ones).

**Context**:
- The skill body enforces scope (one surface/story per invocation, no
  chained runs, `docs/QA.md:215-220`) — that plus the per-day cap is the
  E-4/G-5 cost guardrail.
- FR-7 propagation is plain doc commits — no `devx revise` cascade;
  pln104 is satisfied by lock (palateful decision file) → compare →
  update (QA.md/OPEN_QUESTIONS/O-4) → this phase.

**Verification plan**:
- Type: tests-after
- Success criteria:
  - devx suite green including the `decide.ts` table test with the new
    row.
  - `skills/devx-test.md` exists, mirror-matches, and contains the
    daily-cap + same-day-recheck language.
  - `git log` on devx main shows QA.md/OPEN_QUESTIONS/O-4 revision
    commits; version bumped.

**Tasks**:
- [ ] T4.1 Author `/devx-test` skill (incl. per-day cap enforcement) +
  mirror — files: `~/personal/devx/.claude/commands/devx-test.md`,
  `~/personal/devx/skills/devx-test.md`
- [ ] T4.2 Routing mention in `devx.md`; `devx next` row + test — files:
  `~/personal/devx/.claude/commands/devx.md`,
  `~/personal/devx/src/lib/next/decide.ts`, its test
- [ ] T4.3 Propagate FR-7: QA.md carve-out, OPEN_QUESTIONS addendum, O-4
  update — files: `~/personal/devx/docs/QA.md`,
  `~/personal/devx/docs/OPEN_QUESTIONS.md`,
  `~/personal/devx/v2/07-decisions.md`
- [ ] T4.4 Version bump + suite + commits to devx main

### 5. Phase: Palateful adoption — install, `qa:` flip, browser-flow eval convention

**Overview**: Pull the upstream work into palateful and make E-5 green by
delivering the convention README + demonstration flow that its wrapper
(authored at RED) asserts. After this phase every machine-verifiable
expectation of the workstream is green except E-3 (needs a story).

**Files**:
- (via `devx init` upgrade) `.claude/commands/devx-test.md`,
  `_devx/templates/engine/qa-walkthrough.md` — installed, not authored.
  The upgrade round-trips `devx.config.yaml` through a comment-preserving
  YAML document (`init-upgrade.ts:245,349`), so the hand-added
  `projects:` block survives.
- `devx.config.yaml` — `qa.browser_harness: claude-in-chrome` (enum now
  extended upstream; validation unenforced today, flip is safe either
  way).
- `_devx/workstreams/browser-qa-agent/evals/README.md` — the convention,
  documented for reuse-without-new-wiring (E-5 threshold clause 2): shape
  (executable `.sh` under `evals/`, self-locate root, precondition
  asserts), exit contract (0 present / 1 missing = right-reason RED / 2 +
  `INFRA:` sentinel = infra), the `run-eval.sh` dispatcher, the
  RED-report `INFRA:` grep discipline, and the headless invocation recipe
  (`flutter test --platform chrome --dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000 <target>`).
- `_devx/workstreams/browser-qa-agent/evals/demo_browser_flow.sh` — the
  reference implementation: targets a deliberately unbuilt behavior,
  prints the asserted behavior, exits 1; exits 2 + `INFRA:` when stack /
  chromedriver missing. Permanently red by design; not a Verified-by
  artifact; excluded from every default suite glob by location.

**Context**:
- `e5_red_browser_flow.sh` was authored at RED as the wrapper asserting
  README + demo shape (see RED-stage prerequisites) — this phase makes it
  green by delivering both; do not re-author the wrapper.
- `right-reason` is exit-code-only (`gate-evals.ts:403-414`) — the
  convention's printed-banner + `INFRA:` sentinel is what keeps
  RED-report quotes readable and wrong-reason RED detectable.

**Verification plan**:
- Type: tests-first
- Success criteria:
  - `devx init` (upgrade) reports the new skill + template installed;
    both files exist here with the version header (template headerless by
    design); `projects:` block still present in `devx.config.yaml`
    afterwards.
  - `devx config get qa.browser_harness` prints `claude-in-chrome`.
  - `bash run-eval.sh browser-qa-agent/evals/e5_red_browser_flow.sh`
    exits 0 with the stack up; with the stack down it exits 2 printing
    `INFRA:` (spot-check both, paste evidence).
  - `bash run-eval.sh browser-qa-agent/evals/e1_runner_resolution.sh`
    still exits 0 (config regression guard).

**Tasks**:
- [ ] T5.1 Run `devx init` upgrade; verify skill + template landed and
  `projects:` survived — files: `.claude/commands/devx-test.md`,
  `_devx/templates/engine/qa-walkthrough.md`, `devx.config.yaml`
- [ ] T5.2 Flip `qa.browser_harness` to `claude-in-chrome` — files:
  `devx.config.yaml`
- [ ] T5.3 Author the convention README + demo flow — files:
  `_devx/workstreams/browser-qa-agent/evals/README.md`,
  `_devx/workstreams/browser-qa-agent/evals/demo_browser_flow.sh`
- [ ] T5.4 Re-run `e5` (both stack states) + `e1`; paste evidence

### 6. Phase: First attended pass — walkthrough emission + recipe-import journey

**Overview**: The attended proof of the whole stack: emit the first
walkthrough from the installed template for the recipe-import surface,
execute its machine items, then run `/devx-test` on that journey with
Claude-in-Chrome against the local `E2E_MODE` web build. Requires Leo
present — book the session when Phase 5 closes (G-3's 2026-08-31 date
rides on it).

**Files**:
- `test/test-<this-spec-hash>-qa-walkthrough.md` — first emitted
  walkthrough (recipe-import surface), machine items executed with fenced
  evidence, human items with one-line hints; TEST.md entry appended.
- `FOCUS.md` / `DEBUG.md` — findings from the pass (each finding in
  exactly one, bugs with a repro line).
- `_devx/workstreams/browser-qa-agent/evals/E-4_devx_test_pass.md` —
  updated from stub to the pass record: journey driven, findings routed,
  cumulative same-day spend vs the $1/day cap.

**Context**:
- Launch command for the target build:
  `flutter run -d chrome --web-port=8888 --dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000`
  (cwd `app`) — the `API_BASE_URL` define is load-bearing; without it the
  pass drives production (see Current state). The skill offers the
  command when the build is absent.
- One surface per invocation + per-day cap (Phase 4's skill body) are the
  cost guardrails; recipe-import is the journey named by E-4's threshold.
- `e3_walkthrough_emission.sh` was authored at RED: asserts the template
  exists in `_devx/templates/engine/`, ≥ 1 `test/test-*-qa-walkthrough.md`
  exists, its `machine` items are 100% checked with fenced evidence
  blocks, and every `human` item carries a hint line. E-3 proves the
  mechanism on one story (see scope fence for the "every story"
  boundary).

**Verification plan**:
- Type: human
- Success criteria:
  - ≥ 1 completed `/devx-test` pass on recipe-import; every finding lands
    in exactly one of FOCUS.md/DEBUG.md with a repro line; cumulative
    same-day spend ≤ $1 (reported by the skill).
  - `bash run-eval.sh browser-qa-agent/evals/e3_walkthrough_emission.sh`
    exits 0.
  - E-4's `.md` record updated with the evidence.

**Tasks**:
- [ ] T6.1 Emit + execute the recipe-import walkthrough per the installed
  template — files: `test/test-<hash>-qa-walkthrough.md`, `TEST.md`
- [ ] T6.2 Run the attended `/devx-test` pass (Leo present); route
  findings — files: `FOCUS.md`, `DEBUG.md`
- [ ] T6.3 Re-run `e3` → green; record the pass in
  `E-4_devx_test_pass.md`

### 7. Phase: Persona-seeded passes

**Overview**: FR-8, explicitly last (PRD precondition: only after Phase
6's end-to-end pass). Adds `--persona <name>` to the upstream skill and
runs one persona-seeded pass here.

**Files**:
- `~/personal/devx/.claude/commands/devx-test.md` + mirror — `--persona`
  argument: read `focus-group/personas/persona-<name>.md` before target
  resolution; goals/frustrations → journey priorities; vocabulary/
  tech-comfort → interaction style; findings annotated `persona: <name>`;
  unknown name → list available files and stop. Version bump + reinstall
  here.
- `FOCUS.md` / `DEBUG.md` — persona-annotated findings.
- `_devx/workstreams/browser-qa-agent/evals/E-6_persona_pass.md` —
  updated from stub to the pass record.

**Context**:
- 5 persona files exist in `focus-group/personas/`; the pass reuses the
  Phase 6 protocol unchanged — persona only varies priorities and tone.
  The per-day cap applies across persona and plain passes alike.

**Verification plan**:
- Type: human
- Success criteria:
  - ≥ 1 pass with a real persona file; every finding annotated
    `persona: <name>` (greppable).
  - Unknown-persona invocation lists files and stops (spot-check).
  - E-6's `.md` record updated.

**Tasks**:
- [ ] T7.1 Add `--persona` to the skill upstream + bump + reinstall —
  files: `~/personal/devx/.claude/commands/devx-test.md`, mirror,
  `package.json`
- [ ] T7.2 Run one persona-seeded pass (Leo present); annotate findings —
  files: `FOCUS.md`, `DEBUG.md`
- [ ] T7.3 Record in `E-6_persona_pass.md`
