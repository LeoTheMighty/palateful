---
hash: rsh101
type: dev
created: 2026-07-27T12:30:00-06:00
title: Unblock the deploy path on main — repair the date-fused Flutter fixtures
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: in-progress
owner: /devx-2026-07-27T1253-25281
branch: feat/dev-rsh101
---

## Goal

Nothing in this workstream can reach production until `flutter-test` is
green. It is a root job (`ci.yml:304`) sitting in the `needs:` list of both
`deploy-web` (`ci.yml:462`) and `detect-changes` (`ci.yml:521`), so its 3
failures skip every deploy job — prod has run image `c85e350` since
2026-04-26. The 3 failures are a **date time-bomb**, not a regression:
fixtures frozen at `2026-04-18T10:*` against a 30-day `DateTime.now()`
cutoff. Fix belongs in the test, not the widget.

**Deadline: 2026-07-29** (G-1 — the next scheduled rotation).

## Acceptance criteria

- [ ] `cd app && flutter test` reports **0 failures** (currently 3 of 1524).
- [ ] Fixture timestamps for `completed`/`skipped` items (`:277`, `:445`,
      `:518`, `:525`) are `DateTime.now()`-relative. The `awaiting_review`
      fixture at `:510` (`item-buried-review`) is age-independent and stays
      hardcoded.
- [ ] The two previously-masked assertions at `:543` (`find.text('Skipped
      photo')`) and `:544` (`find.textContaining('Skipped · 1')`) both run
      and pass — the run aborts at `:542` today, so neither is currently
      reached.
- [ ] A grep guard under `app/test/` fails on any new hardcoded year literal
      in a `created_at` fixture, and is demonstrated failing when one is
      reintroduced.
- [ ] On the `main` push: `flutter-test` green, `deploy-web` reaches
      `success`, `detect-changes` **runs** (not skipped).
- [ ] The 2026-05-03 `deploy-web` outcome — reproduced or not — is recorded
      in this spec's status log. If reproduced, pin `flutter-version`
      (`ci.yml:467-470`) and `wrangler@latest` (`:493`) and re-run.
- [ ] The status log states explicitly that E-1's `deploy-services` half is
      deferred to rsh102 — not silently dropped.

## Technical notes

- The 30-day cutoff is **intentional product behavior**, commented at
  `app/lib/features/activity/imports_tab.dart:165-167` and applied at `:168`
  to `completed` (`:183-189`) and `skipped` (`:190-195`). Changing the widget
  to satisfy a stale fixture would delete a shipped product decision.
- **This phase cannot reach `deploy-services`, and must not try.** An
  `app/`-only commit leaves `services_to_build` empty (`ci.yml:592-604`), so
  `deploy-images` (`:641-643`), `terraform-prod` (`:703-705`) and
  `deploy-services` (`:845-851`) all skip. `deploy-web` *does* run, so the
  2026-05-03 `deploy-web` question is answerable here; the
  `deploy-images (parser)` question is not, and moves to rsh102.
- 39 test files under `app/test/` carry `2026-0*` literals on the same fuse.
  The repo-wide sweep is explicitly NOT in scope; the guard exists so one of
  the other 36 crossing the cutoff mid-workstream does not silently re-red
  `flutter-test` and skip the deploy graph for every remaining phase.
- Files: `app/test/features/activity/imports_tab_test.dart`, a new grep-guard
  test under `app/test/`, and **conditionally** `.github/workflows/ci.yml`.
- RED artifact: `app/test/features/activity/imports_tab_test.dart` (E-1,
  first half) — already failing. Re-run it; do **not** re-author it to pass.
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 1.

## Status log

- 2026-07-27T12:30 — emitted from plan 462355 at RED-gate PASS. E-1 observed
  RED right-reason (3 failures, fixture dates past the 30-day cutoff); see
  `_devx/workstreams/rotation-self-heal/evals/RED-report.md`.
- 2026-07-27T12:53:05-06:00 — claimed by /devx in session /devx-2026-07-27T1253-25281
