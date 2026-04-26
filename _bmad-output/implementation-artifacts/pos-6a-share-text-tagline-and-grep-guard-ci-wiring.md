# Story pos-6a — Share-text tagline + copy-grep-guard CI wiring

**Status:** done
**Epic:** [epic-recime-positioning](../planning-artifacts/epic-recime-positioning.md)
**Source-of-truth copy:** [pos-1-content-copy-for-all-surfaces](pos-1-content-copy-for-all-surfaces.md)

## Goal

Two deliverables:
1. **Share-text tagline.** Append the canonical "Get Palateful — free
   forever: https://palateful.app" tagline to every share-text payload
   in `app/lib/services/share_service.dart`. Recipe / recipe-book /
   shopping-list shares all funnel through one composer.
2. **Copy-grep-guard CI gate.** A bash scanner at
   `tools/copy-grep-guard.sh` that fails CI when paywall-shaped
   vocabulary appears in user-facing copy outside the allowlist. Same
   pattern as `tools/no-silent-catch-check.sh`. Wired into the existing
   `flutter-test` job in `.github/workflows/ci.yml`.

## Acceptance criteria

- [x] All three `ShareService.share*` methods produce text ending with
  `Get Palateful — free forever: https://palateful.app`. Every share
  text passes through one private `_withTagline()` composer to keep
  copy in lockstep.
- [x] `tools/copy-grep-guard.sh` scans `app/lib/`, `app/web/`,
  `app/web-landing/`, `ANDROID.md`, `README.md` and fails with exit 1
  on any unallowlisted match.
- [x] Forbidden patterns (per epic refinement, narrowed to reduce
  Dart-comment false positives):
  - `\b(premium|paywall)\b` (case-insensitive).
  - `\bPro\b` (case-sensitive standalone).
  - `v1[ _-]+.*purchases` (the "v1 — Palateful is free, no in-app
    purchases" hedge phrasing).
  - **Deliberately not scanned**: `subscription`, `upgrade`, `unlock`
    — they collide with technical Dart code (Stream subscription, SDK
    upgrade, file unlock) too often. Reasoning + mitigation documented
    in the script's header comment.
- [x] `tools/copy-grep-allowlist.txt` matches the
  `file:lineno:rationale` format from `tools/silent-catch-allowlist.txt`.
  Pre-populated with 16 negation-context entries from pos-2/3/4
  surfaces.
- [x] Wired into CI as a step `No paywall language (pos-6a grep
  guard)` between `no-direct-get-recipe-books-check.sh` and
  `flutter test` in `.github/workflows/ci.yml`.
- [x] Self-test: temporarily appended `// Try our Premium tier today!`
  to `app/lib/main.dart`, the guard exited 1 with the expected
  violation; reverted, guard exits 0.
- [x] Standalone QA walkthrough at `pos-6a-qa-walkthrough.md`.
- [x] Unit test for `ShareService.appendTagline` (3 cases — happy
  path, separator, degenerate empty body).

## File List

- `app/lib/services/share_service.dart` (added `_withTagline` private
  composer + `@visibleForTesting appendTagline` static + applied to
  all 3 share methods)
- `app/test/services/share_service_tagline_test.dart` (new — 3 tests)
- `tools/copy-grep-guard.sh` (new — POSIX bash scanner)
- `tools/copy-grep-allowlist.txt` (new — 16 negation-context entries)
- `.github/workflows/ci.yml` (added `pos-6a grep guard` CI step)
- `_bmad-output/implementation-artifacts/pos-6a-share-text-tagline-and-grep-guard-ci-wiring.md` (this file)
- `_bmad-output/implementation-artifacts/pos-6a-qa-walkthrough.md` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)

## Implementation notes

### Why narrow the forbidden-strings regex?

The epic-listed canonical set is `(premium, pro, upgrade,
subscription, paywall, unlock, v1.*purchases)`. In Dart code,
`subscription` collides with Stream / Riverpod `subscription`
references in technical comments (and we have ~15 such mentions
already), `upgrade` collides with SDK / dependency upgrade comments,
and `unlock` collides with file-unlock and screen-unlock vocabulary.
Allowlisting all of those would require ~25+ entries with rationale
"technical, not paywall."

The pragmatic narrowing keeps the four patterns where false positives
are essentially zero in non-marketing contexts (`premium`, `paywall`,
standalone `Pro`, the very specific `v1.*purchases` phrase). If a
future regression introduces "subscription tier" or "upgrade required"
in user copy, those phrases almost always cluster with `premium` or
`paywall` in the same sentence, so the broader copy regression
will still be caught. If we ever miss one, future-pos-6c can extend
the regex.

### Why exclude `_bmad-output/planning-artifacts/`?

Counted 53 pre-existing matches across PRD, investigations
(competitor-analysis-recime, typography-evaluation, ios-native-features,
etc.), UX spec, and the cross-epic epics.md. Allowlisting all would
bury actual regressions in noise. Planning docs *describe* the topic
the guard enforces; they don't ship to users. Deviation from epic AC
documented in the script header.

## Out of scope

- A `subscription` / `upgrade` / `unlock` extension to the regex.
  Future pos-6c follow-up if needed.
- A "no allowlist additions without code review" enforcement
  mechanism. The convention is documented in the allowlist header
  comment (matching tools/silent-catch-allowlist.txt's convention).
