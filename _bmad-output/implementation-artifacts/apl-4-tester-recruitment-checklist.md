# Story apl-4: Tester recruitment checklist

**Status:** ready-for-dev
**Epic:** epic-android-play-console-launch

## Goal

Replace the Section 17 placeholder in `ANDROID.md` with a bounded
tester-recruitment checklist: create a Google Group, wire it to Play
Console's Internal testing track, capture the opt-in URL, and send a
paste-ready outreach email that links testers to the GitHub Issues
feedback channel + sets expectations about the 14-day × 12-tester
closed-test gate.

## Scope (from epic)

Section 17 content only. No new files; no code changes; no backend
changes.

## Content outline

1. **Google Group creation.** Literal values:
   - URL: `https://groups.google.com/`
   - Group email: `palateful-android-testers@googlegroups.com`
   - Access: Public (anyone can find), restricted (only members can
     post).
   - Post permission: Group members only.
   - Purpose note: "A Google Group address is the only way Play
     Console Internal testing accepts multi-tester opt-in without
     manually entering each tester email."

2. **Play Console Internal testing wiring.**
   - Path: Play Console → Testing → Internal testing → **Testers**
     tab → **Manage testers**.
   - Add the Google Group email from step 1 as a tester.
   - Capture the **Opt-in URL** (shown under the Testers list).
     Expected format (as of 2026-04):
     `https://play.google.com/apps/internaltest/<app-specific-id>`
     — the operator reads the real URL from Play Console; the
     `<app-specific-id>` is assigned by Google.

3. **Outreach email template.** Paste-ready:
   - Subject: "Palateful internal-testing — install on your Android
     phone"
   - Body: 4–5 sentences. Must include (a) the opt-in URL
     placeholder, (b) a reminder to sign into the Google account
     that joined the Google Group, (c) the GitHub Issues feedback
     URL, and (d) the operator's reply-to email
     (`leonid@ac93.org`).

4. **Expectation-setting block.** Short note to testers:
   > Google requires ≥ 12 people to install and use the app for
   > ≥ 14 days before we can promote to the production track.
   > Keep the app installed for at least 2 weeks — even if you only
   > open it once. Every install counts toward the gate.

5. **Tester target count note (internal-only).** Short operator-facing
   note on the scale target: "Aim for 15–20 invitations to land 12
   active testers; assume ~60–70% install-and-keep rate."

## Implementation

### ANDROID.md — replace Section 17 placeholder

Replace the existing Section 17 body (stub: `(apl-4 content appends
here)`) with the 5-part content above. Keep the section header
`## Section 17 — Tester recruitment`.

Use subsection headers `###` for each of the five parts so the
Markdown TOC stays navigable.

## Tests

No automated tests. Validation:

1. Section 17 header intact; stub placeholder gone.
2. `grep -c 'palateful-android-testers@googlegroups.com' ANDROID.md`
   → 2+ (once in Section 17 Google Group step; once in opt-in
   wiring step).
3. Outreach email template contains a placeholder for the opt-in
   URL (operator fills with Play Console value); template is in a
   code fence so line breaks survive copy-paste.
4. GitHub Issues feedback URL appears (placeholder for the repo's
   actual GitHub URL is acceptable — `<your-user>/palateful`).
5. 14-day × 12-tester language appears in the expectation-setting
   block.

## File List

- Modified: `ANDROID.md` (in-place replacement of Section 17
  placeholder).

## QA Checklist

See `apl-4-qa-walkthrough.md` for the standalone walkthrough.

### AC — Google Group creation

- [ ] Section 17 subsection 1 names `https://groups.google.com/` as
  the starting URL.
- [ ] Group email literal `palateful-android-testers@googlegroups.com`
  appears.
- [ ] Access + post permission settings literally named.

### AC — Play Console wiring

- [ ] Path literal: "Play Console → Testing → Internal testing →
  Testers".
- [ ] Opt-in URL format example is
  `https://play.google.com/apps/internaltest/<app-specific-id>`
  with note that the real value comes from Play Console.

### AC — Outreach email template

- [ ] Template is inside a fenced code block.
- [ ] Contains opt-in URL placeholder (e.g.
  `<PASTE OPT-IN URL FROM SECTION 17 STEP 2>`).
- [ ] Names the Google account caveat.
- [ ] GitHub Issues URL + reply-to `leonid@ac93.org` both present.

### AC — Expectation-setting

- [ ] 14-day language is literal.
- [ ] 12-tester language is literal.
- [ ] Expectation note is shown as something the operator pastes
  into the outreach email body (sets tester expectations
  up-front).

### AC — Operator-facing note

- [ ] Short operator-only note on aiming for 15–20 invitations to
  net 12 active testers.
