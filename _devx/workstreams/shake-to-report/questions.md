<!-- questions.md — Shake To Report health queue. Gate concerns and parked
  questions, one `## Q-<n>: <title>` each, carrying exactly these bullets:

  Kind: gate-concern | open-question | discovered-gap | needs-revision ·
  Severity: blocking | concern (required — missing fails the parse) ·
  Blocks: gate-<prd|design|plan|evals> | phase-N | — · Origin (which run
  recorded it) · Recommendation (required when blocking) ·
  Status: open | asked | answered | resolved · Resolution

  Auto-populated — every `devx gate` run reconciles its own findings: adds,
  updates, resolves. Current-state, never a gate INPUT, ids never reused;
  hand-edits are legal. `/devx-walk` resolves one entry per invocation.
-->

## Q-1: expectation-threshold-not-numeric at _devx/workstreams/shake-to-report/expectations.md:155: E-8 Threshold 'the queued item is sent exactly once and the queue is empty, with Profile never built; Profile's tile opens the same sheet with `trigger` `profile` and route `/profile`.' carries no numeric value — thresholds must be measurable

- **Kind:** gate-concern
- **Severity:** blocking
- **Blocks:** gate-prd
- **Origin:** devx gate prd · _devx/workstreams/shake-to-report/prd/agent.md
- **Recommendation:** E-8 Threshold 'the queued item is sent exactly once and the queue is empty, with Profile never built; Profile's tile opens the same sheet with `trigger` `profile` and route `/profile`.' carries no numeric value — thresholds must be measurable
- **Status:** resolved
- **Resolution:** plan/plan-f89791-2026-11-25T09:02-shake-to-report.md

---
