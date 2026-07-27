---
hash: arci1
type: debug
created: 2026-07-27T23:10:00-06:00
title: await-remote-ci reports success while a sibling workflow is red
from: dev/dev-rsh101-2026-07-27T12:30-unblock-deploy-path.md
status: ready
owner: null
branch: null
---

## Goal

`devx devx-helper await-remote-ci <branch>` should not report a terminal
`success` for a branch that has a failing workflow run on the same commit.
Today it reports the newest run only, so `/devx` Phase 7 concludes "CI
green, proceed to merge" while `devx merge-gate` — which aggregates every
check — correctly says `merge:false`. The two helpers disagree about the
same commit, and the disagreement is silent.

Repo state matters here: this repo runs **two** workflows on every PR,
`CI & Deploy` (`ci.yml`) and `devx-ci` (`devx-ci.yml`). Any branch where
they disagree hits this.

## Acceptance criteria

- [ ] `await-remote-ci` returns a non-success terminal state when *any*
      workflow run at the branch's `headSha` concluded non-success.
- [ ] The returned JSON names which workflow failed, so the Phase 7 status
      log line is actionable without a second `gh` call.
- [ ] A branch with one green and one red workflow is covered by a test —
      this is the exact case that produced the false green.
- [ ] `in-progress` still wins over a completed sibling: if one workflow is
      done and another is still running, the state stays `in-progress`
      rather than resolving early on a partial view.
- [ ] The skill's Phase 7 dispatch table in `.claude/commands/devx.md` still
      describes the states accurately after the change.

## Technical notes

- Observed on 2026-07-27 during rsh101 Phase 8, commit `408aeaf`:
  - `await-remote-ci feat/dev-rsh101 --once` →
    `{"state":"completed","conclusion":"success","runId":30296754787}`
    (that is `CI & Deploy`, which genuinely passed).
  - `devx merge-gate rsh101` →
    `{"merge":false,"reason":"CI not green (conclusion=failure)"}`.
  - `gh run list --branch feat/dev-rsh101` showed both runs at the same
    `headSha`: `30296754787 CI & Deploy … success` and
    `30296754128 devx-ci … failure`.
- The merge gate caught it, so nothing bad shipped — **this is a
  defense-in-depth failure, not an incident**. The risk is that Phase 7 is
  documented as the place that waits for CI, and a future change that
  trusts its verdict without a merge-gate re-check would merge red.
- Likely fix shape: `gh run list` already returns every run; take the set at
  `headSha` rather than `[0]`, and fold: any `failure`/`cancelled`/
  `timed_out` → that conclusion; any still running → `in-progress`; all
  success → `success`.
- Adjacent smell, worth deciding rather than inheriting: `debug-dvxci1`
  left an open question about whether a TS/JS `devx-ci` should exist at all
  in a Python/Flutter repo where `ci.yml` already runs the real suites. If
  that workflow is deleted, this bug stops biting *this* repo — but the
  helper is still wrong for any repo with two workflows.

## Status log

- 2026-07-27T23:10 — filed from rsh101 Phase 8. Found because `merge-gate`
  and `await-remote-ci` disagreed on commit `408aeaf`; investigating the
  disagreement is also what surfaced the imptab1 collision, so the false
  green cost nothing this time and saved something.
