---
hash: bqa107
type: dev
created: 2026-07-27T11:45:00-06:00
title: Persona-seeded passes — --persona flag + one seeded pass
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: ready
blocked-by: [bqa106]
branch: feat/dev-bqa107
---

## Goal
FR-8, explicitly last (PRD precondition: only after bqa106's end-to-end pass). Add `--persona <name>` to the upstream `/devx-test` skill and run one persona-seeded pass here. **Requires Leo present** for the pass. Fills the E-6 pass record.

## Acceptance criteria
- [ ] `~/personal/devx/.claude/commands/devx-test.md` + mirror gain the `--persona` argument: read `focus-group/personas/persona-<name>.md` before target resolution; goals/frustrations → journey priorities; vocabulary/tech-comfort → interaction style; findings annotated `persona: <name>`; unknown name → list available files and stop. Version bump + reinstall here (`devx init` upgrade).
- [ ] ≥ 1 pass with a real persona file; every finding annotated `persona: <name>` (greppable) in FOCUS.md / DEBUG.md.
- [ ] Unknown-persona invocation lists files and stops (spot-check, evidence pasted).
- [ ] `_devx/workstreams/browser-qa-agent/evals/E-6_persona_pass.md` updated from stub to the pass record.

## Technical notes
- Cross-repo (skill change upstream in `~/personal/devx`, direct to its main) + attended pass here.
- 5 persona files exist in `focus-group/personas/`; the pass reuses the bqa106 protocol unchanged — persona only varies priorities and tone. The per-day cap ($1/day) applies across persona and plain passes alike.
- Full context: plan `_devx/workstreams/browser-qa-agent/plan.md` §Phase 7.

## Status log
- 2026-07-27T11:45 — emitted from plan 41ee13 at RED-gate PASS (human-validation phase; E-6 pass record filled here).
