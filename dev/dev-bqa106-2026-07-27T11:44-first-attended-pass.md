---
hash: bqa106
type: dev
created: 2026-07-27T11:44:00-06:00
title: First attended pass — walkthrough emission + recipe-import journey
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: ready
blocked-by: [bqa105]
branch: feat/dev-bqa106
---

## Goal
The attended proof of the whole stack: emit the first walkthrough from the installed template for the recipe-import surface, execute its machine items, then run `/devx-test` on that journey with Claude-in-Chrome against the local `E2E_MODE` web build. **Requires Leo present** — book the session when bqa105 closes (G-3's 2026-08-31 date rides on it). Turns E-3 green and fills the E-4 pass record.

## Acceptance criteria
- [ ] `test/test-<this-spec-hash>-qa-walkthrough.md` emitted from the installed template for the recipe-import surface: machine items executed with fenced evidence, human items unchecked with one-line "how to verify" hints; TEST.md entry appended.
- [ ] ≥ 1 completed `/devx-test` pass on the recipe-import journey; every finding lands in exactly one of FOCUS.md (UX friction) / DEBUG.md (reproducible bugs, with a repro line); cumulative same-day spend ≤ $1 (reported by the skill).
- [ ] `bash run-eval.sh browser-qa-agent/evals/e3_walkthrough_emission.sh` (cwd `_devx/workstreams`) exits 0. Eval NOT re-authored (authored at RED — its parse contract is what the walkthrough must satisfy).
- [ ] `_devx/workstreams/browser-qa-agent/evals/E-4_devx_test_pass.md` updated from stub to the pass record (journey, findings routed, spend vs cap).

## Technical notes
- Launch command for the target build (cwd `app`): `flutter run -d chrome --web-port=8888 --dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000` — the `API_BASE_URL` define is load-bearing; without it the pass drives production. The skill offers the command when the build is absent.
- One surface per invocation + per-day cap (bqa104's skill body) are the cost guardrails; recipe-import is the journey named by E-4's threshold.
- Attended story: /devx can prepare the walkthrough emission, but the exploratory pass itself needs Leo in the loop — coordinate via INTERVIEW.md/MANUAL.md if picked up unattended.
- Full context: plan `_devx/workstreams/browser-qa-agent/plan.md` §Phase 6.

## Status log
- 2026-07-27T11:44 — emitted from plan 41ee13 at RED-gate PASS (human-validation phase; E-3's RED artifact goes green here).
