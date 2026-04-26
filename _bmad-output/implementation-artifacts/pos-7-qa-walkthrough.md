# QA walkthrough — Story pos-7 (web-relocation safety net)

**What shipped:** a runbook + pre-written `_redirects` rules + Auth0
operator checklist + 3-command smoke-test playbook. pos-3 follows
this end-to-end at the moment it relocates the Flutter web app from
`palateful.app/` to `palateful.app/app/`. No user-facing code in this
story; it's the safety net itself, validated as a procedure.

## Setup

You don't need a build. Open the story file:
`_bmad-output/implementation-artifacts/pos-7-web-relocation-safety-net-redirects-and-auth0-callbacks.md`.

## Reviewer checklist

### A. _redirects file content
- [ ] Section A is one valid Cloudflare Pages `_redirects` file
  (parseable; each line has 3 columns or is a comment).
- [ ] All app routes that today live at the apex are forwarded:
  /login, /auth, /recipes, /recipe-books, /calendar, /cart, /profile,
  /admin, /onboarding, /invitations, /recipe-public, /meal-public.
- [ ] Status code is `301` (permanent) for all rules — sanity-checked
  on each line.
- [ ] Both `/path` and `/path/*` patterns appear for each route
  (Cloudflare doesn't auto-include sub-paths).
- [ ] Privacy explicitly noted as staying at apex (`palateful.app/privacy`).
  No redirect rule for it.

### B. Auth0 operator checklist
- [ ] Allowed Callback URLs section enumerates the new `/app/...`
  entries to add.
- [ ] Allowed Logout URLs entries listed.
- [ ] "Do not remove the apex entries" warning present, with the
  rationale (≥7-day no-rollback window before cleanup).
- [ ] Operator step explicitly hands off if dashboard access is
  unavailable.

### C. Smoke-test playbook
- [ ] All three commands are copy-pasteable.
- [ ] Step C.1 expected output is concrete (HTTP/2 301 + Location
  header).
- [ ] Step C.2 grep expects exactly the SPA-SDK + bootstrap markers.
- [ ] Step C.3 documents what success looks like (no
  `redirect_uri_mismatch`, lands on `/app/home` or
  `/app/onboarding/welcome`).
- [ ] Failure path explicit: revert DNS flip immediately.

### D. Risks
- [ ] All three named risks have a concrete mitigation cross-referenced
  to a section of the story or the playbook.

## Acceptance gate

This story is a runbook gate for pos-3. If any checkbox above fails,
revise the story file before pos-3 is allowed to flip DNS.

## Dry-run (optional but recommended)

If you have a staging Cloudflare Pages project, you can dry-run the
_redirects content there before pos-3 ships:

1. Create a tiny static site at `staging.palateful.app/` with just
   `_redirects` (the section A content) and a placeholder index.html.
2. Curl each redirect from section C.1 against the staging origin.
3. Confirm the Flutter web shell at `/app/...` responds (you can
   deploy a stub static page at `/app/index.html` if you don't want
   to ship the real Flutter build to staging).

This is optional because the rules are small enough to read by eye.
But it's the cheapest way to catch a typo before it hits prod.
