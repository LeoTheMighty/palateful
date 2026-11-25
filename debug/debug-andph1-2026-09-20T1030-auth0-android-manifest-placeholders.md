---
hash: andph1
type: debug
created: 2026-09-20T10:30:00-06:00
title: auth0_flutter's RedirectActivity manifest placeholders are never defined in the Android build
from: lgort1
status: ready
owner: unassigned
branch: unassigned
---

## Goal
`flutter build apk` / `appbundle` should succeed and the Auth0 redirect should
land on `com.auth0.android.provider.RedirectActivity`, not on a chooser or the
launcher activity's catch-all scheme filter.

## Evidence

`auth0_flutter` 1.14.0 ships this in its own library manifest
(`~/.pub-cache/hosted/pub.dev/auth0_flutter-1.14.0/android/src/main/AndroidManifest.xml`):

```xml
<activity android:name="com.auth0.android.provider.RedirectActivity" android:exported="true">
    <intent-filter>
        ...
        <data
            android:host="${auth0Domain}"
            android:pathPrefix="/android/${applicationId}/callback"
            android:scheme="${auth0Scheme}" />
    </intent-filter>
</activity>
```

`${applicationId}` is injected by AGP. `${auth0Domain}` and `${auth0Scheme}`
are not — the consuming app has to supply them via
`android.defaultConfig.manifestPlaceholders`, which is the documented
auth0_flutter Android setup step. This repo never does:

```
$ grep -rn "manifestPlaceholders\|auth0Scheme\|auth0Domain" app/android/
(no matches)
```

AGP's manifest merger normally fails the build on an unresolved placeholder
("requires a placeholder substitution but no value for <auth0Domain> is
provided"). Two things make the current state ambiguous rather than obviously
broken, and both need checking before a fix:

1. **No Android build runs in CI** — `grep -rln "flutter build apk\|flutter
   build appbundle\|bundleRelease" .github/workflows/` returns nothing, so
   nothing has been proving the merge succeeds.
2. **`MainActivity` carries a catch-all scheme filter** —
   `app/android/app/src/main/AndroidManifest.xml:41-47` registers
   `android:scheme="com.palateful.app"` with no host or path, commented
   "preserved for backward-compat". If the merge *does* somehow succeed, that
   filter (not `RedirectActivity`) is what would catch the Auth0 redirect, and
   it would also catch every other `com.palateful.app://` URL.

Found while fixing lgort1 (native Auth0 logout `returnTo`). Not in lgort1's
scope — lgort1 is about the string the app sends to `/v2/logout`; this is
about whether Android can receive the redirect at all.

## Acceptance criteria
- [ ] `flutter build apk --debug` in `app/` is run and its result recorded here
      (succeeds → the placeholder theory is wrong, close with the evidence;
      fails on manifest merge → the rest of these ACs apply)
- [ ] `manifestPlaceholders` for `auth0Scheme` / `auth0Domain` added to
      `app/android/app/build.gradle.kts`, sourced from the same values as
      `Environment.auth0Scheme` / `Environment.auth0Domain` rather than
      re-typed
- [ ] The merged manifest is inspected and `RedirectActivity` carries the
      concrete host/scheme
- [ ] A decision is recorded on whether `MainActivity`'s catch-all
      `com.palateful.app` scheme filter should stay
- [ ] An Android build step is added to CI so this cannot regress silently

## Technical notes
- `Environment` is compile-time Dart (`--dart-define`), Gradle is a separate
  world; if the values are to stay in sync automatically, the gradle side
  probably reads them from the same place `bin/dev` passes to `--dart-define`.
- Confirming AC #1 needs an Android SDK + a Gradle run; it was not run while
  filing this (out of lgort1's scope and its worktree).

## Status log
- 2026-09-20T10:30 — filed from lgort1 Phase 8 gap-filing; placeholder absence
  verified by grep, build impact NOT verified
