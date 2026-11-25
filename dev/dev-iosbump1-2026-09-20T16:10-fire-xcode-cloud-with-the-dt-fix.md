---
hash: iosbump1
type: dev
created: 2026-09-20T16:10:00-06:00
title: Bump to 1.0.64+90 — fire Xcode Cloud with the deployment-target fix in place
from: dev/dev-iosdt1-2026-09-20T15:00-raise-ios-deployment-target-to-15.md
status: in-progress
owner: null
branch: feat/dev-iosbump
---

## Goal

`iosdt1` (the iOS 15.0 deployment-target fix) is on `main` as `a225c305` and
**has never been tested**, because it changed the Podfile, the Xcode project
and a plist — and the Xcode Cloud start condition fires only on
`app/pubspec.yaml`. The fix is sitting in front of a trigger that cannot see it.

This bump is the trigger. `1.0.64+89` → `1.0.64+90`, which also keeps the repo
ahead of App Store Connect's 88.

## Why a version bump is the right shape

Not a hack to poke CI. **Committing a version bump is what the deploy trigger
*is*** — see `docs/DEPLOYMENT.md` § Xcode Cloud. Shipping a build by bumping
the version is the intended workflow; the only reason it feels like a trick
today is that the repo went five months without doing it.

## What to expect

`iosdt1` is verified locally (`pod install` clean, 243/243 pods at 15.0,
`flutter build ios --release` exit 0 with zero deployment-target diagnostics),
so this run should clear `pod install` and reach `xcodebuild` **for the first
time**. Everything past that point is untested territory:

| Outcome | Reading |
|---|---|
| Fails in post-clone again | Something beyond the deployment target; read the `--- ci_post_clone: <phase> ---` marker |
| Fails in `xcodebuild`/archive | **New ground.** First time CI has got this far. The appex-embed assertion in `ci_post_xcodebuild.sh` is a deliberate hard failure and would be a real finding |
| **Rejected at upload, duplicate/low build number** | **Expected, and the good outcome.** Xcode Cloud's `CI_BUILD_NUMBER` starts at 1 per workflow and does not read `pubspec.yaml`. A rejection here proves trigger → clone → pinned Flutter → pods → archive → extension embed → ASC auth. **Not a regression** |
| Uploads successfully | Xcode Cloud is managing numbering above 88. Leo then has a live build — and still must **assign it to a tester group**, which every mechanism in this saga stops short of |

## Acceptance criteria

- [ ] Xcode Cloud fires on the merge commit (status present via the
      commit-statuses API — *not* the Actions UI)
- [ ] The run gets past `pod install`, proving `iosdt1`
- [ ] Outcome recorded here with its reading, so a red is not misread
- [ ] Iterate: read failure → fix → bump → merge → repeat, until a build
      reaches TestFlight

## Status log
- 2026-09-20T16:10 — filed. `a225c305` (`iosdt1`) is on main and untriggered;
  this bump exists to give it a run. Also carries the `xcstart1` rewrite and
  the `docs/DEPLOYMENT.md` mechanism write-up.
