---
hash: bqa105
type: dev
created: 2026-07-27T11:43:00-06:00
title: Palateful adoption — install, qa flip, browser-flow eval convention
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: ready
blocked-by: [bqa101, bqa102, bqa103, bqa104]
branch: feat/dev-bqa105
---

## Goal
Pull the upstream work into palateful and make E-5 green by delivering the convention README + demonstration flow that its wrapper (`evals/e5_red_browser_flow.sh`, authored at RED) asserts. After this story every machine-verifiable expectation of the workstream is green except E-3 (needs a story to emit a walkthrough — bqa106).

## Acceptance criteria
- [ ] `devx init` (upgrade) run: reports the new skill + template installed; `.claude/commands/devx-test.md` exists with the version header, `_devx/templates/engine/qa-walkthrough.md` exists (headerless by design); the hand-added `projects:` block still present in `devx.config.yaml` afterwards (upgrade round-trips through a comment-preserving YAML document, `init-upgrade.ts:245,349`).
- [ ] `devx.config.yaml`: `qa.browser_harness: claude-in-chrome` (enum now extended upstream); `devx config get qa.browser_harness` prints `claude-in-chrome`.
- [ ] `_devx/workstreams/browser-qa-agent/evals/README.md` (new) documents the browser-flow eval convention for reuse-without-new-wiring: shape (executable `.sh` under `evals/`, self-locate root via `git rev-parse --show-toplevel`, precondition asserts), Exit contract (0 present / 1 missing = right-reason RED with `MISSING BEHAVIOR:` banner / 2 + `INFRA:` sentinel = infra), the `run-eval.sh` dispatcher, the RED-report `INFRA:` grep discipline, and the headless invocation recipe (`flutter test --platform chrome --dart-define=E2E_MODE=true --dart-define=API_BASE_URL=http://localhost:8000 <target>`). Must contain the literal terms the e5 wrapper greps: `Exit contract`, `INFRA:`, `run-eval.sh`, `MISSING BEHAVIOR:`.
- [ ] `_devx/workstreams/browser-qa-agent/evals/demo_browser_flow.sh` (new) — reference implementation: targets a deliberately unbuilt behavior, prints the asserted behavior with the `MISSING BEHAVIOR:` banner, exits 1; exits 2 + `INFRA:` when stack/chromedriver missing. Permanently red by design; not a Verified-by artifact; excluded from every default suite glob by location.
- [ ] `bash run-eval.sh browser-qa-agent/evals/e5_red_browser_flow.sh` exits 0 with the stack up; with the stack down it exits 2 printing `INFRA:` (spot-check both, evidence pasted). Wrapper NOT re-authored.
- [ ] `bash run-eval.sh browser-qa-agent/evals/e1_runner_resolution.sh` still exits 0 (config regression guard).

## Technical notes
- `right-reason` is exit-code-only in the gate (`gate-evals.ts:403-414`) — the printed-banner + `INFRA:` sentinel convention is what keeps RED-report quotes readable and wrong-reason RED detectable.
- Depends on all of bqa101–bqa104: the qa flip builds on bqa101's interim values + bqa103's enum; the install needs bqa104's version bump; the demo flow's stack-down INFRA path exercises bqa102's stack.
- Full context: plan `_devx/workstreams/browser-qa-agent/plan.md` §Phase 5.

## Status log
- 2026-07-27T11:43 — emitted from plan 41ee13 at RED-gate PASS (tests-first phase; RED artifact `evals/e5_red_browser_flow.sh` observed failing right-reason, see `evals/RED-report.md`).
