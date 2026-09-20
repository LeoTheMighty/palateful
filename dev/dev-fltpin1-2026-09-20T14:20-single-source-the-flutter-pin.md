---
hash: fltpin1
type: dev
created: 2026-09-20T14:20:00-06:00
title: Single-source the Flutter version pin — three copies, nothing keeps them in step
from: dev/dev-tfship1-2026-09-20T11:30-ios-testflight-shortest-path.md
status: ready
owner:
branch:
---

## Goal

The Flutter version is pinned in **three** places with **no mechanism keeping
them in step**:

| # | Site | Value |
|---|---|---|
| 1 | `.github/workflows/ci.yml:336` (`flutter-test`) | `3.41.7` |
| 2 | `.github/workflows/mobile-builds.yml:42` (`FLUTTER_VERSION`) | `3.41.7` |
| 3 | `app/ios/ci_scripts/ci_post_clone.sh` (`FLUTTER_VERSION`) | `3.41.7` *(added by `tfship1`, 2026-09-20)* |

They agree today only because `tfship1` just made them agree. **Three pins with
nothing reconciling them is a fuse, not a fix** — the next person to bump
Flutter will change the one their task touches, and the divergence starts
again in whichever surface they didn't think about.

This is not hypothetical, and the evidence is the reason site 3 exists. It
read `-b stable` (tip of channel) from 2026-04-15 until 2026-09-20. It matched
the pin when written, then drifted to **3.47.5 vs 3.41.7 — six minor
versions** — with nothing reporting it, because nothing compared them. Xcode
Cloud would have built against a Flutter no test in this repo has ever
exercised. Same shape as `fxfuse`'s date-fused fixtures and `tfship1`'s
build-number drift: **correct when written, wrong by the calendar, silent
throughout.**

There is also a **fourth**, looser copy worth deciding about:
`ci.yml`'s `deploy-web` requests `channel: stable` with **no version pin at
all**, so the deployed web bundle can be built by a different framework than
the one that tested it. Flagged in `fltup1`'s technical notes as deserving its
own ticket; fold it in here or split it, but do not leave it unnamed a third
time.

## Acceptance criteria

- [ ] One authoritative declaration of the Flutter version, with the other
      sites deriving from or verified against it. Mechanism is open — a
      committed `.flutter-version` file read by all three, or a CI check that
      greps all sites and fails on disagreement. **Prefer the check if
      single-sourcing turns out to be awkward**: GitHub Actions' `uses:` inputs
      and a shell script have no shared config format, and a check that fails
      loudly beats an abstraction that hides where the value comes from.
- [ ] The guard fails a PR that changes one site without the others.
      Demonstrate it by deliberately diverging one and watching CI go red —
      **an unproven guard is the same class of thing this story exists to
      remove.**
- [ ] `deploy-web`'s unpinned `channel: stable` is resolved: pinned, or
      documented as intentionally floating with the reason.
- [ ] `docs/DEPLOYMENT.md`'s note naming `ci_post_clone.sh` as the third pin
      site is updated to describe whatever mechanism lands.

## Technical notes

- The three sites have genuinely different shapes — `subosito/flutter-action`
  input, a workflow `env:`, and a shell variable. A shared file plus three
  small readers is likely simpler than forcing one format.
- `fltup1`'s status log is the best existing account of what version skew
  actually costs (94 failures from one stale shader; a dwds attach failure
  that only cleared on the pinned version). Worth reading before choosing a
  mechanism.
- Blast radius is CI config only; no app code. But the failure mode it
  prevents is "CI builds something no test covered", which is as bad as it
  sounds.

## Status log
- 2026-09-20T14:20 — filed from `tfship1` at the coordinator's request, after
  pinning site 3 revealed there were three. Filed rather than left as a doc
  note because a note does not fail a build, and this failure mode is
  specifically one that nothing reports.
