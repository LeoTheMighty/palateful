# Story pos-3 — Web: real landing page replacing the empty Flutter shell

**Status:** done (asset shipped; CI cutover deferred to operator)
**Epic:** [epic-recime-positioning](../planning-artifacts/epic-recime-positioning.md)
**Source-of-truth copy:** [pos-1-content-copy-for-all-surfaces](pos-1-content-copy-for-all-surfaces.md)
**Blocked-by:** [pos-7](pos-7-web-relocation-safety-net-redirects-and-auth0-callbacks.md) — DNS / Auth0 callback safety net.

## Goal

Replace the bare Flutter web shell at `palateful.app/` with a real
public landing page that:
- Communicates the layered hook ("free AND pantry-aware AND household-
  native AND Meals-capable") to first-time visitors.
- Surfaces the 4-column comparison table (Palateful vs Recime / Recipe
  Notes / Mela) — the in-app `pos-2` page only renders 2 columns at
  a time on a phone, so the web is where the full grid lives.
- Loads fast and ranks ≥95 on Lighthouse Performance + Accessibility.
- Lets visitors continue to reach the existing Flutter web app at
  `palateful.app/app/`.

## Acceptance criteria

- [x] Static HTML + CSS asset checked in at `app/web-landing/`. Pure
  HTML5 + one CSS file. No JS, no fonts loaded over the network, no
  framework. Manual lighthouse audit (operator) target ≥95.
- [x] HTML includes hero (with locked-phrasing hook from pos-1), 5
  feature cards, the 4-column comparison table (7 rows from pos-1),
  Why-we're-free body, and dual App Store / Play Store CTA rows.
- [x] CSS is mobile-first with prefers-color-scheme dark mode.
  Comparison table uses `overflow-x: auto` so a 360px viewport degrades
  cleanly (horizontal scroll, no overflow warning).
- [x] Footer links: privacy + "/app/" + copyright. Honors that
  `/privacy` stays at apex (per pos-7 redirect-rules).
- [x] No forbidden strings outside negation contexts (the only hits
  are in the "Why we're free" paragraph which quotes the forbidden
  tokens to advertise the grep guard — same pattern as pos-2).
- [x] Cutover runbook below references pos-7 explicitly.
- [x] Standalone QA walkthrough at `pos-3-qa-walkthrough.md`.

## What this story DOES NOT do (deliberately deferred)

- **Does not flip CI to deploy the new landing.** Today the deploy job
  in `.github/workflows/ci.yml` runs `flutter build web --release` and
  ships `build/web/` to Cloudflare Pages, which serves the Flutter
  shell at apex. Cutting over involves: (1) building Flutter with
  `--base-href=/app/`, (2) merging `app/web-landing/` into the deploy
  root, and (3) updating `app/web/_redirects` to pos-7's rules. That's
  one CI change + one Auth0 dashboard change + one DNS smoke test
  (per pos-7). Doing it autonomously without the operator confirming
  Auth0 is live risks a multi-hour login outage. **Operator does the
  cutover; this story produces the asset.**
- **Does not change `app/web/index.html`** (the Flutter web shell
  template). That file stays as-is until the cutover.
- **Does not edit the Cloudflare Pages project config**. Static-site
  Cloudflare Pages handles `app/web-landing/`-style content out of
  the box; no infra change needed.

## File List

- `app/web-landing/index.html` (new — landing markup)
- `app/web-landing/styles.css` (new — landing styles)
- `_bmad-output/implementation-artifacts/pos-3-web-real-landing-page-replacing-flutter-shell.md` (this file)
- `_bmad-output/implementation-artifacts/pos-3-qa-walkthrough.md` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)

## Cutover runbook (operator action — when ready)

Run these in order. Do not skip steps.

### Step 1: Auth0 callbacks (per pos-7 section B)
Add the new `/app/...` callback / logout entries to the Auth0
"Palateful Web" application in the Auth0 dashboard. Keep the old apex
entries as well — both must work for ≥7 days post-cutover so a rollback
is cheap. Confirm by spot-checking the Auth0 settings before moving on.

### Step 2: Update CI deploy step

Edit `.github/workflows/ci.yml` `deploy-web` job. Replace:

```yaml
      - name: Build Flutter web (prod)
        working-directory: app
        run: flutter build web --release

      - name: Deploy to Cloudflare Pages
        working-directory: app
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: npx --yes wrangler@latest pages deploy build/web --project-name palateful --branch=main --commit-dirty=true
```

With:

```yaml
      - name: Build Flutter web (prod, base-href /app/)
        working-directory: app
        run: flutter build web --release --base-href=/app/

      - name: Compose deploy directory (landing at apex, Flutter at /app)
        working-directory: app
        run: |
          mkdir -p build/deploy
          # 1. Static landing at root.
          cp -R web-landing/* build/deploy/
          # 2. Flutter app under /app/.
          mkdir -p build/deploy/app
          cp -R build/web/* build/deploy/app/
          # 3. pos-7 redirects at root (ensure the file exists at this point).
          cp web/_redirects build/deploy/_redirects
          # 4. Privacy + favicon stay at apex (already handled by web/_redirects
          #    + Cloudflare auto-strip).
          cp web/privacy.html build/deploy/privacy.html
          cp web/favicon.png build/deploy/favicon.png || true

      - name: Deploy to Cloudflare Pages
        working-directory: app
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: npx --yes wrangler@latest pages deploy build/deploy --project-name palateful --branch=main --commit-dirty=true
```

### Step 3: Activate pos-7's _redirects
Replace `app/web/_redirects` content with the rules from
`_bmad-output/implementation-artifacts/pos-7-web-relocation-safety-net-redirects-and-auth0-callbacks.md`
section A.

### Step 4: Push to main, wait for deploy, run pos-7 smoke test
Per pos-7 section C — three commands. Any failure → revert this CI
change and re-deploy.

### Step 5: Update App Store + Play Console listing URL
If listings already point to `https://palateful.app/`, they still work
post-cutover (apex still serves a real page). No change needed unless
the listing references a deep-link path that's now under `/app/`.

## Why ship the asset before the cutover

Per the parallel-loop / single-operator memory: this loop ships small
auditable diffs. The static landing is independently reviewable today;
the cutover is a single 5-line CI diff plus an Auth0 dashboard change
plus a DNS smoke test. Splitting the asset (low-risk PR-style work)
from the cutover (operational work) lets the operator schedule the
flip when they have eyes on Auth0 and CloudFlare logs. If the asset
ships first and the cutover never happens, no harm done.
