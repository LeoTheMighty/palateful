# Android — Launch Runbook

> **Status (2026-04-18):** Stub. Paste-ready values live below;
> the full keystore/signing/Data Safety/tester-recruitment runbook
> lands under **epic-android-play-console-launch** stories
> `apl-1`–`apl-4`.
>
> This file exists today so the Palateful privacy policy epic
> (`epic-android-privacy-policy-page`) has a concrete cross-reference
> target and the two critical URL/email values have a single source of
> truth. Do **not** delete this file without updating
> `app/web/privacy.html` and the live Play Console fields listed below.

## Play Console Store Listing — paste-ready values

When filling the Play Console **Store Listing** and **Data Safety**
forms, use these exact values. They must match the content of
`app/web/privacy.html` — update both together or fail Play review.

| Play Console field          | Value                                       |
| --------------------------- | ------------------------------------------- |
| **Privacy Policy URL**      | `https://palateful.app/privacy`             |
| **Developer contact email** | `leonid@ac93.org`                           |

### Where these values must also be consistent

- `app/web/privacy.html` — the page itself at the URL above. The
  `mailto:` links must use the same contact email. Check with
  `grep -F leonid@ac93.org app/web/privacy.html` (expect 4+ matches).
- Play Console **Store Listing** → Privacy Policy URL field (pasted
  manually during apl-1 / apl-3).
- Play Console **Data Safety** form → the "Privacy policy" link field
  at the top of the form (same URL, same email in the developer
  contact block).
- iOS App Store Connect → App Privacy section (parallel field; same
  URL).

Changing the URL or email in any one of these places requires
simultaneous updates to all the others. Run
`grep -rF 'leonid@ac93.org' ANDROID.md app/web/privacy.html` as a
quick consistency check before shipping a change.

## Ownership

| Story                 | Owns                                                |
| --------------------- | --------------------------------------------------- |
| `app-1`               | `app/web/privacy.html` content + `_redirects`       |
| `app-2` (this file)   | The two paste-ready values above                    |
| `apl-1`               | Keystore generation + GitHub Secrets runbook        |
| `apl-2`               | Play Console store-listing graphics (icon / screens)|
| `apl-3`               | Data Safety paste blocks + permission justifications|
| `apl-4`               | Internal / closed-testing recruitment checklist     |

The `apl-*` stories will expand this file in place — keep the top
preamble and the paste-ready table; append everything else below.

---

## YOLO acceptance

> **Tag → internal-track AAB is reliable; production promotion is
> manual via Play Console after the 14-day × 12-tester closed-test
> gate clears.** This runbook is considered "shipped" once the first
> `v*.*.*` tag push lands an AAB on the internal track and at least
> one opted-in tester has the app installed on their Android phone.
>
> The first production release will be at minimum ~14 days after the
> first internal-track release, and requires ≥12 testers to have
> installed + used the closed-test build for at least 14 days. This
> is a Google requirement for new developer accounts. Plan
> accordingly.

---

# Day 1 — Signup (20 minutes active + 2–3 day verification wait)

## Section 1 — Goal and scope

This runbook covers the Palateful Play Store publishing flow end to
end: keystore generation → GitHub Secrets → Google Cloud service
account → Google Play Developer account → Play Console app creation
→ Play App Signing → first manual AAB upload → App Links SHA-256
handoff → Store Listing → Content Rating → Target Audience → Data
Safety → Sensitive Permissions → Internal tester recruitment →
first CI-driven tag. What it does **not** cover:

- In-app features or bug triage (see `BUGS.md` / individual epics).
- iOS release (separate flow; App Store Connect + Xcode Cloud).
- Day-to-day Play Console operations post-launch (staged rollouts,
  review response) — covered briefly in Section 20 only.

**Read this top-to-bottom once before starting.** The 2–3 day
identity-verification wait in Section 3 is out of your hands — if
you do Day 1 on a Thursday evening, Day 2 realistically starts
Monday morning at the earliest.

## Section 2 — Prerequisites

Before opening [https://play.google.com/console/signup](https://play.google.com/console/signup):

1. Repo checked out at `~/personal/palateful` (or equivalent). All
   shell commands below assume this working directory unless
   otherwise noted.
2. 1Password (or your vault of choice) access, with the ability to
   create new entries in a shared vault.
3. Government photo ID — passport or driver's license. Google Play
   requires gov-issued to verify developer identity.
4. Payment method with $25 available. One-time fee, non-refundable.
5. A Google account that will own the Play Console. A dedicated
   account is recommended — account recovery via this email matters
   long-term. Do not use the Google account of a shared company
   login that might be rotated.
6. Private repo (or access to one) you can paste GitHub Secrets into
   via GitHub → Settings → Secrets and variables → Actions.

## Section 3 — Google Play Developer account signup

1. Visit [https://play.google.com/console/signup](https://play.google.com/console/signup).
2. Choose **Personal** (not Organization — simpler; switchable later
   for a nominal fee if the app takes off).
3. Display name: `Palateful` (literal — matches package name
   convention + what stores show to end users).
4. Contact email: `leonid@ac93.org`. Must match the email in
   `app/web/privacy.html` + the Store Listing field (Section 13).
   See the consistency table at the top of this file.
5. Pay $25. Upload gov-ID photo. Submit.
6. **Wait 2–3 business days** for Google to verify. You receive an
   email when the account is active.
7. Do not proceed to Day 2 until the verification email arrives.

---

# Day 2 — Credentials + first AAB (75 minutes)

## Section 4 — Upload keystore generation

Run from `app/android/` so the keystore lands where the existing
Flutter `.gitignore` already covers `*.jks` + `key.properties`:

```bash
cd ~/personal/palateful/app/android
keytool -genkeypair -v \
  -keystore palateful-upload.jks \
  -alias upload \
  -keyalg RSA -keysize 2048 \
  -validity 9125 \
  -storepass '<STRONG_STORE_PASSWORD>' \
  -keypass  '<STRONG_KEY_PASSWORD>' \
  -dname 'CN=Palateful, O=Palateful, L=<CITY>, C=US'
```

Notes:

- `9125` validity = 25 years. Must exceed Play App Signing expiry.
- Store both passwords + alias in 1Password under
  `Palateful / Android Upload Keystore`.
- `palateful-upload.jks` must **never** be committed. `app/android/.gitignore`
  has `**/*.jks`, `**/*.keystore`, and `key.properties` — sanity-check
  with:

  ```bash
  git check-ignore -v app/android/palateful-upload.jks
  ```

  Expect output pointing at the `app/android/.gitignore` rule. If you
  generate the keystore anywhere else in the repo, confirm the same
  check returns "yes" before running any `git add`.

- Immediately after generation, base64-encode a disaster-recovery
  copy into 1Password:

  ```bash
  base64 -i app/android/palateful-upload.jks | tr -d '\n' | pbcopy
  ```

  Paste into 1Password as a secure note
  `palateful-upload.jks (base64)`. **This copy is not optional** —
  even though Play App Signing makes upload-key loss recoverable
  (Section 21), the 2–3 day Google reset path is worth avoiding.

## Section 5 — GitHub Secrets population

GitHub → repo → Settings → Secrets and variables → Actions →
New repository secret. Paste the raw value (no quotes, no trailing
newline).

| Secret                          | Value source                                                                                     |
| ------------------------------- | ------------------------------------------------------------------------------------------------ |
| `ANDROID_KEYSTORE_BASE64`       | Output of `base64 -i palateful-upload.jks \| tr -d '\n'` from Section 4                          |
| `ANDROID_STORE_PASSWORD`        | The `-storepass` used in Section 4                                                               |
| `ANDROID_KEY_ALIAS`             | Literal `upload` (matches Section 4 `-alias`)                                                    |
| `ANDROID_KEY_PASSWORD`          | The `-keypass` used in Section 4                                                                 |
| `PLAY_STORE_JSON_KEY`           | Service-account JSON from Section 6                                                              |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Same JSON as `PLAY_STORE_JSON_KEY` (one GCP SA, three roles — locked decision)                   |

Cross-reference: `.github/workflows/mobile-builds.yml` consumes
`ANDROID_KEYSTORE_BASE64`, `ANDROID_STORE_PASSWORD`,
`ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, and
`PLAY_STORE_JSON_KEY` today. `FIREBASE_SERVICE_ACCOUNT_JSON` is
consumed by the Crashlytics native-symbol upload step wired under
`ach-3` (epic-android-ci-hardening).

## Section 6 — Single GCP service account for CI

One service account holds three roles: Play Store release-manager,
Firebase Crashlytics upload, Firebase Test Lab access. This is the
**locked cross-epic decision** — one JSON, one rotation surface.

1. Open [https://console.cloud.google.com](https://console.cloud.google.com).
2. Create project `palateful-prod` (or select it if it already
   exists from Cloudflare/Terraform setup).
3. IAM & Admin → Service Accounts → Create service account.
   - Name: `palateful-ci`
   - ID: `palateful-ci` (auto-generated from name)
   - Description: `CI: Play Store upload + Firebase Crashlytics + Test Lab`
4. Grant the four roles below. Run each `gcloud` command with the
   project set to `palateful-prod`:

   ```bash
   PROJECT=palateful-prod
   SA=palateful-ci@${PROJECT}.iam.gserviceaccount.com

   # Android Publisher (Play Store upload)
   gcloud projects add-iam-policy-binding "$PROJECT" \
     --member="serviceAccount:$SA" \
     --role="roles/androidpublisher.user"

   # Firebase Crashlytics (mapping + native symbol upload via Gradle plugin)
   gcloud projects add-iam-policy-binding "$PROJECT" \
     --member="serviceAccount:$SA" \
     --role="roles/firebase.crashlytics.access"

   # Firebase Test Lab (Robo crawl in CI)
   gcloud projects add-iam-policy-binding "$PROJECT" \
     --member="serviceAccount:$SA" \
     --role="roles/firebase.testlab.access"

   # Cloud Trace agent — optional, for debugging CI-side API calls
   gcloud projects add-iam-policy-binding "$PROJECT" \
     --member="serviceAccount:$SA" \
     --role="roles/cloudtrace.agent"
   ```

5. Keys tab → Add Key → JSON → download. File lands in
   `~/Downloads/palateful-ci-<timestamp>.json`.
6. **Immediately**:
   - Base64-encode + paste into 1Password as secure note
     `palateful-ci service-account JSON`.
   - Paste the raw JSON content into both GitHub Secrets
     (`PLAY_STORE_JSON_KEY` + `FIREBASE_SERVICE_ACCOUNT_JSON`).
   - Delete the local `~/Downloads/…` file. Do not leave the JSON
     on disk.

## Section 7 — Link service account to Play Console

Prerequisite: Developer account is verified (Section 3) + the
service account exists (Section 6). Then:

1. Play Console → Setup → API access.
2. Accept the Google Cloud project link prompt (one-time pairing).
3. Find `palateful-ci@palateful-prod.iam.gserviceaccount.com` in the
   service-accounts list.
4. Grant access. Role: **Release manager**.
5. App permissions: check "All apps in your account" (simpler for a
   single-app Play Console account).
6. Invite → Accept.

## Section 8 — Create Play Console app

1. Play Console home → **Create app**.
2. Fill the creation form with these literals:
   - **App name:** `Palateful`
   - **Default language:** `English (United States)`
   - **App or game:** `App`
   - **Free or paid:** `Free`
3. Declarations: agree to developer program policy + US export laws.
4. Click **Create app**.

Once the app exists, fill the top-bar fields (they become locked
after first upload but can be edited until then):

- **App category:** `Food & Drink`
- **Tags** (up to 5): `recipes`, `meal planning`, `kitchen`,
  `cooking`, `grocery list`
- **Contact details:** email `leonid@ac93.org`. Phone optional —
  leave blank for v1.
- **Privacy Policy URL:** `https://palateful.app/privacy`

## Section 9 — Play App Signing enrollment

Automatic on first upload. No manual step required — just confirm
during Section 10 that the Play Console upload UI shows "Play App
Signing" as the signing method. If asked whether to use the legacy
unrestricted signing flow, choose **Play App Signing** (the default
for new apps since 2021).

## Section 10 — First manual AAB upload

Fastlane cannot create a new Play Console app — the first upload
must go through the Play Console web UI. After Sections 4–9 are
complete:

```bash
cd ~/personal/palateful/app

# Write keystore paths for Gradle's signingConfigs.release block.
# Values come from 1Password — do NOT paste them into shell history.
# (app/android/.gitignore covers key.properties — safe to keep
# locally during the build, but delete after.)
cat > android/key.properties <<'EOF'
storePassword=<ANDROID_STORE_PASSWORD from 1Password>
keyPassword=<ANDROID_KEY_PASSWORD from 1Password>
keyAlias=upload
storeFile=/Users/<you>/personal/palateful/app/android/palateful-upload.jks
EOF

flutter build appbundle --release
```

Output: `app/build/app/outputs/bundle/release/app-release.aab`.

Upload via Play Console:

1. Play Console → Testing → Internal testing → **Create new release**.
2. App bundles → Upload → pick `app-release.aab`.
3. Release name: auto-generated from version code (e.g., `1.0.17 (30)`).
4. Release notes (English US):

   ```
   Initial internal-track release. Tester-only preview — please
   report anything broken to leonid@ac93.org or file a GitHub issue
   at https://github.com/<your-user>/palateful/issues.
   ```

5. Save. **Do not click "Review release" yet** — the Data Safety
   form (Section 15) has to be filled first, or Play review will
   block the rollout.

Immediately after save — delete the keystore passwords file. They
live in 1Password + GitHub Secrets; no need on disk:

```bash
rm app/android/key.properties
```

## Section 11 — Retrieve SHA-256 fingerprint

Play Console → Setup → App integrity → **App signing key certificate**
→ copy the `SHA-256 certificate fingerprint`.

Format: `AA:BB:CC:DD:…:11:22` (95 characters including 31 colons).
This is **not** the same as the upload certificate fingerprint — use
the **App signing** one, not the upload one.

## Section 12 — Commit real SHA-256 into `assetlinks.json`

The placeholder fingerprint committed by `arh-4`
(`epic-android-release-hardening`) lives in
`app/web/.well-known/assetlinks.json`. Replace it with the real
value from Section 11:

```bash
cd ~/personal/palateful
$EDITOR app/web/.well-known/assetlinks.json
# Replace the sha256_cert_fingerprints array entry with the literal
# fingerprint copied from Play Console (keep the colons; upper case is fine).

git add app/web/.well-known/assetlinks.json
git commit -m "chore(app): apl-1 — commit real Play App Signing SHA-256"
git push origin main
```

The `deploy-web` job in `.github/workflows/ci.yml` rebuilds + ships
everything under `app/web/` (including `.well-known/`) on the next
main-branch push. Its built-in smoke step verifies `/privacy` returns
200 (owned by `app-3`) but does **not** check `/.well-known/assetlinks.json`
— do the check yourself once CI is green:

```bash
curl -sI https://palateful.app/.well-known/assetlinks.json | head -1
curl -s  https://palateful.app/.well-known/assetlinks.json | jq .
```

Expect `HTTP/2 200` and a JSON array containing `com.palateful.palateful`
+ the just-committed SHA-256.

Until this commit ships, Android App Links **do not auto-verify** and
`https://palateful.app/recipes/...` links fall back to the browser
chooser. Acceptable for internal-track v1; must be fixed before
public launch.

---

# Day 3 — Forms + testers + first tag (90 minutes)

## Section 13 — Store listing

Play Console → Store presence → Main store listing. Paste-ready
values:

- **App name:** `Palateful`
- **Short description** (≤ 80 chars):

  ```
  Your kitchen's recipe memory — save, plan, cook, and share.
  ```

- **Full description** (≤ 4000 chars):

  ```
  Palateful is a kitchen app that remembers your recipes, plans
  your meals, and shops for your ingredients — so you can focus on
  the cooking.

  • Save recipes from the web, your camera roll, or paste them
    in. Palateful extracts ingredients and steps automatically.
  • Organize into personal and shared recipe books. Household
    members stay in sync in real time.
  • Plan meals on a calendar. Aggregate a shopping list from a
    week of meals in one tap.
  • Cooking mode: large-text steps, concurrent timers, voice
    input when your hands are busy.
  • AI assistant that searches your library by vibe ("something
    warm for a rainy night") and adds notes to recipes hands-free.

  Palateful is designed for the household, not just the
  individual. Forked recipes keep lineage. Shared shopping lists
  update live. Meal plans sync across devices.

  Contact: leonid@ac93.org
  Privacy: https://palateful.app/privacy
  ```

Asset uploads (paths relative to repo root — produced by `apl-2`):

- **App icon (512×512):** `app/android/play-store-assets/icon-512.png`
- **Feature graphic (1024×500):** `app/android/play-store-assets/feature-graphic-1024x500.png`
- **Phone screenshots** (portrait, ≥ 1080×1920, 2–8 required):
  - `app/android/play-store-assets/screenshots/phone-1.png` — home + recipes
  - `app/android/play-store-assets/screenshots/phone-2.png` — recipe detail
  - `app/android/play-store-assets/screenshots/phone-3.png` — meal calendar
  - `app/android/play-store-assets/screenshots/phone-4.png` — cooking mode + timer

Assets are version-controlled so re-upload from a clean checkout is
idempotent — no "where did I put that PNG" hunt.

## Section 14 — Content Rating (IARC)

Play Console → Store presence → Content rating → **Start
questionnaire**.

- **Category:** `Reference, News, or Educational` (Food & Drink
  falls under this IARC top-level — not "Game").
- **Email:** `leonid@ac93.org`.
- **Answer key** (reviewed against the shipped feature set
  2026-04-18):

| Question                                                      | Answer                                                                                                  |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Violence — cartoon / fantasy / realistic                      | **No**                                                                                                  |
| Sexual content                                                | **No**                                                                                                  |
| Crude humor                                                   | **No**                                                                                                  |
| Drug, alcohol, or tobacco reference                           | **Yes** — recipes may include alcoholic ingredients (wine, beer, spirits used in cooking)               |
| Simulated gambling                                            | **No**                                                                                                  |
| User-generated content shared between users                   | **Yes** — household members share recipes and notes                                                     |
| Unrestricted internet access (i.e. web browser)               | **No** — app communicates with a fixed Palateful backend + sign-in providers + subprocessors (Auth0, S3, Firebase, OpenAI, Anthropic) |
| Location sharing                                              | **No**                                                                                                  |
| Digital purchases                                             | **No** (v1 — change to **Yes** when Play Billing ships)                                                 |

**Expected rating:** Teen (13+) in ESRB / IARC 12+ in most regions,
due to the alcohol ingredient reference.

## Section 15 — Data Safety form

*Content below is owned by `apl-3` — paste-ready disclosure blocks
for Firebase Crashlytics, Firebase Messaging, Auth0, S3 user media,
Google/Apple Sign-In, OpenAI/Anthropic LLM chat, and reserved Play
Billing. Each block is code-fenced and sized to paste verbatim into
the Play Console text areas.*

*(apl-3 content appends here — placeholder until that story lands.)*

## Section 16 — Sensitive Permissions Declaration

*Content below is owned by `apl-3` — paste-ready justification
blocks for `SCHEDULE_EXACT_ALARM`, `POST_NOTIFICATIONS`, `CAMERA`,
and `RECORD_AUDIO`. Each block is sized for the Play Console
sensitive-permission justification textarea.*

*(apl-3 content appends here — placeholder until that story lands.)*

## Section 17 — Tester recruitment

*Content below is owned by `apl-4` — Google Group creation, Play
Console internal-testing wiring, opt-in URL format + capture,
outreach email template with GitHub Issues feedback link, and
14-day gate expectation-setting.*

*(apl-4 content appends here — placeholder until that story lands.)*

## Section 18 — First CI-driven release (tag → internal track)

Pre-flight — make sure `main` is green and the pubspec version is
bumped:

1. `git pull origin main` — ensure you're on the latest.
2. Edit `app/pubspec.yaml`: `version: 1.0.<NEW>+<NEW>`. Both numbers
   **must** advance (Play Store requires a strictly increasing
   version code, i.e. the `+<build>` integer).
3. From `app/`: run `flutter test` — green.
4. Commit + push:

   ```bash
   git commit -am "chore(app): bump to 1.0.<NEW> for tag"
   git push origin main
   ```

5. Wait for `.github/workflows/ci.yml` to finish green on main.

Tag:

```bash
git tag v1.0.<NEW>
git push origin v1.0.<NEW>
```

This triggers `.github/workflows/mobile-builds.yml` → `android-build`
job. Within ~10 minutes the signed AAB lands on Play Console
internal track. A `::notice::` annotation on the workflow summary
page links back to the Play Console build listing (wired by
`ach-1`, `epic-android-ci-hardening`).

Watch the workflow for:

- `flutter analyze` or `flutter test` failure → fix on main before
  re-tagging. The tag must point at a green commit.
- Play upload failure due to duplicate version code → the build
  number didn't advance. Bump pubspec, commit, re-tag with a new
  `v*.*.*`.
- Crashlytics symbol upload failure → `FIREBASE_SERVICE_ACCOUNT_JSON`
  secret is missing or scoped without `firebase.crashlytics.access`.

## Section 19 — Verify Pre-Launch Report

Play Console → Testing → Pre-launch report. The first report lands
~30 min after the AAB is fully processed (not just uploaded).

**Pre-Launch Report success criteria** — so the first few reports
don't trigger unnecessary alarm:

1. **Zero critical crashes** — required. Any crash in this category
   holds the release until the root cause is fixed.
2. **Zero app-signing errors** — required. Any signing error means
   the keystore diverged somewhere; see Section 21 Troubleshooting.
3. **Accessibility warnings** — acceptable for v1. Address in a
   later polish story.
4. **Performance warnings** — acceptable for v1. Track in a
   post-launch polish epic if any recur.

Only (1) and (2) block the release.

---

# Post-launch

## Section 20 — Closed test → production promotion

The 14-day × 12-tester gate is a hard Google requirement for new
developer accounts' first production release. Don't plan an earlier
production launch — the tester metrics have to accrue first.

To promote an existing internal-track AAB to closed or production
(no rebuild):

1. GitHub → Actions → **Promote Android** workflow
   (`.github/workflows/promote-android.yml`, owned by `ach-5`).
2. Run workflow → pick `source_track: internal`,
   `target_track: closed` (or `production` after 14-day gate).
3. If promoting to production, GitHub prompts for `production`
   environment approval (same pattern `ci.yml` uses for prod
   infrastructure).
4. The Fastlane `android promote` lane calls
   `upload_to_play_store(track: "internal", track_promote_to: "...")`
   — moves the existing AAB by version code, does not rebuild.
5. Play Console shows the AAB on the target track within ~5 min.

**Rollout percentage** — set manually in Play Console UI for
production. Staged rollout UI is Play's strength; duplicating it in
CI adds fragility with no upside.

---

# Troubleshooting

## Section 21 — Troubleshooting + disaster recovery

- **"Upload failed: duplicate version code."** Bump the build
  number in `app/pubspec.yaml` (`+30` → `+31`), commit, re-tag.

- **"Certificate fingerprint doesn't match."** The local keystore
  and the one in `ANDROID_KEYSTORE_BASE64` diverged. Re-export:

  ```bash
  base64 -i palateful-upload.jks | tr -d '\n' | pbcopy
  ```

  Re-paste into the GitHub Secret.

- **Play App Signing enrollment stuck at "Pending."** Usually a
  5–15 minute delay after first upload. If > 1 hour, contact Play
  support via Console → Help → Contact us.

- **Service-account JSON rotation.** GCP → IAM → Service Accounts
  → `palateful-ci` → Keys → Add new → JSON. Paste into both GitHub
  Secrets (`PLAY_STORE_JSON_KEY` + `FIREBASE_SERVICE_ACCOUNT_JSON`).
  Then delete the old key in the Keys tab. Rotate at least annually,
  or whenever someone with 1Password access leaves the project.

- **Upload keystore lost.** Because we use Play App Signing, this is
  **recoverable** — losing the upload key is inconvenient, not
  fatal:

  1. Play Console → Setup → App Integrity → **Request upload key
     reset**.
  2. Google re-issues the upload key. Takes 2–3 business days.
  3. Generate a new keystore (repeat Section 4). Update all GitHub
     Secrets (Section 5). Re-upload the base64 to 1Password.
  4. Next release uses the new upload key; Play re-signs it under
     the same app-signing key transparently for users. Existing
     installs keep updating without a "reinstall" prompt.

  **Prevention:** 1Password has both the keystore passwords and the
  base64-encoded keystore file. An offline encrypted copy (e.g., an
  external drive) is a belt-and-suspenders extra layer —
  recommended but not strictly required given the Play-managed
  reset path.

---

# Cross-epic references

- **`epic-android-privacy-policy-page`** — owns `https://palateful.app/privacy`
  + the `_redirects` rule that makes the URL resolve.
- **`epic-android-release-hardening`** — owns the adaptive icon
  (via `flutter_launcher_icons`), `POST_NOTIFICATIONS` manifest
  entry + runtime prompt + FCM channel, the `assetlinks.json`
  placeholder file this runbook replaces in Section 12, and the
  Crashlytics native-symbol Gradle config (`mappingFileUploadEnabled`
  + `nativeSymbolUploadEnabled`).
- **`epic-android-ci-hardening`** — owns `mobile-builds.yml`
  Flutter pinning + Gradle cache + analyze/test gate + Crashlytics
  native-symbol upload + Firebase Test Lab soft-smoke +
  `promote-android.yml` workflow + the `::notice::` build-link
  annotation.
- **`apl-2`** — owns `app/android/play-store-assets/` graphics
  (512×512 icon, 1024×500 feature graphic, 4 phone screenshots).
- **`apl-3`** — owns Section 15 (Data Safety paste blocks) + Section
  16 (Sensitive Permissions justifications) content.
- **`apl-4`** — owns Section 17 (tester recruitment checklist).
