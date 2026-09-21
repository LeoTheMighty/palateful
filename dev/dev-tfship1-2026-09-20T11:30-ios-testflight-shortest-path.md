---
hash: tfship1
type: dev
created: 2026-09-20T11:30:00-06:00
title: iOS TestFlight — get a live build to testers, then wire the pipeline
from: coordinator dispatch (leonidbelyi-41), 2026-09-20
status: ready
owner: null
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

## Operating principle — the console is authoritative, the repo is a stale cache

Established twice in twenty minutes, both times against this spec's own
drafted expectation:

| Question | What the repo said | What the console said |
|---|---|---|
| What build are we on? | `pubspec.yaml` → **77** | ASC → **88** (11 ahead) |
| Does the `.share` App ID exist? | `SHARE.md` §1 open → **no** | Identifiers → **yes**, for months |

Both times the repo was not merely stale but *confidently wrong*, and both
times acting on it would have cost real time — a duplicate-build upload
failure with no obvious cause, and ~15 minutes recreating an identifier that
already existed.

The mechanism is the same in both: the work happens in Apple's systems, and
**nothing writes back to the repo.** `pubspec.yaml` records what someone
remembered to commit; `SHARE.md` records what was true when it was written.
Neither is a source of truth for Apple's state, and neither announces that it
has gone stale.

**So: for anything that lives in Apple's systems, read the console first —
especially when the repo looks unambiguous, because that is exactly when the
instinct is to skip the check.** Every remaining Path 1 step that touches
Apple state is written as a confirmation, not an assumption.

## Headline finding — CORRECTED 2026-09-20T13:10

The original framing of this spec was **wrong**, and the correction matters
more than anything it got right.

> ~~"The pipeline is unwired scaffolding."~~

That was true of `mobile-builds.yml` and false of the repo. **There is a
working end-to-end iOS deploy: `bin/prod-ios-deploy`.** One command — `flutter
build ios --release` → `xcodebuild archive` → generated ExportOptions
(`method: app-store-connect`, `destination: upload`, `teamID: H66YP2QFW2`) →
`xcodebuild -exportArchive -allowProvisioningUpdates`. No Fastlane, no Match,
no Xcode UI. Last touched `c97d25a5` (2026-04-24), which brackets builds
78–88 exactly. **That is how they were uploaded.**

How the error was made, because it is the same one twice: we searched
`.github/workflows/`, found a workflow with 0 runs, and concluded "mobile has
never deployed". That is true of *CI* and false of *deploying* — the presence
of an unused workflow read as the absence of a working path. Same proxy
mistake as reading `pubspec.yaml` for what shipped.

**Corrected premise: there is a working local deploy and no CI wrapper around
it.** Everything below is re-reasoned from that.

The script's two real gaps are precisely today's two symptoms:

- **No build-number bump.** Its last line is `echo "Don't forget to commit the
  version bump!"` — a comment standing in for automation. **That is the
  eleven-build drift mechanism, found.** A1 is no longer a mystery.
- **No tester-group assignment.** Upload only, so testers stay blocked until
  someone clicks in App Store Connect. B4 is a property of every mechanism
  here, not of Fastlane.

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

### A1. RESOLVED — and the repo lied by eleven

**Measured, not inferred.** Leo read App Store Connect: **Version 1.0.64,
Build (88)**. The repo said `1.0.64+77`. **ASC was eleven builds ahead.**

`app/pubspec.yaml` is now bumped to **`1.0.64+89`** on this branch. Version
stays `1.0.64`; only the build number has to clear 88 for TestFlight.

**The part worth keeping is not the number, it's why the repo was wrong.**
Builds 78–88 were archived from a working copy whose version bump was never
committed. So `pubspec.yaml` is **not the source of truth for what has
shipped**, and anyone who reads the repo to answer "what build are we on"
gets 77 and is wrong by eleven — in the direction that makes every upload
fail with a duplicate-build error and no obvious cause.

The original draft of this spec reasoned *from* `pubspec.yaml` and predicted
"77 is probably the latest". That was wrong, and it was wrong in the way
checklists usually go wrong: the repo is right there, the console needs a
login, so the instinct is to trust the repo and skip the console read. **Path 1
step 1 exists to stop exactly that, and it earned its place on its first run.**
Keep it even when the repo looks unambiguous — especially then.

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

**Prediction: this is almost certainly already done.** The reasoning changed
once ASC turned out to be at 88 rather than 77, and it got *stronger*:

- `PalatefulShare.appex` sits in Runner's **Embed App Extensions** copy-files
  phase (`project.pbxproj:61-71`), and `git log -S` puts that phase in the
  original `0a93369e` commit of **2026-04-18**. So every Runner archive since
  04-18 embeds the extension — there is no variant that quietly leaves it out.
- Builds **78–88 were uploaded after 2026-04-26** and they succeeded.
- An `app-store` archive signs every embedded target. Eleven successful
  uploads carrying the extension are only possible if
  `com.palateful.palateful.share` already has an App ID and a distribution
  profile.

So Leo should expect to **find it present**. He still has to look — a
prediction is not a verification, and this one is built on the assumption that
78–88 came from a checkout of `main` rather than some older branch. But if it
is missing, that is the surprise worth stopping on, not the expected case.
Apple Developer → Identifiers → `com.palateful.palateful.share`. Present →
skip to A3. Absent → `SHARE.md` §1a–1c first (~15 min).

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
run may pass on a manual bump; the second fails.

**A1 is the real argument for fixing this, and it is better than
"automation is nice".** The eleven-build divergence happened *because* a human
bumped a local working copy and archived from it. The fix is not discipline —
it is making ASC authoritative:

```ruby
increment_build_number(
  build_number: latest_testflight_build_number(api_key: api_key) + 1
)
```

That reads the number from App Store Connect at build time, so the repo can
drift and it no longer matters: the pipeline cannot produce a duplicate, and
nobody has to remember to commit a bump. Deriving from `GITHUB_REF_NAME`
would fix the *version* string but not this — a tag can be re-cut, ASC cannot
be un-uploaded. **Once CI owns the build number, the A1 class of failure stops
being possible.**

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

1. ~~Read the highest build number in App Store Connect.~~ **DONE** — 88.
   `pubspec.yaml` is already bumped to `1.0.64+89` on this branch. (A1.)
2. ~~Apple Developer → Identifiers.~~ **DONE** — Leo confirmed
   `com.palateful.palateful.share` is present, 2026-09-20. Prediction held.
   `SHARE.md` §1 annotated and the MANUAL.md row refreshed per-part. (A2.)
3. ~~Confirm capabilities.~~ **Skip — the same evidence covers it.** A
   provisioning profile cannot be issued unless the App ID carries the
   declared entitlements, so eleven signed uploads already prove **App
   Groups** on both identifiers and **Push Notifications** on
   `com.palateful.palateful` (`Runner.entitlements` declares
   `aps-environment: production`). Xcode will say so in step 4 if not. (A3.)
4. Xcode → open `app/ios/Runner.xcworkspace` → check signing on **both**
   `Runner` and `PalatefulShare` → Product ▸ Archive → Distribute ▸ App Store
   Connect.
5. **App Store Connect → TestFlight → assign the build to your tester group.**
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

## D. There are FOUR mechanisms, not two — and one of them is already supposed to do this

Before building anything, the landscape, because proposing a fourth without
accounting for the third would repeat today's mistake:

| # | Mechanism | State | Evidence |
|---|---|---|---|
| 1 | `bin/prod-ios-deploy` | **Works.** Produced builds 78–88 | `c97d25a5`, 2026-04-24 |
| 2 | `mobile-builds.yml` (Fastlane + Match) | **0 runs, ever.** Defects B1–B5 | `gh run list` |
| 3 | **Xcode Cloud** | Scaffolded, actively maintained, **status unknown** | `app/ios/ci_scripts/ci_post_clone.sh`, last touched 2026-07-31 |
| 4 | A new GitHub Actions macOS job | What Leo just asked for | — |

**`docs/DEPLOYMENT.md:91-97` already claims mechanism 3 does exactly what Leo
is asking for:**

> "Pushes to `main` **also trigger an Xcode Cloud workflow** that archives and
> uploads to TestFlight without running `bin/prod-ios-deploy`."

That is the requested feature, documented as already existing. And it is
demonstrably **not happening** — if it were, builds would have continued past
88 on their own. They stopped.

**So the first question is not "how do we build this" but "why did the thing
that already does this stop?"** Note where the answer lives: Xcode Cloud is
configured in **App Store Connect**, not in the repo. `ci_scripts/` is its
only repo-side trace. This is the operating principle a third time — the repo
documents a working path, the console knows it isn't running, and nothing
reconciles them.

**Leo's check (2 min): App Store Connect → Xcode Cloud → the workflow.** Is it
present, is it enabled, when did it last run, and what did it say? Three
outcomes:

- **Disabled or never finished being configured** → re-enable it. Probably the
  shortest path to "runs on main" of anything in this document.
- **Failing** → fix that. It may be the known artifact-save failure.
- **Genuinely absent** → then build mechanism 4, per §E.

## E. Design proposal — answers to the four questions

Deliberately a proposal, not an implementation. Q2's answer changes Leo's
secret list, so it should be agreed first.

### Q2 first — signing in CI. **The ASC API key is necessary but NOT sufficient.**

This is the highest-value question and the answer is a qualified no, so
stating it plainly to head off a wrong expectation:

`xcodebuild -exportArchive -allowProvisioningUpdates` does accept
`-authenticationKeyPath` / `-authenticationKeyID` / `-authenticationKeyIssuerID`
(Xcode 13+). Those cover **provisioning-profile creation and upload auth** —
so the *profile* half of Fastlane Match genuinely disappears.

They do **not** put an **Apple Distribution certificate and its private key**
in the runner's keychain. A fresh macOS runner has neither. And the tempting
shortcut is a trap: `-allowProvisioningUpdates` *can* mint a new distribution
certificate, but the private key dies with the ephemeral runner, so every run
creates another — until the account hits Apple's distribution-certificate cap
and every subsequent run hard-fails. It would look like it worked for a few
runs.

So the cert must be supplied:

| Secret | Where Leo gets it |
|---|---|
| `APP_STORE_CONNECT_API_KEY_ID` | ASC → Users and Access → Integrations |
| `APP_STORE_CONNECT_ISSUER_ID` | same page |
| `APP_STORE_CONNECT_API_KEY_P8` | downloaded `.p8`, once only |
| `IOS_DIST_CERT_P12_BASE64` | Keychain Access → export Apple Distribution as `.p12` → `base64` |
| `IOS_DIST_CERT_PASSWORD` | the passphrase he sets on that export |

**Net: five secrets, same count as Fastlane — so this is not the "down to
three" win it looked like.** The real win is different and still large:
**the Match bootstrap disappears.** No private certificate repo, no local
`fastlane match appstore` write run, no Ruby in the deploy path. B2 — the
chicken-and-egg that made the Fastlane path unshippable — stops existing.
Leo exports a `.p12` from Keychain Access in two minutes instead.

**And if mechanism 3 is revivable, all five go away**: Xcode Cloud handles
signing entirely on Apple's side. **Zero signing secrets.** That is the
strongest argument for checking §D before building §E.

### Q1 — gating. Path-filter on `app/`, and do **not** copy `deploy-web`'s trigger.

`deploy-web` does **not** depend on `detect-changes` (`ci.yml` — its `needs:`
is `[setup, lint, test, check-models, flutter-test, terraform]`). It
redeploys on *every* main push. That is harmless for Cloudflare and actively
bad for TestFlight: a build per docs commit means a burned build number and a
**push notification to every tester** each time. Today proves the case — four
PRs merged, none touched `app/`.

So: gate on `app/`. `detect-changes` is the right lever and it just became
usable — **`app/project.json` was created today** (11:28, the `nxappproj`
fix), so `npx nx show projects` now lists `app`. It didn't when this
investigation started. `detect-changes` needs one new output (`app`) alongside
`api`/`worker`/`migrator`/`parser`; the job already does exactly this shape of
filtering.

Recommend `workflow_dispatch` as well, so Leo can ship without a code change.

### Q3 — build number. Derive from App Store Connect, never from the repo.

`github.run_number` is monotonic but unanchored — it is currently far below
88, so it would need a hardcoded offset that silently rots the same way
`pubspec.yaml` did. Rejected for being the same class of bug.

Query ASC for the latest build number and add one. With the API key already
present this is a short JWT-signed `GET /v1/builds` — no Fastlane needed,
though `latest_testflight_build_number` is the same idea if Ruby is acceptable.

**The property that matters: the repo stops being the source of truth.**
`pubspec.yaml`'s build number becomes advisory, CI's computed value wins, and
the A1 drift class cannot recur regardless of who archives from what. That is
the fix, not the convenience.

### Q4 — `mobile-builds.yml` should be deleted, plainly.

It has never run, its iOS lane has three defects (B1/B3/B4), and it needs a
Match bootstrap nobody has done. If mechanism 3 or 4 lands, the Fastlane path
is superseded and keeping it means **two mechanisms where one has never
worked** — a standing invitation for the next person to wire the wrong one, as
this spec itself did for its first three hours. Delete the iOS job with the
change that replaces it. (Its Android job is out of scope here and should be
handled by whoever picks Android up; do not delete that half silently.)

### Still in scope regardless of mechanism: tester-group assignment

Every mechanism in the table uploads and stops. **"Uploaded" is not "testers
can install."** Whatever lands must either assign the build to a tester group
(ASC API, or Fastlane's `groups:`) or state explicitly that a human click
remains — it should not be discovered later by testers who still can't
install.

## F. Xcode Cloud audit — what would break it now (measured 2026-09-20)

Leo picked Xcode Cloud. Audited the hooks against seven weeks of repo drift.
**One real break, one real hazard, and two suspicions cleared.**

### F1. THE BREAK — `ci_post_clone.sh` installs the wrong Flutter, and the gap widens weekly

```sh
git clone https://github.com/flutter/flutter.git --depth 1 -b stable "$HOME/flutter"
```

That is the **tip of stable**, not the repo's pin. Measured today:

| Surface | Flutter |
|---|---|
| Tip of `stable` (what the hook installs) | **3.47.5** |
| `ci.yml:336`, `mobile-builds.yml:42` | **3.41.7** |

**Six minor versions apart, and it widens with every Flutter release** —
nothing in the repo constrains it. `fltup1` already paid for this lesson
locally (3.38.9 → 3.41.7 produced 94 failures from one stale shader). Xcode
Cloud has been silently doing the same drift, unbounded, since the hook was
written on 2026-04-15 — when tip-of-stable *was* roughly the pin, which is
why it worked then and rots now.

Same shape as the fixture dates and the build number: **fine when written,
wrong by the calendar, and nothing reports it.** Fix: `-b 3.41.7`, kept in
step with `ci.yml`. (`--depth 1 -b <tag>` works for tags.)

### F2. THE HAZARD — a symbol upload can fail the whole archive

`ci_post_xcodebuild.sh` hard-`exit 1`s when
`app/ios/Pods/FirebaseCrashlytics/upload-symbols` is missing. `Pods/` is not
tracked, so that path exists only if `pod install` produced it — and a
Crashlytics *niceness* failing a *release archive* is a bad trade. If Leo's
workflow shows a late-stage failure after a clean build, look here first;
it matches the shape of the reported artifact-save failure. Recommend
downgrading to a warning + `exit 0`.

### F3. CLEARED — `.env.prod` is a non-issue, and the doc was wrong twice

`.env.prod` does not exist and `ci_post_clone.sh` does not reference `.env`
at all (grep: 0 hits). Not a break: the staging step was **removed** in
`5f13ad7f` (2026-04-23) when `flutter_dotenv` was dropped, and prod config is
now compile-time constants in `environment.dart`. `docs/DEPLOYMENT.md`
described the staging for *both* the Xcode Cloud hook **and**
`bin/prod-ios-deploy`, and had been wrong about both for five months. Both
corrected.

### F4. CLEARED — the share-extension gates pass

Ran them rather than reasoning about them:
`tools/share-extension-tests.sh` → **7/7 passed**. Memory-footgun lint →
clean. The `flutter test` rot that hit `imports_tab` does not reach these —
they are `swiftc`-compiled pure-logic sources with no Flutter fixtures. No
retired-command references in either hook.

### F5. Q1 and Q3 are NOT moot — Q3 especially

- **Q1 (gating): natively solved.** Xcode Cloud start conditions take
  file/folder path filters, so scope the branch-change condition to `app/`.
  No `detect-changes` output needed; the concern about a TestFlight build per
  docs commit is handled in the workflow UI.
- **Q3 (build number): the drift comes back in a new place, exactly as
  suspected.** Xcode Cloud's `CI_BUILD_NUMBER` is per-workflow and **starts at
  1** for a new workflow. App Store Connect is at **88**. A revived workflow
  would therefore upload build 1, 2, 3… and be rejected until it climbed past
  88. Either enable Xcode Cloud's own build-number management *and* verify it
  starts above 88, or add a `ci_pre_xcodebuild.sh` that sets `CFBundleVersion`
  monotonically above the ASC maximum. **Do not assume Xcode Cloud inherits
  the repo's number — it does not read `pubspec.yaml` for it.**
- **Q2 is genuinely moot.** Apple signs. Zero signing secrets, which is why
  this path beats the GitHub Actions one.

### F6. If it is disabled or was never configured — what Leo clicks

Xcode Cloud config lives in App Store Connect / Xcode, so this is his hands:

1. **Xcode → Product ▸ Xcode Cloud ▸ Manage Workflows** (or ASC → the app →
   Xcode Cloud), targeting `app/ios/Runner.xcworkspace`, scheme **Runner**.
2. **Start condition:** Branch Changes → `main`. Add a **Files and Folders**
   filter scoped to `app/` (this is Q1).
3. **Environment:** macOS/Xcode version matching the 3.41.7 toolchain, and
   confirm `ci_scripts/` is detected (Apple requires it adjacent to the
   `.xcworkspace` — it is, at `app/ios/ci_scripts/`).
4. **Action: Archive**, configuration **Release**, deployment prep
   **TestFlight (Internal Testing)** — this is what makes `CI_ARCHIVE_PATH`
   exist, which `ci_post_xcodebuild.sh` keys off.
5. **Post-action: TestFlight Internal Testing → select the tester group.**
   **Do not skip.** Every mechanism examined in this spec stops at "uploaded";
   this is the step that makes testers able to install, and it is the entire
   point of the exercise.
6. Fix F1 (and ideally F2) **before** the first run, then trigger manually and
   read the log — do not trust it until a run is green and a build number
   above 88 appears in TestFlight.

## G. The deliberate trigger — how to read the three outcomes

Merging this branch touches `app/pubspec.yaml`, so it should satisfy any
`app/`-scoped path filter. Leo's ASC reading — "it was all working at some
point", nothing above 88, something "says it expired" — plus the fact that
**two merges today already touched `app/` (#1 rbv101, #26) and neither fired**
points at disabled/expired rather than filtered. Filtering was already ruled
out by evidence before we spend a merge on it.

Fixed first so the test measures what we want: **F1 (Flutter pinned to
3.41.7)** and **F2 (Crashlytics downgraded to a warning)**. Without those the
run fails on causes already diagnosed and teaches nothing.

**`CI_BUILD_NUMBER` is deliberately NOT fixed.** Read the expected rejection
as a success.

| # | Outcome | What it means | Next |
|---|---|---|---|
| 1 | **No run at all.** Nothing appears in Xcode Cloud; no email, no log | The workflow is not connected to the trigger — disabled, deleted, or **compute hours/subscription genuinely expired**, which matches "says it expired". **Silence is a real answer, not an inconclusive test.** It rules out every code-side cause at once: the hooks never executed, so nothing in this repo is implicated | §F6 click-list. Check the billing/hours state first — a lapsed plan produces exactly this and no diagnostic anywhere |
| 2 | **Runs, fails before upload** | The workflow IS live and the trigger works — that alone is worth the merge. Now it's a hook problem. Read the log for *which* phase | If post-clone: F1 should have covered Flutter; look at `pod install`. If post-xcodebuild: F2 should have covered symbols; the appex-embed assertion is the other `exit 1` there |
| 3 | **Runs, builds, rejected at upload as a duplicate/too-low build number** | **The best realistic outcome.** It proves the whole chain — trigger fired, clone worked, pinned Flutter installed, pods resolved, archive built, extension embedded, upload reached App Store Connect. Only the build number is wrong, and we already know why | Fix Q3 (§F5): `CI_BUILD_NUMBER` starts at 1 against ASC's 88. Add `ci_pre_xcodebuild.sh` setting `CFBundleVersion` above the ASC max, or enable Xcode Cloud's own numbering and verify where it starts |

**Do not read outcome 3 as a new failure.** It is the expected result of a
known, deliberately-unfixed gap, and it carries more information than a green
tick would — a green tick would only prove the workflow runs, whereas a
duplicate-build rejection proves every stage up to and including ASC
authentication.

Outcome 1 is the one that needs no code from us and the only one whose fix is
entirely in Leo's hands.

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
- 2026-09-20T12:10 — A1 resolved by measurement, and the measurement
  contradicted this spec's own prediction: ASC is at **build 88**, the repo at
  77 — eleven ahead, because builds 78–88 were archived from a working copy
  whose bump was never committed. Bumped `app/pubspec.yaml` to `1.0.64+89`.
  Recorded the lesson rather than just the number: `pubspec.yaml` is not the
  source of truth for what has shipped, and the draft's "77 is probably the
  latest" was exactly the trust-the-repo instinct Path 1 step 1 exists to
  block. Knock-on: A2's prediction flipped to **"expect the share App ID to
  already exist"** — `PalatefulShare.appex` has been in Runner's Embed App
  Extensions phase since `0a93369e` (2026-04-18, confirmed by `git log -S`),
  so all eleven post-04-26 uploads carried the extension and could only have
  signed with a real distribution profile. B3 rewritten to argue from this:
  `latest_testflight_build_number` makes ASC authoritative and forecloses the
  whole A1 failure class, which is a stronger case for the pipeline than
  automation-for-its-own-sake.
- 2026-09-20T12:35 — A2 confirmed positive: Leo read Apple Developer →
  Identifiers and `com.palateful.palateful.share` is present. The prediction
  held, and by the argued route (one of builds 78-88 shipped the extension).
  Knock-on, stated before Leo opens Xcode: **step 3 collapses too.** A profile
  cannot be issued unless the App ID carries the declared entitlements, so the
  same eleven signed uploads that prove the App ID exists also prove App Groups
  on both identifiers and Push Notifications on the main app. Steps 2 and 3
  are now confirmations already made; Leo's real remaining path is **get the
  bump → Xcode signing check → archive → distribute → assign to tester
  group**. Annotated `SHARE.md` §1 with a skip-to-§2 notice and refreshed the
  MANUAL.md row per-part rather than closing it — §2 Xcode signing, §3
  on-device happy path and §4 device matrix genuinely remain, and closing the
  whole row would have been the same stale-bookkeeping error in the opposite
  direction. Added the operating principle above; it is the generalisation of
  both surprises, not an anecdote about either.
- 2026-09-20T13:10 — **premise corrected.** `bin/prod-ios-deploy` is a working
  end-to-end iOS deploy and is how builds 78-88 reached TestFlight; this
  spec's "the pipeline is unwired scaffolding" was true of `mobile-builds.yml`
  and false of the repo. Root of the error: searched `.github/workflows/`,
  found 0 runs, concluded "never deployed" — CI absence read as deploy
  absence. Re-reasoned the whole document from the corrected premise rather
  than patching the line. Found in the process that there are **four**
  mechanisms, not two: `docs/DEPLOYMENT.md:91-97` claims an **Xcode Cloud**
  workflow already archives and uploads on every push to `main` — which is
  exactly the feature being requested — and `app/ios/ci_scripts/` was
  maintained as recently as 2026-07-31. It is demonstrably not running (builds
  stopped at 88), and its config lives in App Store Connect where the repo
  cannot see it. So the first question is why the existing mechanism stopped,
  not how to build another. Design answers in §E; the load-bearing one is Q2 —
  an ASC API key covers profiles and upload auth but **not** the distribution
  certificate, so it is 5 secrets rather than the hoped-for 3, and the real
  prize is that the Match bootstrap (B2) disappears. If Xcode Cloud is
  revivable it is 0 signing secrets, which is why §D gates §E.
- 2026-09-20T13:45 — Leo picked Xcode Cloud; audited both hooks against seven
  weeks of drift (§F). One real break: `ci_post_clone.sh` clones tip-of-stable
  Flutter (**3.47.5** today) against a repo pinned at **3.41.7** — six minors
  and widening, the same fine-when-written/wrong-by-the-calendar shape as the
  fixture dates and the build number. One hazard: `ci_post_xcodebuild.sh`
  hard-fails the archive on a missing Crashlytics `upload-symbols`. Two
  suspicions cleared by measurement rather than argument: `.env.prod` is a
  non-issue (staging was removed in `5f13ad7f`; the doc was wrong about it for
  both mechanisms) and `tools/share-extension-tests.sh` passes **7/7** with the
  footgun lint clean. Q3 is **not** moot — Xcode Cloud's `CI_BUILD_NUMBER`
  starts at 1 per workflow and does not read `pubspec.yaml`, so a revived
  workflow would upload below ASC's 88 and be rejected; the drift returns in a
  new place exactly as the coordinator suspected. Deliverables landed:
  `docs/DEPLOYMENT.md` corrected in three places (all traceable to `5f13ad7f`)
  and now documents *how to tell the workflow is running* rather than
  asserting that it does; `mobile-builds.yml`'s iOS job deleted with its
  rationale in the header, Android job untouched, `actionlint` clean.
  `bin/prod-ios-deploy` retained as the documented manual fallback.
- 2026-09-20T14:05 — prepared the branch for a deliberate Xcode Cloud trigger.
  Pinned `ci_post_clone.sh` to Flutter **3.41.7** (was tip-of-stable, 3.47.5
  today) — shallow-cloning the tag then naming the local branch `stable`,
  because Flutter derives its channel from the branch name and a detached tag
  checkout reports channel "unknown"; added a version assertion that fails
  loudly rather than building against something untested, since a *silent*
  mismatch is the exact failure mode the pin exists to prevent. Downgraded
  `ci_post_xcodebuild.sh`'s missing-`upload-symbols` `exit 1` to a warning +
  `exit 0`: symbolication is a convenience and should not cost a shippable
  archive, and during this test it would mask what we are trying to see. Left
  `CI_BUILD_NUMBER` unfixed on purpose — §G explains why the resulting
  duplicate-build rejection is the *best realistic outcome* rather than a
  failure. Added §G so all three outcomes, including **no run at all**
  (expired compute/subscription — silence as a real answer), are interpretable
  without another round trip.
