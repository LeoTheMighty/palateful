# Story app-3: Post-deploy verification in deploy-web

**Status:** ready-for-dev
**Epic:** epic-android-privacy-policy-page

## Goal

Prove on every `main` push that `https://palateful.app/privacy`
actually resolves `HTTP/2 200` after Cloudflare Pages has finished its
deploy. Without this smoke, silent drift in `app/web/privacy.html` or
in the Pages project config would go unnoticed until a Play Console
reviewer hits a 404 — which is how apps get suspended.

## Scope (from epic)

- `.github/workflows/ci.yml` `deploy-web` job gets a new trailing
  "Verify /privacy is live" step after `wrangler pages deploy`.
- The step runs `curl -sSfI https://palateful.app/privacy` and
  greps the response for `^HTTP/.* 200`. A non-200 (or a missing
  `HTTP/` status line) fails the step and thus the job.
- A second trailing step emits a `::notice::` with the URL for easy
  click-through from the Actions tab.
- Wrangler's `pages deploy` output exits before Cloudflare's edge
  finishes propagating. Add a short retry loop (3 attempts, 10s
  apart) so the smoke step doesn't flake on cold propagation.

## Implementation

### Modified — `.github/workflows/ci.yml`

After the existing `Deploy to Cloudflare Pages` step in the
`deploy-web` job (currently line 426), append two new steps:

```yaml
- name: Verify /privacy is live (retry on propagation)
  run: |
    URL="https://palateful.app/privacy"
    for attempt in 1 2 3; do
      echo "Attempt $attempt: curl -sSfI $URL"
      if curl -sSfI "$URL" | grep -Eq '^HTTP/.* 200'; then
        echo "✓ Privacy page returned 200 on attempt $attempt"
        exit 0
      fi
      echo "Propagation not ready, sleeping 10s..."
      sleep 10
    done
    echo "✗ Privacy page failed to return 200 after 3 attempts"
    exit 1

- name: Emit privacy URL notice
  run: echo "::notice title=Privacy Policy URL::https://palateful.app/privacy is live"
```

- `-f` fails on non-2xx, so combined with the explicit grep the step
  catches both network failures and stale-content-at-200 (the grep
  proves the HTTP line is literally `HTTP/2 200` or `HTTP/1.1 200`).
- Three attempts at 10s each (= up to 30s) is enough time for
  Cloudflare's global edge to pick up the new deploy. Real-world
  propagation is usually instant in the US-east runner pool; this is
  insurance.
- `::notice::` appears in the Actions run summary, which makes the
  privacy URL one-click accessible for anyone doing QA after a
  deploy.

### No other changes

`ci.yml` already builds with `flutter build web --release` (line 422)
and deploys via `wrangler pages deploy build/web` (line 431). The new
static files from app-1 (`privacy.html` + `_redirects`) ship inside
that bundle — no copy step needed.

## Tests

No new unit tests — the change is a YAML-only smoke step. Validation
strategies:

1. **Syntax-only check locally** — `npx js-yaml .github/workflows/ci.yml`
   (or equivalent) confirms the YAML parses cleanly.
2. **Act / run on merge** — the true test is the first post-merge run.
   If Cloudflare hasn't propagated yet, the retry loop handles it.
3. **Manual curl from dev machine** after the first deploy:
   ```
   curl -sSI https://palateful.app/privacy | head -3
   ```
   Expect `HTTP/2 200` + `content-type: text/html`.

## File List

- Modified: `.github/workflows/ci.yml` (deploy-web job — 2 new steps
  appended).

## QA Checklist

See `app-3-qa-walkthrough.md` for the standalone walkthrough.

### AC — Workflow changes

- [ ] `ci.yml` `deploy-web` job gains a "Verify /privacy is live"
  step after the wrangler deploy.
- [ ] The step curls `https://palateful.app/privacy` and asserts
  `HTTP/.*200`; a non-200 fails the job.
- [ ] Retry loop tolerates up to 30s of Cloudflare edge propagation
  (3 attempts × 10s sleep).
- [ ] A `::notice::` surfaces the URL in the Actions run summary
  after success.

### AC — YAML valid

- [ ] `ci.yml` parses cleanly (local `yamllint` or `python -c
  "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`).
- [ ] `actionlint` (if installed) reports no new errors in the
  deploy-web job.

### AC — First post-merge run green

- [ ] After merging to main, the `deploy-web` Actions job finishes
  with conclusion `success`.
- [ ] The new "Verify /privacy is live" step shows "✓ Privacy page
  returned 200 on attempt N".
- [ ] The Actions run summary surfaces a `Privacy Policy URL`
  notice.

### AC — Play Console paste validation (deferred handoff)

- [ ] `apl-1` (epic-android-play-console-launch) pastes the URL into
  the Play Console Store Listing → Privacy Policy URL field and
  Data Safety form header. That step is outside this story's scope
  — this AC only notes the handoff.
