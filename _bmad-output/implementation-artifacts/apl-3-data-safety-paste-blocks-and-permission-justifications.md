# Story apl-3: Data Safety paste blocks + permission justifications

**Status:** ready-for-dev
**Epic:** epic-android-play-console-launch

## Goal

Replace the Section 15 (Data Safety) and Section 16 (Sensitive
Permissions) placeholders in `ANDROID.md` with paste-ready, code-fenced
disclosure and justification blocks that the operator pastes verbatim
into Play Console form textareas. No operator rewriting required.
Each block is sized to fit the target textarea (Play Console's
sensitive-permission justification field has an internal ~600-char
soft cap; disclosure blocks are structured as form-field pairs, not
free-form prose).

## Scope (from epic)

7 Data Safety disclosures + 4 sensitive-permission justifications,
appended in-place to `ANDROID.md`. No code changes. No cross-file
updates.

## Data Safety disclosures (Section 15)

Each disclosure block is structured as Play Console's form fields so
the operator can read → type → submit without re-thinking the mapping.
The structure is:

```
Data type:           <Play Console taxonomy entry>
Collected:           Yes / No
Shared:              Yes / No  (with third-party name if Yes)
Optional / Required: <classification>
Purpose(s):          <Play Console purpose taxonomy>
Encrypted in transit:Yes / No
Deletion request:    <link or procedure>
Notes:               <free-form explanation — operator may edit>
```

Seven blocks to write:

1. **Firebase Crashlytics** — crash logs + device ID + IP address.
   Purpose: Analytics. Collected; not shared. Encrypted in transit.
   Deletion: not user-initiated; collection stops on app uninstall.

2. **Firebase Messaging (FCM)** — installation ID token. Purpose:
   App functionality (push delivery). Collected; not shared.
   Encrypted in transit. Deletion via account deletion flow.

3. **Auth0 (Okta)** — email, name, user ID (`sub`). Purpose: Account
   management. Collected; **shared with Auth0/Okta Inc.** Encrypted
   in transit. Deletion on request via support email
   (`leonid@ac93.org`) — 30-day SLA per privacy policy.

4. **S3 user-uploaded media** — photos, audio files, video files.
   Purpose: App functionality (recipe attachments). Collected via
   Amazon S3. Encrypted in transit + at rest. Deletion: per-recipe
   or per-account on request.

5. **Google / Apple Sign-In** — email, name, user ID. Purpose:
   Account management. Collected via the provider's OAuth SDK (not
   directly collected by Palateful; attributed to provider). Not
   shared beyond the provider.

6. **OpenAI / Anthropic LLM chat** — "Messages (other in-app
   messages)" — user prompts to the AI assistant. Purpose: App
   functionality + Personalization. Collected; **shared with OpenAI
   L.L.C. and Anthropic PBC** as LLM subprocessors. Encrypted in
   transit. Opt-in — only users who engage the AI assistant send
   messages.

7. **Play Billing (reserved for future subscriptions)** — financial
   info (purchase history). Purpose: App functionality + Fraud
   prevention. Collected via Google Play only. Not shared. **Mark
   "not currently collected" for v1** — add when subscriptions ship.

## Sensitive-permission justifications (Section 16)

Four paste-ready blocks, each sized for Play Console's
sensitive-permission-declaration textarea:

- **SCHEDULE_EXACT_ALARM** (~400 chars) — cook-timer UX requires
  exact firing; imprecise alarms can drift by minutes which makes
  multi-concurrent timers unreliable during cooking. No background
  work beyond timer firing.

- **POST_NOTIFICATIONS** (~200 chars) — import-completion and meal
  reminder notifications; opt-in prompt shown during onboarding; all
  notifications originate from direct user action (recipe import,
  meal plan creation, household sharing).

- **CAMERA** (~150 chars) — photo capture for recipe hero images and
  printed cookbook scanning; no video recording, no continuous
  capture, no background use.

- **RECORD_AUDIO** (~150 chars) — voice memos during cooking + voice
  commands for AI assistant; user-initiated only, never
  always-listening.

## Implementation

### ANDROID.md — replace Section 15 placeholder

Replace the existing Section 15 body (stub: "*apl-3 content appends
here*") with the 7 disclosure blocks. Keep the section header
`## Section 15 — Data Safety form` and its introductory paragraph;
append the blocks below.

### ANDROID.md — replace Section 16 placeholder

Replace the existing Section 16 body (stub) with the 4 justification
blocks. Same header-preservation rule.

### Introductory prose per section

Section 15 should open with a short paragraph naming the Play
Console path (`Play Console → App content → Data safety`), stating
that each block below maps 1:1 to a "Data type" row in the form, and
noting that operators can skip Block 7 (Play Billing) in v1.

Section 16 should open similarly: Play Console path is
`Play Console → App content → Sensitive app permissions`. Each block
is one textarea. Paste verbatim; no edits required.

## Tests

No automated tests. Validation:

1. `grep -c '^### Block' ANDROID.md` → 7 (Section 15 blocks) + 4
   (Section 16 blocks) = 11.
2. Each code block inside Section 15 contains all of:
   `Data type:`, `Collected:`, `Shared:`, `Purpose`, `Encrypted`,
   `Deletion`.
3. Section 16 permission blocks reference the exact permission name
   (`android.permission.SCHEDULE_EXACT_ALARM`, etc.) in the header.
4. Spot-read: the seven disclosures align with the subprocessor
   list in `app/web/privacy.html`. Every subprocessor named there
   has a corresponding block here; every block here matches one of
   the enumerated subprocessors.
5. Byte-size sanity: each permission justification paragraph stays
   under 600 chars (Play Console's soft cap).

## File List

- Modified: `ANDROID.md` (in-place replacement of Section 15 + 16
  placeholders).

## QA Checklist

See `apl-3-qa-walkthrough.md` for the standalone walkthrough.

### AC — 7 Data Safety blocks

- [ ] Firebase Crashlytics block has: Crash logs + Device ID +
  Approximate IP data types; Analytics purpose; collected not
  shared; encrypted in transit; deletion on uninstall.
- [ ] Firebase Messaging block: Installation ID; App functionality;
  not shared.
- [ ] Auth0 block: email + name + user ID; Account management;
  shared with Auth0/Okta; encrypted; deletion via support email.
- [ ] S3 media block: photos + audio + video; App functionality;
  collected via Amazon S3; encrypted in transit + at rest; deletion
  on request.
- [ ] Google/Apple Sign-In block: email + name + user ID; Account
  management.
- [ ] OpenAI/Anthropic block: Messages (other in-app messages);
  App functionality + Personalization; shared with OpenAI and
  Anthropic.
- [ ] Play Billing block marked "not currently collected" with a
  note about when to flip to "Yes."

### AC — 4 permission justifications

- [ ] `SCHEDULE_EXACT_ALARM` block ~400 chars, argues cook-timer
  precision requirement.
- [ ] `POST_NOTIFICATIONS` block ~200 chars, covers import
  completion + meal reminders.
- [ ] `CAMERA` block ~150 chars, covers recipe photos + cookbook
  scanning.
- [ ] `RECORD_AUDIO` block ~150 chars, covers voice memos + AI voice
  commands.
- [ ] Each permission block uses the fully-qualified Android
  permission name (`android.permission.*`) in the block heading.

### AC — Paste-readiness

- [ ] Every block is inside a code fence so line breaks + form
  structure survive copy-paste.
- [ ] No `<FILL>` / `<TBD>` tokens in Section 15 or 16 (except Play
  Billing's "not currently collected" note which is deliberate).

### AC — Section header preservation

- [ ] Section 15 header intact: `## Section 15 — Data Safety form`.
- [ ] Section 16 header intact:
  `## Section 16 — Sensitive Permissions Declaration`.
