# QA Walkthrough — app-3: Post-deploy verification in deploy-web

This walkthrough proves the curl smoke step catches a missing or
broken `/privacy` page. Run `app-1` and `app-2` walkthroughs first —
they verify the file and cross-references; this story verifies the
*deployment* of the file.

## Setup

- [ ] On main with `app-1` and `app-2` merged.
- [ ] Access to the GitHub Actions UI for this repo.

## AC — YAML valid

- [ ] `python3 -c "import yaml;
  yaml.safe_load(open('.github/workflows/ci.yml'))"` exits 0.
- [ ] Optional: `actionlint .github/workflows/ci.yml` reports no
  errors in the `deploy-web` job.

## AC — Step wiring (static inspection)

- [ ] `grep -n "Verify /privacy is live"
  .github/workflows/ci.yml` returns exactly one match inside the
  `deploy-web` job.
- [ ] The step runs *after* `Deploy to Cloudflare Pages` and *before*
  the next top-level job (`detect-changes`).
- [ ] `grep -n "::notice title=Privacy Policy URL"
  .github/workflows/ci.yml` returns exactly one match.

## AC — First post-merge run

Watch the first `deploy-web` run after merge:

- [ ] Navigate to Actions → CI → the run for the merge commit.
- [ ] The `deploy-web` job completes with conclusion **success**.
- [ ] The "Verify /privacy is live" step log shows:
  ```
  Attempt 1: curl -sSfI https://palateful.app/privacy
  ✓ Privacy page returned 200 on attempt 1
  ```
  (Attempt 2 or 3 is acceptable — edge propagation occasionally
  takes a few seconds.)
- [ ] The Actions run summary surfaces a `Privacy Policy URL` notice
  annotation.

## AC — Manual curl from dev machine

After the first deploy lands, from a local terminal:

- [ ] `curl -sSI https://palateful.app/privacy | head -3` returns
  `HTTP/2 200` + `content-type: text/html`.
- [ ] `curl -sSI https://palateful.app/privacy.html | head -3` also
  returns `HTTP/2 200` (Pages serves the `.html` extension too).
- [ ] Open `https://palateful.app/privacy` in a mobile browser (or
  360-px devtools viewport). Scroll top-to-bottom without
  horizontal overflow.

## AC — Failure mode (destructive test — optional, do this once)

Optional sanity check that the new step actually fails when the page
is missing. Not required to ship; run once on a throwaway branch to
confirm:

- [ ] Temporarily rename `app/web/privacy.html` →
  `privacy.html.bak`, push to a feature branch that runs the same
  workflow.
- [ ] Expected: the "Verify /privacy is live" step fails after 3
  attempts with `✗ Privacy page failed to return 200`.
- [ ] Rename back before merging.

## Known limitations

- The smoke step only checks HTTP 200 + `HTTP/.* 200` status line. It
  does **not** grep page content for specific phrases (e.g., "Privacy
  Policy v1.0"). A deeper content assertion belongs in a later
  hardening story if Play Console ever changes what it validates.
- Cloudflare Pages preview-branch deploys are not covered — the smoke
  only runs on `push` to `main`. Preview-branch drift would be
  caught at merge time, not before.
