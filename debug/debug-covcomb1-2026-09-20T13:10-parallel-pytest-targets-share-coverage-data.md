---
hash: covcomb1
type: debug
created: 2026-09-20T13:10:00-06:00
title: Parallel pytest targets share one coverage data file — local-green, CI-red
from: dev/dev-rsh102-2026-07-27T12:31-credential-aware-health-probe.md
status: ready
owner: null
branch: null
---

## Goal

Make the class of failure that took PR #29 red impossible to reintroduce,
or at least impossible to miss locally.

## Repro (confirmed both directions)

    npx nx run-many -t test --projects=utils,test-helper,migrator --parallel=3

With `--cov-branch` on `utils:test` only:

    INTERNALERROR> coverage.exceptions.DataError:
        Can't combine branch coverage data with statement data

Without it, or with `COVERAGE_FILE` isolated: 738 passed, gate OK.

## Root cause

`libraries/utils`, `libraries/test-helper` and `services/migrator` all run
`poetry run pytest` with `cwd: {workspaceRoot}`. coverage.py writes its data
files relative to the process cwd, so all three write into the **same**
directory. CI runs them concurrently (`nx affected -t test --parallel=3`,
`ci.yml`), so whichever finishes last runs `combine` over a pile of
`.coverage.*` files contributed by all three.

That is tolerable while every project measures the same *kind* of coverage.
It breaks the moment one of them differs: coverage refuses to combine
branch-measured data with statement-only data. rsh102 added `--cov-branch`
to `utils` alone and tripped it.

**The local/CI asymmetry is the real defect.** `npx nx run utils:test` on its
own is green, because there are no sibling data files to combine. Nothing a
developer runs locally exercises the condition. The shared cwd is a latent
trap that only springs under parallelism.

## Acceptance criteria

- [ ] Every pytest target that runs from `{workspaceRoot}` writes its
      coverage data somewhere unique — `COVERAGE_FILE` per project, or
      `cwd: {projectRoot}` where that is workable. rsh102 fixed `utils` only,
      because that was the target it broke; `test-helper` and `migrator` are
      still sharing and will collide the next time the two differ.
- [ ] A regression check that fails when two workspace-root pytest targets
      would share a coverage data file. Grep-level is fine — the point is
      that it fires without anyone having to run the parallel combination.
- [ ] `libraries/utils/pyproject.toml`'s `../../`-prefixed report paths are
      either corrected or documented. They resolve against the invocation
      cwd, not the rootdir, so the package default writes reports two levels
      above the repo — outside it in CI, and into the main checkout when run
      from a worktree. rsh102 pinned the paths in the nx target as a
      workaround; the package default is still wrong for anyone running
      pytest from the workspace root by hand.
- [ ] Document the trap wherever the nx target conventions live, so the next
      person adding a coverage flag to one project learns about the shared
      cwd before CI tells them.

## Technical notes

- rsh102's fix, for reference: prefix the command with
  `mkdir -p coverage/libraries/utils && COVERAGE_FILE=coverage/libraries/utils/.coverage`.
  Scoped deliberately to the one target that introduced the incompatibility.
- `services/api` and `services/worker` use `cwd: {projectRoot}` and are not
  affected — which is also the cleaner pattern to converge on.
- Cost of the miss: one full 24-minute CI cycle, and the failure surfaced as
  a pytest `INTERNALERROR` traceback with the real cause 40 lines down,
  under a job whose own test run had already printed `2631 passed`.

## Status log

- 2026-09-20T13:10 — filed from rsh102 Phase 7 after PR #29's `test` job went
  red while every local gate was green. Root cause found and fixed for
  `utils` inside rsh102 (`6d375e71`); this item covers the siblings still
  sharing, the missing regression check, and the `pyproject.toml` report
  paths. Repro confirmed in both directions before the fix was committed.
