---
hash: imptb1
type: debug
created: 2026-07-27T18:53:00-06:00
title: imports_tab_test.dart — 3 widget tests red on main
from: btri01
spawned:
  - dev/dev-fxfuse-2026-09-20T10:35-drain-the-fixture-date-fuse-baseline.md
status: done
owner: /devx-2026-09-20T0958-90325
branch: feat/debug-imptb1
---

## Goal
`flutter test` on `main` is not green: three widget tests in
`app/test/features/activity/imports_tab_test.dart` fail. Find out whether the
tests or the Imports tab drifted, and make the suite green again.

## Reproduction

```bash
cd app && flutter test test/features/activity/imports_tab_test.dart
```

Result on `main` (746bbbe) and on `feat/debug-btri01` alike — 5 passed, 3
failed. Confirmed independent of any btri01 change by stashing the branch's
only `app/lib` edit and re-running: same three failures.

| Test | Failure |
|---|---|
| `renders all four sections with one row each` (line 294) | `Found 0 widgets with text containing "Auto-Imported · 1"` — expected exactly one |
| `green row taps navigate to /recipes/:id` | `tap()` on `find.text('Ship it')` found 0 widgets |
| `buckets by item.status — items still render when parent job.status differs` (line 542) | same shape — expected row text absent |

All three are "the row I expected to render isn't there", which points at one
cause: either the section header / row copy changed (`Auto-Imported · N`), or
the bucketing that decides which rows land in which section changed, and the
test's fixtures no longer land where it looks for them.

## Acceptance criteria
- [x] Root cause identified: test drift vs. a real Imports-tab regression —
      say which, with the commit that introduced it
- [x] `flutter test test/features/activity/imports_tab_test.dart` green
- [x] `flutter test` (whole app) green, or any *other* remaining failure
      filed separately
- [x] If it was a real regression, the user-visible symptom is described
      (which rows stopped rendering, in which section)

## Technical notes
- Prime suspect list: anything that touched Imports-tab bucketing or section
  copy after the test was written. `git log --oneline -- app/lib/features/activity/imports_tab.dart`
  is the first stop.
- Note bas-2 renamed "Archive" → "Dismiss" across this exact surface. If the
  copy assertions drifted once already, they may have drifted again.
- The non-failing noise in the same run (`API Error: 400 …` from
  `non-blue swipe archives + fires API`) is an intentional error-path fixture,
  not a failure — don't chase it.

## Status log
- 2026-07-27T18:53 — filed by btri01 after a full-suite run during shopping-cart
  triage: 1530 passed, 3 failed, all three in this file, all pre-existing on main
- 2026-09-20T09:58:48-06:00 — claimed by /devx in session /devx-2026-09-20T0958-90325
- phase 2: spec ACs direct (v2 native); 4 ACs; workstream=none; red-artifacts=none

### Root cause — AC #1. Two causes, neither a regression; this ticket is a duplicate.

> **Read this even if you skim the rest.** The fixture rot diagnosed below is
> not a CI-hygiene story. `flutter-test` is the root job `deploy-web` hangs
> off (`ci.yml:462`, `:521` for `detect-changes`), so aged-out test fixtures
> **froze production deploys** — prod sat on image `c85e350` from
> **2026-04-26 to 2026-07-27**, three months, because a `'created_at'` literal
> in a widget test drifted past a 30-day cutoff. Source is the header comment
> of `app/test/fixture_date_guard_test.dart` (landed by `0a5c3d41`), which is
> why that guard exists and why its baseline only shrinks. If you are
> reconstructing the freeze as a credentials or merge-conflict problem, this
> was the mechanism for most of its duration.


The three failures this spec was filed against **no longer exist**, and the
one failure observable today is a different thing wearing the same filename.
Separating them is the whole answer.

**(a) The original three: test drift, already fixed — `640987e`.** Filed
2026-07-27T18:53. `debug/debug-imptab1-…` was filed at **18:50**, three
minutes earlier, by a different session (from `bqa101` Phase 7; this one came
from `btri01` full-suite verification). Same three tests, same
zero-widgets-not-wrong-widgets signature. imptab1 root-caused it that evening:
the fixtures hardcoded `2026-04-18`, and `imports_tab.dart:168` drops
`completed` + `skipped` items past a 30-day recency cutoff (`awaiting_review`
+ `failed` are exempt as actionable). Around 2026-05-18 the fixtures aged out
and those two sections stopped rendering — a time bomb, not a commit. None of
the suspects this spec's Technical notes nominate were implicated: not the
`Archive` → `Dismiss` rename from bas-2, not `0c6bf52` / `0e643f3` /
`f5f714c`. The contract call went to the **widget**, so fixtures were anchored
to `now` via `_fixtureBase`/`_at()`
(`imports_tab_test.dart:147-154`) instead of relaxing assertions. Shipped as
PR #6, squash **`640987e`**, 2026-07-27T19:20.

So there is no commit that "introduced" the original breakage, and **AC #4 is
vacuous by the same finding**: no user-visible regression ever existed. The
30-day cutoff is deliberate product behaviour with See-all as the documented
escape hatch; no row stopped rendering for any real user, only for fixtures
that had aged out of the window.

**(b) What is red today: a stale build artifact, local-only, not in the repo.**
Observed on `main` @ `dfbff598`: **7 passed / 1 failed**, not 5/3. The two
bucketing tests (`renders all four sections with one row each`,
`buckets by item.status …`) now pass — `640987e` holding. The survivor,
`green row taps navigate to /recipes/:id`, fails on a different exception
entirely:

```
Exception: Asset 'shaders/ink_sparkle.frag' manifest could not be decoded:
INVALID_ARGUMENT: Unsupported runtime stages format version. Expected 1, got 0.
  #0  new FragmentProgram._fromAsset (dart:ui/painting.dart:5337:7)
```

Not "Found 0 widgets" — the row renders fine; rasterizing its ink ripple
throws. `fltup1` documented this exact signature on 2026-07-30: the 3.41.7
engine reading a shader compiled by 3.38.9. Direct evidence here —
`app/build/unit_test_assets/shaders/ink_sparkle.frag` in the main checkout is
dated **Jul 27 11:08**, three days *before* the SDK bump, and
`app/.dart_tool` dates to Apr 18. fltup1 ran its `flutter clean` inside
`.worktrees/dev-fltup1`, so the main checkout was never cleared and has been
carrying the 3.38.9 shader ever since.

Hypothesis → check → result, run as a controlled pair on identical code:

| # | Hypothesis | Check | Result |
|---|---|---|---|
| 1 | Not the bucketing/copy drift this spec assumes | Read the failure text | Shader decode, not a missing finder. 2 of the 3 named tests pass |
| 2 | Stale artifact, not code | Same SHA in a fresh worktree with no `build/` | **8/8 pass** |
| 3 | The artifact is *the* cause, not a correlate | `flutter clean && flutter pub get` in the main checkout, re-run | **8/8 pass** — zero code edits |

Test 3 is the load-bearing one: same commit, same tree, only the stale shader
removed, red → green.

**AC #2/#3 — green.** `imports_tab_test.dart` 8/8; full `flutter test`
**1607 passed / 0 failed** (1m07s). No other failure remains to file. The
`API Error: 400` line from `non-blue swipe archives + fires API` is the
intentional error-path fixture this spec's notes already excluded — it prints
on a passing test.

**Why one test here and 94 in fltup1 — selectivity noted, mechanism NOT
established.** Only tests that rasterize a Material ink ripple touch the
shader, so the subset is small either way. Beyond that I did not verify the
rule, and the obvious guess is wrong: the README draft initially claimed the
survivor was "the only test in the file that taps an `InkWell`", which is
false twice over — `imports_tab.dart` contains no `InkWell`/`ListTile` at all
(both tap paths go through the shared row widget at `:717`), and two tests
tap, `green row taps …` (`:474`) and `yellow row taps …` (`:598`). Only the
green one failed, and it ran first. That is consistent with the failed
`FragmentProgram` being cached per test-file isolate so later ripples in the
same file no-op — and with fltup1's 94 failures across 216 test files being
roughly one per rippling *file* rather than per test. Consistent with, not
demonstrated by: reproducing it needs a 3.38.9-compiled shader, which
`flutter clean` has already destroyed. The claim was cut from the README
rather than hedged there. The selectivity is what makes the trap read as
"an arbitrary scattering of unrelated widget failures" instead of one
environmental cause — and it is why the remediation is now written into
`app/README.md` rather than left in a closed spec's status log, where neither
this session nor the one that filed this ticket would have found it.

**Duplicate disposition.** imptb1 adds nothing over imptab1 and is closed as a
duplicate of it. The deliverable is the README note plus this record; no Dart
changed, because nothing in the repo was wrong.

- phase 3: no code fix — root cause (a) shipped in `640987e`, (b) is a local
  build artifact. Durable output is the `ink_sparkle.frag` troubleshooting
  section in `app/README.md` (+33 lines), placed there because the trap cost
  two sessions and was previously recorded only inside fltup1's status log.
- phase 4: single-pass adversarial review (diff is 2 markdown files, ~+33
  lines of README — far below the >500-line multi-agent threshold); 4 findings,
  ALL fixed in-place. Most load-bearing (HIGH): the README asserted the failing
  test was "the only test in the file that taps an `InkWell`" — a mechanism I
  inferred rather than checked, and `grep` disproved both halves (no `InkWell`
  anywhere in `imports_tab.dart`; two tests tap). Shipping it would have put a
  confident falsehood in the one document written to stop the next person
  guessing. Replaced with the verified selectivity only, and the failed guess
  recorded above so it isn't re-derived. Others: (MED) the fltup1 reference was
  elided to `dev/…-fltup1-…`, ungreppable in the exact moment a reader needs
  it — expanded to the full path; (LOW) that expansion pushed a line past the
  file's wrap width — rewrapped; (MED) `devx devx-helper claim --type debug`
  wrote `owner:` without consuming the spec's existing empty `owner:` key,
  leaving duplicate keys in the frontmatter — deduped here and reported to the
  coordinator as a CLI bug, since it will recur on every debug-spec claim.
  Re-review of the changed hunks clean; every file:line citation in this log
  re-verified by grep after editing.
- phase 5: touched surface = `app/README.md` (project `app`) + this spec.
  Gate for `app` per `devx.config.yaml` is `flutter test` → **1607 passed, 0
  failed**, exit 0, 1m07s. No Dart, Python or Node source changed. Coverage is
  informational under YOLO.
- 2026-09-20 — addendum, prompted by the coordinator session converging on the
  same finding mid-run. It cited **two** commits as having fixed the three
  tests: `640987e5` and `0a5c3d41` (rsh101, PR #7). Checked rather than
  accepted: `git show 0a5c3d41 --stat` does **not** touch
  `imports_tab_test.dart` at all. It adds `app/test/fixture_date_guard_test.dart`
  + `fixture_date_guard_baseline.txt` — a grep ratchet that fails any *new*
  hardcoded `'created_at': '<year>-…'` literal under `app/test/`, with
  `// age-independent` and a shrink-only baseline of the 29 files already on
  the fuse as its two escapes. So the correct split is: **`640987e5` fixed
  these three tests; `0a5c3d41` made the class of rot unable to recur.** Both
  belong in the record, for different reasons. Worth noting from that guard's
  own header comment: this fuse is why prod sat frozen on image `c85e350` from
  2026-04-26 to 2026-07-27 — `flutter-test` is the root job `deploy-web`
  (`ci.yml:462`) hangs off, so aged-out fixtures froze deploys, not just CI —
  elevated to a callout at the top of the root-cause section, since three
  sessions were reconstructing that freeze as a credentials-and-conflicts
  problem while a date-fused fixture was the actual mechanism.
  The coordinator independently hit the stale-shader trap too (94 false
  failures, cleared by `rm -rf app/build/unit_test_assets`), which is the same
  root cause as (b) above reached from a second machine-state — `flutter clean`
  is the broader form of that `rm`. Independent reproduction is why the
  `app/README.md` note is worth its 33 lines.
  Suite count differs harmlessly between sessions: 1607 here on `main`
  @ `dfbff598`, 1612 on the coordinator's rebased branch.
- phase 8: DEBUG.md `[/]` → `[x]` flip deliberately NOT made here — handed to
  palateful-4f, which is already writing DEV.md/DEBUG.md/MANUAL.md in one
  commit. Two writers on that file was the avoidable half of today's conflicts,
  so #26 touches no backlog file at all.
- phase 8 (gap-filing): filed `dev/dev-fxfuse-2026-09-20T10:35-drain-the-fixture-date-fuse-baseline.md`.
  `0a5c3d41`'s ratchet stops the fused-fixture population growing but nothing
  drains it: **66 literals across 29 files** still grandfathered in
  `app/test/fixture_date_guard_baseline.txt`, each a live fuse on the exact
  mechanism that froze prod on `c85e350` for three months. Sharpened while
  writing it — `grep -rn "DateTime.now().subtract" app/lib/` returns **three**
  30-day boundaries, not one: `imports_tab.dart:168`,
  `plan_meal_sheet.dart:179` (a date-picker `firstDate`, so calendar fixtures
  rot by unselectability rather than by list filtering) and
  `profile_screen.dart:417`. That reframes the work as triage against three
  surfaces rather than a blanket rewrite, and most of the 29 likely want the
  guard's `// age-independent` marker instead of a refactor. The story carries
  a time-travel AC (run the suite with the clock advanced) because otherwise it
  cannot distinguish success from "the bombs haven't gone off yet" — which is
  how the baseline reached 29 files in the first place.
