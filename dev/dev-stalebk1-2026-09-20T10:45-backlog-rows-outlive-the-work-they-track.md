---
hash: stalebk1
type: dev
created: 2026-09-20T10:45:00-06:00
title: Backlog rows outlive the work they track — reconcile against merged reality
from: dev/dev-rsh102-2026-07-27T12:31-credential-aware-health-probe.md
status: ready
owner: null
branch: null
---

## Goal

Detect backlog rows that have fallen out of step with **merged git reality**,
rather than only with each other.

rsh102 sat `blocked` in `DEV.md` for roughly seven weeks after its blocker had
merged. Three files pointed at work that no longer existed:

| File | Said | Reality |
|---|---|---|
| `DEV.md:58` | rsh102 `[-]` blocked on `debug-rshred1` | rshred1 merged 2026-07-31 (PR #9, `bac7d6b9`) |
| `DEBUG.md:14` | rshred1 `[/]` in-progress | same |
| `dev-rsh102…md` Technical notes | RED artifact is `test_health.py` | rshred1 had split it into `test_health_credential_probe.py` |

It also carried a hard deadline (2026-07-29) and a "first `terraform apply`
since 2026-04-26" framing, both of which real AWS and CI state had already
falsified. The story was not blocked on anything; it was blocked on
bookkeeping, and the top production blocker in the repo went unworked as a
result.

## The gap, precisely

Detectors already exist and they are not the problem:

- `devx next` **did** report the rsh102 `status-mismatch` (DEV.md `blocked` vs
  frontmatter `ready`) — as a `drift[]` field alongside a routing decision that
  pointed somewhere else entirely. It was emitted and ignored.
- `devx doctor` **does** have a `dead-blocker` check. It fired for `bqa102`
  (blocker `e2edwds` marked done) and did **not** fire for rsh102 — because
  rsh102's blocker `rshred1` was *itself* stale. Its `DEBUG.md` row still read
  `in-progress`, so the blocker looked alive.

That is the actual defect: **every current check compares one backlog
assertion against another backlog assertion.** When a row and its blocker go
stale together, the pair is self-consistent and invisible. Nothing compares a
backlog row against the merge that ended the work.

## Acceptance criteria

- [ ] A `devx doctor` check resolves each `Blocked-by:` target to its
      **merge state** (a merged PR, or a commit on `main` closing its spec),
      not to the blocker's backlog row. Flags a blocker whose work has merged
      regardless of what that blocker's own row claims. This is the check that
      would have caught rsh102 and did not.
- [ ] A check flags any `dev/*` spec whose `status:` has been `blocked` or
      `in-progress` for more than N days with no new status-log line and no
      commits on its branch. Staleness is a function of time, and nothing
      currently measures it. N configurable; default 14.
- [ ] A check flags a spec whose body cites a file path that no longer exists
      (rsh102's Technical notes pointed at `test_health.py` as its RED
      artifact for seven weeks after rshred1 moved it). Scope to paths inside
      fenced/backticked spans so prose is not parsed.
- [ ] `devx next` stops burying drift in a side-channel. When drift rows exist,
      either route to reconciling them or make the emitted `detail` name them
      as the reason the routed item was chosen over a drifted one — being
      correctly reported and still ignored for seven weeks is the failure mode.
- [ ] Deadline/date assertions in a spec body are flagged once past, so
      "Deadline: 2026-07-29" cannot still read as live on 2026-09-20.
- [ ] Whatever CI or scheduled job is chosen to run these, it reports
      somewhere a human sees without opting in. A detector nobody runs is the
      state we are already in.
- [ ] Regression test reconstructs the rsh102 shape: row A blocked on row B,
      B's own row stale, B's work merged — and asserts the new check fires.

## Technical notes

- `devx doctor`'s existing `dead-blocker`, `dead-owner` and `orphan-worktree`
  checks are the right place to extend; the machinery and the report format
  already exist.
- Merge state is cheaply available: `gh pr list --state merged --search <hash>`,
  or the `chore: mark <hash> done after PR #<n> merge` commits that the /devx
  Phase 8 tail already writes to `main`.
- Beware the inverse false positive: a spec may legitimately stay blocked on
  work that merged behind a feature flag. The check should report, not fix —
  consistent with `doctor`'s existing report-only posture for anything whose
  correct resolution depends on what a worktree holds.
- Cross-reference: `palateful-fb`'s sibling item covers the other half of this
  gap — **finished work stranding in a conflicted PR with no detector**. Same
  root shape (completed work that no backlog signal reflects), different
  surface. Link the two when that hash is known.

## Status log

- 2026-09-20T10:45 — filed from rsh102 Phase 1, which lost its first pass to
  this exact failure. Authorized by Leo via the coordinator session. The
  sharpening detail, found while filing: the detectors are not missing, they
  are mutually-referential — `doctor`'s `dead-blocker` check fired for bqa102
  and structurally could not fire for rsh102.
