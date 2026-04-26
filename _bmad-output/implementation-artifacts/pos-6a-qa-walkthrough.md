# QA walkthrough — Story pos-6a (share tagline + grep-guard CI)

**What shipped:**
1. The canonical "Get Palateful — free forever: https://palateful.app"
   tagline appended to every share-text payload from `ShareService`
   (recipe, recipe book, shopping list).
2. A `tools/copy-grep-guard.sh` CI gate that fails on paywall-shaped
   vocabulary in user-facing copy outside the allowlist.

## Setup

Local dev — no special build needed.

## Share-text tagline

- [ ] Open the app on iOS or Android.
- [ ] Recipe detail → tap share → confirm the share-sheet text body
  ends with two newlines + `Get Palateful — free forever:
  https://palateful.app`.
- [ ] Recipe-books list → long-press a book → "Share invite" →
  confirm tagline appears at the end.
- [ ] Shopping-list screen → "Share" → confirm tagline appears.
- [ ] In all three cases, the body still includes the original
  "Check out / Join my … on Palateful!" lead and the deep-link URL.

## Unit-test confirmation

```bash
cd app
flutter test test/services/share_service_tagline_test.dart
```
- [ ] All 3 tests pass (happy path, separator, empty-body degenerate).

## Grep-guard local run

```bash
bash tools/copy-grep-guard.sh
```
- [ ] Exit code 0 on a clean checkout.
- [ ] Output line: `copy-grep-guard: OK (scanned N file(s))` (N
  somewhere in the 250-300 range as of 2026-04-26).

## Grep-guard self-test (force a violation, confirm fail, revert)

Quick sanity that the guard actually *would* fail if a regression slipped in:

```bash
echo '// Premium tier launching soon.' >> app/lib/main.dart
bash tools/copy-grep-guard.sh   # expected: exit 1 with line printed
git checkout -- app/lib/main.dart
bash tools/copy-grep-guard.sh   # expected: exit 0
```
- [ ] First call exits 1 with the violation line printed and a
  remediation hint.
- [ ] Second call exits 0.

## Allowlist sanity

- [ ] `cat tools/copy-grep-allowlist.txt` shows ~16 entries, each in
  `file:lineno:rationale` format.
- [ ] Each rationale starts with "negation —" or names a meta-context.
- [ ] No allowlist line points to a file that doesn't exist:
  ```bash
  awk -F: '$1!~/^#/ && $1!="" { if (system("test -f " $1) != 0) print "MISSING: " $0 }' \
    tools/copy-grep-allowlist.txt
  ```
  Expected output: empty.

## CI integration

- [ ] `.github/workflows/ci.yml` `flutter-test` job has a step labelled
  `No paywall language (pos-6a grep guard)` running
  `bash tools/copy-grep-guard.sh`. Confirm it sits between
  `no-direct-get-recipe-books-check.sh` and `flutter test`.

## Acceptance gate

If any checkbox above fails, fix in the story File List before
unblocking pos-6b. Specifically: the self-test MUST fail-closed
(exit 1 on a deliberate violation) — otherwise the guard is silently
broken.

## Out of scope

- Live device-share roundtrip with screenshot proof (operator action
  on a real device — the unit-test + visual confirmation above is
  sufficient for the autonomous loop).
- Extending the regex to `subscription`/`upgrade`/`unlock` — future
  pos-6c follow-up if needed.
