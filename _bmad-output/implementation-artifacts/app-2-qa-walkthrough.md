# QA Walkthrough — app-2: Wire Play Console form references

This walkthrough is a cross-reference audit, not a runtime test.
It exists to catch silent drift between `app/web/privacy.html`, the
Play Console fields, and `ANDROID.md`.

## Setup

- [ ] On main (or this feature branch) with `app-1` already merged.
- [ ] Repo root on PATH in a shell (so grep commands below resolve
  from `./ANDROID.md` and `./app/web/privacy.html`).

## AC — ANDROID.md exists

- [ ] `cat ANDROID.md` prints the stub.
- [ ] `grep -F 'https://palateful.app/privacy' ANDROID.md` returns the
  paste-ready row.
- [ ] `grep -F 'leonid@ac93.org' ANDROID.md` returns the paste-ready
  row.
- [ ] ANDROID.md mentions `apl-1`–`apl-4` as the owning stories for
  future expansion.

## AC — privacy.html ↔ ANDROID.md consistency

- [ ] `grep -F 'leonid@ac93.org' app/web/privacy.html` returns 4+
  matches (mailto links in Who-we-are, Rights, Deletion, Contact
  sections).
- [ ] `grep -F 'ANDROID.md' app/web/privacy.html` returns 1 match —
  the reviewer-warning comment at the top of the file.
- [ ] `grep -F 'leonid@ac93.org' ANDROID.md` is identical to the
  contact email referenced in `app/web/privacy.html`.

## AC — No premature aliases

- [ ] `grep -rF 'support@palateful.app' ANDROID.md app/web/privacy.html`
  returns nothing. The alias is a deferred polish; v1 is the
  personal address.

## AC — No redundant privacy URL definitions

- [ ] `grep -rF 'palateful.app/privacy' --include='*.md' --include='*.html' .`
  from the repo root returns only `ANDROID.md`, `app/web/privacy.html`,
  the story file(s), and this walkthrough — no other live reference
  has hard-coded the URL (those would need to chain back to this
  source of truth instead).

## Known limitations

- ANDROID.md is a stub. apl-1 through apl-4 expand it in place with
  the full keystore / Play App Signing / Data Safety / tester-recruit-
  ment content. Keep the paste-ready table at the top so later work
  appends below instead of rewriting above.
