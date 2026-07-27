---
hash: rcres1
type: debug
created: 2026-07-27T18:21:00-06:00
title: Deleted recurring-meal occurrence resurrects on next materialize pass
from: dev/dev-bugscal3b-2026-07-27T17:07-backend-recurrence-expansion.md
status: in-progress
owner: /devx-loop-2026-07-27T17-03-31-550-87857
branch: feat/debug-rcres1
---

## Goal
Deleting a single occurrence of a recurring meal stays deleted. Today the delete path detaches the row from its rule, which makes it invisible to the materializer's dedup check — so the same slot re-inserts on the next window advance.

## Acceptance criteria
- [ ] Repro exists: a failing test that deletes one occurrence via the single-occurrence path, advances the materialization window, and asserts the slot is NOT re-inserted
- [ ] Root cause documented with evidence in the status log
- [ ] Fix + regression test in `libraries/utils/test/test_materializer.py` (19 existing tests, none cover detach-then-rematerialize)
- [ ] Decide + fix the sibling inconsistency: materialized rows never get `is_recurring` set (`materializer.py` insert_values omits it, so it stays False; clients currently key off `recurrence_rule_id` instead — either set the flag or document it as intentionally vestigial)

## Technical notes
- Mechanism: `delete_recurrence_rule.py:155-158` detaches (comment says "Detach so a subsequent materialize pass doesn't re-insert" — inverted: detaching causes re-insert). `materializer.py:181-190` builds `existing` by filtering `MealEvent.recurrence_rule_id == rule.id`, so the detached row is invisible; its timestamp lands in `missing` (`materializer.py:214`) and the partial unique index (`meal_event.py:61-64`, `WHERE recurrence_rule_id IS NOT NULL`) doesn't block the insert.
- Candidate fixes: a tombstone (keep `recurrence_rule_id` + a `deleted`/`skipped_at` marker instead of detaching), or have the materializer also exclude rows whose (rule_id, scheduled_at) matches a detached-row audit record.
- Found 2026-07-27 during BMAD→devx import verification of bugs-cal-3b (see that spec's status log).

## Status log
- 2026-07-27T18:21 — filed from bugs-cal-3b verification findings during BMAD→devx migration
- 2026-07-27T12:26:13-06:00 — claimed by /devx in session /devx-loop-2026-07-27T17-03-31-550-87857
- 2026-07-27T18:34:59.715Z — loop iteration 1: Replaced the detach-on-delete behavior with an attached tombstone so single-occurrence deletions survive materialization window advances, set is_recurring on materialized rows, and added 7 regression tests backed by a new in-memory session fake.
  - Change: delete_recurrence_rule.py `_delete_single_occurrence` now tombstones (sets archived_at, keeps recurrence_rule_id) instead of detaching, so materialize()'s dedup query still sees the slot as occupied
  - Change: materializer.py excludes tombstones from the returned row set and from title-rename propagation, while keeping them in the dedup set that suppresses re-insertion; docstring/comments rewritten to state the tombstone contract
  - Change: materializer.py insert_values now sets is_recurring=True on materialized rows (AC4 decision: fix the flag rather than document it as vestigial — nothing filters on it server-side, but it ships on every meal-event response schema)
  - Change: update_recurrence_rule.py move-to-calendar comment corrected: tombstones now ride the cascade; only pre-fix detached rows remain orphaned
  - Change: Added an in-memory _FakeSession/_FakeQuery harness to test_materializer.py that interprets SQLAlchemy binary-expression filters, is_/is_not, session.delete, and pg_insert ON CONFLICT DO NOTHING including the partial unique index
  - Change: Added 7 tests: no-resurrection on window advance, survival across repeated passes, tombstone excluded from return value, no title rewrite on tombstones, tombstone dropped when its slot leaves the expected set, a root-cause guard proving detach causes a duplicate, and is_recurring=True on materialized rows
  - Change: Updated services/api/tests/test_recurrence_rule.py::test_delete_scope_this_occurrence to assert recurrence_rule_id is preserved rather than nulled
  - Learning: Root cause with evidence: materializer.py:185-192 filters existing rows by `recurrence_rule_id == rule.id`; the delete path's `recurrence_rule_id = None` made the archived row invisible to that query, so its timestamp fell into `missing` (line ~214) and re-inserted. The partial unique index (meal_event.py:61-64, `WHERE recurrence_rule_id IS NOT NULL`) also can't block a NULL-rule row. The inline comment claiming detach prevents re-insert was inverted.
  - Learning: The tombstone fix needs no schema change and no new column — archived_at already exists on JoinsBase, and list_meal_events (line 121) plus every other read path already filter `archived_at IS NULL`, so the tombstone is invisible to clients for free.
  - Learning: Detaching was also producing a silent duplicate on rule edits: the detached row stayed on the calendar while materialize re-inserted a live row at the same slot. The tombstone fixes that too.
  - Learning: libraries/utils has zero DB-backed test infrastructure (no conftest.py, no sqlite/testcontainers). Testing materialize() end-to-end requires a fake Session; SQLAlchemy binary expressions are evaluable via `criterion.left.name` / `criterion.right.value` / `criterion.operator`, but `is_`/`is_not` carry SQLAlchemy's own operator callables that expect ClauseElements and must be special-cased. pg_insert values are reachable via `stmt._multi_values[0]`.
  - Learning: Running tests in a fresh worktree: `poetry install` is not needed — `PYTHONPATH=libraries/utils:services/api/src /Users/leonidbelyi/personal/palateful/.venv/bin/python -m pytest` reuses the main repo's venv while resolving utils/api source to the worktree. services/api tests additionally require DATABASE_URL to be set (any value; CI uses postgresql://postgres:postgres@localhost:5432/test) or every client-fixture test errors at import.
  - Learning: AC2 asks for the root cause in the spec's Status log, which this iteration cannot edit (loop-owned) — the evidence is captured here and in code comments for the loop to transcribe.
