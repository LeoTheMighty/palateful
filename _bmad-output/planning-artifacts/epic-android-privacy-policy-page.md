<!-- refined via party-mode 2026-04-18 -->
# Epic: Android Privacy Policy Page

## Added by this workshop

- **Ships FIRST in the Android-launch chain** — every downstream Play Console form (Store Listing, Data Safety) hard-requires a reachable privacy URL, so this epic blocks itself into pole position. Independent of `android-release-hardening` and `android-ci-hardening` (which can proceed in parallel after this lands).
- **v1 contact email: `leonid@ac93.org`** — no blocking on a `support@palateful.app` alias. The alias is a later enhancement; today's address is genuinely reachable, which is what Play Console reviewers validate.
- **Cloudflare Pages extension-stripping** — add `app/web/_redirects` (Cloudflare Pages convention) with `/privacy /privacy.html 200` so `https://palateful.app/privacy` resolves whether or not Pages' auto-extension-strip is on. Belt-and-suspenders; no downside.
- **Post-deploy smoke lives in the existing `deploy-web` job** — add a trailing `curl -sSIf https://palateful.app/privacy | grep "HTTP/2 200"` as a success check after `wrangler pages deploy`. Fails the job if the file didn't actually land. Owned by Story `app-3`.
- **Subtle top-of-page "← Palateful" breadcrumb** linking back to https://palateful.app — helps Play reviewers confirm the URL is genuinely our site (not a typosquat). Tiny UX addition; zero JS.

## Overview

Google Play Console hard-requires a public HTTPS privacy policy URL before the first submission of any Android app. The Store Listing form validates the URL for reachability; the Data Safety form cross-references it during review. Palateful has no privacy policy anywhere in the repo today and no `/privacy` path served from `palateful.app`.

This epic publishes a static `app/web/privacy.html` that ships automatically with the existing Flutter-web Cloudflare Pages deploy (the `deploy-web` job in `ci.yml` already serves everything under `app/web/`). The content enumerates every SDK and data surface the app touches: Firebase (Crashlytics + FCM), Auth0 (email + name + sub), S3 user-uploaded media (photos, audio, video), Google/Apple sign-in, OpenAI/Anthropic LLM chat subprocessors, Play Billing (reserved for future subscriptions), plus the GDPR / CCPA / COPPA stance, retention policy, contact email, and a deletion-request process. The URL is then paste-ready for the Play Console Store Listing and Data Safety forms.

## Goal

A reachable, Play-Console-compliant privacy policy at `https://palateful.app/privacy`, published alongside the next main-branch deploy, without any workflow-yaml changes.

## End-user flow

1. User taps "Privacy policy" in any app-store listing (iOS App Store, Play Store) or in a future in-app Settings link.
2. Browser opens `https://palateful.app/privacy`.
3. Page loads — plain HTML, readable on mobile, ~1 scroll of content. No framework, no JavaScript. A light header + a Playfair Display title to match brand (uses same Google Fonts the Flutter web shell loads, so no new dependencies).
4. User can scan: what's collected, who gets it, how to delete, contact.
5. Footer has `mailto:leonid@ac93.org` (or equivalent dedicated address) for deletion / GDPR requests.

Alternative: the Play Console reviewer clicks the URL from the form. It must return HTTP 200 and render without auth gate.

## Frontend changes

### New static asset

- `app/web/privacy.html` — pure HTML5 + minimal inline CSS. Loads the same `Playfair Display` + system sans-serif the Flutter web shell uses, but doesn't depend on the Flutter bundle loading. No JS.
- `app/web/index.html` unchanged — the Flutter web SPA still serves at `/`. Cloudflare Pages routes `/privacy` to `/privacy.html` automatically because Cloudflare serves the file if it exists before falling back to SPA routing.
- No change to `app/lib/` — the in-app "Privacy Policy" footer link (if added later) would be a `url_launcher` external link to `https://palateful.app/privacy`.

### Content structure

1. **Title + effective date.**
2. **Who we are + contact.** Palateful, developer contact email.
3. **Data we collect** — six subsections:
   - Account data (Auth0 email, name, sub, Google/Apple sign-in).
   - Recipe content (user-created recipes, notes, photos, audio memos, video memos — all in our S3).
   - Shared household data (recipe books, shopping lists, meal plans — shared with invited members only).
   - Device + crash data (Firebase Crashlytics crash reports, device model, OS version, anonymous install ID).
   - Notification data (Firebase Messaging tokens, notification preferences).
   - AI chat messages (when user opts into AI assistant — sent to OpenAI and Anthropic subprocessors).
4. **Third-party subprocessors** — bulleted list with purpose + data shared:
   - Auth0 (Okta) — authentication, email + name + sub.
   - Amazon Web Services — server infrastructure + media storage (S3).
   - Google Firebase — crash reporting, push notifications.
   - OpenAI — AI assistant (opt-in).
   - Anthropic — AI assistant (opt-in, same feature).
   - Google Play (Android), Apple App Store (iOS) — identifier / purchase data for future subscriptions.
5. **How long we keep data.** Account data kept while account active, 30 days after delete request. Crash logs 90 days. AI chat messages not persisted server-side beyond request lifecycle except for quality-control review sampling.
6. **Children.** App is 13+ (Teen), no COPPA compliance claim, no targeted advertising ever.
7. **Rights.** GDPR: access, rectification, erasure, portability. CCPA: right to know, delete, opt-out of sale (no sale occurs).
8. **Deletion.** How to request: email + 30-day SLA.
9. **Updates.** Policy version string + "last updated" date. Change-log placeholder.
10. **Contact.** Email address.

Keep it to roughly 1,200–1,800 words. Readable on a phone in one screen-scroll per section.

## Backend changes

None. Backend has no role here. The `/privacy` path is served by Cloudflare Pages from the Flutter web bundle; the API never sees the request.

## Infrastructure changes

- **Cloudflare Pages routing** — already handles arbitrary static files under `app/web/`. `app/web/privacy.html` is served at `/privacy.html` by default; Cloudflare auto-strips `.html` and also serves at `/privacy` without extra config. Confirm behavior with a `curl -I https://palateful.app/privacy` after first deploy.
- **No CI changes.** The existing `deploy-web` job in `ci.yml:379` already runs `flutter build web --release` and `wrangler pages deploy build/web`. Flutter's `build web` copies everything under `web/` into `build/web/` by default.
- **`.well-known/security.txt`** — out of scope here, but the `.well-known/` pattern we use for Android App Links assetlinks.json (Epic: Android Release Hardening) confirms the static-file approach works. Privacy page is trivially simpler.

## Initial design principles

- **Write in plain English, not lawyer.** Play Console reviewers skim; users who find the page should actually read it.
- **Zero framework.** No Flutter bundle load, no JS, no analytics. The page must render on a slow 3G Android device in under a second.
- **Paste-ready for Play Console.** Final URL is `https://palateful.app/privacy` — a single line the user pastes into the Play Console Store Listing form and the Data Safety form.
- **Source of truth is the repo, not a Notion doc.** Policy changes go through PR + CI deploy, same as code.

## File structure (anticipated)

### New
- `app/web/privacy.html` — the policy page.
- `app/web/_redirects` — Cloudflare Pages redirect rule `/privacy /privacy.html 200` (idempotent fallback if Pages' auto-extension-strip isn't on).

### Modified
- `.github/workflows/ci.yml deploy-web` job — append a `curl -sSIf https://palateful.app/privacy | grep "HTTP/2 200"` smoke step after `wrangler pages deploy` (Story `app-3`).

## Stories

### Story 1: `app-1` — Draft privacy policy HTML

**AC:**
- `app/web/privacy.html` exists and is valid HTML5 (`<!DOCTYPE html>`, `<html lang="en">`, meta viewport, OG tags).
- Contains all 10 sections from the content structure above. Each section header is an `<h2>`.
- Contact email is `leonid@ac93.org` (locked v1 decision; the `support@palateful.app` alias is a later polish).
- Inline CSS only — no external stylesheet. Max-width container, readable font sizes on a 360px-wide viewport.
- Last-updated date is 2026-04-18.
- `<title>` is "Privacy Policy — Palateful".
- Page lists every third-party subprocessor with a one-sentence purpose.
- Flutter web build includes the file (confirmed via `flutter build web && ls build/web/privacy.html`).
- `ci.yml deploy-web` run deploys it end-to-end — post-merge `curl -I https://palateful.app/privacy` returns 200 and `content-type: text/html`.

### Story 2: `app-2` — Wire Play Console form references

**AC:**
- `ANDROID.md` (owned by epic-android-play-console-launch, cross-referenced here) has a "Privacy Policy URL" line pointing to `https://palateful.app/privacy`.
- The `/web/privacy.html` contact email matches what `ANDROID.md` tells the user to set up in the Play Console contact form.
- A sanity-check comment block at the top of `privacy.html` warns against removing it without updating `ANDROID.md` and the Data Safety form.
- This story is effectively a doc + cross-reference check — it exists to make sure the URL lands in the two Play Console fields that actually require it. Not a code change beyond `ANDROID.md`.

### Story 3: `app-3` — Post-deploy smoke in `deploy-web`

**AC:**
- `.github/workflows/ci.yml` `deploy-web` job gains a new trailing step (after `wrangler pages deploy`): `curl -sSIf https://palateful.app/privacy | grep -E '^HTTP/.* 200'`. Fails the job if the file didn't deploy.
- A second trailing step posts a `::notice::` with the resolved URL for easy verification from the Actions tab.
- Manual spot-check after first deploy: open `https://palateful.app/privacy` on a phone-sized viewport (dev tools); scroll works; no horizontal overflow; fonts readable.
- Paste URL into Google's Data Safety form URL validator in Play Console (deferred to `epic-android-play-console-launch` Story `apl-1`).

## Dependencies

- No upstream dependencies. Blocks `epic-android-play-console-launch` (Data Safety + Store Listing forms require the URL).
- Does **not** block `epic-android-release-hardening` or `epic-android-ci-hardening` — those can proceed in parallel.

## Open questions for the user

None — party-mode resolved the contact-email question (v1 = `leonid@ac93.org`) and the iOS-cross-reference question (policy mentions iOS App Store + Play Store together; data practices are platform-independent).
