---
hash: xcstart1
type: dev
created: 2026-09-20T15:10:00-06:00
title: Xcode Cloud start condition is narrower than app/ — Dart-only changes never ship a build
from: dev/dev-tfship1-2026-09-20T11:30-ios-testflight-shortest-path.md
status: ready
owner:
branch:
---

## Goal

Leo's requirement is "it should simply run on `main` once the PRs are merged."
The current start condition does not do that, and fixing the deployment-target
failure (`iosdt1`) will not make it do that. **These are two separate defects
and only one of them is in the repo.**

## Evidence

Checked the GitHub commit-statuses API across every merge to `main` on
2026-09-20:

| Merge | Touched | Xcode Cloud fired? |
|---|---|---|
| `03133116` #25 | `.github/` | no status |
| `f05d4a30` #1 | **`app/lib`** (Flutter view fix) | **no status** |
| `c992552e` #12 | `services/e2e`, `tools/` | no status |
| `b40e31e0` #24 | docs | no status |
| `65d4d75a` #26 | **`app/README.md`** | **no status** |
| `185b4de9` #30 | **`app/ios/ci_scripts/`**, `app/pubspec.yaml` | **FIRED** |

Only the merge touching `app/ios/` produced a status. A merge touching
`app/lib` — real Flutter application code that absolutely changes the shipped
binary — produced nothing.

**Best reading: the start condition is scoped to iOS-native paths rather than
`app/`.** That also explains the original mystery cleanly: nothing has touched
`app/ios/` since the April freeze, so the workflow never fired, which is
entirely consistent with "it was all working at some point" plus nothing above
build 88. It was not broken; it was never asked.

## Why this matters more than it looks

Palateful is a Flutter app. **The overwhelming majority of shipping changes are
Dart-only** and touch nothing under `app/ios/`. A condition scoped to iOS-native
paths therefore fires for approximately the changes that matter least to a
release, and skips the ones that matter most. Left as-is, `iosdt1` lands, the
build goes green, and TestFlight still receives nothing for weeks — which would
read as "Xcode Cloud is broken again" rather than "it was never triggered".

## Acceptance criteria

- [ ] Read the current start condition in App Store Connect and **write down
      what it actually is** — this spec infers it from six data points and has
      not seen the configuration. The inference could be wrong in detail
      (it might be a `Files and Folders` filter, or something else entirely).
- [ ] Trigger covers Dart changes: scope the `main` branch-change condition to
      **`app/`**, or remove the path filter entirely.
- [ ] Verified by a **Dart-only** merge producing an Xcode Cloud run — not by
      reading the configuration screen. Configuration that looks right is what
      `docs/DEPLOYMENT.md` asserted for seven weeks.
- [ ] Decide and record the cadence. Every `main` merge shipping a TestFlight
      build means a build number burned and **a notification to every tester**
      per merge. If that is too noisy, the alternative is tag-triggered rather
      than a narrower path filter — narrowing by path is what produced this
      defect. State the choice in `docs/DEPLOYMENT.md`.

## Technical notes

- **Xcode Cloud reports via the GitHub commit-statuses API, not check-runs.**
  It therefore never appears in the PR checks list or in `gh pr checks`. This
  is why the workflow looked dead: anyone checking GitHub for evidence would
  find none regardless of whether it ran. Check with:
  `gh api repos/<owner>/<repo>/commits/<sha>/status`
- Depends on `iosdt1` only in practice, not in principle — widening the trigger
  before the deployment-target fix lands would just fire more failing builds.

## Status log
- 2026-09-20T15:10 — filed from `tfship1`. Kept separate from `iosdt1` at the
  coordinator's direction: one is a repo build defect, the other is App Store
  Connect configuration, and folding them together would let the invisible one
  ride along unfixed behind the visible one's green build.
