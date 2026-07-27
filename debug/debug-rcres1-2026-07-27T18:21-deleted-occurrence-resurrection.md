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
