---
gate: PASS
status_reason: 'Every runnable expectation observed RED for the right reason (4 run(s), 2 deferred).'
reviewer: 'devx gate evals'
updated: 2026-07-27
waiver: { active: false, approver: null, reason: null }
---

# RED report — _devx/workstreams/browser-qa-agent — 2026-07-27

## Runs

### E-1: RED gate resolves runners in palateful (P0)

- **Artifact**: _devx/workstreams/browser-qa-agent/evals/e1_runner_resolution.sh
- **Command**: `bash run-eval.sh browser-qa-agent/evals/e1_runner_resolution.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  runner resolution OK: 4 planned (all with commands) + 2 deferred
  MISSING BEHAVIOR: devx.config.yaml still names playwright 2 time(s) — playwright is installed nowhere in this repo; the qa: block must name only installed tools (E-1 threshold)
  ```
- **RED verdict**: right-reason

### E-2: One-command e2e suite green (P0)

- **Artifact**: _devx/workstreams/browser-qa-agent/evals/e2_e2e_one_command.sh
- **Command**: `bash run-eval.sh browser-qa-agent/evals/e2_e2e_one_command.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  MISSING BEHAVIOR: services/e2e/scripts/e2e_lifecycle.sh does not exist — 'npx nx run e2e:test' has no stack lifecycle (up → wait-healthy → flows → teardown-in-trap); the one-command e2e suite is not built yet
  ```
- **RED verdict**: right-reason

### E-3: Walkthrough template emission with executed checks (P1)

- **Artifact**: _devx/workstreams/browser-qa-agent/evals/e3_walkthrough_emission.sh
- **Command**: `bash run-eval.sh browser-qa-agent/evals/e3_walkthrough_emission.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  MISSING BEHAVIOR: _devx/templates/engine/qa-walkthrough.md does not exist — the QA-walkthrough template is not installed
  ```
- **RED verdict**: right-reason

### E-5: Interactive expectation goes RED for the right reason (P1)

- **Artifact**: _devx/workstreams/browser-qa-agent/evals/e5_red_browser_flow.sh
- **Command**: `bash run-eval.sh browser-qa-agent/evals/e5_red_browser_flow.sh`
- **Exit code**: 1
- **Failure quote**:
  ```
  MISSING BEHAVIOR: _devx/workstreams/browser-qa-agent/evals/README.md does not exist — the browser-flow eval convention is not documented for reuse
  ```
- **RED verdict**: right-reason

## Deferred stubs

- E-4: not-run (deferred: human) (P1)
- E-6: not-run (deferred: human) (P2)
