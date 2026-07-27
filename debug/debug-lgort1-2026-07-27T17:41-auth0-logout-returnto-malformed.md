---
hash: lgort1
type: debug
created: 2026-07-27T11:41:00-06:00
title: Native Auth0 logout returnTo uses the URL scheme where the bundle id belongs
from: btri01
status: ready
owner: unassigned
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
