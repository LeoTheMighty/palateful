---
hash: tfship1
type: dev
created: 2026-09-20T11:30:00-06:00
title: iOS TestFlight — get a live build to testers, then wire the pipeline
from: coordinator dispatch (leonidbelyi-41), 2026-09-20
status: ready
owner:
branch: feat/dev-tfship1
---

## Goal

Leo's TestFlight beta has **expired**. TestFlight builds die 90 days after
upload and cannot be renewed — the only fix is uploading a new build. Testers
are blocked today.

`.github/workflows/mobile-builds.yml` exists and has **0 runs, ever**. Every
step below is therefore unverified in the sense that matters: nothing has
executed it. That is the `deploy-freshness` lesson — carefully written,
correctly reasoned, dead at step 3 on all 52 runs.

Scope: **iOS only.** Android, `promote-android.yml` and `debug-andph1` are
explicitly out (coordinator, 2026-09-20).

## Headline finding

**The pipeline does not work as written, and two of its three blockers also
break the manual Xcode stopgap.** Fixing the pipeline first does not get a
build to testers any sooner, and it is the slower path. Ship by hand, then
wire.

## Acceptance criteria

- [ ] **A build is live on TestFlight and a tester can install it.** Upload is
      not the finish line — see B4, the build still needs assigning to a
      tester group.
- [ ] Version bumped past `+77` before any archive (see B1).
- [ ] Share-extension signing resolved (B2) — blocks both paths.
- [ ] Pipeline defects B1/B2/B3 fixed in `app/fastlane/Fastfile`, and the
      pipeline proves itself by producing an upload **after** the manual build
      has already unblocked testers. A green `workflow_dispatch` run is the
      only acceptable evidence; "it should work now" is not.
- [ ] Every secret is pasted by Leo directly into GitHub's secret store. No
      key, `.p8` content, password or JSON passes through an agent, a spec, a
      commit or a chat message.

## A. Blockers that hit BOTH paths (manual and pipeline)

### A1. The build number is already taken — `1.0.64+77`

`app/pubspec.yaml:19` reads `version: 1.0.64+77`, last bumped in `e9d5a05e`
on **2026-04-26** — the same day prod froze on image `c85e350`. Shipping
stopped repo-wide that day. A build uploaded around then expires ~2026-07-25,
which matches "the beta has expired".

So build **77 is almost certainly already on App Store Connect**, and App
Store Connect rejects a duplicate `CFBundleVersion` for the same
`CFBundleShortVersionString`. **Xcode will fail at upload too** — this is not
a pipeline-only problem.

**Verify before anything else** (30 seconds, and it decides the next step):
App Store Connect → Apps → Palateful → TestFlight → iOS builds. Read the
highest build number present. Then bump `app/pubspec.yaml` above it
(`1.0.65+78` if 77 is the max). Cheap and safe to bump regardless.

### A2. The share extension is in the archive and needs its own App ID

`app/ios/Runner.xcodeproj` has two shipping targets, not one:

| Target | Bundle ID |
|---|---|
| `Runner` | `com.palateful.palateful` |
| `PalatefulShare` | `com.palateful.palateful.share` |

(`PalatefulWidgets/` has entitlements on disk but is **not** a target — dead
files, ignore them.)

`PalatefulShare` landed 2026-04-18 (`0a93369e`), and `SHARE.md` — still an
open MANUAL item — says its App ID, App Group and provisioning profile are
human-only steps to do "before submitting the next TestFlight build". An
`app-store` archive signs **every** embedded target, so if
`com.palateful.palateful.share` has no distribution profile, the archive fails
for the pipeline and for Xcode alike.

**Unresolved and only Leo can settle it:** build 77 was bumped 2026-04-26,
*after* the extension landed on 04-18. If 77 shipped with the extension, the
App ID already exists and this is a no-op. If the extension went in after that
upload, it is a hard blocker. Check Apple Developer → Identifiers for
`com.palateful.palateful.share`. Present → skip to A3. Absent → `SHARE.md`
§1a–1c first (~15 min).

### A3. Entitlements the App IDs must carry

Both targets declare App Group `group.com.palateful.app`
(`Runner.entitlements`, `PalatefulShare.entitlements`). `Runner` additionally
declares `aps-environment: production` and time-sensitive notifications.

A profile can only be issued if the App ID has the matching capabilities
enabled, so **App Groups** and **Push Notifications** must both be on for
`com.palateful.palateful`, and **App Groups** for the `.share` App ID.

**This is the APNs distinction worth being precise about**, because it decides
whether M4.2 is in scope: signing needs the Push Notifications *capability*
enabled on the App ID. Actually *delivering* a push needs the APNs auth key
uploaded to Firebase. **The capability blocks the build; the key does not.**

## B. Pipeline-only defects

### B1. `match` provisions only the main app — archive will fail

`app/fastlane/Fastfile`:

```ruby
match(type: "appstore", readonly: is_ci,
      app_identifier: "com.palateful.palateful")
```

The extension's profile is never fetched, so `build_ios_app(export_method:
"app-store")` has nothing to sign `com.palateful.palateful.share` with. Fix:

```ruby
app_identifier: ["com.palateful.palateful", "com.palateful.palateful.share"]
```

### B2. The Match repo is empty and CI is read-only — chicken-and-egg

`readonly: is_ci` is correct practice, but it means CI can only *consume*
certs. Nothing has ever populated the Match repo, and `MATCH_GIT_URL` points
at a private repo that must exist and be initialised first.

**Leo must run `fastlane match appstore` locally once, in write mode, from a
machine signed in to the Apple Developer account**, for both identifiers. Until
that happens the pipeline cannot work no matter which secrets are set. This is
the single biggest reason the pipeline is not the fast path today.

### B3. No build-number increment — every run after the first collides

The Fastfile never calls `increment_build_number`, and the iOS lane never
reads the git tag, so `bundle exec fastlane ios beta` uploads whatever is in
`pubspec.yaml`. Tagging `v1.0.65` does **not** make the build `1.0.65`. First
run may pass on a manual bump; the second fails. Needs either
`increment_build_number(build_number: <ASC latest + 1>)` or deriving
version/build from `GITHUB_REF_NAME`.

### B4. Upload ≠ testers can install

`upload_to_testflight(skip_waiting_for_build_processing: true)` with no
`groups:` or `changelog:` uploads the binary and stops. The build lands in App
Store Connect and is assigned to **no tester group**, so nobody can install it.
Either add `groups:` to the lane or accept a manual step in App Store Connect
after each upload. **The AC is "a tester can install", so this counts.**

### B5. Minor — the `.p8` secret is newline-fragile

`APP_STORE_CONNECT_API_KEY_KEY` takes raw multiline `.p8` content with
`is_key_content_base64: false`. That works, but a mangled paste fails at
authentication with an unhelpful error. If it misbehaves, switch to
`is_key_content_base64: true` and paste base64 instead.

### What is NOT wrong

`actionlint` passes clean on both workflows (exit 0). `app/Gemfile`,
`app/fastlane/{Appfile,Fastfile}`, `app/ios/Podfile{,.lock}` all exist. The
job's step order (`flutter pub get` → `pod install`) is correct — `pub get`
generates the `Generated.xcconfig` that `pod install` needs.
`DEVELOPMENT_TEAM = H66YP2QFW2` is already set in `project.pbxproj:634`.
**So MANUAL M1.1 (Team ID) is already answered — it is in the repo, Leo does
not need to go look it up.**

## C. Leo's checklist — one pass, in order

**Path 1 — ship today by hand (~45 min, unblocks testers).**

1. **App Store Connect → TestFlight → iOS builds.** Read the highest build
   number. (Settles A1.)
2. **Apple Developer → Identifiers.** Is `com.palateful.palateful.share`
   there? Absent → do `SHARE.md` §1a–1c now (~15 min). (Settles A2.)
3. While there, confirm capabilities: `com.palateful.palateful` has **App
   Groups** + **Push Notifications**; `.share` has **App Groups**. (A3.)
4. Bump `app/pubspec.yaml` above the number from step 1.
5. Xcode → open `app/ios/Runner.xcworkspace` → check signing on **both**
   `Runner` and `PalatefulShare` → Product ▸ Archive → Distribute ▸ App Store
   Connect.
6. **App Store Connect → TestFlight → assign the build to your tester group.**
   Do not skip — upload alone leaves testers blocked. (B4.)

Register an iPhone UDID (M1.2) only if you want a development build on a
device; TestFlight does not need it.

**Path 2 — wire the pipeline afterwards (needs everything above, plus more).**

7. Create/choose a **private** git repo for Fastlane Match certificates.
8. From a machine signed in to the Apple Developer account, run `fastlane
   match appstore` in write mode for **both** identifiers. (B2 — the pipeline
   cannot work until this exists.)
9. **App Store Connect → Users and Access → Integrations → App Store Connect
   API.** Generate a key with **App Manager** role. Download the `.p8`
   **once** — Apple will not show it again. Note the **Key ID** and the
   **Issuer ID** on that page.
10. Paste into **GitHub → repo Settings → Secrets and variables → Actions →
    New repository secret**, five secrets, exact names:

    | Secret | Value |
    |---|---|
    | `MATCH_PASSWORD` | the passphrase chosen in step 8 |
    | `MATCH_GIT_URL` | the private repo URL from step 7 |
    | `APP_STORE_CONNECT_API_KEY_KEY_ID` | Key ID from step 9 |
    | `APP_STORE_CONNECT_API_KEY_ISSUER_ID` | Issuer ID from step 9 |
    | `APP_STORE_CONNECT_API_KEY_KEY` | full `.p8` contents incl. BEGIN/END lines |

11. Land the B1/B3/B4 Fastfile fixes, then `workflow_dispatch`
    `mobile-builds.yml` and watch it. Do not trust it until a run is green.

**Not needed for a first TestFlight build:** M4.1 Firebase project (already
exists — `app/android/app/google-services.json` is tracked, project
`palateful`, and `GoogleService-Info.plist` is present, so M4.3 is done too),
M4.2 APNs auth key (delivery, not signing — see A3), M4.4 GitHub webhook.
Android secrets are out of scope.

## Technical notes

- The Android job's `google-github-actions/auth@v2` step is **not**
  `continue-on-error`, so `FIREBASE_SERVICE_ACCOUNT_JSON` is a hard
  requirement for that job. Noted only to correct the "Firebase can wait"
  assumption for whoever picks Android up — out of scope here.
- `devx devx-helper claim` was deliberately **not** used: it commits and
  pushes to `main`, and main is serialised behind 0a's #29 and 4f's gated
  commit. This spec was authored directly on `feat/dev-tfship1`.

## Status log
- 2026-09-20T11:30 — filed from a coordinator dispatch, narrowed to iOS
  mid-investigation. Evidence: `actionlint` clean on both workflows; two
  native targets confirmed in `project.pbxproj`; entitlements read for both;
  `pubspec.yaml` version history cross-referenced against the 90-day TestFlight
  expiry window and the 2026-04-26 prod freeze. Not verified and not
  verifiable from here: App Store Connect and Apple Developer portal state
  (A1, A2) — both flagged as Leo's first two checks precisely because they
  gate which path is shortest.
