---
hash: bqa104
type: dev
created: 2026-07-27T11:42:00-06:00
title: Upstream attended layer — devx-test skill, routing, QA.md carve-out
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: ready
blocked-by: [bqa103]
branch: feat/dev-bqa104
---

## Goal
Fill the devx O-4 slot: the attended exploratory `/devx-test` skill, its dispatcher routing, its `devx next` nudge, and the FR-7 decision propagation (framework QA.md attended carve-out). Closes with the devx version bump so bqa105 installs everything in one upgrade.

## Acceptance criteria
- [ ] `~/personal/devx/.claude/commands/devx-test.md` (new) + `skills/devx-test.md` mirror — protocol: resolve target (surface | story hash → walkthrough | TEST.md top) → preconditions (Claude-in-Chrome connected via `tabs_context`; local web build at `localhost:8888` running with `--dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000`, offer the launch command if absent) → drive journeys, one surface per invocation → route findings (UX friction → FOCUS.md; reproducible bugs → DEBUG.md with repro line; harness crashes → DEBUG.md against devx per `docs/QA.md:129-133`).
- [ ] The skill enforces the cost cap: G-5 is $1/**day** — skill body states the daily budget, checks for a same-day prior pass (its own report lines in FOCUS.md/DEBUG.md are the record), warns + requires explicit user confirmation before a second same-day invocation, and reports cumulative same-day spend at end of every pass.
- [ ] `/devx` dispatcher routing mention at the seam (`skills/devx.md:566`); `src/lib/next/decide.ts` gains the row: TEST.md has unclaimed walkthrough entries → suggest `/devx-test` (placement by first-match-wins ordering); table test updated.
- [ ] FR-7 propagated: `docs/QA.md` §Layer 2 line 53 blanket ❌ becomes "❌ for unattended/automated; ✅ for user-attended on-demand passes" (cadence cap $1/day unchanged); `docs/OPEN_QUESTIONS.md:148-155` addendum; `v2/07-decisions.md:86-92` O-4 points at the shipped skill.
- [ ] `package.json` version bumped; devx suite green; mirror matches.

## Technical notes
- Cross-repo story: work lands in `~/personal/devx` (direct to its main). Sequenced after bqa103 (same repo; single version bump at end of this story).
- Skill-body scope enforcement (one surface/story per invocation, no chained runs, `docs/QA.md:215-220`) + per-day cap = the E-4/G-5 cost guardrail.
- FR-7 propagation is plain doc commits — no `devx revise` cascade; pln104 satisfied by lock (palateful `decisions/2026-07-27-hybrid-qa-driver.md`) → compare → update → this story.
- Full context: plan `_devx/workstreams/browser-qa-agent/plan.md` §Phase 4.

## Status log
- 2026-07-27T11:42 — emitted from plan 41ee13 at RED-gate PASS (tests-after phase).
