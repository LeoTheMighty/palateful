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

## Q-2: G-2 coverage

- **Kind:** gate-concern
- **Severity:** concern
- **Blocks:** gate-design
- **Origin:** devx gate coverage · _devx/workstreams/shake-to-report/design/agent.md
- **Recommendation:** G-2 is ⚠️ partial (self-judged by the authoring session (no subagent tool). Mechanism and its physics are specified, but whether 2 g / 4 reversals hits 9 of 10 real shakes with 0 kitchen prompts is unproven until E-7 runs on hardware. The design says so.)
- **Status:** open
- **Resolution:** —

---

## Q-3: G-4 coverage

- **Kind:** gate-concern
- **Severity:** concern
- **Blocks:** gate-design
- **Origin:** devx gate coverage · _devx/workstreams/shake-to-report/design/agent.md
- **Recommendation:** G-4 is ⚠️ partial (self-judged by the authoring session (no subagent tool). Depends on arq103's route reaching main (external). Until then admins get feedback by the route-exists check.)
- **Status:** open
- **Resolution:** —

---

## Q-4: E-1 coverage

- **Kind:** gate-concern
- **Severity:** blocking
- **Blocks:** gate-plan
- **Origin:** devx gate coverage · _devx/workstreams/shake-to-report/plan/agent.md
- **Recommendation:** P0 floor unmet: E-1 is P0 but names no runnable artifact path
- **Status:** resolved
- **Resolution:** _devx/workstreams/shake-to-report/decisions/2026-11-25-plan-verify.md

---

## Q-5: E-2 coverage

- **Kind:** gate-concern
- **Severity:** blocking
- **Blocks:** gate-plan
- **Origin:** devx gate coverage · _devx/workstreams/shake-to-report/plan/agent.md
- **Recommendation:** P0 floor unmet: E-2 is P0 but names no runnable artifact path
- **Status:** resolved
- **Resolution:** _devx/workstreams/shake-to-report/decisions/2026-11-25-plan-verify.md

---

## Q-6: E-3 coverage

- **Kind:** gate-concern
- **Severity:** blocking
- **Blocks:** gate-plan
- **Origin:** devx gate coverage · _devx/workstreams/shake-to-report/plan/agent.md
- **Recommendation:** P0 floor unmet: E-3 is P0 but names no runnable artifact path
- **Status:** resolved
- **Resolution:** _devx/workstreams/shake-to-report/decisions/2026-11-25-plan-verify.md

---

## Q-7: E-4 coverage

- **Kind:** gate-concern
- **Severity:** blocking
- **Blocks:** gate-plan
- **Origin:** devx gate coverage · _devx/workstreams/shake-to-report/plan/agent.md
- **Recommendation:** P0 floor unmet: E-4 is P0 but names no runnable artifact path
- **Status:** resolved
- **Resolution:** _devx/workstreams/shake-to-report/decisions/2026-11-25-plan-verify.md

---
