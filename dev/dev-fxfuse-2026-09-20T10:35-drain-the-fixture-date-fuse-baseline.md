---
hash: fxfuse
type: dev
created: 2026-09-20T10:35:00-06:00
title: Drain the 29-file hardcoded-fixture-date baseline before the next one freezes deploys
from: debug/debug-imptb1-2026-07-27T18:53-imports-tab-widget-tests-red-on-main.md
status: in-progress
owner: /devx-fxfuse
branch: feat/dev-fxfuse
---

## Goal

`0a5c3d41` (rsh101) installed a grep ratchet that stops **new** hardcoded
fixture dates entering `app/test/`. Nothing drains the **66 literals across 29
files** it grandfathered in. Each one is a live fuse on a known,
already-realized failure mode, and the next to age out will look exactly as
mysterious as the last one did.

This is not hypothetical. The causal chain is established end to end:

1. A test fixture hardcodes `'created_at': '<literal date>'`.
2. A widget filters that surface against a `DateTime.now()`-relative cutoff,
   so the fixture silently ages out of the window.
3. The rows stop rendering, the test fails finding **zero** widgets — a
   signature that reads as "someone broke the feature", not "the clock moved".
4. `flutter-test` goes red. It is the root job `deploy-web` (`ci.yml:462`) and
   `detect-changes` (`:521`) hang off.
5. **Deploys stop.** Prod sat on image `c85e350` from **2026-04-26 to
   2026-07-27** — three months — by exactly this mechanism.

Steps 3–5 are the expensive part: the failure surfaces months after the commit
that "caused" it, names no culprit, and points investigators at recent feature
work. `imptab1` and `imptb1` were both filed against innocent commits; a third
session (`btri01`) filed a duplicate three minutes after the first. The
diagnosis has now been paid for three times.

## Acceptance criteria

- [ ] Every one of the 29 baseline files is triaged against the
      `DateTime.now()`-relative cutoffs it can actually reach, and the
      disposition recorded per file. **Triage, not blanket rewriting** — most
      of these fixtures are almost certainly age-irrelevant and want the
      guard's `// age-independent` marker, not a refactor.
- [ ] Genuinely age-sensitive fixtures are anchored to `now`, following the
      pattern `640987e5` established in `imports_tab_test.dart:147-154`
      (`_fixtureBase` + `_at(offsetMinutes)`), which preserves the relative
      ordering that created-at-descending sort assertions depend on.
- [ ] `app/test/fixture_date_guard_baseline.txt` shrinks accordingly. The
      guard's counts ratchet **both** ways — cleaning a file without lowering
      its count fails the guard too — so the baseline edit is part of the work,
      not follow-up.
- [ ] Ideally the baseline reaches zero and the file is deleted. If any entry
      must survive, its line carries a real rationale replacing the current
      placeholder `pre-existing date fuse (rsh101 baseline)`, which says
      nothing a reader can act on.
- [ ] `flutter test` green (currently 1612 passed / 0 failed).
- [ ] A time-travel check proves the drain worked rather than asserting it:
      re-run the suite with the clock advanced (e.g. `faketime '+120 days'`, or
      a temporary `--dart-define` the fixtures honor) and confirm no new
      zero-widget failures. **Without this the story cannot tell success from
      "the bombs just haven't gone off yet"** — which is precisely how the
      baseline got to 29 files.

## Technical notes

- **Baseline:** `app/test/fixture_date_guard_baseline.txt`, format
  `path:count:rationale`, paths relative to `app/`. 29 entries, 66 unmarked
  literals. Heaviest: `notifications_tab_test.dart` (10),
  `activity_screen_test.dart` (6), `import_activity_detail_test.dart` (6),
  `meal_model_test.dart` (4), `shopping_list_model_test.dart` (4).
- **Guard:** `app/test/fixture_date_guard_test.dart`. Read its header comment
  first — it documents the two escapes (`// age-independent`, baseline entry)
  and the shrink-only ratchet.
- **The cutoff surfaces are not just the Imports tab.** `grep -rn
  "DateTime.now().subtract" app/lib/` finds three 30-day boundaries:
  - `lib/features/activity/imports_tab.dart:168` — the known one. Cuts
    `completed` + `skipped`; `awaiting_review` + `failed` are exempt as
    actionable, which is why only *some* assertions in a file rot.
  - `lib/features/calendar/widgets/plan_meal_sheet.dart:179` — a date-picker
    `firstDate`. A fixture-dated meal outside it is unselectable, so calendar
    fixtures can rot through a different mechanism than list filtering.
  - `lib/features/profile/profile_screen.dart:417`.
  Triage each baseline file against the surface it actually exercises. A
  `meal_model_test.dart` literal that never reaches a cutoff is
  `// age-independent` and costs nothing.
- **Do not relax assertions to get green.** `imptab1` explicitly ruled on this:
  the 30-day cutoff is deliberate product behaviour with See-all as the
  documented escape hatch, so the *widget* holds the correct contract and the
  fixtures move. Same call applies here.
- **Blast radius is test-only** but the payoff is deploy reliability, so this
  is worth its own PR even though no `lib/` code should change.
- Related: `app/README.md` documents a *different* trap that produces a
  similar-looking scatter of widget failures (stale `ink_sparkle.frag` after an
  in-place SDK bump). Rule it out with `flutter clean` before assuming a
  fixture rotted — the two are easy to confuse and both were hit on the same
  day.

## Status log
- 2026-09-20 — filed from `/devx imptb1` Phase 8 gap-filing. imptb1 resolved as
  a duplicate of `imptab1`; this is the systemic residue neither ticket
  covered. `0a5c3d41` stopped the population growing; nothing shrinks it.
- 2026-09-22 — phase 1: claimed on `feat/dev-fxfuse` (worktree `.worktrees/dev-fxfuse`).
  Claim recorded on the feature branch, NOT on `main`: palateful `main` is a
  serialized deploy lane right now (every push cancels the in-flight
  `CI & Deploy`, which carries prod Terraform applies), so this run pushes
  nothing to `main` until the coordinator signals a window.
- 2026-09-22 — phase 2: spec ACs direct (v2 native); 6 ACs; workstream=none;
  red-artifacts=none.
