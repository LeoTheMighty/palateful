# Story apl-1: Draft ANDROID.md runbook skeleton

**Status:** ready-for-dev
**Epic:** epic-android-play-console-launch

## Goal

Expand the existing `ANDROID.md` stub at repo root (committed under `app-2`)
into a complete single-operator runbook covering every manual step between
"never opened Play Console" and "first internal-track AAB available to a
tester's Android phone." Structure: **Day 1 (signup, ~20 min + 2–3 day
verification wait)**, **Day 2 (credentials + first AAB, ~75 min)**, **Day 3
(forms + testers + first tag, ~90 min)**, plus post-launch checks and
troubleshooting. Every shell command is in a fenced code block; every
Play Console form value decided today is a literal in the fence (not a
`<FILL>`). Only two genuine `<FILL>`s: the Play App Signing SHA-256
(post-first-upload) and the current pubspec version for each tag push.

Data Safety paste blocks (Section 15) and sensitive-permission
justifications (Section 16) are owned by `apl-3` and appended under this
story's skeleton. Screenshot paths in Section 12 reference asset files
produced by `apl-2`.

## Scope (from epic)

- `ANDROID.md` at repo root — append to the existing stub, preserve the
  top preamble + paste-ready value table.
- `CLAUDE.md` — add one line under "Key References" pointing to
  ANDROID.md as the Play Store release runbook.
- No code changes, no backend changes, no Flutter changes.

## Implementation

### Preserve the existing stub header

The existing `ANDROID.md` (committed under `app-2`) has:
- A status note at the top.
- A "Play Console Store Listing — paste-ready values" table (Privacy
  Policy URL + Developer contact email).
- A "Where these values must also be consistent" list.
- An "Ownership" table mapping `app-*` + `apl-*` stories to sections.

Keep all of this as-is. Expand **below** it with the Day 1 / Day 2 /
Day 3 structure. The existing stub already says "The `apl-*` stories
will expand this file in place — keep the top preamble and the
paste-ready table; append everything else below."

### Add: YOLO acceptance criteria block

Right below the existing stub, a fenced block restating the epic's
locked decision:

> **YOLO acceptance:** tag → internal-track AAB reliable; production
> promotion is manual via Play Console after the 14-day × 12-tester
> gate clears. This runbook is considered "shipped" once the first
> `v*.*.*` tag push lands an AAB on the internal track and at least one
> opted-in tester has the app installed.

### Day 1 — Signup (20 min active + 2–3 day verification wait)

**Section 1 — Goal and scope.** One paragraph: what this runbook
covers (Play Store publishing flow, first internal-track build),
what it doesn't (in-app features, iOS — see `iOS-RELEASE.md` or
similar). Calls out the 14-day × 12-tester gate explicitly so the
operator doesn't plan a same-day production launch.

**Section 2 — Prerequisites.** Numbered checklist:
1. Repo checked out at `/Users/<you>/personal/palateful` (or equivalent).
2. 1Password access + ability to create new vault entries.
3. Government photo ID (passport or driver's license — Play requires
   gov-issued to verify identity).
4. A payment method with $25 available (one-time Play Console fee).
5. A Google account that will own the Play Console. Use a dedicated
   account if possible — account recovery via this email matters.

**Section 3 — Google Play Developer account signup.** Numbered with
the exact click path:
1. Visit [https://play.google.com/console/signup](https://play.google.com/console/signup).
2. Choose **Personal** (not Organization — simpler; switchable later
   for a nominal fee).
3. Display name: `Palateful` (literal — matches package name convention
   + what stores show).
4. Contact email: `leonid@ac93.org`.
5. Pay $25. Upload gov ID photo. Submit.
6. Wait 2–3 business days for Google to verify. You will get an email
   when the account is active. **Stop here until that email arrives.**

Cross-reference: the contact email is the same as the one surfaced in
`app/web/privacy.html` (owned by `app-1`). Consistency enforced by the
table at the top of this file.

### Day 2 — Credentials + first AAB (75 min)

**Section 4 — Upload keystore generation.** Fenced `keytool` command
with literal paths:

```bash
cd ~/personal/palateful
keytool -genkeypair -v \
  -keystore palateful-upload.jks \
  -alias upload \
  -keyalg RSA -keysize 2048 \
  -validity 9125 \
  -storepass '<STRONG_STORE_PASSWORD>' \
  -keypass  '<STRONG_KEY_PASSWORD>' \
  -dname 'CN=Palateful, O=Palateful, L=<CITY>, C=US'
```

Notes (each under its own sub-bullet):
- `9125` validity = 25 years. Must exceed Play App Signing expiry.
- Store both passwords + alias in 1Password under
  `Palateful / Android Upload Keystore`.
- `palateful-upload.jks` is in `.gitignore`. Do **not** commit it.
- Immediately after generation:
  `base64 -i palateful-upload.jks | tr -d '\n' | pbcopy` — paste
  into 1Password as a secure note `palateful-upload.jks (base64)` as
  a disaster-recovery copy.

**Section 5 — GitHub Secrets population.** Numbered list, one entry
per secret name, with the exact value source:

| Secret | Value source |
| ------ | ------------ |
| `ANDROID_KEYSTORE_BASE64` | Output of `base64 -i palateful-upload.jks \| tr -d '\n'` from Section 4 |
| `ANDROID_STORE_PASSWORD` | The `-storepass` used in Section 4 |
| `ANDROID_KEY_ALIAS` | Literal `upload` (matches Section 4 `-alias`) |
| `ANDROID_KEY_PASSWORD` | The `-keypass` used in Section 4 |
| `PLAY_STORE_JSON_KEY` | Service-account JSON from Section 6 (below) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Same JSON as `PLAY_STORE_JSON_KEY` (one GCP SA, multiple roles) |

Click path: GitHub → repo → Settings → Secrets and variables → Actions
→ New repository secret. Paste the raw value. **Do not add quotes.**

Cross-reference: `mobile-builds.yml` already consumes
`ANDROID_KEYSTORE_BASE64`, `ANDROID_STORE_PASSWORD`,
`ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, `PLAY_STORE_JSON_KEY`.
`FIREBASE_SERVICE_ACCOUNT_JSON` is consumed by the Crashlytics native
symbol upload step wired under `ach-3` (epic-android-ci-hardening).

**Section 6 — Single GCP service account for CI.** The same JSON holds
Play Console release-manager + Firebase Crashlytics upload + Firebase
Test Lab roles (locked cross-epic decision: one JSON, one rotation
surface). Numbered:

1. Open [https://console.cloud.google.com](https://console.cloud.google.com).
2. Create project `palateful-prod` (or select if it exists from
   Cloudflare/other setup).
3. IAM & Admin → Service Accounts → Create service account.
   - Name: `palateful-ci`
   - ID: `palateful-ci` (auto)
   - Description: `CI: Play Store upload + Firebase Crashlytics + Test Lab`
4. Grant these roles (one gcloud command per role; project set to
   `palateful-prod`):

   ```bash
   PROJECT=palateful-prod
   SA=palateful-ci@${PROJECT}.iam.gserviceaccount.com

   # Android Publisher (Play Store upload)
   gcloud projects add-iam-policy-binding "$PROJECT" \
     --member="serviceAccount:$SA" \
     --role="roles/androidpublisher.user"

   # Firebase Crashlytics (symbol upload via Gradle plugin)
   gcloud projects add-iam-policy-binding "$PROJECT" \
     --member="serviceAccount:$SA" \
     --role="roles/firebase.crashlytics.access"

   # Firebase Test Lab (Robo crawl in CI)
   gcloud projects add-iam-policy-binding "$PROJECT" \
     --member="serviceAccount:$SA" \
     --role="roles/firebase.testlab.access"

   # Cloud Trace agent (optional: debug CI traces)
   gcloud projects add-iam-policy-binding "$PROJECT" \
     --member="serviceAccount:$SA" \
     --role="roles/cloudtrace.agent"
   ```

5. Keys tab → Add Key → JSON → download. Save as
   `~/Downloads/palateful-ci-<timestamp>.json`.
6. **Immediately** base64-encode into 1Password as disaster-recovery,
   then paste the raw JSON into GitHub Secret `PLAY_STORE_JSON_KEY`
   AND `FIREBASE_SERVICE_ACCOUNT_JSON`. Delete the local file.

**Section 7 — Link service account to Play Console.** After the
Developer account is verified (Section 3) and the service account
exists (Section 6):
1. Play Console → Setup → API access.
2. Accept the Google Cloud project link prompt (one-time).
3. Find `palateful-ci@palateful-prod.iam.gserviceaccount.com`.
4. Grant access. Role: **Release manager**.
5. App permissions: check "All apps in your account" (simpler for a
   single-app account).
6. Invite → Accept.

**Section 8 — Create Play Console app.**
1. Play Console home → **Create app**.
2. App name: `Palateful`
3. Default language: `English (United States)`
4. App or game: `App`
5. Free or paid: `Free`
6. Declarations: agree to content policy + US export laws.
7. → Create app.

Once the app exists, fill the top-bar fields (they become locked
after first upload but can be edited earlier):
- App category: `Food & Drink`
- Tags (up to 5): `recipes`, `meal planning`, `kitchen`, `cooking`,
  `grocery list`
- Contact details: email `leonid@ac93.org`, phone optional.
- Privacy Policy URL: `https://palateful.app/privacy`

**Section 9 — Play App Signing enrollment.** Automatic on first
upload. No manual step — just confirm during Section 10 that "Play
App Signing" is shown as enrolled. If the upload UI asks whether to
use the legacy unrestricted signing flow, choose **Play App
Signing** (the default).

**Section 10 — First manual AAB upload.** Fastlane cannot create a
new Play Console app (the first upload has to go through the Play
Console web UI). After Sections 4–9:

```bash
cd ~/personal/palateful/app

# Inject keystore paths for Gradle signingConfigs.release
cat > android/key.properties <<EOF
storePassword=<ANDROID_STORE_PASSWORD from 1Password>
keyPassword=<ANDROID_KEY_PASSWORD from 1Password>
keyAlias=upload
storeFile=/absolute/path/to/palateful-upload.jks
EOF

flutter build appbundle --release
```

Output: `app/build/app/outputs/bundle/release/app-release.aab`.

Upload via Play Console:
1. Play Console → Testing → Internal testing → Create new release.
2. App bundles → Upload → pick `app-release.aab`.
3. Release name: auto-generated from version code (e.g., `1.0.17 (30)`).
4. Release notes (English US):
   ```
   Initial internal-track release. Tester-only preview — please report
   anything broken to leonid@ac93.org or file a GitHub issue.
   ```
5. Save. Do **not** click "Review release" yet — the Data Safety form
   (Section 15) has to be filled first, else review blocks.

Immediately after save: delete `app/android/key.properties` (do not
commit).

```bash
rm app/android/key.properties
```

**Section 11 — Retrieve SHA-256 fingerprint.** Play Console →
Setup → App integrity → **App signing key certificate** → copy the
`SHA-256 certificate fingerprint` (format:
`AA:BB:CC:...:11:22` — 95 chars incl. colons).

**Section 12 — Commit real SHA-256 into `assetlinks.json`.** The
placeholder fingerprint in `app/web/.well-known/assetlinks.json`
(owned by `arh-4`) is `AA:AA:AA:...` or similar. Replace with the
real value from Section 11:

```bash
cd ~/personal/palateful
# Open app/web/.well-known/assetlinks.json in editor, replace the
# sha256_cert_fingerprints entry with the real fingerprint.
git add app/web/.well-known/assetlinks.json
git commit -m "chore(app): apl-1 — commit real Play App Signing SHA-256 into assetlinks.json"
git push origin main
```

`deploy-web` workflow ships the updated file on the next main-branch
push; the `deploy-web` smoke step (owned by `app-3`) already confirms
`/.well-known/assetlinks.json` returns 200.

Verification (run after Cloudflare Pages finishes deploying):

```bash
curl -sI https://palateful.app/.well-known/assetlinks.json | head -1
curl -s  https://palateful.app/.well-known/assetlinks.json | jq .
```

Expect `HTTP/2 200` and a valid JSON array with your package name +
the just-committed SHA-256.

### Day 3 — Forms + testers + first tag (90 min)

**Section 13 — Store listing.** Fill in Play Console → Store presence
→ Main store listing. Literal paste-ready values:

- **App name:** `Palateful`
- **Short description** (≤ 80 chars):
  ```
  Your kitchen's recipe memory — save, plan, cook, and share.
  ```
- **Full description** (≤ 4000 chars):
  ```
  Palateful is a kitchen app that remembers your recipes, plans your
  meals, and shops for your ingredients — so you can focus on the
  cooking.

  • Save recipes from the web, your camera roll, or paste them in —
    Palateful extracts ingredients and steps automatically.
  • Organize into personal and shared recipe books. Household
    members stay in sync in real time.
  • Plan meals on a calendar. Aggregate a shopping list from a week
    of meals in one tap.
  • Cooking mode: large-text steps, concurrent timers, voice input
    when your hands are busy.
  • AI assistant that searches your library by vibe ("something
    warm for a rainy night") and adds notes to recipes hands-free.

  Palateful is designed for the household, not just the individual.
  Forked recipes keep lineage. Shared shopping lists update live.
  Meal plans sync across devices.

  Contact: leonid@ac93.org
  Privacy: https://palateful.app/privacy
  ```

Asset uploads (paths relative to repo root):
- **App icon (512×512):** `app/android/play-store-assets/icon-512.png`
- **Feature graphic (1024×500):** `app/android/play-store-assets/feature-graphic-1024x500.png`
- **Phone screenshots (portrait, ≥1080×1920, 2–8 required):**
  - `app/android/play-store-assets/screenshots/phone-1.png` — home + recipes
  - `app/android/play-store-assets/screenshots/phone-2.png` — recipe detail
  - `app/android/play-store-assets/screenshots/phone-3.png` — meal calendar
  - `app/android/play-store-assets/screenshots/phone-4.png` — cooking mode + timer

Assets are produced by `apl-2` and committed to git, so re-upload
from a clean checkout is idempotent.

**Section 14 — Content Rating (IARC).** Play Console → Store presence
→ Content rating → Start questionnaire.

- Category: **Reference, News, or Educational**
  (Food & Drink falls under this IARC top-level).
- Email: `leonid@ac93.org`.
- Answer key (paste verbatim — derived from the actual feature set,
  reviewed 2026-04-18):

| Question | Answer |
| -------- | ------ |
| Violence (cartoon / fantasy / realistic) | **No** |
| Sexual content | **No** |
| Crude humor | **No** |
| Drug, alcohol, tobacco reference | **Yes** — recipes may include alcoholic ingredients (wine, beer, spirits as cooking ingredients) |
| Simulated gambling | **No** |
| User-generated content shared between users | **Yes** — household members share recipes and notes |
| Unrestricted internet access | **No** — app communicates with fixed Palateful backend + sign-in providers only |
| Location sharing | **No** |
| Digital purchases | **No** (v1; mark **Yes** when subscriptions ship) |

Expected rating: **Teen (13+) / IARC 12+** due to alcohol reference.

**Section 15 — Data Safety form — paste-ready disclosure blocks.**

*Owned by `apl-3`. This section is where the 7 SDK/data disclosure
blocks (Firebase Crashlytics, FCM, Auth0, S3 media, Google/Apple
Sign-In, OpenAI/Anthropic, Play Billing reserved) live. See
`apl-3-data-safety-paste-blocks-and-permission-justifications.md`
for content.*

**Section 16 — Sensitive Permissions Declaration.**

*Owned by `apl-3`. Justification blocks for `SCHEDULE_EXACT_ALARM`,
`POST_NOTIFICATIONS`, `CAMERA`, `RECORD_AUDIO` live here as
paste-ready code-fenced text. See the apl-3 story for content.*

**Section 17 — Tester recruitment.**

*Owned by `apl-4`. Google Group creation, opt-in URL capture, outreach
email template, 14-day gate expectation-setting live here. See the
apl-4 story for content.*

**Section 18 — First CI-driven release (tag → internal track).**
Pre-flight:

1. `git pull origin main` — ensure you're on the latest.
2. Bump `app/pubspec.yaml`: `version: 1.0.<NEW>+<NEW>`. Both numbers
   must advance (build number matters for Play Store version-code
   uniqueness).
3. `npx nx run app:test` (or `flutter test` from `app/`) — green.
4. Commit + push: `git commit -am "chore(app): bump to 1.0.<NEW> for tag"`
5. Wait for `ci.yml` to finish green on main.

Tag:

```bash
git tag v1.0.<NEW>
git push origin v1.0.<NEW>
```

This triggers `.github/workflows/mobile-builds.yml` → `android-build`
job. Within ~10 minutes the AAB lands on Play Console internal track.
A `::notice::` annotation on the workflow summary page links back to
the Play Console build listing (wired by `ach-1`).

Watch for:
- `flutter analyze` or `flutter test` failure → fix before re-tag.
- Play upload failure due to duplicate version code → you didn't bump
  the build number. Fix pubspec and re-tag with a new `v*.*.*`.
- Crashlytics symbol upload failure → check `FIREBASE_SERVICE_ACCOUNT_JSON`
  secret is populated.

**Section 19 — Verify Pre-Launch Report.** Play Console → Testing →
Pre-launch report. The first report lands ~30 min after the AAB is
processed.

**Pre-Launch Report success criteria** (explicitly — so the first few
reports don't trigger unnecessary alarm):
1. **Zero critical crashes** — required. If any, hold the release
   until fixed.
2. **Zero app-signing errors** — required. If any, keystore is
   mismatched — see Section 21 Troubleshooting.
3. **Accessibility warnings** — acceptable. Address in a later story.
4. **Performance warnings** — acceptable at first. Track in a
   post-launch polish epic if any recur.

Only (1) and (2) block the release.

### Post-launch

**Section 20 — Closed test → production promotion.** The 14-day ×
12-tester gate is a hard Google requirement for new developer
accounts (first production release). Don't plan an earlier production
launch.

To promote an internal-track AAB to closed or production:
1. GitHub → Actions → `Promote Android` workflow.
2. Run workflow → `source_track: internal`, `target_track: closed` (or
   `production` after 14-day gate).
3. Approve the `production` environment gate (if promoting to
   production — same pattern `ci.yml` uses for prod infra).
4. Fastlane `android promote` lane runs → Play Console shows the AAB
   on the target track.

Rollout %: set manually in Play Console UI for production (staged
rollout UI is Play's strength; automating it adds fragility).

Cross-reference: `promote-android.yml` workflow is owned by `ach-5`
(epic-android-ci-hardening).

### Troubleshooting

**Section 21 — Troubleshooting + disaster recovery.**

- **"Upload failed: duplicate version code."** Bump the build number
  in `app/pubspec.yaml` (`+30` → `+31`), commit, re-tag.
- **"Certificate fingerprint doesn't match."** The local keystore and
  the one in `ANDROID_KEYSTORE_BASE64` diverged. Re-export with
  `base64 -i palateful-upload.jks | tr -d '\n' | pbcopy` and re-paste
  into the GitHub Secret.
- **Play App Signing enrollment stuck at "Pending."** Usually a 5–15
  minute delay after first upload. If > 1 hour, contact Play support
  via Console → Help → Contact us.
- **Service-account JSON rotation.** GCP → IAM → Service Accounts →
  `palateful-ci` → Keys → Add new → JSON. Paste into GitHub Secrets
  (`PLAY_STORE_JSON_KEY` + `FIREBASE_SERVICE_ACCOUNT_JSON`). Then
  delete the old key. Rotate at least annually.
- **Upload keystore lost.** This is the big one. Because we use Play
  App Signing, losing the upload keystore is **recoverable**:
  1. Play Console → Setup → App Integrity → **Request upload key
     reset**.
  2. Google re-issues the upload key. Takes 2–3 business days.
  3. Generate a new keystore (repeat Section 4), update all GitHub
     Secrets (Section 5), re-upload base64 to 1Password.
  4. Next release uses the new upload key; Play re-signs it under the
     same app-signing key transparently for users.

  **Prevention:** 1Password has both the keystore passwords and the
  base64-encoded keystore file. An offline encrypted copy (e.g.,
  external drive) is a belt-and-suspenders extra layer — recommended
  but not strictly required given the Play-managed reset path.

### Cross-epic references

- `epic-android-privacy-policy-page` — owns `https://palateful.app/privacy`.
- `epic-android-release-hardening` — owns adaptive icon
  (`flutter_launcher_icons`), `POST_NOTIFICATIONS` manifest entry +
  runtime prompt, `assetlinks.json` placeholder, Crashlytics native
  symbol Gradle config.
- `epic-android-ci-hardening` — owns `mobile-builds.yml` Flutter
  pinning + Gradle cache + analyze/test gate + Crashlytics symbol
  upload + Firebase Test Lab soft-smoke + `promote-android.yml`.
- `apl-2` — owns `app/android/play-store-assets/` graphics.
- `apl-3` — owns Sections 15 (Data Safety) + 16 (Sensitive
  Permissions) content.
- `apl-4` — owns Section 17 (tester recruitment).

### `CLAUDE.md` update

Add one line under "Key References":

> - **`ANDROID.md`** — Play Store release runbook (single operator,
>   Day 1 signup → Day 3 first tag). See
>   `epic-android-play-console-launch` for epic-level context.

## Tests

No automated tests. Validation is content-based:

1. Every external URL hyperlinked in the runbook resolves (WebFetch
   sanity check during writing).
2. Every shell command is in a fenced code block (grep for lines
   starting with `keytool`, `flutter`, `git`, `base64`, `curl`, `gcloud`
   outside of fences — expect zero hits).
3. Every Play Console field value decided today is a literal (no
   `<FILL>` placeholders except for the Play App Signing SHA-256 in
   Section 12 and the pubspec version in Section 18).
4. Reading top-to-bottom, a developer unfamiliar with Play Console can
   execute Sections 1–12 without context-switching to Google's docs.
   (Ad-hoc: re-read post-write, flag any ambiguity.)
5. `grep -F 'leonid@ac93.org' ANDROID.md app/web/privacy.html`
   returns matches in both files (cross-file consistency).

## File List

- Modified: `ANDROID.md` (append Day 1/Day 2/Day 3 + Post-launch +
  Troubleshooting below the existing stub).
- Modified: `CLAUDE.md` (one line under Key References).

## QA Checklist

See `apl-1-qa-walkthrough.md` for the standalone walkthrough.

### AC — Structure

- [ ] ANDROID.md preserves the existing stub preamble, paste-ready
  value table, and ownership table at the top.
- [ ] A "YOLO acceptance criteria" fenced block appears below the
  stub's preamble.
- [ ] Day 1 / Day 2 / Day 3 / Post-launch / Troubleshooting sections
  all present with real content.
- [ ] Every shell command is in a fenced code block.
- [ ] Every external URL is hyperlinked.

### AC — Cross-references

- [ ] Sections 15, 16, 17 explicitly reference `apl-3` / `apl-4`
  stories as content owners.
- [ ] Section 12 references `app/web/.well-known/assetlinks.json` +
  the Cloudflare Pages deploy flow.
- [ ] Section 13 references `app/android/play-store-assets/` paths
  exactly as `apl-2` will produce them.
- [ ] `epic-android-privacy-policy-page`, `epic-android-release-hardening`,
  `epic-android-ci-hardening` all named with their slugs in the
  Cross-epic references block.

### AC — Paste-readiness

- [ ] Play Console form values (developer name, contact email,
  category, tags, short description, full description, content
  rating answers) are literals, not placeholders.
- [ ] Only `<FILL>` placeholders are the Play App Signing SHA-256
  (Section 12) and the pubspec version for each tag (Section 18).

### AC — YOLO acceptance

- [ ] YOLO block matches the locked epic decision: tag →
  internal-track AAB reliable; production is manual later after
  14-day × 12-tester gate.

### AC — CLAUDE.md

- [ ] CLAUDE.md has a one-line entry under Key References pointing
  at ANDROID.md.
