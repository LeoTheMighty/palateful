# QA Walkthrough: apl-3 — Data Safety paste blocks + permission justifications

## Setup

- Open `ANDROID.md` at repo root in a Markdown preview pane.
- Confirm Section 15 and Section 16 headers are still present.

## Smoke

- [ ] `grep -c '^### Block' ANDROID.md` → 11 (7 Data Safety + 4
  permission).
- [ ] `grep -c '^## Section 15' ANDROID.md` → 1.
- [ ] `grep -c '^## Section 16' ANDROID.md` → 1.
- [ ] Both section introductory paragraphs are present (naming the
  Play Console path).

## Section 15 — 7 Data Safety blocks

- [ ] **Block 1 — Firebase Crashlytics** lists Crash logs + Device
  or other IDs + Approximate IP data types; purpose Analytics;
  not shared; encrypted in transit; deletion note about uninstall.
- [ ] **Block 2 — Firebase Messaging** lists App interactions +
  installation ID; purpose App functionality; not shared.
- [ ] **Block 3 — Auth0** lists email + name + User ID (sub);
  purpose Account management; shared with Auth0/Okta; deletion via
  leonid@ac93.org.
- [ ] **Block 4 — S3 user media** lists Photos + Audio + Video;
  shared with AWS as storage processor; encrypted in transit + at
  rest; deletion per-recipe or per-account.
- [ ] **Block 5 — Google / Apple Sign-In** lists email + name +
  User ID; purpose Account management; not shared beyond the
  provider.
- [ ] **Block 6 — OpenAI / Anthropic LLM chat** lists Messages
  (other in-app messages); shared with OpenAI and Anthropic;
  purpose App functionality + Personalization.
- [ ] **Block 7 — Play Billing (reserved)** lists Financial info —
  purchase history; Collected = **No** (v1); notes explain when to
  flip to Yes (when subscriptions ship).

## Section 15 — every block has the form-field structure

- [ ] Every Block 1–7 code fence contains all of: `Data type:`,
  `Collected:`, `Shared:`, `Purpose`, `Encrypted in transit:`,
  `Deletion request:` (or N/A for Block 7).
  Verify with:
  ```bash
  awk '/^### Block [1-7] /,/^###|^## Section 16/' ANDROID.md \
    | grep -cE '^(Data type|Collected|Shared|Purpose|Encrypted in transit|Deletion)'
  ```
  Expect ≥ 42 (7 blocks × 6 required fields each).

## Section 16 — 4 permission justification blocks

- [ ] Block 1 heading is exactly
  `### Block 1 — \`android.permission.SCHEDULE_EXACT_ALARM\``.
- [ ] Block 2 heading is exactly
  `### Block 2 — \`android.permission.POST_NOTIFICATIONS\``.
- [ ] Block 3 heading is
  `### Block 3 — \`android.permission.CAMERA\``.
- [ ] Block 4 heading is
  `### Block 4 — \`android.permission.RECORD_AUDIO\``.

## Section 16 — byte-size sanity (under Play Console ~600-char cap)

Run (from repo root):

```bash
python3 -c "
import re
f = open('ANDROID.md').read()
for name, body in re.findall(r'### Block \d+ — \`android.permission\.(\w+)\`.*?\n\`\`\`\n(.*?)\n\`\`\`', f, re.DOTALL):
    print(f'{name}: {len(body)} chars')
"
```

- [ ] `SCHEDULE_EXACT_ALARM` is under 600 chars.
- [ ] `POST_NOTIFICATIONS` is under 600 chars.
- [ ] `CAMERA` is under 600 chars.
- [ ] `RECORD_AUDIO` is under 600 chars.

## Paste-readiness

- [ ] Every Block 1–11 body is inside a triple-backtick code fence
  so line breaks + structure survive copy-paste (Play Console
  preserves newlines in textareas).
- [ ] No `<FILL>` / `<TBD>` / `<TODO>` tokens inside Section 15 or
  Section 16 (Block 7's "v1 — Palateful is free" is intentional
  language, not a placeholder). Verify:
  ```bash
  awk '/^## Section 15/,/^## Section 17/' ANDROID.md \
    | grep -nE '<FILL>|<TBD>|<TODO>'
  ```
  Expect empty output.

## Privacy-policy consistency check

- [ ] Every subprocessor named in `app/web/privacy.html` has a
  matching Block in Section 15. Spot-check by opening
  `app/web/privacy.html`'s "Third-party subprocessors" section
  side-by-side with Section 15 headers.
- [ ] No Section 15 block names a subprocessor NOT also in
  `app/web/privacy.html`.

## Cross-file sanity

- [ ] `grep -c 'leonid@ac93.org' ANDROID.md` ≥ 10 (stub table +
  several disclosure blocks + account-deletion pointer).
- [ ] Block 3 (Auth0) explicitly references the privacy policy URL:
  `https://palateful.app/privacy`.

## Acceptance

All above checkboxes passing.
