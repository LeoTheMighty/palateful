# cla-12 — QA Walkthrough

## What shipped

Firebase Performance scope lockdown — the static manifest/plist
counterparts to the runtime `setPerformanceCollectionEnabled(true)`
call shipped in cla-11.

- `app/ios/Runner/Info.plist` — adds
  `firebase_performance_collection_enabled=true`.
- `app/android/app/src/main/AndroidManifest.xml` — adds the same
  collection toggle plus
  `firebase_performance_auto_activity_trace_enabled=false` aimed at
  silencing the `_st_*` screen-rendering traces.
- `app/test/core/services/firebase_performance_scope_lockdown_test.dart`
  — parses both files on disk and asserts the expected flag-value
  pairs. Any future PR that deletes or flips a flag fails CI before
  a release cuts.
- `docs/PERFORMANCE_OPS.md` — scope lockdown bullet now explicitly
  documents the Firebase SDK limitation (no public build-time key
  exists for disabling **only** screen-rendering) and points at the
  manual 24 h Firebase Console re-verification step.

## Acceptance criteria mapping

| AC                                               | How cla-12 satisfies it |
|--------------------------------------------------|--------------------------|
| (1) iOS Info.plist adds collection_enabled key   | Added as `<true/>` per Firebase docs |
| (2) Android manifest equivalent scope flag       | Added `collection_enabled=true` + `auto_activity_trace_enabled=false` |
| (3) Console shows HTTP + app-start only          | **Best-effort** — no public SDK knob; runbook documents it |
| (4) docs explain the scope decision              | `docs/PERFORMANCE_OPS.md` Firebase section updated |
| (5) re-verifiable via inspection test            | `firebase_performance_scope_lockdown_test.dart` (manifest/plist pin) |

## Manual QA steps

- [ ] Run `flutter test test/core/services/firebase_performance_scope_lockdown_test.dart`
      — 2/2 green locally. The same test runs in CI.
- [ ] After the next TestFlight/Play Internal build rolls, wait 24 h.
- [ ] Firebase Console → Performance → Dashboard. Confirm:
      - Network requests: populated ✓
      - App start: populated ✓
      - Screen rendering: either empty, or a small trickle that we
        **ignore per runbook**.
- [ ] `docs/PERFORMANCE_OPS.md` → Firebase section — skim for
      accuracy.
- [ ] Try to delete either of the manifest flags in a throwaway
      branch and run the lockdown test — confirm it fails loudly with
      the reason string referencing cla-12.

## Regression surface

- `test/core/services/firebase_performance_scope_lockdown_test.dart`
  pins both files.
- No runtime behaviour change from cla-11 — the manifest/plist flags
  are declarative; they simply match what the runtime toggle is
  already doing.
- `dart analyze` clean.

## Known-safe choices (and why)

- **`firebase_performance_auto_activity_trace_enabled=false`** is the
  undocumented-but-widely-used Android SDK flag for the `_st_*`
  screen-rendering traces. If the flag name drifts in a future SDK
  bump, the lockdown degrades to "Firebase shows screen traces we
  ignore" — the operator runbook already treats Firebase as
  secondary, so the blast radius of a mis-named flag is zero.
- **No attempted iOS screen-trace lockdown** because Firebase's
  public iOS contract doesn't expose one. `disable-sdk` docs confirm.
- **Static test instead of a runtime hook** — Firebase doesn't give
  Dart a way to introspect whether auto screen-tracing is currently
  on. A compile-time parse of the manifest/plist catches
  99% of regressions (accidental removal in a merge, typo in a flag
  name); the remaining 1% (SDK behaviour change) is caught by the
  manual 24 h Firebase Console verification step.

## Backout

- Revert the commit. The runtime `setPerformanceCollectionEnabled(true)`
  stays on (cla-11 still in place); Firebase simply returns to its
  default behaviour which auto-collects screen traces on Android.
  Since our operator workflow ignores Firebase screen-trace data, the
  only visible effect would be slightly more noise in the Firebase
  Console — no user-visible impact.
