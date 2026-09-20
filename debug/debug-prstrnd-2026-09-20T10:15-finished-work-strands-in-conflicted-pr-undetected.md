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

## If you are here because `deploy-freshness` is red

**That red is expected, and it is the check working.** As of 2026-09-20 the
alarm has been restored in a building that is still on fire: the credential
fix landed (#25), so the check now authenticates and measures — and the
first thing it correctly reports is that prod is ~51 days stale. Verified
against the live account the same day:

```
Running task definition: palateful-api-prod:63
Deployed commit:         848311af  2026-07-31 10:24:08 -0600
Gap: 51 day(s); threshold: 7 day(s).   -> exit 1
```

Do not suppress it, raise `MAX_GAP_DAYS`, or treat it as a regression in
the check. It goes green when **prod is deployed**, and not before. A green
run before a real deploy would mean the measurement has degraded back into
the blind-and-green mode the check exists to catch.

One caveat that was raised on 2026-09-20 and has since **expired**, recorded
so it is not re-derived: for a few hours it looked as though that day's
merges might deploy prod, which would have made green the *correct* answer
and left the run's exit status carrying no information either way. They did
not — all four ECS legs (`deploy-images`, `terraform-prod`, `run-migrator`,
`deploy-services`) skipped in run 35522939142 because `services_to_build`
came up empty, so prod never changed. The ambiguity was conditional on
something that did not happen. A caveat kept past its condition is just
another stale note, which is precisely the family of defect this story is
about.

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

The scale of the first failure is worth stating precisely, because it is
the argument for this story. Between 2026-08-01 and 2026-09-19 the
pre-fix copy on `main` fired **50 scheduled runs and all 50 failed** in
`configure-aws-credentials` (`gh run list --workflow=deploy-freshness.yml
--event=schedule` over that window: `total=50 failure=50 success=0`). It
never measured prod once. So the detector was not merely misconfigured —
**it was dead for exactly the window it existed to cover**, while its
own repair sat finished and unmergeable a few hundred metres away.

There is a second layer to it. Re-measuring the firing times of those same
50 runs (independently confirmed against palateful-cc's count) shows
**25 of the 49 intervals exceeded 24h**, with a maximum of 31.95h, against
an E-7 requirement of a firing interval no worse than 24h. The single daily
cron did not merely lack margin in theory — it breached the threshold more
than half the time. So even a *living* detector on that schedule could not
have honoured its own requirement, and the guard that was supposed to
protect the schedule asserted a cron string that cannot see interval
breaches at all.

**Three independent failures had to coincide for this to stay invisible for
51 days:**

1. **The detector was dead for the whole window** — 50 scheduled runs,
   50 failures, zero measurements of prod.
2. **The schedule breached its own 24h requirement more than half the
   time** (25 of 49 intervals, max 31.95h), so even a *living* detector
   could not have complied.
3. **The guard meant to catch that pinned a cron *string*** rather than the
   firing interval, so it was structurally blind to the breach — green,
   mutation-verified, and incapable of reporting the thing it existed for.

None of the three is individually exotic. It is the *coincidence* that is
the argument for a detector rather than three point fixes: fixing any one
of them in isolation leaves the other two silently covering for it.

Fifty consecutive identical failures is also, on its own, a signal nobody
consumed. A check that fails every single time it runs is indistinguishable
from a check that is working, if nothing reads the outcome — which
generalises past PRs: the gap is that *nothing in this repo notices a
persistent, unchanging red*. A detector for stranded PRs and a detector
for permanently-red scheduled workflows are close cousins, and whoever
takes this should look at whether one thing can answer both.

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
- Corroborating precedent from the same repo and the same window, found
  independently while fixing the check (see #24): `deploy-freshness`'s own
  self-test asserted the literal cron string `'0 15 * * *'` rather than the
  firing *interval* E-7 actually requires. That assertion was green and
  mutation-verified and still worthless — it would have passed unchanged
  through the entire 50-run window. Same family as the bug above: a signal
  that is green because nothing meaningful is being read. Evidence that
  "we have a check for that" is not evidence the check binds to the
  property anyone cares about.
- Scope guard: this is about *detection*. Do not turn it into an
  auto-rebase or auto-merge feature; a stranded PR often strands for a
  reason (#24 carries ~2000 unreviewed lines), and the correct output is a
  human-legible flag, not an automated resolution.

## Status log

- 2026-09-20T17:05 — recorded that the first post-fix firing is expected to
  be red (~51d gap, verified live against `palateful-api-prod:63`), and
  retired the green-may-be-correct caveat: run 35522939142 skipped all four
  ECS legs, so prod did not go fresh and the check can self-interpret after
  all.
- 2026-09-20T16:30 — amended after #25 merged (`03133116`). Added the
  50/50 run figure, the 25-of-49 interval breach, and the cron-string
  assertion precedent. All three re-derived locally rather than carried
  over from the reporting session. One correction to my own earlier
  reporting: a firing band of 16:05Z-19:47Z I cited in discussion came
  from a 12-run sample, not the full window — over all 50 runs the band is
  00:19Z-23:58Z, with 48 of 50 inside 15:27Z-20:44Z and both extremes
  falling on a single day (2026-08-28).
- 2026-09-20T10:15 — filed while fixing `deploy-freshness` auth. The
  requested fix turned out to already exist and be proven; the real defect
  was that it had been stranded in PR #24 for 51 days with nothing
  watching. Filed at the coordinator session's request, scoped to the
  missing detector rather than to #24 itself. #24 is left untouched.
