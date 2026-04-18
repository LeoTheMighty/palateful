# QA Walkthrough: apl-1 — ANDROID.md runbook skeleton

## Setup

- Open `ANDROID.md` at repo root in a Markdown preview pane.
- Have `CLAUDE.md` open in a second tab for the Key References check.

## Smoke

- [ ] `wc -l ANDROID.md` → at least 300 lines (originally ~55 in stub).
- [ ] `grep -c '^## Section' ANDROID.md` → 21 (Sections 1–21).

## Structural checks

- [ ] Top preamble preserved — `> **Status (2026-04-18):** Stub.`
  still appears at top.
- [ ] Paste-ready values table still present (Privacy Policy URL +
  Contact email).
- [ ] "Where these values must also be consistent" list preserved.
- [ ] Ownership table preserved.
- [ ] "YOLO acceptance" fenced block appears immediately after the
  preamble, restating the 14-day / 12-tester gate.

## Day 1 / Day 2 / Day 3 structure

- [ ] Day 1 header exists — `# Day 1 — Signup (20 minutes active`.
- [ ] Day 2 header exists — `# Day 2 — Credentials + first AAB`.
- [ ] Day 3 header exists — `# Day 3 — Forms + testers + first tag`.
- [ ] Post-launch section exists — `# Post-launch`.
- [ ] Troubleshooting section exists — `# Troubleshooting`.
- [ ] Cross-epic references block at the bottom naming
  `epic-android-privacy-policy-page`, `epic-android-release-hardening`,
  `epic-android-ci-hardening`, `apl-2`, `apl-3`, `apl-4`.

## Shell commands in code fences

- [ ] `keytool -genkeypair` appears exactly once, inside a fenced block.
- [ ] `flutter build appbundle --release` appears inside a fenced block.
- [ ] `gcloud projects add-iam-policy-binding` appears 4 times, all
  inside the same fenced block (Section 6).
- [ ] `git tag v1.0.<NEW>` appears inside a fenced block.
- [ ] `curl -sI https://palateful.app/.well-known/assetlinks.json` in
  fenced block.
- [ ] No shell commands appear outside a fenced block — spot-check
  with `grep -n '^keytool\|^flutter\|^git\|^gcloud\|^curl' ANDROID.md`
  and verify every hit is inside `` ```bash `` context.

## Play Console form values are literals

- [ ] App name: `Palateful` (literal, not `<FILL>`).
- [ ] Contact email: `leonid@ac93.org` (literal).
- [ ] Privacy policy URL: `https://palateful.app/privacy` (literal).
- [ ] Category: `Food & Drink` (literal).
- [ ] Tags list: `recipes`, `meal planning`, `kitchen`, `cooking`,
  `grocery list` — literal.
- [ ] Short description is a literal inside a code fence, ≤ 80 chars.
- [ ] Full description is a literal inside a code fence, ≤ 4000 chars.
- [ ] IARC answer table filled with literal Yes/No per-question
  answers.
- [ ] Expected rating: Teen 13+ / IARC 12+ called out.

## Remaining `<FILL>` placeholders

- [ ] Section 12 has `<FILL>`-equivalent language around the SHA-256
  fingerprint ("Replace it with the real value from Section 11") —
  acceptable: SHA-256 only exists post-first-upload.
- [ ] Section 18 has `1.0.<NEW>` as placeholder for pubspec version —
  acceptable: version changes per release.
- [ ] No other `<FILL>` / `<TODO>` / `<TBD>` tokens anywhere.
  Spot-check with
  `grep -nE '<FILL>|<TODO>|<TBD>|TBD' ANDROID.md`.

## Cross-file consistency

- [ ] `grep -F 'leonid@ac93.org' ANDROID.md` → 4+ matches.
- [ ] `grep -F 'https://palateful.app/privacy' ANDROID.md` → 3+
  matches.
- [ ] `grep -F 'com.palateful.palateful' ANDROID.md app/fastlane/Appfile`
  → matches in both files (package name consistency).

## Hand-off stubs (owned by other stories)

- [ ] Section 15 (Data Safety) is a stub with italic pointer to apl-3.
- [ ] Section 16 (Sensitive Permissions) is a stub pointing to apl-3.
- [ ] Section 17 (Tester recruitment) is a stub pointing to apl-4.
- [ ] Section 13 asset paths reference
  `app/android/play-store-assets/icon-512.png`,
  `.../feature-graphic-1024x500.png`, and
  `.../screenshots/phone-{1,2,3,4}.png` — produced by apl-2.

## CLAUDE.md

- [ ] `CLAUDE.md` has a new line under "Key References" pointing at
  `ANDROID.md` with a one-line description.
- [ ] `grep -F 'ANDROID.md' CLAUDE.md` returns at least one match.

## Ad-hoc reading pass

- [ ] Read Sections 1–12 end-to-end. Can a developer with no prior
  Play Console experience execute every step without opening a Google
  docs tab? Flag any ambiguity as a review finding.
- [ ] Section 4 keystore command uses `<STRONG_STORE_PASSWORD>` +
  `<STRONG_KEY_PASSWORD>` + `<CITY>` placeholders (intentional —
  operator fills their own values).
- [ ] Section 10 `key.properties` heredoc has the same 1Password
  pointer language — operator never pastes literal passwords into
  shell history.

## External URL sanity

- [ ] `grep -oE 'https://[^ )]+' ANDROID.md | sort -u` → ~6 unique
  external URLs. Each should be reachable in a browser:
  - `https://play.google.com/console/signup`
  - `https://console.cloud.google.com`
  - `https://palateful.app/privacy`
  - `https://palateful.app/.well-known/assetlinks.json`
  - `https://github.com/<your-user>/palateful/issues` (user
    placeholder — acceptable)

## Acceptance

All above checkboxes passing.
