# Story app-1: Draft privacy policy HTML

**Status:** ready-for-dev
**Epic:** epic-android-privacy-policy-page

## Goal

Publish a reachable, Play-Console-compliant privacy policy at
`https://palateful.app/privacy`, served as a static page by the existing
Flutter web Cloudflare Pages deploy. Zero framework, zero JavaScript,
zero workflow-yaml changes in this story (the smoke step lands in
`app-3`). The page must render fully on a 360px-wide viewport in under a
second on slow 3G, and every Play Console required section must be
present so reviewers can paste the URL into the Store Listing + Data
Safety forms with no revisions.

## Scope (from epic)

- `app/web/privacy.html` — pure HTML5 + inline CSS. Loads Playfair
  Display from Google Fonts (same family the Flutter web shell uses) but
  does not depend on the Flutter bundle. No JS.
- `app/web/_redirects` — Cloudflare Pages convention file so
  `/privacy` resolves whether or not Pages' auto-extension-strip is on.
  Belt-and-suspenders; rule is `/privacy /privacy.html 200`.
- Contact email is `leonid@ac93.org` (locked v1 decision).
- Last-updated date is `2026-04-18`.
- Ten sections from the epic content structure:
  1. Title + effective date
  2. Who we are + contact
  3. Data we collect (account, recipe content, shared household, device
     + crash, notifications, AI chat — six subsections)
  4. Third-party subprocessors (Auth0/Okta, AWS/S3, Firebase, OpenAI,
     Anthropic, Google Play + Apple App Store)
  5. How long we keep data
  6. Children (13+, no COPPA claim, no targeted advertising)
  7. Rights (GDPR: access/rectification/erasure/portability; CCPA: right
     to know/delete/opt-out of sale — no sale occurs)
  8. Deletion request process + 30-day SLA
  9. Updates + policy version + last-updated date
  10. Contact email
- Subtle top-of-page "← Palateful" breadcrumb linking back to
  `https://palateful.app` — helps Play reviewers confirm the URL is
  genuinely our site.

## Implementation

### New — `app/web/privacy.html`

- `<!DOCTYPE html>` HTML5 doctype.
- `<html lang="en">`.
- `<meta charset="UTF-8">`, `<meta name="viewport"
  content="width=device-width, initial-scale=1">`.
- OG tags: `og:title`, `og:description`, `og:type=website`,
  `og:url=https://palateful.app/privacy`.
- `<title>Privacy Policy — Palateful</title>`.
- `<link rel="preconnect" href="https://fonts.googleapis.com">` +
  `<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&display=swap" rel="stylesheet">` for the title font.
- Inline `<style>` block with:
  - `body { max-width: 720px; margin: 0 auto; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif; font-size: 16px; line-height: 1.6; color: #222; }`
  - `h1 { font-family: "Playfair Display", Georgia, serif; font-weight: 600; font-size: 2rem; }`
  - `h2 { font-size: 1.25rem; margin-top: 2rem; }`
  - `a { color: #1a73e8; }`
  - `.breadcrumb a { color: #666; text-decoration: none; font-size: 0.9rem; }` — subtle "← Palateful" link.
  - `.effective-date { color: #666; font-size: 0.9rem; margin-top: -0.5rem; }`
  - Responsive: `@media (max-width: 420px) { body { padding: 16px; } }` — ensures no horizontal overflow on a 360px viewport.
- Body:
  - `.breadcrumb` → `<a href="https://palateful.app">← Palateful</a>`.
  - `<h1>Privacy Policy</h1>` + `<p class="effective-date">Effective 18 April 2026 · Version 1.0</p>`.
  - Ten `<h2>`-headed sections matching the epic structure.
- Bottom of page has policy version + last-updated string a second time for reviewer scan.

### New — `app/web/_redirects`

Single line: `/privacy /privacy.html 200`.

Optional second line for `/privacy/` with trailing slash parity.
Cloudflare Pages `_redirects` format is `<source> <destination> <status>`
per line.

### Flutter web build

`flutter build web --release` copies everything under `web/` into
`build/web/` by default. Confirm with a local `flutter build web` that
both `privacy.html` and `_redirects` land in `build/web/` and
`build/web/_redirects`.

### Why the content matters

Play Console reviewers validate these exact claims against the Data
Safety form. Every subprocessor the app touches must be enumerated so
the reviewer's "paste the URL into the form" step produces no
mismatches. The list below is the ground truth drawn from the Palateful
codebase as of 2026-04-18:

- **Auth0 (Okta Inc.)** — authentication; email, name, `sub`.
- **Amazon Web Services** — server infrastructure + S3 media storage.
- **Google Firebase** — Crashlytics crash reports + FCM push.
- **OpenAI, L.L.C.** — AI assistant (opt-in).
- **Anthropic, PBC** — AI assistant (opt-in, same feature).
- **Google Play** — Play Billing (reserved for future subscriptions).
- **Apple App Store** — In-App Purchase (reserved for future
  subscriptions).

## Tests

No automated tests in this story — the page is static HTML with no JS.
Validation:

1. `flutter build web --release` succeeds and `build/web/privacy.html`
   exists.
2. Manual local serve: `cd app/build/web && python3 -m http.server 8080`
   then `curl -sI http://localhost:8080/privacy.html | head -1` returns
   `200`.
3. `_redirects` file exists at `build/web/_redirects` after build — no
   other build-time transformation needed.
4. Lint sanity: open the page in a browser, scroll from top to bottom on
   a 360×800 devtools viewport — no horizontal scroll.

Automated curl against `https://palateful.app/privacy` lives in `app-3`.

## File List

- New: `app/web/privacy.html`
- New: `app/web/_redirects`

## QA Checklist

See `app-1-qa-walkthrough.md` for the standalone walkthrough.

### AC — Static asset exists + builds

- [ ] `app/web/privacy.html` exists.
- [ ] `app/web/_redirects` exists with `/privacy /privacy.html 200`.
- [ ] `flutter build web --release` succeeds; `build/web/privacy.html`
  and `build/web/_redirects` both exist.

### AC — Content structure

- [ ] Page renders all 10 sections, each with its own `<h2>`.
- [ ] Contact email (`leonid@ac93.org`) appears in Who-we-are section
  and again in Contact section.
- [ ] All seven third-party subprocessors enumerated with one-sentence
  purpose each.
- [ ] Last-updated date `2026-04-18` + policy version `1.0` both
  visible.
- [ ] Title is `Privacy Policy — Palateful`.
- [ ] Subtle `← Palateful` breadcrumb links to `https://palateful.app`.

### AC — Visual + responsive

- [ ] 360×800 viewport: no horizontal scroll; font is readable without
  zoom.
- [ ] Playfair Display loads for the `<h1>` title (falls back to
  Georgia if the font is blocked).
- [ ] No JavaScript on the page (view source confirms).
- [ ] No external CSS file (only Google Fonts stylesheet + inline
  `<style>` block).
- [ ] No broken links (`← Palateful`, `mailto:leonid@ac93.org`).

### AC — Valid HTML5

- [ ] `<!DOCTYPE html>`, `<html lang="en">`, `<meta name="viewport">`.
- [ ] Validates via https://validator.w3.org/nu/ (manual spot check —
  no errors, warnings acceptable).

### AC — Deployment readiness

- [ ] The file is staged and ready; `app-3` will add the post-deploy
  curl smoke that proves it lands on `https://palateful.app/privacy`.
