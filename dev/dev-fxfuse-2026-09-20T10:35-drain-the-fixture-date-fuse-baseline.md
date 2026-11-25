---
hash: fxfuse
type: dev
created: 2026-09-20T10:35:00-06:00
title: Drain the 29-file hardcoded-fixture-date baseline before the next one freezes deploys
from: debug/debug-imptb1-2026-07-27T18:53-imports-tab-widget-tests-red-on-main.md
status: done
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

- [x] Every one of the 29 baseline files is triaged against the
      `DateTime.now()`-relative cutoffs it can actually reach, and the
      disposition recorded per file. **Triage, not blanket rewriting** — most
      of these fixtures are almost certainly age-irrelevant and want the
      guard's `// age-independent` marker, not a refactor.
- [x] Genuinely age-sensitive fixtures are anchored to `now`, following the
      pattern `640987e5` established in `imports_tab_test.dart:147-154`
      (`_fixtureBase` + `_at(offsetMinutes)`), which preserves the relative
      ordering that created-at-descending sort assertions depend on.
- [x] `app/test/fixture_date_guard_baseline.txt` shrinks accordingly. The
      guard's counts ratchet **both** ways — cleaning a file without lowering
      its count fails the guard too — so the baseline edit is part of the work,
      not follow-up.
- [x] Ideally the baseline reaches zero and the file is deleted. If any entry
      must survive, its line carries a real rationale replacing the current
      placeholder `pre-existing date fuse (rsh101 baseline)`, which says
      nothing a reader can act on.
- [x] `flutter test` green (currently 1612 passed / 0 failed).
- [x] A time-travel check proves the drain worked rather than asserting it:
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
- 2026-09-22 — phase 3: drained all 29 baseline files. Of the 66 `created_at`
  literals: 18 anchored to `now` (7 files, `_fixtureBase` + `_at()` per
  `imports_tab_test.dart`), 48 marked `// age-independent` (22 files), 0 left
  unmarked. Anchored 13 sibling literals on keys the guard does not scan
  (`updated_at`, `archived_at`, `dismissed_at`) where they shared a formatter
  with an anchored `created_at`. Deleted
  `app/test/fixture_date_guard_baseline.txt`; the guard now reads an absent
  baseline as an empty one. Added `app/tool/time_travel_check.sh` — libfaketime
  cannot be used (it crashes the Dart VM at `OS::GetCurrentTimeMillis`,
  `os_macos.cc:67` / `os_linux.cc:474`, at 0.9.10 and 0.9.12, on macOS arm64
  and in a Linux container), so the script shifts fixture dates backwards
  instead, which is arithmetically identical for any `now - fixture`
  comparison.
- 2026-09-22 — phase 4: 3-agent parallel adversarial review (blind hunter,
  edge-case hunter, acceptance auditor) on a 36-file / 493-line diff; 23
  findings, ALL fixed in-place. Most load-bearing: the harness was the only
  thing that could falsify 48 free-text `// age-independent` claims and it was
  wired to nothing, so it now runs nightly via
  `.github/workflows/fixture-time-travel.yml` — with a negative control step
  that re-freezes a fixture anchor and fails the job if the shifted run does
  NOT go red, because a check that has stopped biting reports green exactly
  like a drained suite. Other fixes: the guard's fold was defeated by one
  comment on a `created_at:` key line (silent under-detection — the failure
  mode its own header calls unacceptable); `contains('age-independent')`
  accepted `// NOT age-independent` and prose as opt-outs, now an anchored
  comment-scoped match with negation rejection; `raised`/`stale` became
  unreachable once the baseline was deleted, so the comparison is extracted
  into `compareToBaseline()` with 5 unit tests; the constructor shifter emitted
  invalid Dart for >3-arg `DateTime(...)` and was blind to the year-only and
  dartfmt-wrapped forms; `--days` accepted negative values (shifting fixtures
  into the FUTURE, where every cutoff passes trivially and the run reports a
  vacuous green); an absolute target path ran the real unshifted tree; a no-op
  shift reported success; the default moved 400 → 406 (a multiple of 7, so
  fixture weekdays are preserved for `recurrence_field.dart:141`); `_fixtureBase`
  moved from `now - 2h` (exactly on the 1h/2h formatter boundary, so siblings
  5 minutes apart rendered different labels) to `now - 90min`; the rf2 goldens
  lost their `+00:00` wire format to `toIso8601String()` and got it back; and
  `recipe_list_table_view_regression_test.dart` claimed a recipe updated six
  months before it was created.
- 2026-09-22 — phase 5: the first post-review `--days 406` run went RED — 3
  failures in `fuzzy_expiry_text_test.dart`, all false positives of a second
  kind the harness had not documented. That group injects its own `now`, so it
  can never rot; but shifting both sides of the interval landed it across the
  2025 spring-forward, which shortened the delta by an hour and dropped
  `inDays` from 5 to 4. A multiple-of-7 shift preserves weekdays, not DST
  offsets. Tagged `no-time-travel` with that reason, and the class is now named
  in the script header next to the absolute-date class. Re-ran both suites
  clean afterwards; numbers in the phase-5b line below.
- 2026-09-22 — phase 5b: both suites green on the fixed tree, exit codes
  captured directly rather than read off a summary line. `flutter test` →
  **1642 passed, exit 0** (1633 pre-existing + 9 new guard tests).
  `tool/time_travel_check.sh` (+406 days) → **1642 passed, exit 0**, shifting
  134 ISO literals + 64 `DateTime(...)` constructors across 72 files with 15
  dates held back by `no-time-travel`. Constructor coverage is new in this
  phase: before it, the check saw only ISO strings, so the "+400d green" I
  reported mid-review covered less than it sounded like — that figure is
  superseded, not merely improved on.
- 2026-09-22 — phase 5c: one full-suite run under heavy parallel load came
  back 1641/1, the failure being the 200ms grid↔table perf assertion in
  `recipe_list_table_view_regression_test.dart:232`. Not this change: the
  stopwatch wraps only the view toggle, fixture construction happens before it
  starts, the same tree passed 1642 when the machine was idle, and the file
  passes 3/3 standalone. Filed as `debug/debug-perfflake1` + a DEBUG.md row
  rather than absorbed into this story — a wall-clock assertion that a busy
  host can red is a product judgment about what the gate protects.
- 2026-09-22 — phase 7: rebased onto `840af8e2` after main moved (#51, #56, #60
  and bookkeeping). Conflicts in DEV.md / TEST.md / DEBUG.md only, all
  keep-main's-rows-and-append. Two substantive re-checks rather than a
  force-resolve, because #56 touched both files this story leans on:
  `imports_tab.dart`'s 30-day cutoff still exempts `awaiting_review` + `failed`
  and still cuts `completed` + `skipped` (the triage's premise holds), and
  `imports_tab_test.dart`'s `_fixtureBase` still matches the nightly job's
  control regex exactly once (verified by running the regex, not by reading
  it) — had #56 reshaped that anchor, the control would have failed its
  `assert n == 1` every night. Re-ran everything on the new base: guard 23
  tests green, `flutter test` **1688 passed / exit 0** (up from 1642; main
  added tests), `tool/time_travel_check.sh` **1688 passed / exit 0** shifting
  134 ISO + 64 constructor dates across 72 files. Identical shift counts to
  the pre-rebase run, so main's new tests carry no fixture dates of their own.
- 2026-09-23 — merged via PR #54 (squash → `37d02bb0`), base `1bab0aa8`, green
  at `e579f0d3`: `CI & Deploy` + `devx-ci` both completed/success, no check in
  FAILURE/ERROR/CANCELLED, `mergeStateStatus: CLEAN`. Final local numbers on
  that tree: `flutter test` 1688/exit 0, `tool/time_travel_check.sh --days 406`
  1688/exit 0, guard 23 tests green.
- 2026-09-23 — **open loop, not a closed one**: the nightly
  (`.github/workflows/fixture-time-travel.yml`, 09:12 UTC) has never run in
  CI. Its negative-control step has only ever been proven on a laptop, so
  until the first run reports, the claim "the check still bites in CI" is
  untested. Verification filed in MANUAL.md. **If that step fails, the harness
  has stopped detecting a frozen fixture — it does NOT mean a fixture rotted,
  and the two want opposite responses** (fix the harness vs. anchor a
  fixture); the job prints `::error::` lines saying so.

