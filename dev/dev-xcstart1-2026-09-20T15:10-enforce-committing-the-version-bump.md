---
hash: xcstart1
type: dev
created: 2026-09-20T15:10:00-06:00
title: Nothing enforces committing the version bump — the single cause behind three symptoms
from: dev/dev-tfship1-2026-09-20T11:30-ios-testflight-shortest-path.md
status: ready
owner: null
branch: null
---

> **This spec was rewritten 2026-09-20T16:00. Its original premise — "the
> Xcode Cloud start condition is too narrow" — was WRONG.** The condition is
> right; the defect is upstream of it. Original reasoning and its refutation
> are preserved in the status log, because the way it was wrong is the useful
> part.

## The start condition, verbatim

Read from App Store Connect by Leo (it exists nowhere in the repo):

> Branch: `main` · Files and Folders:
> **"Start if 'pubspec.yaml' file from the 'app' folder changes"**

That is the whole condition. **It is a good rule** — "bump the version, ship a
build" is precise and intentional. Widening it to all of `app/` would fire a
TestFlight build, burn a build number and notify every tester on every Dart
merge.

## One cause, three symptoms

The trigger requires `app/pubspec.yaml` to change **in a commit that reaches
`main`**. `bin/prod-ios-deploy` does not bump or commit anything — it reads
the version, builds, uploads, and prints:

```sh
echo "  Don't forget to commit the version bump!"
```

**A comment standing in for automation.** Bump locally → archive → upload →
forget to commit, and the build ships while `main` never sees the change. From
that one fact:

| Symptom | Explanation |
|---|---|
| ASC eleven builds ahead of the repo (88 vs 77) | Those eleven were local-script uploads whose bumps were never committed |
| No builds since 88 | The repo froze on 2026-04-26; `app/pubspec.yaml` stopped changing, so the trigger had nothing to fire on |
| "It was all working at some point" | It was. It still is. It was never *asked* |

Nothing was broken. The mechanism was starved of its input.

Confirmed against every merge on 2026-09-20: `185b4de9` (a `+89` pubspec bump)
**fired**; `a225c305` (`iosdt1` — Podfile, pbxproj, plist, no pubspec change)
**did not**; #1, #12, #24, #25, #26 — no pubspec change, none fired. The
condition has behaved correctly every single time.

## The remaining defect

**`bin/prod-ios-deploy` can upload a build that `main` has no record of, and
its only guard is a `Don't forget` string.** That is the eleven-build drift
mechanism, still live. Anyone running the manual fallback today reopens the
gap.

## Acceptance criteria

- [ ] `bin/prod-ios-deploy` cannot silently desynchronise the repo from ASC.
      Options, in rough order of preference:
      1. **Bump and commit `app/pubspec.yaml` itself** before archiving, so
         using the script *is* the thing that satisfies the trigger.
      2. **Refuse to run** when `app/pubspec.yaml` is dirty or when its build
         number is ≤ the latest on App Store Connect, with a message saying
         what to do.
      3. At minimum, **exit non-zero** after upload if the bump is uncommitted
         — a reminder nobody reads is what we already have.
- [ ] Whatever lands, it fails **loudly**. The existing `echo` is the control
      case for why advisory text does not work.
- [ ] Verified by running the script with an uncommitted bump and watching it
      refuse — not by reading the code.
- [ ] `docs/DEPLOYMENT.md` reflects the chosen behaviour (the mechanism is
      already documented there as of `iosbump1`).

## Technical notes

- **Xcode Cloud reports via the GitHub commit-statuses API, not check-runs**,
  so it never appears in the PR checks list, `gh pr checks`, or the Actions UI.
  Check with `gh api repos/<owner>/<repo>/commits/<sha>/status`. This is why
  the workflow looked dead for seven weeks: anyone looking at GitHub for
  evidence would have found none whether or not it ran.
- Option 1 interacts with `tfship1` §B3 (CI deriving the build number from App
  Store Connect). If CI eventually owns the number, the script should read it
  from the same place rather than inventing a parallel scheme.

## Status log
- 2026-09-20T15:10 — filed as "start condition too narrow", inferring from six
  merge outcomes that the filter was scoped to iOS-native paths because only
  the `app/ios/` merge fired.
- 2026-09-20T16:00 — **rewritten; the original premise was refuted.** The
  condition is `app/pubspec.yaml`, and `185b4de9` fired because it bumped the
  version, *not* because it touched `app/ios/`. The inference was wrong in a
  specific, instructive way: six data points were consistent with two different
  rules, and I picked the one that matched my expectation ("path filter scoped
  to iOS") without noticing the other fit equally well. The original spec did
  at least require reading the real condition before acting — that AC is what
  caught this, and it is the reason the error cost nothing. Keep writing
  "go read the source of truth" ACs for anything inferred.
  The rewrite is not a smaller story: the real defect is more serious than the
  one first filed, because it silently desynchronises ASC from the repo instead
  of merely failing to fire.
