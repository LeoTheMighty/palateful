# QA Walkthrough — app-1: Draft privacy policy HTML

This walkthrough exercises the static privacy page end-to-end: build,
local serve, visual sanity, and content correctness. The post-deploy
smoke against `https://palateful.app/privacy` lives in the `app-3` QA
walkthrough — run this one first.

## Setup

- [ ] On `main` (or this feature branch) with no uncommitted changes in
  `app/web/`.
- [ ] Flutter installed and on the path (`flutter --version`).

## Build produces the files

- [ ] From `app/`, run `flutter build web --release`.
- [ ] `ls build/web/privacy.html` exists (~12 KB).
- [ ] `ls build/web/_redirects` exists.
- [ ] `cat build/web/_redirects` shows both `/privacy` and `/privacy/`
  rules mapping to `/privacy.html` with a `200` status.

## Local serve — HTTP status + content-type

- [ ] `cd app/build/web && python3 -m http.server 8080`.
- [ ] In another shell: `curl -sSI http://localhost:8080/privacy.html`
  returns `HTTP/1.0 200 OK` and `Content-type: text/html`.
- [ ] `curl -sS http://localhost:8080/privacy.html | grep -c '<h2>'`
  prints `10` (one per section).

## Visual spot-check at 360px viewport (Play Console's mobile reviewer stance)

- [ ] Open `http://localhost:8080/privacy.html` in Chrome.
- [ ] DevTools → device toolbar → custom 360×800 viewport.
- [ ] No horizontal scroll anywhere top-to-bottom.
- [ ] Title "Privacy Policy" renders in a serif (Playfair Display, with
  Georgia fallback if fonts are blocked).
- [ ] Body text is readable without zoom (~16 px).
- [ ] "← Palateful" breadcrumb link at top-left; clicking opens
  `https://palateful.app` in the same tab.
- [ ] `mailto:leonid@ac93.org` links in Who-we-are, Your-rights,
  Deletion, and Contact sections all launch the mail client.

## Content checklist — Play Console reviewer stance

Skim the page top-to-bottom and tick each:

- [ ] Section 1 — Who we are: name + one-line app description + contact
  email.
- [ ] Section 2 — Data we collect: 6 subsections (account, recipe
  content, shared household, device + crash, notifications, AI chat).
- [ ] Section 3 — Third-party subprocessors: 8 bulleted entries (Auth0,
  AWS, Firebase, OpenAI, Anthropic, Google Play, Apple App Store,
  APNs).
- [ ] Section 4 — Retention: 4 rows (account/recipe, crash, push
  tokens, AI chat).
- [ ] Section 5 — Children: Teen 13+, no COPPA claim, no targeted ads.
- [ ] Section 6 — Rights: GDPR + CCPA bullets.
- [ ] Section 7 — Deletion: 30-day SLA.
- [ ] Section 8 — Data transfers: US-hosted notice.
- [ ] Section 9 — Updates: version + effective-date mechanism.
- [ ] Section 10 — Contact: email.

- [ ] Top of page: "Effective 18 April 2026 · Version 1.0".
- [ ] Bottom of page: footer reads "Palateful · Privacy Policy v1.0 ·
  Last updated 18 April 2026".

## HTML validity

- [ ] Paste the rendered HTML into https://validator.w3.org/nu/ — no
  errors. Warnings are acceptable (trailing dashes in comments,
  etc.).
- [ ] `view-source` confirms: `<!DOCTYPE html>`, `<html lang="en">`,
  `<meta name="viewport" ...>`, `<title>Privacy Policy — Palateful</title>`.
- [ ] `view-source` contains zero `<script>` tags. No JavaScript at all.

## Fallback behavior (no Google Fonts)

- [ ] DevTools → Network → block requests matching
  `fonts.googleapis.com`.
- [ ] Reload the page. Title still readable in a serif (Georgia
  fallback). Body text unaffected.

## Known limitations (scoped to follow-up stories)

- The post-deploy curl smoke (`HTTP/2 200` from
  `https://palateful.app/privacy`) lands in `app-3`.
- `ANDROID.md` cross-reference + sanity comment reminder lands in
  `app-2`.
