---
hash: lgort1
type: debug
created: 2026-07-27T11:41:00-06:00
title: Native Auth0 logout returnTo uses the URL scheme where the bundle id belongs
from: btri01
status: in-progress
owner: /devx-2026-09-20T1001-3952
branch: unassigned
---

## Goal
`AuthService.logout()` passes an explicit `returnTo` to the native Auth0
`/v2/logout` that does not match the URL `auth0_flutter` registers for this
app. Auth0 rejects unlisted `returnTo` values with its own hosted error page —
the exact symptom the original BUGS.md report described ("logging out shows a
weird auth0 page"). bas-1 (`f839f67`) intended to fix that report but shipped
a malformed URL, so the report most likely still reproduces.

## Evidence

`app/lib/core/services/auth_service.dart:223-227` builds:

```dart
final platformSegment = Platform.isIOS ? 'ios' : 'android';
await _auth0!.webAuthentication(scheme: Environment.auth0Scheme).logout(
      returnTo:
          '${Environment.auth0Scheme}://${Environment.auth0Domain}/$platformSegment/${Environment.auth0Scheme}/callback',
    );
```

The third path segment is `Environment.auth0Scheme`. Per the `auth0_flutter`
1.14.0 README (§"Configure the callback and logout URLs") the SDK's URL shape is:

- Android — `SCHEME://YOUR_DOMAIN/android/YOUR_PACKAGE_NAME/callback`
- iOS — `YOUR_BUNDLE_ID://YOUR_DOMAIN/ios/YOUR_BUNDLE_ID/callback`

i.e. that segment is the **package name / bundle identifier**, not the custom
scheme. In this app they are different strings:

| value | source |
|---|---|
| `Environment.auth0Scheme` | `com.palateful.app` (`app/lib/core/config/environment.dart:31`) |
| iOS bundle id | `com.palateful.palateful` (`app/ios/Runner.xcodeproj/project.pbxproj:637`) |
| Android applicationId | `com.palateful.palateful` (`app/android/app/build.gradle.kts:43`) |

So the code sends
`com.palateful.app://auth.palateful.app/ios/com.palateful.app/callback`
where the SDK-registered URL is
`com.palateful.app://auth.palateful.app/ios/com.palateful.palateful/callback`.

Two further facts make this a likely no-op-at-best / regression-at-worst:

1. `WebAuthentication.logout()` **already defaults** `returnTo` to the correct
   URL when the argument is omitted — the SDK doc comment says "If `returnTo`
   is not specified, a default URL is used that incorporates the `domain` value
   … and the custom scheme on Android, or the bundle identifier on iOS/macOS."
   Passing a hand-built string can therefore only make things worse than the
   pre-bas-1 code.
2. `returnTo` must appear in the app's **Allowed Logout URLs** list — a list
   that is separate from Allowed Callback URLs. The bas-1 epic doc
   (`_bmad-output/planning-artifacts/epic-bugs-auth-and-shopping.md:233`)
   asserted "No … Auth0 dashboard config — the post-logout callback reuses the
   login callback URL already registered in Allowed Callback URLs", which is
   not how Auth0 validates logout redirects.

`docs/SETUP.md:97` documents Allowed Logout URLs as
`com.palateful.app://logout-callback`, which matches neither the current code
nor the SDK default — SETUP.md is stale (login works in prod, so the real
tenant must already carry the SDK-format callback URL).

The failure is invisible in telemetry: the `catch` in `logout()` clears local
state regardless, so the app looks logged out while the browser tab is parked
on Auth0's error page, and nothing lands in `error_logs`.

## Acceptance criteria
- [ ] Native logout returns to the app instead of an Auth0-hosted page, on a
      real iOS device and a real Android device
- [ ] Either the explicit `returnTo` is dropped (preferred — let the SDK build
      its default) or it is built from the bundle id / package name rather than
      `Environment.auth0Scheme`
- [ ] The URL actually used is confirmed present in the Auth0 app's **Allowed
      Logout URLs** (see the MANUAL.md entry filed alongside this spec)
- [ ] `docs/SETUP.md` Auth0 section updated to the URL shape the app really uses
      (both callback and logout lists)
- [ ] Web logout path (`auth_service_web.dart`) left unchanged — it already
      passes `returnToUrl`

## Technical notes
- Touch point is `app/lib/core/services/auth_service.dart:205-243` only.
- There is no unit test seam here: `logout()` calls into the Auth0 plugin
  directly. Verification is manual/on-device; consider extracting the returnTo
  construction into a pure function if a regression test is wanted.
- Dropping the argument entirely is the smallest change and restores the SDK
  default, but it reverts bas-1 — so confirm on-device first that the default
  URL is the one registered in the tenant.

## Status log
- 2026-07-27T11:41 — filed from btri01 legacy-BUGS triage; bas-1 verified as
  not-a-fix by code + SDK-doc inspection
- 2026-09-20T10:01:24-06:00 — claimed by /devx in session /devx-2026-09-20T1001-3952
- 2026-09-20T10:15 — phase 2: spec ACs direct (v2 native); 5 ACs; workstream=none;
  red-artifacts=none. Root cause re-derived from the **vendored SDK sources**
  rather than the README, which sharpened the diagnosis: the defect is worse on
  iOS than the spec's Evidence section states. `app/ios/Pods/Auth0/Auth0/
  Auth0WebAuth.swift:41-62` builds `redirectURL` with `Bundle.main.
  bundleIdentifier` as **both the URL scheme and the path segment** (the
  `https` branch only fires under `useHTTPS`, which auth0_flutter leaves
  false). So the iOS default is
  `com.palateful.palateful://auth.palateful.app/ios/com.palateful.palateful/callback`
  — the spec predicted `com.palateful.app://…/ios/com.palateful.palateful/callback`,
  which is also wrong in the scheme. Corollary found the same way: the
  `scheme:` argument to `Auth0.webAuthentication(scheme:)` is **ignored
  entirely on iOS** — nothing under `auth0_flutter-1.14.0/darwin/Classes/`
  reads a `scheme` key; it is an Android-only knob.
  Decisive argument for dropping the argument: `Auth0WebAuth.redirectURL` is a
  single lazy property consumed by **both** `start()` (login) and
  `clearSession()` (logout, line 231), so on iOS the logout `returnTo` and the
  login callback URL are byte-identical. Login works in prod, therefore the
  tenant already carries the exact string logout needs — it just has to be in
  the (separate) Allowed Logout URLs list. Android is the analogous story via
  `LogoutWebAuthRequestHandler` → `withScheme` → CallbackHelper, matching the
  `android:pathPrefix="/android/${applicationId}/callback"` that auth0_flutter's
  own library manifest registers.
- 2026-09-20T10:40 — phase 3: AC2 + AC4 + AC5 done; AC1 + AC3 are human-only.
  Dropped the hand-built `returnTo` (AC2, preferred branch). Added
  `app/lib/core/config/auth0_urls.dart` — a pure `auth0DefaultRedirectUrl()`
  that reconstructs what the SDK builds, per the Technical-notes suggestion, so
  the strings are pinned somewhere executable; it is diagnostics-only and is
  never handed back to the SDK. `logout()` now breadcrumbs that URL via
  `ErrorReporter.log` before opening the sheet, which is what makes AC1's
  on-device check a log read rather than an SDK-source re-derivation, and makes
  the URL queryable from `audit_errors.py` as a `ClientLog` row. The catch block
  no longer swallows silently (the Evidence section's "invisible in telemetry"
  point) — it reports to `ErrorReporter` before `_clearSessionState()` resets
  the Crashlytics user id. `docs/SETUP.md` §"Create Auth0 Native App" rewritten
  with both per-platform URLs and the two traps (AC4). `auth_service_web.dart`
  untouched (AC5).
- 2026-09-20T10:45 — phase 4: single-pass adversarial review (diff is ~160 lines,
  one semantic surface — below the 3-agent threshold); 1 finding (1 MED, 0 HIGH,
  0 LOW); fixed in place — the new `ErrorReporter.report` in the logout catch
  would have fired on every user-dismissed browser sheet, since Auth0.swift
  surfaces a sheet dismissal as a user-cancelled `WebAuthenticationException`
  through the same throw path as a real failure; that is one Crashlytics
  non-fatal + one `error_logs` row per normal cancel, which would bury the
  signal the report exists to surface. Now gated on
  `e is WebAuthenticationException && e.isUserCancelledException`, which
  debugPrints instead. Also checked and cleared: `ErrorReporter.log`'s backend
  mirror is `unawaited` so the breadcrumb does not block the logout sheet;
  `PackageInfo.fromPlatform()` memoizes so the added `await` is not a real
  round-trip; the breadcrumb does not start with `nav.` so it is not dropped by
  the mirror's prefix filter; the report runs before `_clearSessionState()` so
  the row still carries the user id; `dart:io`'s `Platform` use stays behind the
  existing non-web branch. Re-review of the changed hunks clean.
- 2026-09-20T10:50 — phase 5: local CI green. `flutter analyze` on the three
  touched Dart files — no issues. `flutter test` (app project's only configured
  gate) — **1611 passed, 0 failed**, including the 4 new
  `test/core/config/auth0_urls_test.dart` cases. Note for future runs: the
  stale-`build/unit_test_assets` trap recorded in project memory is real; the
  suite was run after `rm -rf app/build/unit_test_assets`.
- 2026-09-20T10:52 — phase 8 gap-filing: filed
  `debug/debug-andph1-2026-09-20T1030-auth0-android-manifest-placeholders.md`
  (+ DEBUG.md row). Orthogonal defect found while reading the Android side:
  auth0_flutter's library manifest declares `RedirectActivity` with
  `${auth0Domain}` / `${auth0Scheme}` placeholders that this repo never defines
  in `manifestPlaceholders`, and no CI job builds Android, so nothing proves the
  manifest merge succeeds. Filed rather than fixed — confirming it needs a real
  Gradle run, and it is about whether Android can *receive* the redirect, not
  about the string lgort1 sends.
- 2026-09-20T10:55 — **BLOCKED on AC1 + AC3** (human-only, as the spec and
  MANUAL.md anticipated). Code work is complete and green; what remains is a
  dashboard read-back and an on-device pass. See the PR body for the exact two
  strings that must be present in **Allowed Logout URLs**.
