---
hash: prstrnd
type: debug
created: 2026-09-20T10:15:00-06:00
title: Finished, verified work strands indefinitely in a conflicted PR with no detector
from: null
status: ready
owner: null
branch: null
---

## Goal

A PR that holds *completed, verified* work and has become unmergeable
should surface itself within days, not sit silent for months. Today
nothing in this repo watches the open-PR queue for staleness, so the only
way a stranded PR gets noticed is a human happening to look.

This is a **detector gap, not a merge-queue request**. The ask is not "auto
merge things" — it is "make silence audible". A conflicted PR is currently
indistinguishable from an open one that somebody is actively working.

## Why this is worth a story

Observed 2026-09-20. PR #24 (branch `feat/dev-7c5cf2`, story af8309) was
opened 2026-07-31 and never touched again:

- `mergeable: CONFLICTING`, `mergeStateStatus: DIRTY`
- `statusCheckRollup: []` — **no CI check ever ran on it**
- `updatedAt == createdAt` — zero activity for 51 days
- Its only merge conflict was the append-only devx Status log in
  `dev/dev-7c5cf2-…-rsh108-follow-up….md`. Both workflow files in the PR
  merged clean.

It carried the fix for `deploy-freshness`, whose entire job is to notice a
prod deploy freeze. The fix had already been proven live in Actions
(dispatch runs 30652052889 / 30652190943 pass, 30652140468 correctly
fails on a synthetic 8d gap) before the PR was opened. So for 51 days:

- the freeze detector was red on every scheduled run and produced no verdict,
- prod was genuinely frozen (origin/main last moved 2026-07-31),
- and the repaired detector sat finished-but-unmerged behind a **markdown
  conflict in a bookkeeping file**.

Two independent failures stacked: the monitor was blind, and the fix for
the monitor was also invisible. The second is the more general bug — it
will strand the next thing too, and that thing may not have a coordinator
session stumbling across it.

## Acceptance criteria

- [ ] Something runs on a schedule and reports open PRs that are
      simultaneously (a) unmergeable or conflicted, and (b) untouched for
      more than N days. N configurable; start at 7.
- [ ] The report also flags open PRs with an **empty check rollup** — #24
      never ran CI at all, which is a distinct and quieter signal than
      "CI failed" and is what made it look inert rather than broken.
- [ ] The report distinguishes "conflicted" from "merely stale", because
      the remedies differ: a conflicted PR needs a rebase decision, a stale
      green one needs a merge decision.
- [ ] Output lands where a human or a loop will actually read it — a
      `DEBUG.md` entry, a MANUAL.md entry, or a failing scheduled check.
      A report written only to a run log repeats the original bug.
- [ ] The detector reports on itself honestly: if it cannot reach the
      GitHub API it must fail loudly rather than emit an empty list, since
      "no stranded PRs" and "I could not look" must not look identical.
      This is the same green-and-blind failure mode `deploy-freshness`
      exists to prevent, so the detector must not reproduce it.
- [ ] Verified against the real case: run it against PR #24's recorded
      state (or a fixture of it) and confirm it is reported.

## Technical notes

- `gh pr list --json number,mergeable,mergeStateStatus,updatedAt,statusCheckRollup`
  returns every field the acceptance criteria need in one call — the
  detector is a query plus a threshold, not an integration.
- Deliberately unspecified: whether this ships as a scheduled workflow, a
  `devx` helper, or a `tools/` script. Prefer whichever the repo already
  has a home for; `deploy-freshness.yml` is the nearest prior art for "a
  scheduled check whose failure IS the alarm", and its header comment
  explains why such a check must live in its own file rather than inside
  `ci.yml` — that reasoning applies here verbatim.
- Related but out of scope: the devx spec Status log is append-only by
  convention (CLAUDE.md, "Working agreements"), which makes it a
  near-guaranteed conflict surface whenever a branch lives longer than the
  main-branch bookkeeping commits. Worth a separate look at whether that
  file should be merge-strategy `union`; it is the proximate cause here but
  not the systemic one, and fixing it would not have made the strand
  visible — only less likely.
- Scope guard: this is about *detection*. Do not turn it into an
  auto-rebase or auto-merge feature; a stranded PR often strands for a
  reason (#24 carries ~2000 unreviewed lines), and the correct output is a
  human-legible flag, not an automated resolution.

## Status log

- 2026-09-20T10:15 — filed while fixing `deploy-freshness` auth. The
  requested fix turned out to already exist and be proven; the real defect
  was that it had been stranded in PR #24 for 51 days with nothing
  watching. Filed at the coordinator session's request, scoped to the
  missing detector rather than to #24 itself. #24 is left untouched.
