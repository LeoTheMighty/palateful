---
hash: iosdt1
type: dev
created: 2026-09-20T15:00:00-06:00
title: Raise the iOS deployment target to 15.0 — Xcode Cloud's floor, and three sources that disagreed
from: dev/dev-tfship1-2026-09-20T11:30-ios-testflight-shortest-path.md
status: in-progress
owner:
branch: feat/dev-iosdt1
---

## Goal

The first Xcode Cloud run in five months failed with **81 errors, one cause**:

```
The iOS deployment target 'IPHONEOS_DEPLOYMENT_TARGET' is set to 13.0,
but the range of supported deployment target versions is 15.0 to 27.0.
```

Repeated across pods for 9.0, 11.0, 12.0, 13.0 and 14.0. Xcode Cloud runs a
newer Xcode than the local toolchain and its floor is **15.0**.

## Why this was invisible — the argument for CI

`bin/prod-ios-deploy` **works**. Leo has shipped eleven builds with it, because
his local Xcode accepts a 13.0 floor. Xcode Cloud does not.

**So the repo built fine on the machine that mattered and was unbuildable on
the machine that was supposed to take over, and nothing compared the two.**
Same proxy shape as the rest of 2026-09-20: a local green standing in for a
property it does not actually establish. This is the concrete argument for CI
owning buildability rather than a developer laptop — not tidiness, but that a
laptop's Xcode silently has different rules and nothing reports the divergence.

## Three sources, three answers

Measured before changing anything. There were **six** `IPHONEOS_DEPLOYMENT_TARGET`
entries, not three:

| Source | Was | Now |
|---|---|---|
| `app/ios/Podfile:2` | `14.0` | **15.0** |
| `Runner.xcodeproj` — Runner (Debug/Release/Profile) | `13.0` ×3 | **15.0** |
| `Runner.xcodeproj` — PalatefulShare (Debug/Release/Profile) | `14.0` ×3 | **15.0** |
| Transitive pods | inherited **9.0–14.0** | **15.0** (forced) |
| `app/ios/Flutter/AppFrameworkInfo.plist` | `MinimumOSVersion 13.0` | key removed by Flutter tooling |

Plus a **seventh** declaration nobody was counting:
`app/ios/Flutter/AppFrameworkInfo.plist` carried `MinimumOSVersion 13.0`.
Flutter 3.41.7's own tooling **deleted** that key during `pub get` — newer
Flutter derives it from the project instead of hard-coding it — so it shows up
in this diff without having been hand-edited. Worth knowing it existed: a
`grep` for `IPHONEOS_DEPLOYMENT_TARGET` would never have found it.

The Podfile and the Xcode project had disagreed with each other for a long
time, the share extension disagreed with the main app, and a plist nobody
looks at disagreed with both. Nothing reconciled them because nothing read
them together.

## Does 15.0 cost devices? No — and the repo already answered this

Not taken on trust. `_bmad-output/planning-artifacts/prd.md:252` states:

> **Minimum iOS version:** iOS 16+ (covers ~95% of active devices)

**The product's own committed minimum is already 16, which is stricter than
the 15.0 being set here.** So 15.0 cannot cost a device the product has not
already agreed to lose — the build config was the outlier, sitting *below* the
documented floor rather than the PRD being optimistic.

(Independently: iOS 15 runs on the same hardware as 13 and 14 — iPhone 6s and
later — so the bump is device-neutral in its own right. iOS **16** is where
hardware is dropped, which is worth knowing before anyone closes the remaining
gap to the PRD.)

**Follow-up, not done here:** the PRD says 16 and this sets 15. Closing that
gap is a real product decision with device cost, so it is named rather than
taken — see §Dead availability guards, which is the cleanup that would pair
with it.

## What changed

1. **`app/ios/Podfile`** — `platform :ios, '15.0'`.
2. **`Runner.xcodeproj/project.pbxproj`** — all **six** entries → `15.0`.
3. **`post_install` floor** — the load-bearing part. The previous hook only
   called `flutter_additional_ios_build_settings(target)`, which does **not**
   normalise transitive pods; each kept whatever its podspec declared, which is
   why 81 errors survived a Podfile that already said 14.0. Now every pod
   configuration below the floor is raised to it.
   **Deliberately one-directional**: a pod declaring *higher* than 15.0 is left
   alone. Clamping in both directions would silently downgrade a pod that
   genuinely needs a newer iOS, trading a loud build error for a runtime crash.
4. **`Podfile.lock`** regenerated.

## Verification

- `pod install` → succeeds.
- Generated `Pods.xcodeproj`: **243 `IPHONEOS_DEPLOYMENT_TARGET` entries, all
  `15.0`, zero below floor.** This is the direct test that the 81 errors are
  gone — the error was per-pod, so per-pod is where it has to be proven.
- `flutter build ios --release --no-codesign` — see status log.

## ⚠️ Podfile.lock was ALSO five months stale — a separate finding

Regenerating produced more churn than a deployment-target change should. It is
not caused by this work:

| Pod | Change | Why |
|---|---|---|
| `firebase_performance` + FirebaseABTesting / RemoteConfig / SharedSwift / Performance / MethodSwizzler | **added** | `8944a719` added `firebase_performance` to `pubspec.yaml` on **2026-04-23** |
| `speech_to_text`, CwlCatchException(+Support) | **removed** | `1675837f` removed it on **2026-04-22** |

`Podfile.lock` was last committed **2026-04-15** (`eaa9d2a2`). So for five
months the committed lock claimed a pod set that did not match `pubspec.yaml`
— a third instance of the day's pattern: **a committed artifact that stopped
tracking its source, with nothing comparing them.** A clean CI checkout
re-resolves and self-corrects, which is exactly why nobody noticed.

## Dead availability guards — named, not removed

Raising the floor to 15.0 makes these dead or unconditional:

| Location | Guard | At floor 15.0 |
|---|---|---|
| `Runner/MetricKitReceiver.swift:32` | `@available(iOS 13.0, *)` | dead |
| `Runner/MetricKitReceiver.swift:63` | `@available(iOS 14.0, *)` | dead |
| `Runner/MetricKitReceiver.swift:124` | `if #available(iOS 14.0, *)` | always true |
| `Runner/AppDelegate.swift:38` | `if #available(iOS 13.0, *)` | always true |
| `PalatefulShare/ShareView.swift:208,217` | `if #available(iOS 15.0, *)` | always true |

**Left in place deliberately.** They are harmless (always-true branches), and
removing them is Swift behaviour-adjacent editing that does not belong in a
build-unblocking change. Filed as cleanup to pair with any future move to 16.

## Acceptance criteria

- [x] All six `IPHONEOS_DEPLOYMENT_TARGET` entries and the Podfile agree at 15.0
- [x] Every generated pod target lands at ≥ 15.0 (243/243 verified)
- [x] `Podfile.lock` regenerated; its extra churn explained rather than waved through
- [x] 15.0 shown not to cost devices, from the repo rather than from recall
- [ ] Xcode Cloud run reaches **past** `pod install` — the real proof, and it
      needs a merge. **Do not merge to trigger without coordinating**: every
      merge touching `app/ios/` now fires a real run.

## Status log
- 2026-09-20T15:00 — filed from `tfship1` after Leo pulled the Xcode Cloud log.
  Root cause confirmed as the CocoaPods build-settings pass, which was on the
  suspect list; the Flutter pin from `tfship1` is cleared, as separately
  demonstrated by running its clone/assert sequence in isolation.
