<!-- refined via party-mode 2026-04-18 -->
# Epic: Android Play Console Launch

## Locked cross-epic decisions (inherited — do not re-litigate)

1. **Contact email v1: `leonid@ac93.org`** (from `epic-android-privacy-policy-page`).
2. **Privacy policy URL: `https://palateful.app/privacy`** (from `epic-android-privacy-policy-page`).
3. **Single GCP service account** holds Play Console release-manager + Firebase Crashlytics + Firebase Test Lab roles (from `epic-android-release-hardening` / `epic-android-ci-hardening`). One JSON, one rotation surface.
4. **`assetlinks.json` placeholder → real SHA-256 hand-off** happens in this epic's `apl-1` Section 11–12 (from `epic-android-release-hardening`).
5. **Adaptive icon source PNG** at `app/android/play-store-assets/icon-source-1024.png` (from `epic-android-release-hardening`); `apl-2` down-scales this to the 512×512 Play Store listing icon — one brand source of truth.
6. **YOLO acceptance:** tag → internal-track reliable; production promotion manual via Play Console after the 14-day × 12-tester gate clears.

## Added by this workshop

- **ANDROID.md is structured as "Day 1 / Day 2 / Day 3"** plus a post-launch section. Day 1 is signup + ID verification (then 2–3 day wait). Day 2 is keystore, GitHub Secrets, GCP service account, Play Console app creation, first manual AAB upload. Day 3 is the forms (Store Listing, Data Safety, Content Rating), tester recruitment, first CI-driven tag. Each section has a time estimate. A wall-of-21-steps is cognitively worse than a few bounded sessions.
- **Paste blocks are truly paste-ready** — every value that's decided (developer name "Palateful", contact email `leonid@ac93.org`, audience Teen 13+, category Food & Drink, package name `com.palateful.palateful`) is a literal in the fence, not a placeholder. Only two genuine `<FILL>`s: (a) the Play App Signing SHA-256 (exists only post-first-upload), (b) the current pubspec version for each tag.
- **Pre-Launch Report success criteria explicitly defined** — Section 18: (a) zero critical crashes, (b) zero app-signing errors, (c) accessibility warnings acceptable, (d) performance warnings acceptable. If any (a) or (b) fires, the release is held pending fix. Sets operator expectation so the first few reports don't trigger unnecessary alarm.
- **Keystore disaster-recovery procedure** in Section 21 (Troubleshooting): if the upload keystore is lost, use Play Console → Setup → App Integrity → Request upload key reset (Google re-issues; takes 2–3 business days). Backup: 1Password export + an offline encrypted copy. Addresses the "what if I lose the keystore" operator panic preemptively.
- **Tester outreach template has a feedback channel**: "Reply to this email or file an issue at https://github.com/<user>/palateful/issues if anything breaks." Cheap, removes ambiguity, avoids feedback getting lost in Signal threads.
- **Single-GCP-SA roles checklist** in Section 6: `androidpublisher` (Play Console upload), `firebase.crashlytics.access`, `firebase.testlab.access`, `cloudtrace.agent` (optional, for debugging). Copy-paste gcloud commands to grant each. Reviewable in one block.

## Overview

The code side is ready (epics `android-release-hardening` + `android-ci-hardening`) and the privacy page is live (`android-privacy-policy-page`). Remaining work is the **human runbook**: Google Play Developer account signup, keystore generation, GitHub Secret population, GCP service account, Play Console app creation, first AAB upload (manual — Fastlane cannot create a new Play Console app), store listing, Data Safety form, Content Rating, tester recruitment. None of this is automatable.

This epic emits two deliverables:

1. **`ANDROID.md` at repo root** — a single-operator runbook. Every step is either a link + action or a literal shell command. Paste-ready text blocks for the Play Console forms (Data Safety, content rating, permission justifications) live in-file.
2. **`app/android/play-store-assets/`** — version-controlled store listing assets: 512×512 app icon, 1024×500 feature graphic, 2–4 phone screenshots. Re-uploadable from a clean checkout; no "where did I put that PNG" hunt.

Operator has no Android device. Screenshots are captured from an Android emulator (Pixel 7, API 34). The first internal-track install will be tested by friends/family via a Google Group opt-in URL — also documented here.

## Goal

A single markdown file the operator can follow top-to-bottom, in one sitting (~90 minutes), that results in Palateful listed on Play Store internal track with a reachable privacy policy, a passing content rating, a filled Data Safety form, and a working opt-in URL for friends/family testers.

## End-user flow

**There is no in-app user-visible flow here — this epic is a runbook.** The "user" is the operator (the developer publishing the app). The "end-user flow" is the operator's sequential experience of reading and executing the runbook.

### Operator flow (time estimate in parentheses)

1. **Pre-flight (10 min)** — operator reads the top of ANDROID.md: "YOLO acceptance criteria", what's automated vs. manual, what requires a personal government ID.
2. **Keystore generation (5 min)** — run `keytool -genkeypair -v -keystore palateful-upload.jks -alias upload -keyalg RSA -keysize 2048 -validity 9125`. Save passwords in 1Password.
3. **GitHub Secrets (5 min)** — `base64 -i palateful-upload.jks | pbcopy`, then paste into `ANDROID_KEYSTORE_BASE64`, + passwords + alias.
4. **Google Play Developer signup (20 min + 2–3 day verification wait)** — visit https://play.google.com/console/signup, choose Personal, name "Palateful", pay $25, upload photo ID, wait.
5. **Google Cloud service account (10 min)** — create GCP project, create service account, download JSON. (Covered in ANDROID.md with exact click path.)
6. **Link service account to Play Console (5 min)** — grant Release Manager role in Play Console → Setup → API access. Accept invite.
7. **Populate GitHub Secrets for Fastlane (3 min)** — paste service account JSON into `PLAY_STORE_JSON_KEY`.
8. **Create Play Console app (10 min)** — "Create app" → name "Palateful" → default language → App/Free → agree to policies.
9. **Enroll Play App Signing (5 min)** — during first release upload flow; Google takes over signing key management.
10. **First manual AAB upload (10 min)** — build locally `flutter build appbundle --release`, upload to internal track in Play Console. Wait for Play App Signing enrollment to complete.
11. **Retrieve SHA-256 fingerprint (3 min)** — Play Console → Setup → App integrity → App signing key certificate → copy SHA-256.
12. **Update `assetlinks.json` (3 min)** — paste SHA-256 into `app/web/.well-known/assetlinks.json`, commit + push → Cloudflare Pages deploys.
13. **Fill Store Listing (15 min)** — paste short description, full description, category (Food & Drink), tags from ANDROID.md. Upload 512×512 icon + 1024×500 feature graphic + screenshots from `app/android/play-store-assets/`.
14. **Fill Content Rating (10 min)** — run IARC questionnaire; ANDROID.md has the answer key for Teen 13+ with alcohol-containing recipes.
15. **Fill Target Audience (3 min)** — pick 13+; confirm design is not child-appealing.
16. **Fill Data Safety (20 min)** — ANDROID.md has paste-ready text blocks for each disclosure: Firebase Crashlytics, FCM, Auth0, S3 media, Google/Apple sign-in, OpenAI/Anthropic chat, Play Billing (reserved).
17. **Declare Sensitive Permissions (5 min)** — SCHEDULE_EXACT_ALARM justification block in ANDROID.md; paste verbatim. POST_NOTIFICATIONS justification.
18. **Create tester Google Group (10 min)** — https://groups.google.com → "Palateful Android Testers" → get the group email address.
19. **Set up internal-track opt-in (5 min)** — Play Console → Testing → Internal testing → Testers → add Google Group email. Grab the opt-in URL.
20. **Tag first CI-driven release (3 min)** — bump pubspec, merge, `git tag v1.0.16 && git push origin v1.0.16`. `mobile-builds.yml` takes over; internal-track AAB lands in ~10 minutes.
21. **Verify Pre-Launch Report (wait 30 min, review 10 min)** — Play Console → Testing → Pre-launch report → click the most recent run → fix any critical crashes in follow-up stories.
22. **Distribute opt-in URL to 3–5 friends with Android phones (1 min)** — "click this, install, break it."

Total: ~2 hours of focused operator time, plus 2–3 day wait for Google's identity verification, plus ~14 days for the closed-test gate before production promotion.

## Frontend changes

None. No Flutter code touched.

## Backend changes

None.

## Infrastructure changes

### `ANDROID.md` at repo root

Structured as a numbered runbook. Uses fenced code blocks for every literal command. Each section is self-contained so the operator can bookmark and resume.

Outline (restructured as Day 1 / Day 2 / Day 3 + post-launch):

### Day 1 — Signup (20 minutes active, then 2–3 day wait)

1. **Goal and scope** — what this doc covers, what it doesn't (in-app features, iOS). YOLO acceptance criteria.
2. **Prerequisites** — repo checked out, 1Password access, government photo ID ready, $25 in the payment account.
5. **Google Play Developer account signup** — URL, choose Personal, name "Palateful", identity verification wait.

### Day 2 — Credentials + first AAB (75 minutes)

3. **Upload keystore generation** — exact keytool command + password conventions + 1Password entry naming + 1Password backup of base64.
4. **GitHub Secrets population** — every secret name + source + command to base64-encode + which workflow uses it.
6. **Single GCP service account for all CI** — create GCP project, create service account, grant 3 roles (`androidpublisher`, `firebase.crashlytics.access`, `firebase.testlab.access`), download JSON, link in Play Console with Release Manager permission. Paste-ready `gcloud` commands for each role grant.
7. **Play Console: create app** — literal inputs: name="Palateful", default language=English (United States), App/Game=App, Free/Paid=Free, category=Food & Drink, tags=recipes, meal-planning, kitchen.
8. **Play App Signing enrollment** — automatic during first upload.
9. **First manual AAB upload** — `flutter build appbundle --release` locally with the keystore, upload via Play Console UI, wait for Play App Signing enrollment.
10. **Retrieve SHA-256 fingerprint** — Play Console → Setup → App Integrity → App signing key certificate → copy SHA-256.
11. **Commit real SHA-256 into `assetlinks.json`** — paste into `app/web/.well-known/assetlinks.json`, commit + push. Cloudflare Pages deploys on next main-branch push. `deploy-web` smoke confirms `/privacy` and `/.well-known/assetlinks.json` both serve 200.

### Day 3 — Forms + testers + first tag (90 minutes)

12. **Store listing** — paste-ready short (≤80 char) and full (≤4000 char) descriptions (both literal in ANDROID.md). Upload assets from `app/android/play-store-assets/`.
13. **Content Rating (IARC)** — answer key for a 13+ recipe app with alcohol content: literal Y/N answers for each question.
14. **Target Audience + content** — 13+, not child-appealing, ads declared "no ads in v1".
15. **Data Safety form — paste-ready disclosure blocks** (each is a literal text fence, one per SDK):
    - Firebase Crashlytics (crash logs, device ID; collected, not shared; encrypted in transit).
    - Firebase Messaging (installation ID; app functionality).
    - Auth0 (email, name, user ID; collected + shared; encrypted; deletion on request).
    - S3 user-uploaded photos/audio/video (collected + encrypted; deletion on request).
    - Google/Apple Sign-In (email, name, user ID).
    - OpenAI/Anthropic chat (messages, shared with subprocessors for LLM response).
    - Play Billing (financial info, collected via Play; when subscriptions ship — mark "not currently collected").
16. **Sensitive Permissions Declaration** — paste-ready justifications for SCHEDULE_EXACT_ALARM, POST_NOTIFICATIONS, CAMERA, RECORD_AUDIO. Literal text, ~200–400 chars each.
17. **Tester recruitment** — Google Group creation, opt-in URL capture, outreach template (includes feedback channel: GitHub Issues URL + reply-email).
18. **First CI-driven release** — bump pubspec, merge, `git tag v1.0.16 && git push origin v1.0.16`. `mobile-builds.yml` takes over. `::notice::` link posted to workflow summary within ~10 min.

### Post-launch

19. **Post-launch checks** — Pre-Launch Report success criteria explicitly: (a) zero critical crashes, (b) zero app-signing errors, (c) accessibility warnings acceptable, (d) performance warnings acceptable. Anything (a) or (b) holds the release. Crashlytics dashboard, Play Console vitals sanity-check.
20. **Closed test → production promotion** — the 14-day × 12-tester gate, `promote-android.yml` workflow, manual rollout %.

### Troubleshooting

21. **Troubleshooting + disaster recovery** — version code conflict (pubspec drift), signing mismatch, Play App Signing enrollment stuck, **keystore loss recovery** (Play Console upload-key reset path), service-account JSON rotation.

### `app/android/play-store-assets/` — new directory

- `icon-512.png` — 512×512 PNG 32-bit with alpha. Derived from the same source art as the launcher icon foreground.
- `feature-graphic-1024x500.png` — 1024×500 JPEG or 24-bit PNG (no alpha). Shows Palateful logo + tagline + a kitchen scene.
- `screenshots/phone-1.png` through `phone-4.png` — captured from Android emulator (Pixel 7, API 34). Scenes: home screen with recipes, recipe detail with photos, meal calendar, cooking mode with timers.
- `README.md` — 10-line note: "source PSDs live in [Figma link]; these are the Play-Console-ready exports; re-export if brand colors change."

All assets version-controlled so operator can re-upload idempotently from a clean checkout.

## Initial design principles

- **Runbook, not theory.** Every step either (a) runs a command, (b) clicks a URL, or (c) pastes a text block. No "understand the philosophy of..." sections.
- **One file, no tabs.** All the Play Console content blocks (Data Safety paragraphs, permission justifications, description copy) live inline in ANDROID.md. No separate JSON/YAML config that an operator has to hunt for.
- **Acknowledge the 14-day gate.** First production release is ≥14 days from account creation, full stop. ANDROID.md makes this explicit in the "Goal and scope" section so operator expectations are calibrated.
- **Paste-ready > descriptive.** The Data Safety and Sensitive Permissions sections are literal text blocks inside code fences — operator copies, pastes into Play Console, next step.
- **Store assets version-controlled.** No "I exported a PNG from Figma somewhere" problem.
- **No automation we don't need.** First AAB upload is manual; store listing edits are manual in Play Console UI. Automating either has more fragility than value while we're pre-launch.

## File structure (anticipated)

### New
- `ANDROID.md` at repo root.
- `app/android/play-store-assets/icon-512.png`
- `app/android/play-store-assets/feature-graphic-1024x500.png`
- `app/android/play-store-assets/screenshots/phone-1.png`
- `app/android/play-store-assets/screenshots/phone-2.png`
- `app/android/play-store-assets/screenshots/phone-3.png`
- `app/android/play-store-assets/screenshots/phone-4.png`
- `app/android/play-store-assets/README.md`

### Modified
- `CLAUDE.md` — add a one-liner under "Key References" pointing to ANDROID.md for Android release operations.

## Stories

### Story 1: `apl-1` — Draft `ANDROID.md` runbook skeleton

**AC:**
- `ANDROID.md` exists at repo root.
- All 21 sections from the outline above exist with real content (not TBD placeholders), except sections 11 (screenshots paths) and 14 (Data Safety — paste blocks) which reference Stories 2 and 3 respectively.
- Every shell command is in a fenced code block.
- Every external URL is hyperlinked and resolves (visited in-browser at write time).
- Reading top-to-bottom, a developer unfamiliar with Play Console could execute steps 1–11 without context-switching to Google's docs. (Smoke-test: ask a friend unfamiliar with the repo to read through once and flag ambiguity.)
- A short "YOLO acceptance criteria" block at the top matches Q10 of the /dev-plan intake: tag → internal-track AAB reliable; prod is manual later.
- Cross-references: `epic-android-release-hardening`, `epic-android-ci-hardening`, `epic-android-privacy-policy-page` all named with their slugs.
- `CLAUDE.md` updated with a "ANDROID.md — Play Store release runbook" one-liner.

### Story 2: `apl-2` — Produce Play Console store listing assets

**AC:**
- `app/android/play-store-assets/icon-512.png` exists, is 512×512, 32-bit PNG with alpha. Content: Palateful "P" mark on the cream brand background.
- `app/android/play-store-assets/feature-graphic-1024x500.png` exists, is 1024×500, no alpha. Content: logo + tagline ("Your kitchen's recipe memory") + subtle kitchen imagery.
- `app/android/play-store-assets/screenshots/phone-1.png` through `phone-4.png` exist; each is portrait-orientation, at least 1080×1920, captured from an Android emulator (Pixel 7, API 34) using `flutter run --release` + screenshot tool.
- Screenshot scenes (all shipped features):
  - `phone-1.png` — home screen with 6+ recipes visible, bottom nav visible.
  - `phone-2.png` — recipe detail with a photo + ingredient list + steps.
  - `phone-3.png` — meal calendar (week view) with 3–4 meals scheduled.
  - `phone-4.png` — cooking mode with an active timer.
- `app/android/play-store-assets/README.md` documents source file provenance and the re-export procedure.
- ANDROID.md Story 1's Section 11 references these paths exactly.
- Assets committed to git (not gitignored).

### Story 3: `apl-3` — Data Safety paste blocks + permission justifications in ANDROID.md

**AC:**
- ANDROID.md Section 14 contains a discrete text block (code-fenced) for each of 7 data-safety disclosures:
  1. Firebase Crashlytics — crash logs + device ID + IP; Analytics purpose; collected not shared; encrypted in transit; deletion not directly requestable (delete app to stop collection).
  2. Firebase Messaging — installation ID; App functionality; not shared.
  3. Auth0 — email + name + user ID; Account management; collected + shared with Auth0/Okta; encrypted in transit; deletion on request via support email.
  4. S3 user media — photos, audio files, video files; App functionality; collected via Amazon S3; encrypted in transit + at rest; deletion on request.
  5. Google/Apple Sign-In — email + name + user ID; Account management.
  6. OpenAI/Anthropic LLM chat — "Messages — other in-app messages"; App functionality + Personalization; collected + shared with OpenAI and Anthropic; encrypted in transit.
  7. Play Billing (reserved) — Financial info (purchase history); collected via Google Play; not shared; applies only when subscriptions ship.
- ANDROID.md Section 15 contains a code-fenced justification block for each sensitive permission:
  - `SCHEDULE_EXACT_ALARM` — ~400 chars arguing cook-timer UX requires exact firing.
  - `POST_NOTIFICATIONS` — ~200 chars: import completion + meal reminders.
  - `CAMERA` — ~150 chars: photo capture for recipe photos + cookbook scanning.
  - `RECORD_AUDIO` — ~150 chars: voice memos during cooking + voice commands.
- Each block is pre-wrapped so paste-into-Play-Console-textarea lands unmodified.

### Story 4: `apl-4` — Tester recruitment checklist

**AC:**
- ANDROID.md Section 16 documents:
  - Google Group creation (URL, name "palateful-android-testers@googlegroups.com", access public-restricted, post permission "Group members only").
  - Play Console Internal Testing configuration (add group email, capture opt-in URL).
  - Opt-in URL format: `https://play.google.com/apps/internaltest/<package-id>`.
  - Message template for outreach ("Hey — I'm publishing Palateful on Android. Click [opt-in URL] while signed in on your Android phone, install from Play Store, then let me know of anything broken.").
  - Expectation-setting note about the 14-day closed test gate ("Thanks for testing! We need ~12 of you to install and use the app for 2 weeks before Google lets us publish publicly.").
- No automation — this is pure documentation inside ANDROID.md. Story boundary exists for scoping clarity.

## Dependencies

- **Depends on `epic-android-privacy-policy-page`** — Data Safety form + Store Listing require live `/privacy` URL.
- **Depends on `epic-android-release-hardening`** — adaptive icon + notification permission + sensitive-permission cleanup must be in place before first AAB upload.
- **Depends on `epic-android-ci-hardening`** — ANDROID.md Section 17 references `v*.*.*` tag → internal-track flow, which only works after CI hardening lands.
- Does not block anything downstream — this is the terminal epic of the Android launch train.

## Open questions for the user

None — party-mode resolved: tagline "Your kitchen's recipe memory" held as v1 draft (swappable with a post-launch story); 4 screenshots for v1 (AI chat + shopping list deferred to a polish pass); contact email `leonid@ac93.org`; tester group `palateful-android-testers` (Android-specific slug).
