<!-- refined via party-mode 2026-04-25 -->
# Epic: Recime Mass-Import — Chrome Extension MVP

## Overview

One-click migration from Recime to Palateful via a Palateful-branded Chrome extension. The user logs into recime.app in their own browser; the extension uses their own session cookie to call Recime's internal web API; recipes are fetched + POSTed into Palateful's import endpoint; recipes land in `Trying Out` with full deduplication. **Sidesteps Recime TOS section 2.2(c)/(d) by being a user-side tool that mirrors Recime's own privacy-policy GDPR data-portability promise** — the user is downloading their own data via their own session, not Palateful crawling Recime's servers.

## Goal

Convert the lock-in friction Recime users feel ("my recipes are stuck in their cloud") into a Palateful acquisition lever. Be the first competitor with a working "import from Recime" feature — the 4-year gap (no other competitor has built this) is the strongest signal of opportunity. Lawyer-cleared TOS framing + first-mover advantage.

## End-user flow

1. **Settings entry point.** User opens Settings → "Import from another app" → "Recime."
2. **Walkthrough screen.** Lands on `RecimeImportWalkthroughScreen` with annotated screenshots and a 3-step explanation:
   - **Step 1:** Install the Palateful Chrome extension via a one-tap "Install Extension" CTA that deep-links to the Chrome Web Store listing.
   - **Step 2:** Log in to recime.app in your own browser.
   - **Step 3:** Click the Palateful extension button in your browser toolbar and choose "Send all my recipes to Palateful."
3. **FAQ accordion.** Below the steps, a short FAQ explains: "Why a browser extension? Because Recime doesn't expose a public API and we want to respect their TOS — your browser does the work, your data stays yours. We never see your Recime password."
4. **Extension popup flow.** User clicks the Palateful extension button on recime.app. Popup appears with a single primary action: "Send all my recipes to Palateful." On first use, a Palateful API token entry field appears (paste from Settings → Account); subsequent uses skip this.
5. **Background paginated fetch.** Extension calls Recime's internal list-recipes endpoint with the user's session cookie, paginates through their full library, fetches per-recipe detail. Real-time popup progress: "12 of 87 recipes fetched · 8 sent to Palateful · 0 failed."
6. **Backend ingestion.** Each recipe POSTs to `POST /v1/recipes/import/recime` with the user's Palateful API token. Backend normalizes Recime's JSON to Palateful's recipe model, files into `Trying Out` per `epic-recipe-default-books`, dedupes via existing duplicate-detection path per `epic-import-duplicate-detection` (per-recipe verdict: created / skipped-as-duplicate / failed).
7. **In-app progress visibility.** Activity Hub shows a long-running import job row ("Importing from Recime — 12 of 87 recipes") with the existing YNAB-inspired status icons. Tapping the row opens a per-recipe detail sheet showing each recipe's verdict + reason if failed.
8. **Push notification on completion.** "87 recipes imported from Recime — 84 added, 2 duplicates skipped, 1 failed. Tap to review."
9. **Deep-link to Trying Out.** Tapping the notification opens the user's `Trying Out` book where the imported recipes appear, ready to organize, cook, or move into other books.

## Frontend changes

- New screen `app/lib/features/profile/import_from_another_app_screen.dart` — listing of supported sources (initially just Recime; designed for Paprika/Mela/Crouton future additions).
- New screen `app/lib/features/profile/recime_import_walkthrough_screen.dart` — annotated screenshots (3-step flow), "Install Extension" CTA deep-linking to Chrome Web Store URL, FAQ accordion. Screenshots stored as PNG assets under `app/assets/walkthroughs/recime/`.
- `app/lib/features/import/import_jobs_list.dart` (or wherever Activity Hub long-running rows render) — handle the new `recime_mass_import` job type with per-recipe success/skip/fail counts in the row + a tap-to-expand detail sheet.
- New widget `app/lib/features/import/recime_import_detail_sheet.dart` — per-recipe table showing each recipe's status (created / skipped-as-duplicate / failed) + reason for failures.
- Push-notification deep-link routing: when notification payload `type=recime_mass_import_complete`, deep-link to `Trying Out` book.

## Backend changes

- New endpoint `POST /v1/recipes/import/recime` — body: a single Recime-shaped JSON recipe payload. Authentication: existing Palateful API token (Bearer header). Rate-limited 200 req / 5 min per user (existing rate-limit middleware extension).
- Service `services/api/src/services/recime_normalizer.py` — converts Recime's JSON shape (title, ingredients[], instructions[], imageUrl, sourceUrl, etc.) to Palateful's `RecipeCreate` shape. Best-effort field mapping: missing fields leave the recipe usable; lossy conversions (e.g., free-text servings → integer if parseable, else 4 default) are documented + logged.
- Dedup integration: every Recime-imported recipe runs through the existing duplicate-detection path (per `epic-import-duplicate-detection` Story 1) — exact-title match within the user's recipes + source-URL match. If duplicate, response = `{verdict: 'skipped_as_duplicate', existing_recipe_id: '...', existing_book_name: '...'}`.
- Routing: imported recipe filed into `Trying Out` per `epic-recipe-default-books` (`recipe_book_id = user.trying_out_book_id`).
- Audit rows: per-session start/end audit rows in `error_logs` (`service="audit"`, `error_type="RecimeImportSession"`). Start row captures `user_id` + intended count (estimated from extension's first paginated response); end row captures final `success / skip / fail` counts.
- Per-user cap: at most 2 mass-import sessions per 24h. Tracked via `error_logs` audit query at start. Third attempt within 24h returns 429 with friendly error: "You've already started a Recime import today. Try again tomorrow, or contact support if something went wrong."
- New job-type entry in `import_jobs.job_type` enum: `recime_mass_import`. Long-running progress visible in existing Activity Hub.

## Infrastructure changes

- **NEW Chrome extension distributed via Chrome Web Store** under Palateful's developer account.
  - Manifest V3.
  - Content script injected into recime.app pages.
  - Popup HTML with single primary CTA + first-time API token entry field.
  - Extension storage: `chrome.storage.local` for the user's Palateful API token (encrypted via Chrome's built-in storage encryption).
  - Background service worker handles paginated fetch from Recime's internal API + per-recipe POST to Palateful.
  - One Chrome Web Store listing (description + screenshots + privacy policy URL pointing to `palateful.app/privacy`).
- **No new AWS resources** on the FastAPI side. No new env vars. New endpoint reuses existing Postgres + auth + audit infra.
- **Lawyer review required pre-launch.** 30-minute review of: extension privacy policy framing ("user is exporting their own data via their own session, mirroring Recime's GDPR portability clause"); FAQ copy; Chrome Web Store listing; in-app walkthrough copy. Not an epic blocker; the lawyer review can happen in parallel with development. Public Chrome Web Store launch is gated on green-light.

## Initial design principles (from feasibility check; party-mode TBD)

- **User-side, not server-side.** Server-side scraping by Palateful violates Recime TOS 2.2(c). User-side via the user's own session cookie mirrors Recime's GDPR data-portability promise. The framing is the legal protection; lawyer review confirms.
- **Chrome MVP only.** Firefox / Safari extensions are deferred. ~95% of recipe-app users on desktop are Chrome-based; that's enough surface for v1.
- **Lossy normalization is fine; lossless is the bar.** Recime's data model isn't ours. Best-effort field mapping; recipes land usable even if metadata is approximate. Document lossy conversions in `recime_normalizer.py` for future audit.
- **Dedup via the existing path.** Don't build a parallel duplicate-detection model. Reuse `epic-import-duplicate-detection` Story 1's exact-title + source-URL match — this is the same dedup users see for any other import source.
- **Audit rows for everything.** Every session writes start + end audit rows. No PII (cookies, tokens) ever logged. Enables retroactive cost / abuse / debugging analysis via `audit_errors.py --drill audit:RecimeImportSession`.
- **First-mover advantage matters.** Recipe Notes / Snapshot / Deglaze haven't built this. The 4-year gap suggests they all assumed it was infeasible. Ship before they figure out the extension pattern.

## File structure (anticipated)

```
app/lib/features/
  profile/
    import_from_another_app_screen.dart                # NEW
    recime_import_walkthrough_screen.dart              # NEW
  import/
    import_jobs_list.dart                              # extend for recime_mass_import job type
    recime_import_detail_sheet.dart                    # NEW per-recipe verdict view

app/assets/walkthroughs/recime/
  step_1_install_extension.png                         # NEW screenshot
  step_2_login_recime.png                              # NEW screenshot
  step_3_click_extension.png                           # NEW screenshot

services/api/src/
  api/v1/recipe/import_recime.py                       # NEW endpoint
  services/recime_normalizer.py                        # NEW

chrome-extension/                                      # NEW directory at repo root
  manifest.json
  popup.html
  popup.js
  content-script.js
  background.js
  styles.css
  icons/                                               # 16, 48, 128 px
  README.md
  privacy-policy.md                                    # links to palateful.app/privacy

_bmad-output/implementation-artifacts/
  recime-imp-1-backend-recime-normalizer-and-import-endpoint.md
  recime-imp-2-backend-rate-limit-audit-and-job-type.md
  recime-imp-3-chrome-extension-mvp-manifest-popup-content.md
  recime-imp-4-frontend-walkthrough-and-activity-hub-integration.md
  recime-imp-5-lawyer-checklist-chrome-store-listing-and-e2e.md
```

## Story list

- **recime-imp-1 — Backend: recime_normalizer + import endpoint.** New `POST /v1/recipes/import/recime` accepting a Recime-shaped JSON payload. New `recime_normalizer.py` with best-effort field mapping. Dedup integration via existing `epic-import-duplicate-detection` path. Routing into `Trying Out`. Spike sub-task: load recime.app in DevTools, capture XHR/fetch calls, document the actual list-recipes + get-recipe-detail JSON shape (this informs the normalizer's input schema). **AC:** spike documented in story file with sample payload; endpoint accepts a recorded sample payload + returns 201 with the new recipe_id; duplicate detection works; integration test covers create + skip-as-duplicate + fail paths; 100% coverage.
- **recime-imp-2 — Backend: rate limit + audit rows + job_type entry.** Rate-limit middleware extension (200 req / 5 min per user on the Recime endpoint specifically). Per-session audit rows (`service="audit"`, `error_type="RecimeImportSession"`). Per-user cap of 2 sessions / 24h with 429 + friendly error on overage. New `import_jobs.job_type` enum entry: `recime_mass_import`. **AC:** rate limit triggers correctly under load test; audit rows captured at start + end; per-user cap enforced; integration test for the over-cap flow.
- **recime-imp-3 — Chrome extension MVP (Manifest V3).** New `chrome-extension/` directory at repo root with `manifest.json`, `popup.html`, `popup.js`, `content-script.js`, `background.js`, `styles.css`, `icons/`. Popup with single primary CTA + first-time API token entry. Background service worker paginated-fetch loop. Per-recipe POST to Palateful with progress reporting back to popup. **AC:** extension installs from a local `.zip` in Chrome dev mode; clicking the CTA on recime.app fetches at least one recipe + POSTs successfully to a local Palateful instance; progress UI accurately reflects fetch + send state.
- **recime-imp-4 — Frontend: walkthrough screen + Activity Hub integration.** New `RecimeImportWalkthroughScreen` with the 3 annotated screenshots + "Install Extension" CTA + FAQ. New `import_from_another_app_screen.dart` listing supported sources (initially just Recime). Extend Activity Hub long-running import job row to handle the `recime_mass_import` job type with per-recipe success/skip/fail counts. New per-recipe detail sheet. Push-notification deep-link routing to `Trying Out`. **AC:** walkthrough screen renders all assets; "Install Extension" CTA deep-links correctly; Activity Hub row + detail sheet render counts accurately; push-notification taps land in `Trying Out`; widget tests cover all three states.
- **recime-imp-5 — Lawyer checklist + Chrome Web Store listing + e2e.** Pre-launch checklist: lawyer-review FAQ copy, walkthrough copy, extension privacy policy, Chrome Web Store listing description. Chrome Web Store listing prepared (description, screenshots, privacy URL). End-to-end test: install extension → log in to a test Recime account → click extension button → see progress → see Activity Hub → see push notification → land in `Trying Out` with all imported recipes. **AC:** lawyer review documented (sign-off captured in story file); Chrome Web Store listing draft submitted; e2e test passes against a Recime test account; staging deploy verified.

## Dependencies

- **`epic-recipe-default-books`** — for the `Trying Out` destination. Stories 1 + 2 already shipped per recent /dev commits; remaining stories don't block this epic.
- **`epic-import-duplicate-detection`** — for the dedup path. Stories shipping this round; the Recime endpoint imports the same dedup helper.
- **Lawyer review** — required before public Chrome Web Store launch. Not an epic blocker; can run parallel with dev.

## Open questions for the user

- **Chrome extension distribution — public Chrome Web Store or unlisted/dev-only first?** Default proposed: unlisted/dev-only for v1 (only users with the link install it), expand to public listing after 30 days of dogfood + lawyer green-light. If you want public from day one, we lock in the lawyer review as a hard blocker on `recime-imp-5`.
- **API token entry UX — paste-once or per-session?** Default: paste-once (stored in `chrome.storage.local`, encrypted by Chrome's built-in mechanism). If you want per-session for paranoia (less convenient), we add a "remember me" checkbox.
- **Failure-row retention.** When an individual recipe fails to import (e.g., Recime returns malformed JSON), we currently log + count it. Should we offer a retry CTA in the per-recipe detail sheet, or is "log + skip" enough for v1?

---

## Refinements applied (party-mode 2026-04-25)

### End-user-flow additions / rewrites
- **Insert step 1.5:** "If you're on mobile, we'll email you a desktop link" — with an "Email me the install link" button sending a one-tap link to the Chrome Web Store + the user's pre-filled API token via a magic-link endpoint. **Eliminates the manual paste step** and solves the mobile-cohort UX gap.
- **Rewrite step 4:** API token shown in a separate, copy-buttoned screen in the app (NOT buried in extension popup). Reduces friction.
- **Add step 6.5:** "Walkthrough screen transitions to live progress view as soon as the first recipe POST arrives (via WS-lowered MutationBus event)." Auto-advances; user doesn't need to manually navigate to Activity Hub.
- **Add step 9.5:** If 0 recipes received within 10 minutes of token issuance, walkthrough screen shows "Need help? Tap to message support" state.

### Frontend section additions
- **New WS/mutation event `RecimeImportSessionStarted`** — walkthrough screen subscribes, auto-advances on first POST.
- **New idle/empty/error states on `RecimeImportWalkthroughScreen`:** waiting / no-recipes-after-10min / extension-disabled-by-server.
- **New "Email me the desktop link" widget** with magic-link payload.
- **Drop static screenshots** in favor of looping silent MP4/Lottie under `app/assets/walkthroughs/recime/` (more durable when Recime ships UI refreshes); keep one PNG fallback per step for low-bandwidth.

### Backend section additions
- **New `POST /v1/recipes/import/recime/session` (start)** — explicit session lifecycle; fixes 24h-cap race and gives in-app side a deterministic "session started" signal.
- **New `POST /v1/recipes/import/recime/session/{id}/finalize` (end)** — explicit session finalization.
- **Inbound payload requires `payload_schema_version` field** — unknown versions reject loudly with `error_type="RecimeSchemaDrift"` audit row. Prevents silent garbage on contract drift.
- **New `GET /v1/extensions/recime/status`** returning `{enabled: bool, min_extension_version: str, message: str}` — read by extension on each session start. **Server-side kill-switch** without a Chrome Web Store push.
- **New `POST /v1/extensions/recime/magic-link`** — emails desktop install link + one-time-use API token to requesting user.
- **New `POST /v1/extensions/recime/telemetry`** — extension reports client-side errors invisible to FastAPI.

### Infrastructure section additions
- **New CI workflow `.github/workflows/chrome-extension.yml`:** lint → build → zip → on-tag upload via `chrome-webstore-upload-cli` to UNLISTED track (manual promote to public).
- **Extension version scheme:** SemVer; major bump = API contract break; CI enforces extension's declared `min_api_version` matches a real deployed API tag.
- **Document Google developer-account ownership:** which Google account holds the listing, who has MFA, recovery-key location (1Password Palateful vault). Captured in `chrome-extension/README.md`.
- **Kill-switch wiring:** extension queries `/v1/extensions/recime/status` first thing every session.
- **Sentry-equivalent telemetry** from extension → backend `/v1/extensions/recime/telemetry`.

### Story changes
- **Split `recime-imp-1` into `1a` + `1b`:**
  - `1a` — **spike:** capture recime.app XHR shapes, document, commit fixtures. Output is hard prerequisite, not sub-task.
  - `1b` — normalizer + endpoint built from fixtures.
- **Split `recime-imp-3` into `3a` + `3b`:**
  - `3a` — extension MVP (manifest + popup + content script + background).
  - `3b` — extension hardening (kill-switch query, schema-version stamping, telemetry, magic-link consumption).
- **Add `recime-imp-6 — CI/CD + kill-switch + magic-link.`** Chrome extension CI workflow, `/v1/extensions/recime/status` + `/magic-link` + `/telemetry` endpoints, developer-account documentation, rollback runbook.
- **Add `recime-imp-7 — Contract drift canary + QA fixture set.`** Nightly canary diffing recime.app response shape; recorded fixture set for CI replay; documented QA account roster.
- **`recime-imp-5` reframed:** lawyer review is a **parallel checklist, not a sequential story** — can run alongside development; sign-off gate captured in story file under `## Lawyer Sign-off` section.

### Open questions (escalated)
1. **Lawyer review mechanics** — which lawyer, what's the SLA, where's sign-off captured, what's escalation if framing must change? **User decision required.**
2. **Chrome Web Store listing strategy** — unlisted-only forever / unlisted v1 → public after 30d dogfood / public from day one? **Recommend unlisted v1 → public after 30 days + lawyer green-light.**
3. **Recime API breaking mid-import** — kill-switch + schema-drift audit + canary defense, or do we want auto-pause-and-refund-the-cap behavior? **Recommend kill-switch + canary as v1; auto-pause is v2.**
4. **QA Recime accounts** — authorized to maintain a small set of test Recime accounts under Palateful's name, or each QA tester uses their own? **Recommend recorded fixtures for CI + 1 personal test account for manual smoke.**
5. **Mobile-only users** — magic-link flow covers laptop+phone, but pure-mobile users have no path. Acceptable for v1?

### Locked decisions to propagate (1 remaining epic)
1. **Browser-extension distribution pattern:** Chrome Web Store unlisted track → manual promote, version-pinned to API contract via `min_api_version`. Reuse for any future Mela/Paprika/Crouton extensions.
2. **Lawyer-review gate convention:** parallel with dev, sign-off in story file under `## Lawyer Sign-off`, public listing gated on green-light. Not a hard story blocker.
3. **New `error_logs` conventions:** `service="audit"` `error_type="RecimeImportSession"` (session bookends), `service="recime_import"` `error_type="RecimeSchemaDrift"` (contract break), `service="recime_extension"` `error_type=*` (extension telemetry). Future extensions follow `service="<source>_extension"`.
4. **Server-side kill-switch endpoint pattern:** `GET /v1/extensions/<source>/status` returning `{enabled, min_extension_version, message}`. Every extension Palateful ships queries its own status endpoint at session start.
5. **Magic-link mobile→desktop hand-off:** `POST /v1/extensions/<source>/magic-link` is the standard for any "user must do this on a different device" flow.

### Risks
1. **Recime breaks their internal API silently** (most likely failure mode). *Mitigation:* schema-version field on every payload + nightly contract-drift canary + server-side kill-switch endpoint.
2. **Chrome Web Store rejects the listing** (unclear policy on "scrape competitor data" extensions). *Mitigation:* submit unlisted first to get rejection feedback without burning PR; lawyer pre-reviews CWS description copy.
3. **Recime updates TOS to ban session-cookie tools** post-launch. *Mitigation:* lawyer reviews privacy-policy framing for residual GDPR-portability defense; have 24h server-side kill-switch ready; pre-draft user-comms email.
4. **Support load when extension misfires.** *Mitigation:* in-app idle/error states with "message support" CTA + magic-link / telemetry endpoint capturing client-side errors.
