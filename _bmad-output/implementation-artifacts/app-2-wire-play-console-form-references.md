# Story app-2: Wire Play Console form references

**Status:** ready-for-dev
**Epic:** epic-android-privacy-policy-page

## Goal

Close the cross-reference loop between `app/web/privacy.html` and the
Play Console forms that depend on it. The Play Console Store Listing
and Data Safety forms both reference the privacy URL and a developer
contact email — if either drifts, the app is rejected. This story
creates the ANDROID.md anchor file so the URL + email have a single
source of truth that apl-1 (epic-android-play-console-launch) will
later expand into the full runbook.

## Scope (from epic)

- `ANDROID.md` at the repo root contains a "Privacy Policy URL" line
  pointing to `https://palateful.app/privacy`.
- The contact email in `app/web/privacy.html` matches the email
  referenced in `ANDROID.md` for the Play Console developer contact
  field (`leonid@ac93.org`).
- A sanity-check comment block already exists at the top of
  `app/web/privacy.html` (added in app-1) warning against removing the
  file without updating `ANDROID.md` and the Data Safety form. This
  story verifies the comment mentions `ANDROID.md` by exact name —
  already true as of the app-1 commit.

## Implementation

### New — `ANDROID.md`

Minimal stub with:

- Short "this is the Android launch runbook" preamble.
- A `## Play Console Store Listing — paste-ready values` section with:
  - **Privacy Policy URL** → `https://palateful.app/privacy`
  - **Developer contact email** → `leonid@ac93.org`
- A `## Ownership` note explaining that the full runbook (keystore,
  signing, Data Safety paste blocks, tester recruitment) lands under
  `epic-android-play-console-launch` stories `apl-1`–`apl-4`. This
  stub exists only so the privacy-policy epic has a concrete
  cross-reference target today.
- A warning that changing either of these values requires updating
  `app/web/privacy.html` (bottom of the section).

### Modified — `app/web/privacy.html`

No change in app-2 — the sanity comment was added in app-1 and
already names `ANDROID.md`. Verification-only check here.

## Tests

No automated tests. Manual grep verifies:

```
grep -F 'leonid@ac93.org' app/web/privacy.html ANDROID.md
grep -F 'https://palateful.app/privacy' ANDROID.md
```

Both should print matching lines from both files.

## File List

- New: `ANDROID.md`

## QA Checklist

See `app-2-qa-walkthrough.md` for the standalone walkthrough.

### AC — ANDROID.md exists with the two values

- [ ] `ANDROID.md` at repo root.
- [ ] Contains the line `**Privacy Policy URL** → <url>` where `<url>`
  is `https://palateful.app/privacy`.
- [ ] Contains the line `**Developer contact email** → <email>` where
  `<email>` is `leonid@ac93.org`.
- [ ] Contains a "this is expanded by apl-1" ownership note so future
  runbook work doesn't collide with the stub.

### AC — privacy.html cross-references are consistent

- [ ] Top-of-file comment in `app/web/privacy.html` names `ANDROID.md`
  verbatim.
- [ ] The four `mailto:leonid@ac93.org` occurrences in
  `app/web/privacy.html` match the email in `ANDROID.md`.

### AC — Single source of truth

- [ ] `grep -rF 'support@palateful.app' ANDROID.md app/web/privacy.html`
  returns nothing (the alias is a deferred polish, not in v1).
- [ ] No other files in the repo reference the privacy URL without
  going through `ANDROID.md` or `privacy.html` (soft check).
