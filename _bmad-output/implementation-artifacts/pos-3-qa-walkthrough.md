# QA walkthrough — Story pos-3 (real landing page asset)

**What shipped:** a static HTML + CSS landing page at
`app/web-landing/`, ready for the operator-driven cutover described in
the story file. No CI change, no DNS flip, no Cloudflare Pages config
change in this story. The asset is independently reviewable today.

## Setup

Open the two new files in your editor:
- `app/web-landing/index.html`
- `app/web-landing/styles.css`

For the visual review, serve the directory with any local static
server. From the repo root:

```bash
cd app/web-landing && python3 -m http.server 8765
```

Then open `http://localhost:8765/` in a browser. Open dev tools and
toggle into a 360-px viewport (DevTools → Device toolbar) to verify
mobile rendering.

## Reviewer checklist

### Markup + copy
- [ ] Hero `<h1>` text reads exactly: `The kitchen app that's actually
  for households — free forever.` (canonical layered hook from pos-1).
- [ ] The pill-shaped commitment line reads: `Free forever. No ads, no
  premium tier — ever.` (canonical tagline from pos-1).
- [ ] Two CTA rows (top-of-page + bottom) point at App Store + Play
  Store URLs. Stub IDs `id000000000` and `app.palateful` are
  placeholders — operator updates them with real bundle IDs at
  pos-5 listing prep time. Verify the placeholder format is obvious
  (no risk of a real visitor 404ing on a fake link before pos-5).
- [ ] Comparison `<table>` has 1 header row + 7 data rows + 5 columns
  (label + Palateful + 3 competitors). Every cell populated; no `—`
  placeholders.
- [ ] "Why we're free" paragraph cites the grep-guard CI commitment
  (the negation-context phrasing — pos-6a's allowlist must cover this).
- [ ] Footer has 3 links: Privacy, /app/, and copyright. Privacy is
  `/privacy` (apex per pos-7); /app/ is the post-cutover Flutter web
  location.

### CSS / responsive
- [ ] Light theme (default): warm palette, brand color #8B5A3C.
- [ ] Dark theme: toggle prefers-color-scheme in DevTools. Background
  flips to #1a1410, text to #f5ede2. Comparison table still legible.
- [ ] At 360px width: hero stacks cleanly. Comparison table scrolls
  horizontally inside the rounded container; no page-level overflow.
  No red/yellow box from the browser dev-tools warnings.
- [ ] At 1200px width: hero, features grid (auto-fit minmax), and
  comparison table all sit within the 960px max-width container.

### Performance + accessibility (lighthouse target ≥95)
- [ ] No external font URLs — system font stack only. Confirm by
  searching `index.html` for `googleapis.com` or `fonts.` (should find
  none).
- [ ] No JS — confirm `index.html` has no `<script>` tags.
- [ ] Single CSS file (`styles.css`). Confirm by counting `<link
  rel="stylesheet">` (one).
- [ ] All `<a>` and `<button>` elements have visible text content (no
  icon-only links).
- [ ] `<table>` uses `<thead>` / `<th scope="col|row">` correctly.
- [ ] Color contrast: brand color on the hero pill background should
  pass WCAG AA at 4.5:1. (Spot-check with Chrome DevTools Accessibility
  pane.)

## Acceptance gate

If all the markup + CSS checks pass and the manual lighthouse audit
clears ≥95 perf + ≥95 a11y, the asset is ready for cutover. Operator
follows the story file's "Cutover runbook" sections 1-5 to flip DNS.

## Out of scope

- Real App Store / Play Store URLs in the CTA buttons. Filled in at
  `pos-5` operator-paste time.
- Lighthouse audit automation in CI. Manual run for now; if listing
  prep wants this automated later, that's a follow-up.
- Multi-page expansion (blog, /features, etc.). Single-page landing
  is the chosen path per epic open question default.
