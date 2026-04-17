<!-- refined via party-mode 2026-04-17 -->
# Epic: Recurring Meal Plans — Foundation (Slot-Based Recurrence, MVP Grammar)

## Overview

The calendar today treats every meal as a one-off. Leo re-types Pizza Friday, the Monday lunch salad, and the weekday-breakfast smoothie every week. The previously-deferred `bugs-cal-3` story proposed iCalendar RRULE bolted onto `meal_event` — that path is replaced by this epic. Recurrence here is **slot-based** ("Every Monday dinner"), not time-based, and lives in a new `meal_recurrence_rules` table. Rules materialize into concrete `meal_events` rows inside a rolling 9-week window so every existing read path (calendar list, shopping-list aggregation, prep steps, invites) keeps working unchanged.

**Goal:** When Leo finishes this epic, setting up "Pizza every Friday dinner" is one sheet and two taps. The next 8 Fridays fill in on his calendar automatically with the Pizza recipe attached; each tile is visually marked as recurring; he can End Series Today from any occurrence.

## End-User Flow (MVP — v1 grammar)

1. Leo opens Calendar → taps the FAB → the plan-meal sheet appears.
2. He types "Pizza," picks the Pizza recipe from autocomplete, picks "Friday" for the date, picks "Dinner" slot.
3. Below Meal Type he now sees a new **Repeats** row: `Repeats: Never ▾`.
4. He taps it → a compact picker appears: chips `Never | Weekly | Every other week | Monthly (first Friday)`. Below the chip row: day-of-week multi-select (Mon–Sun) with preset pills `Weekdays` (Mon–Fri) and `Weekends` (Sat–Sun). Below that: an optional "Ends on" date picker (default blank = forever).
5. He picks **Weekly**, leaves Friday selected, leaves end-date blank, taps Done.
6. The sheet's save button now says **"Add Recurring Meal"** (subtle copy change to avoid surprise). He taps it.
7. The sheet dismisses. A snackbar reads "Repeating Friday dinners added." The calendar immediately shows Friday dinner with the Pizza recipe, this week and every Friday of the next 8 weeks — each tile has a small repeat-arrow glyph in the corner.
8. Leo taps next Friday's pizza tile → the meal detail sheet appears with a new "Recurring" badge and a summary line "Every Friday dinner · Pizza." The sheet's primary and secondary actions are unchanged from the existing epic (Open Recipe / Reschedule / Unschedule / Mark as Cooked), plus a new row at the bottom: **End series today**.
9. If he taps **End series today** → confirmation "Stop repeating Pizza every Friday? Future occurrences will be removed." → tap Stop → future Friday pizzas vanish, past ones (including today's, if already past) remain untouched.

Note: this epic ships with "edit via delete + recreate" semantics only. The GCal-style "This / Following / All" prompts, plus recipe-swap and reschedule on a recurring occurrence, land in `epic-recurring-meals-editing`. From a recurring occurrence in this epic: Open Recipe always works; Mark as Cooked affects only that occurrence (existing behavior); Reschedule and Unschedule on a recurring occurrence behave as single-occurrence actions (detach-on-edit, below).

**Detach-on-edit policy** (applies this epic, kept stable forward): any time the user changes something on a recurring `meal_event` row that is *not* End Series Today (e.g., Reschedule, Unschedule, eventually recipe-swap), the row's `recurrence_rule_id` is cleared and the row becomes a one-off. The rule keeps materializing next week's occurrence into a fresh row. This is the implementation substrate for "This occurrence only" in the editing epic; no user-visible prompt in this epic.

## Frontend Changes

Touches three files in `app/lib/features/calendar/`, adds one widget.

- **`widgets/plan_meal_sheet.dart`** (modify): insert a new "Repeats" section after the Meal Type selector and before the Save button. Manages a new `_recurrence` state object carrying `{interval, weekdays, endDate}`. Save path forks: if `_recurrence != null`, call the new `createRecurrenceRule` service method; else keep existing `createMealEvent` path. Button label swaps between "Add to Calendar" and "Add Recurring Meal" based on that state.
- **`widgets/recurrence_field.dart`** (new): the Repeats picker — chip row, weekday multi-select, presets, end-date picker. Isolated widget with a small API (`RecurrenceValue?` in / out).
- **`widgets/meal_detail_sheet.dart`** (modify): if `event.recurrenceRuleId != null`, show a "Recurring" badge in the header and a summary line ("Every Mon, Wed · Dinner · Pasta"). Add an **End series today** row at the bottom of the secondary action list, with a confirmation dialog.
- **`calendar_screen.dart` → `_buildEventTile`** (modify): when `event.recurrenceRuleId != null`, render a small repeat-arrow glyph in the tile's top-right corner (16px, low-contrast).
- **`models/meal_event.dart`** (modify): add `recurrenceRuleId: String?` to `MealEvent`; parse from the new backend field. Add a new `RecurrenceValue` model (or colocate in `recurrence_field.dart`).
- **`services/meal_calendar_service.dart`** (modify): add `createRecurrenceRule({ title, recipeId, mealType, interval, weekdays, endDate, isShared })`, `deleteRecurrenceRule(ruleId)`, and `getRecurrenceRule(ruleId)` calls matching the new API shape.

No new navigation route. No new provider. No change to the calendar week-load path (still reads `meal_events` only).

## Backend Changes

Touches three directories, adds one table, one router, seven handlers, one worker job.

- **`libraries/utils/utils/models/meal_recurrence_rule.py`** (new): the new model — columns per the PRD/architecture addendum. `id`, `owner_id`, `title`, `recipe_id` (nullable FK), `meal_type`, `weekdays` (Postgres JSONB or ARRAY of weekday strings), `interval` ("weekly" | "biweekly"), `start_date`, `end_date` (nullable), `is_shared`, `materialized_through` (DATE), `archived_at`, `created_at`, `updated_at`. Monthly-nth-weekday shape is added in the editing epic, not here.
- **`libraries/utils/utils/models/meal_event.py`** (modify): add `recurrence_rule_id` (nullable UUID FK → `meal_recurrence_rules.id`, ON DELETE SET NULL). The relationship is one-way (rule → events); `meal_events` doesn't hold a back-pop.
- **`services/migrator/migrations/versions/<new>.py`** (new alembic revision): create the new table + the new FK column + indexes on `owner_id` and `materialized_through`. No backfill of legacy `is_recurring` data.
- **`services/api/src/api/v1/recurrence_rule/`** (new handler directory): `create_recurrence_rule.py`, `get_recurrence_rule.py`, `list_recurrence_rules.py`, `delete_recurrence_rule.py`. No update handler yet — updates land in the editing epic. All handlers follow the existing `Endpoint`-subclass pattern used under `api/v1/meal_event/`.
- **`services/api/src/routers/v1/recurrence_rule_router.py`** (new): registers the four endpoints under `/api/v1/recurrence-rules`.
- **`libraries/utils/utils/recurrence/materializer.py`** (new): the core materialization function. Signature: `materialize(rule, through_date, db)`. Idempotent: deletes future `meal_events` with this `recurrence_rule_id` that are `>= today` and `< through_date` but outside the new expected-set, then inserts any missing ones. Updates `rule.materialized_through`. Handles the weekday + interval + end-date grammar.
- **`services/api/src/api/v1/meal_event/list_meal_events.py`** (modify): before the existing query, SELECT active rules for the current user whose `materialized_through < requested_end_date`; call `materialize(...)` for each within the same transaction; then run the existing query. Bounded work; no change to response shape. The `MealEventItem` response adds `recurrence_rule_id` so the Flutter tile can render the glyph.
- **`services/worker/`** (modify): new scheduled job "advance_recurrence_windows" runs nightly, walks every non-archived rule, calls `materialize(rule, today + 9 weeks, db)`. Also archives materialized rows older than 6 months (to keep row count bounded). Registered in the existing worker-scheduler.
- **Schema update (`services/api/src/schemas/meal_event.py`)**: add `recurrence_rule_id: str | None` on list / get responses.

Legacy `meal_events.is_recurring`, `recurrence_rule`, `recurrence_end_date`, `parent_event_id` columns are untouched — removal is a follow-up epic after this one stabilizes.

## Infrastructure Changes

- **Migration**: one alembic revision (new table + FK + indexes). Runs through the existing `migrator` profile (`docker compose --profile migrate up migrator`).
- **Worker scheduling**: the new nightly job registers in the existing `worker` service. No new queues, no new container.
- **Env vars / secrets**: none.
- **Terraform / AWS**: none — no new resources.
- **CI**: covered by the existing `npx nx run api:test` / `worker:test` matrix; the new handler dir and model are picked up by discovery.

## Design Principles (refined via party-mode 2026-04-17)

1. **Concrete rows always win** (backend / architect). The calendar UI reads `meal_events` only; recurring occurrences are materialized rows like any other. No virtualization leak to the client. Downstream (shopping list, prep steps, invites) requires zero refactor.
2. **Materialization is idempotent under concurrency** (backend). A `UNIQUE (recurrence_rule_id, scheduled_at)` index + `INSERT ... ON CONFLICT DO NOTHING` semantics guard against the `ListMealEvents` hot path and the nightly worker colliding. No row-lock required; no duplicate rows possible.
3. **Rule owns the rule; recipe owns the title when attached** (backend). `rule.title` is required only when `recipe_id IS NULL` (free-text meal). When `recipe_id` is set, the materialized row's title is pulled live from `recipes.name` at materialization time — recipe renames flow through to future occurrences automatically. No denormalization drift.
4. **Detach-on-edit is the escape hatch** (frontend + backend). Any recurrence-row edit that isn't "End series today" (e.g., Reschedule, Unschedule, eventually recipe-swap) clears `recurrence_rule_id` and the row becomes a one-off. This is the substrate the editing epic's "This occurrence" branch stands on — no user-visible prompt yet.
5. **"Repeats: Never ▾" must read as an affordance** (UX). Not passive status text. The row uses the same chevron-right chip styling as the Date and Meal Type rows below it, with the caret indicating tap-to-open.
6. **Destructive confirmations don't offer undo** (UX / backend). End series today is confirm-then-commit. Partial re-insertion after async undo is a correctness nightmare and misleads users about what's recoverable.
7. **Errors preserve form state** (UX). If rule creation fails (materializer failure, network drop, validation error), the plan-meal sheet stays open with fields intact and a specific snackbar reads "Couldn't save repeating meal. Try again."
8. **Legacy columns stay as dead weight** (backend). Don't rip out `is_recurring` / `recurrence_rule` / `recurrence_end_date` / `parent_event_id` in this epic; clean up after this stabilizes in a follow-up.
9. **9 weeks forward is the window; 6 months back is the archive cutoff** (infra / QA). Not configurable, not per-user. Covers the realistic planning horizon, bounds table growth, and is small enough that a single nightly worker run completes well within the container lifetime budget.
10. **End = forever or until-date** (PM). No count-based ends. If a user wants 10 pizzas exactly, they delete after 10.
11. **No feature flags** (devops). Ships directly behind a passing migration. Rollback is a documented SQL script (below).
12. **Rule writes include `tz_name` (IANA)** (backend + frontend contract). The client always sends the user's device TZ with rule create; server resolves the per-slot local time (8:00/12:00/18:00/15:00) to a UTC `scheduled_at` at materialize time. Missing `tz_name` → 400. No UTC default fallback.

## Locked Cross-Epic Decisions (propagate to editing epic)

- **Co-edit on shared rules**: `is_shared == true` means any household member of the owner can read, update, and delete. Private rules (`is_shared == false`) are owner-only for every mutation. Symmetric with how household meal plans already work.
- **UNIQUE `(recurrence_rule_id, scheduled_at)` index** enforces idempotent materialization across all future epics.
- **Title denormalization**: rule.title required only when recipe_id is NULL; materialized row.title pulled from recipe.name at materialize time when recipe_id is set.
- **"Last" weekday semantics for monthly rules** (lands in editing epic): = **last in calendar month** (so a 4-Saturday month has Last == Fourth; a 5-Saturday month has Last == Fifth). Confirmed as the ship default — flagged in the editing epic's open questions if user prefers "skip month" instead.
- **Repeats-control affordance**: caret/chip styling, not plain text, in the plan-meal sheet.
- **`tz_name` (IANA) is a required field** on all recurrence-rule write requests.
- **Observability**: the worker job `advance_recurrence_windows` logs start, complete, and per-rule failure to `error_logs` with `service="worker"`. Reuses the audit-log pattern from `promote_admin.py`.
- **Rollback SQL** (kept as an ops artifact, documented in epic DoD): `UPDATE meal_recurrence_rules SET archived_at = NOW() WHERE archived_at IS NULL; DELETE FROM meal_events WHERE recurrence_rule_id IS NOT NULL AND scheduled_at >= NOW();` — reverses the forward population without losing past history or one-off events.

## Inherited Locked Decisions (from prior epic workshops)

- All datetime writes UTC; reads render in device-local.
- No feature flags, no backwards-compat shims.
- Directories: handlers → `services/api/src/api/v1/<area>/`; migrations → `services/migrator/migrations/versions/`; Flutter feature subdirs → `app/lib/features/<area>/widgets/`.
- Destructive user actions use snackbar-undo (3s) — **exception**: series-delete (End series today) is confirm-then-commit, not undo-able (principle #6 above).
- Audit-log all admin-invoked mutations. The new worker job's per-rule failures log with `service="worker"` (not "audit").
- Idempotent writes over wider transactions.
- No stories for capabilities without a named user ask.
- Field-render policy: every backend-returned field is rendered or annotated-not-shown (Leo's screen renders `recurrence_rule_id` by emitting the glyph + summary line rather than hiding it).

## File Structure (expected)

```
app/lib/features/calendar/
├── widgets/
│   ├── plan_meal_sheet.dart            # MODIFIED — Repeats section + _recurrence state
│   ├── recurrence_field.dart           # NEW — the Repeats picker widget
│   └── meal_detail_sheet.dart          # MODIFIED — recurring badge, summary line, End series today
├── calendar_screen.dart                # MODIFIED — repeat glyph on recurring tiles
├── models/meal_event.dart              # MODIFIED — add recurrenceRuleId
└── services/meal_calendar_service.dart # MODIFIED — add rule CRUD methods

libraries/utils/utils/
├── models/meal_recurrence_rule.py      # NEW
├── models/meal_event.py                # MODIFIED — recurrence_rule_id FK
└── recurrence/materializer.py          # NEW — core materialize(rule, through_date, db)

services/api/src/
├── api/v1/recurrence_rule/             # NEW — create / get / list / delete handlers
│   ├── __init__.py
│   ├── create_recurrence_rule.py
│   ├── get_recurrence_rule.py
│   ├── list_recurrence_rules.py
│   └── delete_recurrence_rule.py
├── api/v1/meal_event/list_meal_events.py  # MODIFIED — pre-query materialization check
├── routers/v1/recurrence_rule_router.py   # NEW
└── schemas/meal_event.py               # MODIFIED — recurrence_rule_id on list/get responses

services/migrator/migrations/versions/
└── 2026041700000_add_recurrence_rules.py  # NEW — table + FK + indexes

services/worker/
└── <existing scheduler path>           # MODIFIED — register advance_recurrence_windows
```

## Story Map

| # | Story | Priority | Est. Effort | Depends on |
|---|-------|----------|-------------|------------|
| rm-found-1 | `meal_recurrence_rules` model, migration, CRUD endpoints (no update) | 🔴 P0 | 1 d | — |
| rm-found-2 | Rolling-window materializer + `recurrence_rule_id` FK on meal_events | 🔴 P0 | 1 d | rm-found-1 |
| rm-found-3 | `ListMealEvents` materialization hook + nightly worker job + shopping-list smoke | 🔴 P0 | 1 d | rm-found-2 |
| rm-found-4 | Flutter Repeats picker + plan-meal-sheet integration | 🔴 P0 | 1 d | rm-found-1 |
| rm-found-5 | Calendar recurring visual + meal detail sheet summary + End series today | 🟡 P1 | 0.5–1 d | rm-found-3, rm-found-4 |

**Total estimated effort: 4.5–5 days.**

**Sequencing:** rm-found-1 → rm-found-2 → (rm-found-3 ∥ rm-found-4) → rm-found-5. rm-found-3 and rm-found-4 can run in parallel once the model + materializer exist.

---

## Story rm-found-1: Recurrence-rule model, migration, and create/get/list/delete endpoints

As Leo, I want the backend to be able to store and retrieve recurring meal plans so that any Flutter-side recurrence work has something to talk to.

### Acceptance Criteria

1. A new `meal_recurrence_rules` table exists via alembic migration with columns per the architecture addendum.
2. The new `meal_events.recurrence_rule_id` FK column exists (nullable, ON DELETE SET NULL) and an index.
3. `POST /api/v1/recurrence-rules` accepts `{title?, recipe_id?, meal_type, weekdays[], interval, start_date, end_date?, tz_name, is_shared}` and persists a rule owned by the authenticated user. **Validation rejects** empty `weekdays`, unknown `meal_type`, `interval` outside `{"weekly", "biweekly"}`, `start_date > end_date`, missing `tz_name`, invalid IANA `tz_name`, and the case where both `title` and `recipe_id` are null (rule must have *either* a recipe *or* a free-text title). When `recipe_id` is set, `title` in the request is ignored — the materialized row pulls `title` from `recipes.name` live at materialize time.
4. `GET /api/v1/recurrence-rules/{id}` returns the rule or 404 if archived or not owned / shared with the user. Visibility rules: the authenticated user can read the rule if `rule.owner_id == user.id` OR (`rule.is_shared == true` AND `rule.owner_id` is in the same household as `user.id`).
5. `GET /api/v1/recurrence-rules` lists all active (`archived_at IS NULL`) rules visible to the user per the rule in AC #4, ordered by `created_at DESC`. No pagination yet — user cap is small.
6. **Co-edit for shared rules** — if `rule.is_shared == true`, any household member of the owner can read, update, *and delete* the rule. Non-shared (private) rules are owner-only; a household member attempting delete/update on a private rule → 403. Rationale: `is_shared` is the user's explicit opt-in to joint ownership; the symmetry (either partner can end Pizza Friday) matches shared-calendar expectations.
7. `DELETE /api/v1/recurrence-rules/{id}` sets `archived_at = now()` and deletes all future-date materialized `meal_events` with that `recurrence_rule_id` (i.e., `scheduled_at >= today_local_midnight_in_utc`). Past occurrences remain (their `recurrence_rule_id` is *not* cleared because the rule row is archived, not hard-deleted — the FK still resolves; archived_at is what makes the rule invisible). Owner-only per AC #6.
8. Idempotent: re-deleting an archived rule returns 200 with no further side effects.
9. Tests in a new `test_recurrence_rule.py` cover: happy-path create (with recipe), happy-path create (free-text, no recipe), title-and-recipe-both-null → 400, invalid weekdays, mismatched start/end, missing `tz_name` → 400, invalid IANA `tz_name` → 400, get-own-rule, list-empty, list-multiple, delete-cascade-future-only, delete-idempotent, auth enforcement (user-A cannot read or delete user-B's *private* rule → 403/404; household-member *can* read, update, and delete user-B's *shared* rule; non-household users → 404 regardless of shared flag).

### Key Files
- Create: `libraries/utils/utils/models/meal_recurrence_rule.py`
- Modify: `libraries/utils/utils/models/meal_event.py` (add nullable FK `recurrence_rule_id`)
- Create: `services/migrator/migrations/versions/2026041700000_add_recurrence_rules.py` (table + FK + **UNIQUE index on `(recurrence_rule_id, scheduled_at)` where `recurrence_rule_id IS NOT NULL`** + index on `owner_id` + index on `materialized_through`)
- Create: `services/api/src/api/v1/recurrence_rule/*.py` (4 handlers + `__init__.py`)
- Create: `services/api/src/routers/v1/recurrence_rule_router.py`
- Create: `services/api/tests/test_recurrence_rule.py`
- Modify: `services/api/src/main.py` (or wherever routers are registered)

---

## Story rm-found-2: Rolling-window materializer + expansion logic

As the system, I want to expand any rule into concrete `meal_events` rows bounded by a rolling 9-week window so that every downstream read (calendar, shopping list, prep steps, invites) keeps working unchanged.

### Acceptance Criteria

1. `libraries/utils/utils/recurrence/materializer.py` exposes `materialize(rule, through_date, db) -> list[MealEvent]` that:
   - Computes the expected set of `scheduled_at` datetimes for the rule between `max(rule.start_date, today_local)` and `min(through_date, rule.end_date or through_date)`, respecting weekday selection and interval. Per-slot local time (8:00 / 12:00 / 18:00 / 15:00 — matching the existing Flutter `_mealDefaultTime`) is resolved to UTC using `rule.tz_name`.
   - Queries existing `meal_events` with `recurrence_rule_id == rule.id` and `scheduled_at >= today_local_midnight_utc`.
   - Inserts missing concrete rows via `INSERT ... ON CONFLICT DO NOTHING` on the unique `(recurrence_rule_id, scheduled_at)` index. For recipe-linked rules, the inserted `title` is pulled from `recipes.name` live (not from `rule.title`). Owner and host participant default to the rule's owner.
   - Deletes extraneous rows (rows scheduled for dates no longer in the expected set — i.e., the rule's end-date was shortened).
   - Sets `rule.materialized_through = through_date`.
   - Runs in a single transaction. Idempotent under concurrency: two simultaneous invocations converge (no duplicate rows — the unique index blocks them).
2. Biweekly interval: "every other week" anchors to `rule.start_date`'s week (ISO week number parity).
3. Weekly interval with multi-weekday: one row per matching weekday per week.
4. All datetime writes are UTC; the slot's default local time resolves to UTC via `rule.tz_name` (IANA). Missing `tz_name` on a rule row → create-rule returned 400 at rm-found-1, so the materializer can assume presence. A dedicated server-side TZ test: `tz_name="America/Los_Angeles"`, Friday dinner rule, DST-transition week (second Sunday of March / first Sunday of November) → materialized rows still render 18:00 local after TZ offset shifts.
5. `CreateRecurrenceRule` from rm-found-1 now calls `materialize(rule, today + 9 weeks, db)` in the same transaction as the rule insert. NFR36 holds: P95 ≤ 500ms for up to ~45 occurrences.
6. New tests in `libraries/utils/tests/test_materializer.py` cover: weekly-one-weekday, weekly-multi-weekday, biweekly-odd-week-anchor, end-date-bound, materialization-shortened-end-date (shrinks), materialization-extended-end-date (grows), idempotency (calling twice in a row produces identical state), **concurrent-invocation safety (two concurrent transactions → no duplicate rows, thanks to the unique index)**, **DST-transition correctness (`America/Los_Angeles` spring-forward + fall-back weeks)**.
7. Test covers the stack-on-collision policy: manual `meal_event` on Monday dinner + rule "every Monday dinner" → after materialization, **both** rows exist on Monday. No dedupe.
8. Test covers the recipe-rename propagation: rule with `recipe_id=X`; recipe X renamed from "Pizza" to "Calzone"; next materialize pass → new rows have title "Calzone", existing future rows updated to "Calzone" via the regenerate path, past rows untouched.

### Key Files
- Create: `libraries/utils/utils/recurrence/materializer.py`
- Modify: `services/api/src/api/v1/recurrence_rule/create_recurrence_rule.py` (call materializer)
- Create: `libraries/utils/tests/test_materializer.py`
- Modify: `services/api/src/api/v1/recurrence_rule/delete_recurrence_rule.py` (reuse materializer deletion path or share helper)

---

## Story rm-found-3: ListMealEvents extension hook + nightly worker job + shopping-list smoke test

As Leo, I want the calendar and the weekly shopping list to always see rule-materialized occurrences for the weeks I'm looking at, without any client-side awareness of rules.

### Acceptance Criteria

1. `services/api/src/api/v1/meal_event/list_meal_events.py` runs a pre-query check: for the requesting user, fetch all active rules where `materialized_through < request.end_date`; for each, call `materialize(rule, request.end_date, db)` in the same transaction as the read.
2. The modified list response includes `recurrence_rule_id` on each `MealEventItem` (nullable).
3. NFR37 holds: a benchmark test measures list P95 latency with and without 10 active rules + 9-week-ahead read; difference is within 20%.
4. A new `advance_recurrence_windows` worker job registers in the worker scheduler, runs daily at 03:00 UTC, and for every active rule in the DB:
   - Calls `materialize(rule, today + 9 weeks, db)`.
   - Archives materialized `meal_events` with `scheduled_at < today - 6 months` by setting `archived_at` (does NOT touch rows already archived by the user).
   - **Observability**: logs job-start, job-complete (with rule-count and total-rows-touched), and per-rule failures to `error_logs` with `service="worker"`. Per-rule failure does not abort the whole run — the job continues to the next rule.
5. The existing `PopulateFromCalendarRange` (shopping list from week) endpoint is not modified — a smoke test confirms that after a rule is created, populating a shopping list for the rule's first week returns the rule's ingredients as expected.
6. New tests: `test_list_meal_events_with_active_rule` (list extends materialization), `test_list_hot_path_no_materialize_when_watermark_sufficient` (rule already materialized through requested date → zero materialize calls), `test_list_latency_baseline` (NFR37), `test_worker_advance_recurrence_windows` (worker job idempotency + archive cutoff + per-rule-failure doesn't abort run), `test_populate_from_calendar_includes_rule_occurrence`, `test_worker_job_logs_to_error_logs`.

### Key Files
- Modify: `services/api/src/api/v1/meal_event/list_meal_events.py`
- Modify: `services/api/src/schemas/meal_event.py`
- Modify: `services/worker/src/...` (register job + implementation)
- Create: `services/api/tests/test_list_meal_events_recurrence.py`
- Create: `services/worker/tests/test_advance_recurrence_windows.py`

---

## Story rm-found-4: Flutter Repeats picker + plan-meal-sheet integration

As Leo, I want to set "Repeats: Weekly, Friday" in the plan-meal sheet in two taps so I don't have to retype pizza every week.

### Acceptance Criteria

1. `plan_meal_sheet.dart` gains a **Repeats** section between the Meal Type selector (line ~371) and the Save button (line ~377), matching the existing read-only-row-plus-chevron pattern of the Date field.
2. Tap opens the new `RecurrenceField` bottom sheet: interval chips (`Never`, `Weekly`, `Every other week`), a weekday multi-select chip row (Mon–Sun), preset pills (`Weekdays`, `Weekends`), and an optional "Ends on" date picker (blank = forever).
3. Selecting any interval other than Never requires at least one weekday; attempting to save with none disables Done.
4. When `_recurrence != null`, the Save button label flips to **"Add Recurring Meal"** and the save path POSTs to the new `/api/v1/recurrence-rules` endpoint with: title (free-text only; omitted when a recipe is attached), `recipe_id` (if picked via autocomplete), `meal_type`, `weekdays`, `interval`, `start_date = selectedDate`, optional `end_date`, `tz_name` (from `DateTime.now().timeZoneName` / the platform's IANA name), `is_shared: true` (matching existing default). While the POST is in flight, the Save button shows a spinner (reusing lines 388–403) and all form fields are disabled.
5. **Success**: the sheet dismisses with `result = true` (triggers calendar reload via the existing `_loadEvents()` hook at line 538) and the snackbar reads "Repeating [meal-type]s added." **Failure**: the sheet **stays open**, the button returns to "Add Recurring Meal," form state is preserved intact, and a snackbar reads "Couldn't save repeating meal. Try again." No form reset on error.
6. Edit mode (`eventId` provided, reschedule flow from the ellipsis menu): the Repeats section is **hidden** — editing a single occurrence never opens the recurrence picker. Series-level edits happen from the manage screen in epic 2.
7. TZ test case: user in `America/Los_Angeles` creates a weekly Friday-dinner rule at 10am local on a Monday; the first materialized Friday dinner renders at 18:00 local on Friday, not 01:00 Saturday or 10:00 Friday.
8. Accessibility: the weekday chip row is tappable via keyboard (web) and screen-reader-labels are set ("Monday, not selected" / "Monday, selected"). Interval chips announce their state similarly ("Weekly, selected").
9. **Affordance styling**: the collapsed "Repeats: Never ▾" row uses the same chevron-right container as the Date and Meal Type rows — it must read as tappable, not as passive status. Visual parity with existing rows is required.
10. **Offline behavior is unchanged**: rule creation follows the same online-only path as existing `createMealEvent`. No new offline queueing. If offline at save time, the existing "no network" error surfaces via the preserved-form-state path in AC #5.

### Key Files
- Create: `app/lib/features/calendar/widgets/recurrence_field.dart` (bottom sheet + chip row)
- Modify: `app/lib/features/calendar/widgets/plan_meal_sheet.dart`
- Modify: `app/lib/features/calendar/services/meal_calendar_service.dart` (add `createRecurrenceRule`)
- Modify: `app/lib/features/calendar/models/meal_event.dart` (add `RecurrenceValue` value class)
- Tests: `app/test/features/calendar/plan_meal_sheet_recurrence_test.dart`, `app/test/features/calendar/recurrence_field_test.dart`

---

## Story rm-found-5: Calendar recurring visual + meal detail sheet summary + End series today

As Leo, I want a glance to tell me which meals are part of a series and a clear one-tap way to stop a series from any occurrence.

### Acceptance Criteria

1. `calendar_screen.dart → _buildEventTile` renders a 16×16 repeat-arrow glyph (`Icons.repeat`, 0.55 opacity, `onSurface` color) in the tile's top-right when `event.recurrenceRuleId != null`. Layered on top of the existing chevron area — does not push other content. A `Semantics(label: "Recurring meal")` wraps the glyph so screen readers announce it.
2. `meal_detail_sheet.dart` when `event.recurrenceRuleId != null`: the header shows a **"Recurring"** text badge next to the existing meal-type pill; below the datetime line, a new secondary line shows the rule summary "Every Mon, Wed · Dinner · [recipe-name]" (fetched via `getRecurrenceRule(ruleId)` on sheet open, cached for the sheet lifetime).
3. The sheet adds a new bottom row **End series today** with a destructive-colored icon (Icons.stop_circle_outlined). Tapping it shows a confirmation dialog ("Stop repeating X? Future occurrences will be removed. Past occurrences stay."). On confirm, calls `deleteRecurrenceRule(ruleId)`, dismisses the sheet, reloads the calendar.
4. End series today is **not** offered for non-recurring events (the row is absent when `recurrenceRuleId == null`).
5. Offline/retry: `getRecurrenceRule` failure does not block the sheet — the summary line falls back to "Recurring meal" without detail; the End series today row is hidden if the rule couldn't be loaded (to avoid mistakenly triggering a write without context).
6. Snackbar-undo on End series today is **not** offered (per existing project policy: destructive bulk actions like series-delete are confirm-then-commit, not undo-able, because partial re-insertion is messy).
7. Visual regression test: golden-image test for `meal_detail_sheet.dart` in the recurring-state.

### Key Files
- Modify: `app/lib/features/calendar/calendar_screen.dart` (tile glyph)
- Modify: `app/lib/features/calendar/widgets/meal_detail_sheet.dart` (badge + summary + End series row)
- Modify: `app/lib/features/calendar/services/meal_calendar_service.dart` (add `getRecurrenceRule`, `deleteRecurrenceRule`)
- Tests: `app/test/features/calendar/meal_detail_sheet_recurring_test.dart`

---

## Definition of Done (Epic Level)

- `meal_recurrence_rules` table exists in prod; a migration has landed and is reversible.
- Setting up a weekly-Friday-pizza rule from the plan-meal sheet results in 8 future Friday dinners on the calendar, each tile marked with a repeat glyph.
- Weekly shopping-list aggregation picks up rule-materialized occurrences without endpoint-level changes.
- End series today from any recurring occurrence removes future occurrences and leaves past ones alone.
- Editing (reschedule / unschedule / recipe-swap) a single recurring occurrence detaches it as a one-off. No user-facing "This / Following / All" prompt ships in this epic — that's the editing epic.
- All datetime writes go out UTC; TZ test case passes for `America/Los_Angeles`.
- NFR36 (materialization P95 500ms), NFR37 (list latency ≤20% drift), and the P0 test cases above all pass in CI.

## Open Questions for the User

- **Device TZ source**: the rule create endpoint needs the user's device TZ to resolve "18:00 local" on weekdays. Current `create_meal_event` relies on the client sending an already-UTC `scheduled_at`. For rules, the server has to derive per-occurrence UTC, so the client must send `tz_name` (IANA). This is a small but real new contract. Acceptable?
- **Default sharing**: rules default `is_shared: true` to mirror the existing meal_event default. If the user wants rules to default to private, call it out now — cheap to flip before shipping.
- **Archive-after-6-months worker cutoff**: 6 months is a guess for the history window. If Leo expects to look back a year at what he's eaten, lift it to 12 months. No functional risk either way.
