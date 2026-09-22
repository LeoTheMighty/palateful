# PRD — Browser QA Agent (hybrid exploratory + scripted RED-gate QA)

<!-- Stage: PRD. Gate: `devx gate prd 41ee13`. IDs are stable, never renumbered. -->

## Problem

Palateful has no QA agent, and the seams reserved for one are all dead ends
today. `/devx-test` is named as the owner of exploratory QA in `CLAUDE.md` and
`devx.md` but was never built (devx framework open question O-4 — its
precondition, V2.4, has since shipped). The de-facto QA process — 228
hand-rolled `*-qa-walkthrough.md` files in `_bmad-output/implementation-artifacts/`
— has no template, three drifting format generations, and stopped being
produced on 2026-05-03 while dev work continued through 2026-07-27.

The executable layer is dormant, not rotted: `services/e2e/` holds an
abandoned Maestro suite (gen 1) and a working-locally Flutter
`integration_test` + `flutter drive` + ChromeDriver harness (gen 2, 7 passing
tests, known ChromeDriver flake), with intact, unit-tested `E2E_MODE` auth
bypass on both the Flutter and API sides. CI explicitly excludes it
(`.github/workflows/ci.yml:223 --exclude=e2e`). Meanwhile a real
browser-drivable surface ships to production on every push (Flutter web at
https://palateful.app).

Two structural blockers make this urgent beyond QA itself: palateful's
`devx.config.yaml` has **no `projects:` runner block**, so `devx gate evals`
returns `not-run (no runner)` for every artifact and auto-fails any P0 — the
RED gate is dead on arrival for *every* workstream in this repo. And the
`qa:` config block claims `browser_harness: playwright`, which is installed
nowhere; reality is Maestro/flutter-drive.

## Goals

- **G-1**: By 2026-08-15, `devx gate evals --dry-run` in palateful resolves
  every eval artifact to a `projects:` runner — 0 `not-run (no runner)`
  verdicts on this and subsequent workstreams.
- **G-2**: By 2026-08-15, the gen-2 e2e harness runs green locally via one
  command (`npx nx run e2e:test` or equivalent) with the ChromeDriver flake
  mitigated — ≥ 7 integration tests passing.
- **G-3**: By 2026-08-31, every `/devx` story with a user-visible surface
  emits a QA walkthrough from a single template, with 100% of its
  machine-checkable items executed by the agent before handoff (human-only
  items listed unchecked).
- **G-4**: By 2026-09-15, at least one interactive expectation on a
  UI-touching workstream receives a `right-reason` RED verdict via a scripted
  browser flow, instead of `not-run (deferred: human)`.
- **G-5**: Exploratory QA passes are on-demand and cost ≤ $1/day (framework
  YOLO cadence cap, `docs/MODES.md` §2.6 / `docs/QA.md` §Cadence), measured
  from first `/devx-test` availability.

## Non-goals

- **CI wiring of the browser e2e suite** — the ChromeDriver flake makes CI
  gating premature; local one-command green is the bar this workstream sets.
- **Reviving Maestro (gen 1)** — superseded by the flutter-drive harness;
  gen-1 flows get archived, not fixed.
- **A subprocess browser-use/Stagehand runner on a separate API key** — the
  framework's QA.md architecture for *unattended* QA stays reserved; this
  workstream covers on-demand, user-attended passes only (see FR-7).
- **Mobile-native QA (iOS/Android device automation)** — web build only;
  Firebase Test Lab / device farms are out of scope.
- **Replacing the eval harness at `services/eval/`** — that is LLM
  answer-quality eval ("qa" = question-answer), unrelated; we reuse its
  `projects:` runner idiom, not its code.

## Users

- **Primary**: Leo (solo operator) — wants stories verified against the real
  running system without hand-working 30-item checklists.
- **Secondary**: the `/devx` dev agent — needs a walkthrough contract to emit
  against and a runner to execute machine-checkable items with; and the
  `/devx-plan` planner — needs interactive expectations to be RED-able.
- **Anti-persona**: a QA team running scheduled unattended regression sweeps —
  the cadence here is on-demand, single-operator, YOLO mode.

## Use cases

- **UC-1**: The `/devx` agent completes a story with user-visible changes,
  emits `test/test-<hash>-qa-walkthrough.md` from the engine template,
  executes every machine-checkable item, and hands the human-only remainder
  to Leo.
- **UC-2**: Leo runs `/devx-test` after a story lands; the agent drives the
  local Flutter web build (`E2E_MODE=true`) through the affected user
  journeys via Claude-in-Chrome, files UX friction to `FOCUS.md` and real
  bugs to `DEBUG.md`.
- **UC-3**: During planning, an expectation about interactive behavior is
  given a browser-flow eval artifact; at the RED gate the `projects:` runner
  executes it and it fails for the right reason (feature missing), not
  `deferred: human`.
- **UC-4**: Leo runs the e2e suite locally before a risky merge with one
  command and gets a green/red answer in minutes.
- **UC-5** *(later phase)*: `/devx-test` seeds an exploratory pass from
  `focus-group/personas/*.md`, walking the app as a specific persona
  (framework items O-3 / OPEN_QUESTIONS #25).

## Capabilities

- **CAP-1**: Truthful QA config — a `projects:` runner block in palateful's
  `devx.config.yaml` (api, app, e2e, workstream-evals) and a corrected `qa:`
  block reflecting the hybrid driver.
- **CAP-2**: A revived one-command e2e runner over the gen-2 harness
  (stack-up → drive → teardown) with the ChromeDriver flake mitigation
  built in, and gen-1 Maestro archived.
- **CAP-3**: A QA-walkthrough template in `_devx/templates/engine/` plus
  emission wiring in the `/devx` story flow (the `docs/QA.md:150-185`
  "story-derived QA" flow, currently specified but unbuilt).
- **CAP-4**: A `/devx-test` skill in the devx framework repo
  (`~/personal/devx/skills/devx-test.md`), with its dispatcher routing row
  and `devx next` decision-table row, installed into palateful.
- **CAP-5**: An exploratory-pass driver protocol using Claude-in-Chrome
  against the local `E2E_MODE` web build, with findings routing
  (friction → `FOCUS.md`, bugs → `DEBUG.md`, runner crashes → filed against
  devx itself) per the framework QA contract.
- **CAP-6**: A browser-flow eval-artifact convention (paths matched by a
  `projects:` runner, nonzero exit when the feature is missing) making
  interactive expectations mechanically RED-able.
- **CAP-7**: A recorded, propagated revision of the framework's 2026-04-23
  QA-driver decision (see FR-7) — narrow carve-out, not a reversal.

## Feature requirements

### FR-1: `projects:` runner block in palateful

`devx.config.yaml` gains a `projects:` block with entries for at least:
`api` (path `services/api`, test via `npx nx run api:test` or pytest),
`app` (path `app`, test via `flutter test`), `e2e` (path `services/e2e`,
test via the revived runner), and `workstream-evals` (path
`_devx/workstreams`, test via a standalone script runner so eval scripts
never join the default suite). `devx gate evals 41ee13 --dry-run` resolves
every artifact of this workstream; longest-prefix resolution picks the
intended runner for each.

### FR-2: Correct the `qa:` config block

`qa.browser_harness` and `qa.scripted_test_runner` are updated to name the
real stack (flutter-drive scripted harness; claude-in-chrome exploratory
driver). No config key claims a tool that is not installed.

### FR-3: One-command e2e revival

A single command (nx target) brings up the e2e stack
(`docker-compose.e2e.yml`), runs all `app/integration_test/*_test.dart`
flows via `flutter drive` + ChromeDriver with the inter-test flake
mitigation applied, tears down, and exits nonzero on any failure. The gen-1
Maestro tree (`services/e2e/flows/`, `config.yaml`) is moved to an archive
location or deleted, and `services/e2e/README.md` rewritten to describe only
the live path.

### FR-4: QA-walkthrough template + emission

`_devx/templates/engine/qa-walkthrough.md` exists, modeled on the strongest
existing generation (the `ifh-*` hybrid: Pre-flight / numbered manual checks
with runnable blocks + expected output / Regressions to watch / Post-merge
follow-ups). `/devx` Phase 6 emits `test/test-<hash>-qa-walkthrough.md` from
it for stories with user-visible surfaces, executes machine-checkable items
inline (evidence pasted, boxes checked), and leaves human-only items
unchecked with a one-line "how to verify".

### FR-5: `/devx-test` skill (devx repo, O-4 slot)

A thin skill body in `~/personal/devx/skills/devx-test.md`: on-demand
exploratory pass over a named surface or recent story; hybrid driver
(Claude-in-Chrome primary for attended passes); reads walkthroughs and
`TEST.md` for targets; routes findings friction → `FOCUS.md`, bugs →
`DEBUG.md`; respects mode-derived cadence/cost caps; adds the `skills/devx.md`
§Routing row and the `devx next` decision-table row. Proved against
palateful as first consumer, then installed here.

### FR-6: RED-able browser-flow eval artifacts

A documented artifact shape for interactive expectations (a script under
`_devx/workstreams/<slug>/evals/` or a Dart integration test under
`app/integration_test/`) that a `projects:` runner executes at Gate 4 and
that exits nonzero while the feature is missing. At least one real
expectation in a subsequent workstream uses it (G-4's proof).

### FR-7: Framework QA-driver decision revision

The 2026-04-23 locked decision (`~/personal/devx/docs/QA.md` §Layer 2,
`docs/OPEN_QUESTIONS.md:148-155`: subprocess browser-use only; Claude Code
browser-MCP ❌ for automated QA) is revised **narrowly**: user-attended,
on-demand exploratory passes MAY use Claude Code browser tooling
(Claude-in-Chrome); unattended/scheduled QA remains subprocess-only on a
separate key. The revision is recorded in this workstream's `decisions/`,
propagated to `docs/QA.md` in the devx repo, and O-4 is updated to point at
the shipped `/devx-test`.

### FR-8: Persona-seeded exploratory passes *(later phase)*

`/devx-test` accepts a persona argument sourcing
`focus-group/personas/*.md`, seeding the pass's goals and tone. Explicitly
last; lands only after FR-5 has run at least once end-to-end.

## Evals seed

- `devx gate evals --dry-run` on this workstream → 0 `no runner` lines
  (threshold: exact 0).
- Revived e2e command → ≥ 7 tests pass, exit 0, on two consecutive runs
  (flake bar).
- Walkthrough template emission → a story's walkthrough has 100% of
  machine-checkable items executed with pasted evidence.
- `/devx-test` pass on the import flow → findings file written with correct
  FOCUS/DEBUG routing; wall spend ≤ $1.
- One interactive expectation → `right-reason` in `evals/RED-report.md`
  instead of `deferred: human`.

## Open questions

- Should the revived e2e runner target the *production* web build
  (palateful.app) for smoke, or local-only? — owner: user (default local-only;
  prod smoke is read-only territory and needs a separate decision).
- Does FR-5's skill land in the devx repo's main branch directly or via its
  own workstream there? — owner: user (default: direct, it's the O-4 slot and
  the framework repo is also YOLO).

## Reference links

- Spec: `plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md`
- Framework QA contract: `~/personal/devx/docs/QA.md` (esp. §Layer 2,
  §Story-derived QA, §Cadence)
- O-4 / O-3: `~/personal/devx/v2/07-decisions.md`; personas:
  `focus-group/personas/`
- RED-gate mechanics: `~/personal/devx/src/lib/engine/gate-evals.ts`
- Live harness: `services/e2e/NEXT_STEPS.md`, `app/integration_test/`,
  `docker-compose.e2e.yml`; auth bypass `app/lib/core/config/environment.dart:37`,
  `services/api/src/config.py:38`
- Walkthrough format exemplars: `_bmad-output/implementation-artifacts/ifh-1-qa-walkthrough.md`,
  `aam-9-qa-walkthrough.md`, `1-1-qa-walkthrough.md`
- Runner idiom to copy: `services/eval/` + `npx nx run eval:eval-gate`
