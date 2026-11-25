---
hash: andbld1
type: debug
created: 2026-11-25T11:15:00-07:00
title: flutter build apk --debug fails on main before manifest merge — a Gradle script error, then AGP 8.7.3 too old for the resolved AndroidX
from: shk103
spawned: []
status: ready
owner: unassigned
branch: unassigned
---

## Goal

`flutter build apk --debug` in `app/` succeeds on `main`. Nothing builds
Android at PR time, and `mobile-builds.yml`, the tag-triggered release
build, has **never run** (`gh api …/actions/workflows/249072022/runs` →
`total_count: 0` on 2026-11-25). So the first `v*.*.*` tag would be the first
Android build anyone has run in CI, and as of today it would fail.

## Who is waiting on it

- **shk103** (shake-to-report phase 3, PR #135): its exit criterion is a
  local `flutter build apk --debug` pasted in the PR. Leo chose on 2026-11-25
  to fix this separately and keep shk103 open on that criterion until this
  lands, then re-run the build on #135.
- **andph1**: its AC "`flutter build apk --debug` in `app/` is run and its
  result recorded here" cannot be answered while the build stops before the
  manifest merger. Its placeholder failure, if real, is next in line behind
  this item.

## Evidence

All of the evidence was measured on the untouched shake-to-report base,
`b677da27`. Its `app/android`, `app/ios`, `app/pubspec.yaml` and
`app/pubspec.lock` are byte-identical to `origin/main` `588445f5`
(`git diff b677da27 origin/main -- …` → 0 lines). Flutter 3.41.7, the CI pin.

**Layer 1: the Kotlin build script does not compile.** This happens under
both Homebrew JDK 22 and Android Studio's JBR 21.0.5 (the Gradle daemon was
confirmed to be the JBR). CI's `mobile-builds.yml` uses Temurin 17, which was
not tried locally.

```
e: file:///…/app/android/app/build.gradle.kts:15:31: Unresolved reference: util
e: file:///…/app/android/app/build.gradle.kts:17:34: Unresolved reference: io
  Line 15: val keystoreProperties = java.util.Properties()
  Line 17:     keystoreProperties.load(java.io.FileInputStream(keystorePropertiesFile))
BUILD FAILED
```

Inside this script `java` resolves to something other than the JDK package,
so the fully qualified names fail. The form Flutter's template uses, with
`import java.io.FileInputStream` / `import java.util.Properties` at the top
and bare `Properties()` / `FileInputStream(…)` below, gets past it. That was
measured in a throwaway worktree and is not committed anywhere.

**Layer 2: with layer 1 patched, `:app:checkDebugAarMetadata` fails.**

```
4 issues were found when checking AAR metadata:
  1. Dependency 'androidx.browser:browser:1.9.0' requires Android Gradle plugin 8.9.1 or higher.
     This build currently uses Android Gradle plugin 8.7.3.
  2. Dependency ':flutter_local_notifications' requires core library desugaring to be enabled for :app.
  3. Dependency 'androidx.core:core-ktx:1.17.0' requires Android Gradle plugin 8.9.1 or higher.
  4. Dependency 'androidx.core:core:1.17.0' requires Android Gradle plugin 8.9.1 or higher.
BUILD FAILED in 9m 30s
```

The toolchain today:
- AGP 8.7.3 and Kotlin 2.1.0 (`app/android/settings.gradle.kts:22`, `:27`)
- Gradle 8.12 (`app/android/gradle/wrapper/gradle-wrapper.properties:5`)
- Java 11 source and target (`app/android/app/build.gradle.kts:26-31`)
- no `isCoreLibraryDesugaringEnabled` anywhere

shk103's branch, which adds sensors_plus 6.1.2, produces the **identical**
four-issue list. `:sensors_plus:assembleDebug` builds under this toolchain,
so shk103 adds nothing here.

**Local-environment note, not part of the defect.** The SDK on the machine
this was measured on has only `platforms/android-33` and build-tools
30.0.3/33.0.2, and has no `cmdline-tools`. The app compiles against 36
(Flutter's default). Layer 2 was reached anyway, so Gradle fetched what it
needed. Whoever picks this up on another machine should not mistake a missing
SDK component for this bug.

## Acceptance criteria

- [ ] Layer 1 fixed in `app/android/app/build.gradle.kts`: explicit imports,
      the Flutter-template form.
- [ ] Layer 2 decided and fixed. **The decision is Leo's**: raise AGP to
      ≥ 8.9.1, with the Gradle and Kotlin versions that AGP requires, or pin
      the three AndroidX artifacts below their AGP-8.9.1 floor. Record which
      one and why. Enable core library desugaring (`isCoreLibraryDesugaringEnabled
      = true` + a `coreLibraryDesugaring` dependency) for flutter_local_notifications.
- [ ] `flutter build apk --debug` in `app/` exits 0 on a JDK matching CI
      (17). Its last lines are recorded in this spec's status log.
- [ ] `flutter build appbundle --release` (ANDROID.md:317, the release
      form) is also tried, and its result recorded. Signing may need
      `key.properties`; a signing failure gets recorded as one, not fixed here.
- [ ] andph1's placeholder question is answered by the same build, either
      "merge succeeded" or the merger's exact error, on andph1's own status log.
- [ ] If AGP moves to ≥ 8.12.1 (with Gradle ≥ 8.13 and Kotlin ≥ 2.2.0), say
      on shake-to-report that sensors_plus 7.x became possible. Its plan pins
      6.1 *because* of the old toolchain (design RQ8). That is a `devx revise`
      over there, not a change made here.

## Technical notes

- Nothing at PR time builds Android. CI's Flutter job runs only analyze,
  test and web. A fix here gets no CI signal unless its PR builds Android
  itself. Consider adding a PR-time `flutter build apk --debug` job in the
  same change, which would also have caught this.
- This is not caused by any one dependency bump. It is what resolution
  produces today from the committed `pubspec.lock`, so it reproduces on
  every machine.

## Status log

- 2026-11-25T11:15 — filed by shk103 (palateful-00). Both layers were
  reproduced on the untouched base `b677da27`, which equals `origin/main`
  `588445f5` for every Android/iOS/pubspec file. Leo chose to fix this
  separately rather than inside PR #135 or by accepting Phase 3 with Android
  unverified. Not started.
