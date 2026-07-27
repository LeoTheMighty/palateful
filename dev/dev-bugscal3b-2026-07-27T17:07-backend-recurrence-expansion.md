---
hash: bugscal3b
type: dev
created: 2026-07-27T17:07:00-06:00
title: Backend server-side recurrence expansion in ListMealEvents
from: _bmad-output/planning-artifacts/epic-bugs-calendar-ux.md
status: superseded
branch: feat/dev-bugscal3b
---

## Goal
`ListMealEvents` currently returns raw `meal_event` rows only — it does not expand recurring occurrences server-side (confirmed by the bugs-cal-3 audit, 2026-04-16). Add server-side expansion so a recurring meal (e.g. "pizza Friday", `FREQ=WEEKLY`) renders as individual occurrences within any requested calendar window. This is the gating backend work that unblocks the deferred bugs-cal-3 recurrence UI story.

## Acceptance criteria
- [ ] `ListMealEvents` expands recurring meal_events server-side within the requested date window: each occurrence is returned as its own entry with its concrete occurrence date, carrying the parent series identity (`is_recurring`, series/meal_event id, recurrence rule) so clients can distinguish series occurrences from one-offs.
- [ ] Expansion supports the RRULEs bugs-cal-3 will write: `FREQ=DAILY`, `FREQ=WEEKLY`, `FREQ=MONTHLY`, with optional `recurrence_end_date` honored (no occurrences emitted past the end date or outside the requested window).
- [ ] Uses existing columns on `meal_event` (`is_recurring`, RRULE, `recurrence_end_date`) — no schema migration (per bugs-cal-3 AC4: "All existing columns — no migration").
- [ ] Non-recurring meal_events are returned exactly as before; the response shape stays backward compatible for the current Flutter client.
- [ ] Occurrences that were converted to independent one-offs (bugs-cal-1 unschedule-this-occurrence + create-one-off flow, and bugs-cal-3 AC6 "Never" downgrade) are not double-emitted alongside their former series.
- [ ] Time-zone correctness: expanded occurrences keep the meal's original local time across the window (epic Definition of Done: "meals stay at their original local time").
- [ ] Tests: unit tests for the expansion helper (window clipping, end-date cutoff, daily/weekly/monthly, monthly edge cases like day-31, empty window) plus an API-level test asserting `ListMealEvents` returns expanded occurrences for a recurring row and unchanged output for one-offs.
- [ ] Sprint status: bugs-cal-3 can move out of `deferred` once this lands (it defers "until backend expansion lands under bugs-cal-3b").

## Technical notes
- The epic file has no dedicated bugs-cal-3b section — the story exists only as a conditional row in the story table ("*(conditional)* Backend server-side recurrence expansion... Only if audit in bugs-cal-3 reveals missing server expansion", ~1 d, P1) and in bugs-cal-3 AC1 ("If it doesn't: spawn `bugs-cal-3b-backend-recurrence-expansion`... this story defers until bugs-cal-3b lands"). Goal/ACs above are synthesized from the bugs-cal-3 section (ACs 1, 4, 5, 6, 8), the epic Definition of Done, and the sprint-status.yaml audit comment ("Audit 2026-04-16 (bugs-cal-3): ListMealEvents does NOT expand recurring occurrences server-side. Returns raw meal_event rows only.").
- Key files (from the bugs-cal-3 section): modify `services/api/src/api/v1/meal_event/list_meal_events.py`; reuse `libraries/utils/utils/models/meal_event.py` (columns already present).
- Consider `dateutil.rrule` for expansion rather than hand-rolling iCalendar parsing; keep the parser tolerant of only the three FREQ values bugs-cal-3 writes.
- Scope is backend-only. The plan-meal-sheet recurrence UI (dropdown, "Ends on" picker, edit semantics) stays in bugs-cal-3.
- Original BMAD story key: bugs-cal-3b-backend-recurrence-expansion.

## Status log
- 2026-07-27T17:07 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration
- 2026-07-27T18:20 — verified against main: SUPERSEDED by epic-recurring-meals-foundation/-editing, which deliver the user-visible outcome via slot-rule + pre-materialization (list_meal_events.py:86-107, materializer.py:153-247) instead of on-the-fly RRULE expansion. AC1/4/6/7 satisfied; AC2 partially void (grammar is weekly/biweekly/monthly-nth, no DAILY); AC3 void by design (new meal_recurrence_rules table). Residual defect found during verification (single-occurrence delete → detach → materializer re-inserts the slot; is_recurring never set on materialized rows) filed as debug/debug-rcres1. bugs-cal-3 recurrence UI's blocker no longer exists.
