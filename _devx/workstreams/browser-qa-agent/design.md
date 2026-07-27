# Design — Browser QA Agent

<!-- Stage: Design. Gate: `devx gate coverage 41ee13` (design mode — one
     tri-state row per G-/UC-/CAP-/FR- ID in prd.md). No phases, no tasks —
     design is the approach, not the sequence. -->

## Overview

- **Objective**: Make QA real in palateful across four depths — a truthful
  config that gives the RED gate live runners (today `devx gate evals`
  resolves *zero* runners because `devx.config.yaml` has no `projects:`
  block), a revived one-command scripted e2e suite, story-derived QA
  walkthroughs emitted and executed by `/devx`, and an attended exploratory
  `/devx-test` skill driven by Claude-in-Chrome — while narrowly revising
  the framework's 2026-04-23 "no browser-MCP for QA" decision to permit the
  attended case.
- **Solution**: Split QA driving by **attendance, not layer** (locked in
  `decisions/2026-07-27-hybrid-qa-driver.md`): scripted/mechanical
  verification uses the existing gen-2 flutter-drive + ChromeDriver harness
  (`services/e2e/scripts/run_all.sh`, `app/integration_test/`) reached
  through new `projects:` runner entries; attended on-demand exploratory
  passes use Claude-in-Chrome against a local `E2E_MODE` web build. All
  devx-owned surfaces (the `/devx-test` skill, the qa-walkthrough template,
  the `qa.browser_harness` schema enum, the QA.md revision) are authored
  upstream in `~/personal/devx` on main and installed here via `devx init`
  — never hand-edited in palateful, where they'd be clobbered on the next
  version bump. Discovered infra defects that block the e2e revival (the
  dormant `E2E_MODE` env gate, the migrator/API database mismatch, the
  stale gen-1 README) are fixed in-scope, per the "fix as much as possible"
  directive.

## Constraints

- **RED-gate mechanics** (`~/personal/devx/src/lib/engine/gate-evals.ts`):
  runner resolution is longest-prefix on the project `path`
  (`resolveRunner()`, lines 144–165); the gate executes
  `` `${runner.test} ${artifact}` `` with **cwd = the runner's `path`**
  (lines 389–394); `.md` artifacts are never mechanically runnable (lines
  370–379) and auto-fail a P0; `right-reason` is **exit-code-only** —
  nonzero exit, with the last 10 output lines captured as the quote, not
  asserted against (lines 403–414). Eval scripts must therefore be
  cwd-independent (self-locate the repo root).
- **Config shape**: `projects:` is mutually exclusive with `stack:`
  (cfg203); palateful currently has neither, so adding `projects:` is
  clean. Per-entry required fields: `name`, `path`; `test` optional
  (`~/personal/devx/_devx/config-schema.json`, `projects` at line 880).
- **Schema enum**: `qa.browser_harness` is currently
  `enum: [playwright, cypress, none]` — `claude-in-chrome` is rejected by
  the load-time validator until the enum is extended upstream.
  `qa.scripted_test_runner` is a free string.
- **Skill/template ownership** (`~/personal/devx/src/lib/init-skills.ts`):
  files carrying the `<!-- devx-skill v… -->` header are overwritten on any
  version change; headerless files are user-owned and skipped. Engine
  templates ship from the packaged `templatesRoot`
  (`~/personal/devx/src/commands/init.ts:77-78,156`). Consequence: every
  skill/template/schema change in this workstream lands in the devx repo
  first, then installs into palateful.
- **Cost cap**: YOLO cadence = on-demand only, $1/day
  (`~/personal/devx/docs/QA.md:206`); G-5 keeps this as a hard guardrail.
- **Local-only browser targets**: exploratory and scripted runs drive
  localhost builds only — never https://palateful.app (user decision this
  session + `docs/QA.md:218` anti-pattern).
- **ChromeDriver is unmanaged**: installed via `brew install chromedriver`
  by hand (`services/e2e/scripts/run_all.sh:8`); no Brewfile exists. The
  runner must fail fast with an install hint when it's absent.
- **`app/` is not an nx project** — no `app/project.json`; Flutter is
  reached via the `e2e` nx project (`services/e2e/project.json`) or plain
  `flutter` commands with `cwd: app`.

## Risks

- **ChromeDriver flake persists** (`AppConnectionException` between
  consecutive drives, `services/e2e/NEXT_STEPS.md:69`) → keep the existing
  inter-test `pkill -f flutter_tools_chrome_device` mitigation
  (`run_all.sh:58-60`) and add exactly one retry per test, triggered only
  on the `AppConnectionException` signature → proven by E-2 (two
  consecutive green runs).
- **E2E auth bypass is silently dormant**: the API gate requires
  `settings.environment in ("development", "test")`
  (`services/api/src/dependencies.py:109`) but `config.py:41` defaults to
  `"dev"` and no compose file sets `ENVIRONMENT` → set
  `ENVIRONMENT: development` in the `docker-compose.e2e.yml` api overlay →
  proven by E-2 (suite cannot pass without a working bypass).
- **Database mismatch**: `migrator-test` migrates `…/test`
  (`docker-compose.yml:57`) while the api service points at `…/palateful`
  (`docker-compose.yml:80`) → the e2e overlay also overrides the api
  `DATABASE_URL` to the `test` database, keeping e2e data out of dev data →
  proven by E-2.
- **Schema rejects the truthful config**: flipping
  `qa.browser_harness: claude-in-chrome` before the upstream enum change
  lands would fail config validation → ordering constraint in the
  migration plan (schema change ships with the FR-5 devx-main work, before
  palateful's config flip) → proven by E-1 (config must load for the
  dry-run to resolve).
- **Wrong-reason RED passes**: because `right-reason` is exit-code-only, an
  eval script broken by an import/wiring error still reads as RED → RED
  stage discipline (read every failure quote in `evals/RED-report.md`)
  plus eval scripts that print the *asserted behavior* before exiting
  nonzero → proven by E-5.
- **Attended-pass cost creep** → skill body enforces scope (one surface or
  story per invocation, no chained runs per `docs/QA.md:215-220`) and the
  $1 cap → proven by E-4.

## Trade-offs

- **`.sh` wrapper scripts as the browser-flow eval shape** (over
  registering `.dart` files directly with a flutter runner): a uniform
  `bash`-runner entry handles every workstream eval, scripts self-contain
  their preconditions (stack check, chromedriver check), and eval flows
  stay out of every default suite glob. Cost: one layer of indirection
  around the flutter command.
- **Point the e2e API at the `test` database** (over re-targeting
  migrator-test at `palateful`): isolates e2e writes from dev data; the
  lazy `find_or_create_by` seeding (`services/api/src/dependencies.py:108-110`)
  means no SQL seed is needed either way.
- **Upstream-first for all devx-owned surfaces** (over patching installed
  copies in palateful): survives `devx init` version-bump overwrites; costs
  a two-repo commit dance, accepted because the user chose direct-to-main
  in the devx repo.
- **One targeted retry on `AppConnectionException`** (over zero retries or
  blanket retries): zero retries fails the two-consecutive-runs bar on
  known infra flake; blanket retries would mask real regressions.
- **Extend the `browser_harness` enum with `claude-in-chrome`** (over
  loosening it to a free string): keeps config validation meaningful; the
  enum documents the supported drivers.

## Out of scope

- CI wiring of the e2e suite (`.github/workflows/ci.yml:223` keeps
  `--exclude=e2e`); local one-command green is this workstream's bar.
- Reviving gen-1 Maestro — `services/e2e/flows/` + `config.yaml` are
  archived, not fixed.
- Unattended/scheduled QA (subprocess browser-use on a separate key) — the
  2026-04-23 architecture stays reserved for it; only the attended
  carve-out changes.
- Mobile-native device QA; production smoke against palateful.app (user
  chose local-only; prod smoke is a separate future decision).
- Any change to `services/eval/` (LLM answer-quality eval) — we copy its
  runner idiom only.

## Assumptions

- The 7 top-level `app/integration_test/0*_test.dart` flows are the E-2
  population; `run_all.sh`'s glob (`integration_test/0*_test.dart`,
  lines 33–48) already excludes `perf_audit/` (subdirectory) and
  `meals_home_promotion_flow_test.dart` (no `0` prefix). If the glob
  changes, E-2's "≥ 7" threshold needs re-basing.
- The gen-2 suite last passed with `ENVIRONMENT` exported ad hoc; no other
  hidden env dependency exists. Breaks → revisit E-2 scope.
- `devx init` installs new template files into consumer repos the same way
  it installs new skills (write-if-absent, overwrite-on-version-change).
  Breaks → template is additionally committed directly in palateful.
- Claude-in-Chrome remains available in the operator's sessions (it is a
  session capability, not a repo dependency). Breaks → attended passes
  fall back to manual walkthrough execution; scripted layers unaffected.
- Chromedriver major version tracks the local Chrome install (brew keeps
  both current). Breaks → run_all.sh's fail-fast check reports the
  mismatch.

## Discarded considerations

- **Playwright as the scripted harness** (what the config falsely claims):
  installed nowhere; would duplicate a working flutter-drive harness and
  discard 7 passing tests plus the unit-tested `E2E_MODE` bypass.
- **Subprocess browser-use for the attended pass**: the framework's
  reserved architecture for *unattended* QA; for user-attended on-demand
  passes it adds a second API key, a Python runner, and result-relay
  plumbing with no benefit over the already-connected Claude-in-Chrome
  session (rationale locked in `decisions/2026-07-27-hybrid-qa-driver.md`).
- **Registering `app` as an nx project to host eval runs**: nx registration
  is orthogonal churn; the `e2e` project and plain `flutter` commands
  already cover every invocation this design needs.
- **A palateful-local `/devx-test` skill file**: would be headerless
  (user-owned) and orphaned from framework upgrades, or headered and
  clobbered by the next `devx init`; O-4 explicitly reserves the skill's
  home in the framework.
- **SQL seed data for e2e**: unnecessary — the bypass's
  `find_or_create_by` lazy-seeds the test user, calendar, and system book
  on first authenticated request.

## Wrap, don't duplicate

- **Reuses**:
  - Gen-2 harness end-to-end: `services/e2e/scripts/run_all.sh` (chromedriver
    autostart, flake pkill, pass/fail summary), `services/e2e/project.json`
    targets (`test`, `test-single`, `test-headless`, `stack-up`,
    `stack-down`), `app/integration_test/` (7 flows + `helpers.dart`),
    `app/test_driver/integration_test.dart`.
  - `E2E_MODE` bypass on both sides: `app/lib/core/config/environment.dart:37`
    (`kE2EMode`), `services/api/src/dependencies.py:108-110,326-334`, canned
    AI reply `services/api/src/api/v1/chat/agent_loop.py:58-66` — all
    unit-tested (`services/api/tests/test_dependencies.py:137-203`).
  - Compose stack: `docker-compose.yml` + `docker-compose.e2e.yml` overlay
    incl. `migrator-test` (`docker-compose.yml:49-62`).
  - devx engine as-is: `gate-evals.ts` resolution/verdicts, `devx revise`
    cascade, `installSkills` ownership semantics,
    `scripts/sync-skills.mjs` mirror — zero engine code changes.
  - Walkthrough format: the `ifh-*` hybrid generation
    (`_bmad-output/implementation-artifacts/ifh-1-qa-walkthrough.md`)
    becomes the template's skeleton.
  - `services/eval/` runner idiom (nx `run-commands` + gate script exiting
    nonzero, `services/eval/src/gate.py:34-44`) — copied, not modified.
- **Adds** (genuinely new):
  - `projects:` block + corrected `qa:` block in palateful
    `devx.config.yaml`.
  - Stack-lifecycle wrapper making `npx nx run e2e:test` one-command
    (up → wait-healthy → drive → down), plus the retry-on-flake and the
    two compose-overlay env fixes.
  - `_devx/templates/engine/qa-walkthrough.md` (upstream) + emission
    wiring in the `/devx` skill's story flow.
  - `.claude/commands/devx-test.md` in the devx repo (the O-4 slot) + its
    routing mention + `devx next` repo-table row.
  - `qa.browser_harness` enum extension (`claude-in-chrome`) in
    `config-schema.json`.
  - The browser-flow eval artifact convention + one demonstration artifact.
  - The QA.md §Layer 2 narrow revision + O-4 status update.

## Design

### Architecture

Four cooperating surfaces, two repos:

**1. Config truth (palateful `devx.config.yaml`)** — a `projects:` block:

| name | path | test |
|---|---|---|
| `api` | `services/api` | `poetry run pytest` |
| `app` | `app` | `flutter test` |
| `e2e` | `services/e2e` | `bash scripts/run_all.sh` |
| `workstream-evals` | `_devx/workstreams` | `bash` |

Longest-prefix resolution sends `_devx/workstreams/<slug>/evals/*.sh` to
the `bash` runner (command becomes `bash <script>` with cwd
`_devx/workstreams`, mirroring the devx repo's own `npx tsx` idiom at
`~/personal/devx/devx.config.yaml:363-390`), API test artifacts to pytest,
and Dart artifacts to `flutter test`. The `qa:` block becomes truthful:
`browser_harness: claude-in-chrome` (post enum extension),
`scripted_test_runner: flutter-drive`.

**2. Scripted layer (gen-2 revival, `services/e2e/`)** — `e2e:test` becomes
the full lifecycle: `stack-up` (compose overlay now also setting
`ENVIRONMENT: development` and `DATABASE_URL=…/test` on the api service) →
wait-for-healthy poll on `localhost:8000` → `run_all.sh` (existing
chromedriver autostart + flake pkill, plus one `AppConnectionException`
retry per test) → `stack-down` in a trap so teardown survives failure →
exit nonzero if any flow failed. Gen-1 (`flows/`, `config.yaml`) moves to
`archive/e2e-maestro/` (config `storage.archive_path`); `README.md` is
rewritten to describe only the live path.

**3. Story-derived QA (both repos)** — upstream:
`_devx/templates/engine/qa-walkthrough.md` modeled on the ifh-1 skeleton
(header + scope blockquote → `## Pre-flight` runnable block with expected
output annotated inline → `## Manual checks` as numbered behavioral
assertions, each a fenced runnable block + expected output + invariant →
`## Regressions to watch` → `## Post-merge follow-ups`), with each item
tagged `machine` or `human`. Emission wiring in the `/devx` skill: at
Phase 5 (local CI validation — evidence is freshest there) the agent
authors `test/test-<hash>-qa-walkthrough.md` for stories with user-visible
surfaces, executes every `machine` item inline (evidence pasted, boxes
checked), leaves `human` items unchecked with a one-line "how to verify",
and appends a TEST.md entry; the file commits with the story in Phase 6.
This implements the `docs/QA.md:150-184` story-derived flow.

**4. Attended exploratory layer (`/devx-test`, devx repo O-4 slot)** —
`.claude/commands/devx-test.md`, mirrored to `skills/` via
`npm run sync:skills`, installed by `devx init`. Protocol: resolve target
(surface name, story hash → its walkthrough, or TEST.md top entry) →
verify preconditions (Claude-in-Chrome connected via `tabs_context`; local
web build at `localhost:8888` running `--dart-define=E2E_MODE=true`, offer
the launch command if absent) → drive the journeys in-browser, one surface
per invocation → route findings: UX friction → `FOCUS.md`, reproducible
bugs → `DEBUG.md` (with repro line), harness/runner crashes → `DEBUG.md`
filed against devx itself (`docs/QA.md:129-133` routing) → report spend
against the $1 cap. Dispatcher wiring: a routing mention in `devx.md`
(the seam already named at `skills/devx.md:566`) and one repo-level
`devx next` row (`~/personal/devx/src/lib/next/decide.ts`): TEST.md has
unclaimed walkthrough entries → suggest `/devx-test`.

**Persona seeding (FR-8, later phase)** — a `--persona <name>` argument on
the same skill, no new surface. The skill reads
`focus-group/personas/persona-<name>.md` (5 files exist) before target
resolution and derives the pass from it: the persona's goals/frustrations
sections become the pass's journey priorities, its vocabulary and
tech-comfort level set the interaction style (e.g. the newcomer persona
never uses keyboard shortcuts or deep links; the power-user persona
races through happy paths hunting for friction at speed), and every
FOCUS.md/DEBUG.md finding is annotated `persona: <name>` so recurring
per-persona friction is greppable. Unknown persona name → list available
files and stop. Sequencing is a hard precondition, restated from the PRD:
FR-8 lands only after FR-5 has completed at least one end-to-end pass
(E-4), so the base protocol is proven before persona variation multiplies
it.

**Browser-flow eval convention (CAP-6)** — a documented shape: an
executable `.sh` under `_devx/workstreams/<slug>/evals/` that (a)
self-locates the repo root (`git rev-parse --show-toplevel`), (b) asserts
its preconditions (stack reachable, chromedriver present) and exits 2 with
a clear message when infra is missing, (c) runs one targeted flow —
`flutter test --platform chrome --dart-define=E2E_MODE=true <target>` for
headless, or a `test-single` drive for full-fidelity — and (d) prints the
asserted behavior before exiting nonzero while the feature is missing.
Exit-code contract: 0 = behavior present, 1 = behavior missing
(right-reason RED), 2 = infra failure (must be fixed before the gate
counts). One demonstration artifact in this workstream proves the shape
end-to-end (E-5).

**Decision propagation (CAP-7/FR-7)** — the locked palateful decision
(`decisions/2026-07-27-hybrid-qa-driver.md`) propagates upstream as plain
devx-main commits: `docs/QA.md` §Layer 2 gains the narrow attended
carve-out (line 53's blanket ❌ becomes "❌ for unattended/automated;
✅ for user-attended on-demand passes"), `docs/OPEN_QUESTIONS.md:148-155`
gets an addendum pointing at the revision, and O-4
(`v2/07-decisions.md:86-92`) is updated to point at the shipped
`/devx-test`. No `devx revise` cascade applies — these are framework docs,
not gated workstream artifacts; pln104 discipline is satisfied by the
lock-compare-update-propagate chain above.

### Interfaces

- `npx nx run e2e:test` — full lifecycle; exit 0 iff all 7 flows pass.
  `npx nx run e2e:test-single --args="--test=integration_test/03_create_recipe_test.dart"`
  — one flow, stack assumed up. `e2e:stack-up` / `e2e:stack-down` retained.
- `/devx-test <surface|story-hash>` (later `--persona <name>`) — attended
  pass; writes FOCUS.md/DEBUG.md entries; no exit code (skill, not CLI).
- Eval scripts: argv-free executables; env: inherits the session; exit
  0/1/2 per the convention above.
- `devx gate evals 41ee13 [--dry-run]` — unchanged engine surface; after
  the config lands it resolves every artifact of this workstream.
- Walkthrough files: `test/test-<hash>-qa-walkthrough.md`; items carry
  `- [ ]`/`- [x]` checkboxes; machine items carry fenced evidence blocks.

### Data

No databases, schemas, or migrations. New/updated files only:
palateful — `devx.config.yaml`, `docker-compose.e2e.yml`,
`services/e2e/{scripts/run_all.sh,README.md,project.json}`,
`archive/e2e-maestro/`, `test/test-*-qa-walkthrough.md` (per story),
`_devx/workstreams/browser-qa-agent/evals/*`; devx —
`.claude/commands/{devx-test.md,devx.md}`, `skills/` mirrors,
`_devx/templates/engine/qa-walkthrough.md`, `_devx/config-schema.json`,
`docs/QA.md`, `docs/OPEN_QUESTIONS.md`, `v2/07-decisions.md`,
`src/lib/next/decide.ts` (+ its table test). Retention: walkthroughs live
with the repo; no cleanup policy needed at current volume.

## Migration plan

Ordering is driven by two dependencies: the schema enum must land before
palateful's `qa:` flip (config would fail validation), and the skill must
exist upstream before it can be installed here.

1. **Palateful, immediately useful**: add the `projects:` block (no schema
   conflict) — the RED gate comes alive for every workstream; fix the two
   compose-overlay defects; wrap `e2e:test` lifecycle; archive gen-1;
   rewrite README.
2. **Devx main, direct commits** (user decision): `browser_harness` enum
   extension; `qa-walkthrough.md` template; `/devx` emission wiring;
   `.claude/commands/devx-test.md` + routing mention + `devx next` row +
   table test; QA.md/OPEN_QUESTIONS/O-4 revision. Version bump.
3. **Palateful, after install**: `devx init` upgrade pulls the new
   skill/template; flip the `qa:` block to truthful values; author the E-5
   demonstration artifact; first attended `/devx-test` pass on the
   recipe-import journey (E-4).
4. **Persona seeding last (FR-8)**: only after step 3's end-to-end
   `/devx-test` pass has completed — the PRD's explicit precondition —
   add the `--persona` argument per the seeding protocol above (E-6).

Nothing breaks mid-sequence: the stale `qa:` block stays inert until step
3, the e2e revival in step 1 has no devx dependency, and step 4 is purely
additive to a proven skill.

## Resolved design questions

- **e2e target: local-only or prod smoke?** → Local-only; prod smoke is a
  separate future decision (user, this session).
- **FR-5 lands on devx main directly or via a devx workstream?** → Direct
  to main; it's the O-4 slot and both repos run YOLO (user, this session).
- **Attended driver?** → Claude-in-Chrome, per the locked hybrid-driver
  decision; user re-confirmed this session.
- **What does "right-reason" mean mechanically?** → Nonzero exit only;
  the failure quote is captured, not asserted (`gate-evals.ts:403-414`).
  Eval scripts compensate by printing the asserted behavior and reserving
  exit 2 for infra failures.
- **Which DB does the e2e API use?** → The `test` database via overlay
  `DATABASE_URL` override, matching `migrator-test`'s target and isolating
  e2e writes (this design, Trade-offs).
- **Where does the walkthrough template live?** → Upstream in the devx
  packaged `templatesRoot`; palateful receives it via `devx init`
  (ownership semantics, Constraints).

## Unresolved design questions

- **Does `devx init` actually install net-new template files into an
  already-initialized repo?** Assumed yes (mirrors `installSkills`
  write-if-absent); verified at plan stage by reading the init-write path.
  Fallback (commit the template directly in palateful) is one file — no
  P0 depends on the answer, so Gate 2 is not blocked.
- **Exact `devx next` row placement for the TEST.md-backlog condition**
  (between execute rows 8/9 or after) — settled during the devx-main
  change by the existing table's first-match-wins ordering plus its test;
  no palateful artifact depends on the placement.
