<!-- refined via party-mode 2026-04-17 -->
# Epic: Recurring Meal Plans — Edit Scopes, Monthly Grammar, and Manage Screen

## Overview

The foundation epic ships recurring-meal creation with "delete-and-recreate" editing and weekly/biweekly grammar only. This epic fills in the three gaps users notice next: (1) editing a recurring occurrence prompts GCal-style **This occurrence / This and following / All occurrences**, (2) the rule grammar adds **monthly-on-nth-weekday** ("first Saturday dinner"), and (3) a dedicated **Recurring Plans** list lives under Profile/Settings so Leo can audit and manage every rule from one place. No new infra; adds one backend handler (update) plus rule-split semantics, one new Flutter screen, and one new grammar path in the Repeats picker.

**Goal:** When this epic ships, Leo can edit "Pizza Friday" to "Pasta Friday this Friday only" and see the rule continue unchanged; he can change the whole series to Pasta going forward; he can set "first Saturday of the month, dinner, date-night recipe"; and he can see all his active recurring plans in one list.

## End-User Flow

1. Leo taps a recurring Friday-pizza tile on the calendar → meal detail sheet opens (from the foundation epic).
2. He taps **Reschedule** → a new prompt appears: **This occurrence · This and following · All occurrences** (three buttons vertically stacked, brief subtitles). He picks **This occurrence**.
3. A date-time picker opens (existing reschedule flow). He moves Friday → Sunday. On save the Friday row becomes a one-off (its `recurrence_rule_id` clears); the rule continues to generate next Friday's pizza as usual. Snackbar: "This Friday moved to Sunday. The series continues."
4. Next time, Leo instead picks **This and following** on a different occurrence. The rule splits: the old rule gets `end_date = day before the chosen occurrence`, a new rule is created starting from the chosen occurrence with the new values. Calendar reloads; past occurrences untouched.
5. For "All occurrences": the rule is updated in place; every future materialized row is regenerated with the new values. Past rows untouched.
6. Leo opens Profile → **Recurring plans**. A list renders every active rule he owns (rule row: title, summary like "Every Mon, Wed · Dinner", next-occurrence date, active/ended chip). He taps "First Saturday dinner" → edit sheet opens pre-selected to **All occurrences** scope — from here changes apply series-wide only.
7. When creating a new rule from the plan-meal sheet, the Repeats picker now offers **Monthly** alongside Weekly and Every other week. Monthly + a weekday selection + an "nth occurrence" picker (`First`, `Second`, `Third`, `Fourth`, `Last`). Leo picks Monthly / Saturday / First / Dinner → rule materializes as "First Saturday dinner."

## Frontend Changes

- **`widgets/edit_scope_prompt.dart`** (new): the three-choice bottom sheet. Reusable widget — returns one of `{thisOccurrence, thisAndFollowing, all}` or null on dismiss. Invoked before any edit action on a recurring occurrence.
- **`widgets/meal_detail_sheet.dart`** (modify): Reschedule and Unschedule handlers route through the new prompt when `event.recurrenceRuleId != null`. Based on the selection, they call the existing delete/update handlers, plus the new rule-scoped equivalents.
- **`widgets/plan_meal_sheet.dart` + `widgets/recurrence_field.dart`** (modify): add **Monthly** as an interval option; when Monthly is selected, show an additional `nth` picker ({`First`, `Second`, `Third`, `Fourth`, `Last`}) that composes with the weekday chips (but only a single weekday — monthly-nth-weekday is inherently one weekday per month).
- **`features/profile/recurring_plans/`** (new feature dir): a new screen `RecurringPlansScreen`, reachable from Profile/Settings via a new list tile "Recurring plans." The screen lists all rules, tappable to open an edit sheet (reuses the plan-meal sheet's Repeats surface at "All occurrences" scope — the other scopes don't apply when editing from a rule-level surface).
- **`features/profile/profile_screen.dart`** (modify): add the "Recurring plans" ListTile entry point.
- **`services/meal_calendar_service.dart`** (modify): add `updateRecurrenceRule(ruleId, fields, scope)` where `scope ∈ {"all", "this_and_following"}`, `listRecurrenceRules()`, and a scoped delete `deleteRecurrenceRule(ruleId, {scope: "series" | "this_occurrence"})` — the latter routes to the existing single-event delete for "this occurrence" scope.
- **`models/`** (modify): add `RecurrenceRule` value class for the manage screen to render.

## Backend Changes

- **`services/api/src/api/v1/recurrence_rule/update_recurrence_rule.py`** (new): accepts `{...ruleFields, scope: "all" | "this_and_following", occurrence_date?}`. For `all`: updates the rule row in place, calls `materialize(rule, rule.materialized_through, db)` to regenerate future rows. For `this_and_following`: validates `occurrence_date` is a future rule-occurrence, sets original rule's `end_date = occurrence_date - 1 day`, creates a new rule with the supplied fields and `start_date = occurrence_date`, materializes both. Runs in a single transaction.
- **`libraries/utils/utils/models/meal_recurrence_rule.py`** (modify): add `monthly_nth` enum field (`null`, `"first"`, `"second"`, `"third"`, `"fourth"`, `"last"`). When non-null, `interval` must be `"monthly"` — a new interval value the model now accepts.
- **`libraries/utils/utils/recurrence/materializer.py`** (modify): extend the expected-date computation to handle `interval = "monthly"` with `monthly_nth`. Weekday selection is required and must have exactly one entry in monthly mode (validator).
- **`services/migrator/migrations/versions/<new>.py`** (new alembic revision): adds `monthly_nth` column and loosens the `interval` check constraint to allow `"monthly"`.
- **`services/api/src/api/v1/recurrence_rule/delete_recurrence_rule.py`** (modify): accept `scope` query param; `scope=series` keeps existing behavior, `scope=this_occurrence` treats it as a single-event delete (routes through the existing `DeleteMealEvent` logic with rule-detach as a side effect). `scope=this_and_following` is also supported here for symmetry with update.
- **Tests**: new coverage for rule split (end-date-of-old + new rule + no gap + no overlap), for all-scope regeneration, for monthly-nth materialization (first/second/third/fourth/last edge cases, including "fifth Saturday doesn't exist this month"), for this-occurrence-detach semantics.

## Infrastructure Changes

- **Migration**: one alembic revision — add `monthly_nth` column, widen `interval` check.
- **Worker job**: unchanged — `advance_recurrence_windows` already calls `materialize` which gains the monthly path.
- **No new env vars, secrets, Terraform, or CI changes.**

## Design Principles (refined via party-mode 2026-04-17)

1. **The prompt is the gate** (UX / frontend). Any edit-by-tap on a recurring occurrence prompts for scope before any write. No silent guessing. The prompt's subtitles must be concrete ("Apply to this Friday only. Past and future untouched.") — abstract wording ("this event") has been ruled out as confusing.
2. **Prompt copy flavors the action** (UX). The `EditScopePrompt` takes an `action` enum (`reschedule | unschedule | recipe_swap`) so the subtitles read naturally in destructive contexts ("Remove only this Friday. Future continues.") vs. edit contexts ("Change only this Friday. Series stays.").
3. **Rule-split never silently drops or duplicates occurrences** (backend / QA). A gap-free/overlap-free test verifies that the day-before-new-rule's-start materializes on the old rule and the day-of-new-rule's-start materializes on the new rule — never both, never neither.
4. **Split validator is strict** (backend). A `this_and_following` split at an `occurrence_date` that isn't actually a valid rule-occurrence (wrong weekday, before `rule.start_date`, after `rule.end_date`, in the past) returns 400. Idempotency: submitting the same split twice (network retry) is detected and returns 200 with no further state change.
5. **Client refreshes the full visible week after any scope change** (frontend). A split at week N affects week N+1's tiles too; the client must refetch the whole `[week_start, week_end]` range rather than patching in place. Reuses the existing `_loadEvents()` path.
6. **Monthly is one weekday per month** (backend / UX). The grammar stays tight; "first Saturday + first Sunday" is two rules, not one. Validator enforces `weekdays.length == 1` when `interval == "monthly"`.
7. **"Last" weekday = last-in-calendar-month** (backend — propagated from foundation). A 4-Saturday month has Last == Fourth; a 5-Saturday month has Last == Fifth. This is the confirmed ship semantics — the open question surfaces "skip month" as an alternative only if the user objects post-ship.
8. **Manage screen is opt-in** (PM). Users who never open it see no difference vs. the foundation epic. Leo's existing flow (create from plan-meal sheet, edit from calendar) stays primary.
9. **Manage screen is list-only in v1** (UX). No filter, no search, no sort controls. With <30 rules per user (expected), a scrollable list with active-then-ended ordering suffices. Add filters later only if a real user hits a real limit.
10. **Shared rules are co-editable by any household member** (backend — propagated from foundation). If `rule.is_shared == true`, any household member of the owner can update / split / delete the rule from any surface (calendar meal detail sheet, manage screen). Private rules stay owner-only. The manage screen subtitle "Shared by [name]" stays as provenance context, but does not imply read-only. The creator is still recorded in `owner_id` and displayed; edits do not transfer ownership.
11. **This-occurrence detach is already in place** (foundation epic); this epic just adds the prompt on top and the rule-split + in-place-update paths.

## File Structure (expected)

```
app/lib/features/calendar/
├── widgets/
│   ├── edit_scope_prompt.dart        # NEW — reusable 3-choice sheet
│   ├── meal_detail_sheet.dart        # MODIFIED — route edits through the prompt
│   ├── plan_meal_sheet.dart          # MODIFIED — Monthly interval + nth picker
│   └── recurrence_field.dart         # MODIFIED — Monthly + nth grammar
├── models/                           # MODIFIED — RecurrenceRule value class
└── services/meal_calendar_service.dart # MODIFIED — updateRecurrenceRule + scoped delete

app/lib/features/profile/
├── profile_screen.dart               # MODIFIED — ListTile entry point
└── recurring_plans/                  # NEW
    ├── recurring_plans_screen.dart
    └── widgets/rule_row.dart

libraries/utils/utils/
├── models/meal_recurrence_rule.py    # MODIFIED — monthly_nth column + interval values
└── recurrence/materializer.py        # MODIFIED — monthly-nth expected-date computation

services/api/src/
├── api/v1/recurrence_rule/
│   ├── update_recurrence_rule.py     # NEW — all + this_and_following scopes
│   └── delete_recurrence_rule.py     # MODIFIED — scope param
└── routers/v1/recurrence_rule_router.py  # MODIFIED — register PUT + scope param

services/migrator/migrations/versions/
└── <next>_add_monthly_recurrence.py  # NEW
```

## Inherited Locked Decisions (from foundation epic workshop + prior epics)

- **Concrete rows always win**; calendar reads `meal_events` only. Split and regenerate both produce concrete rows.
- **UNIQUE `(recurrence_rule_id, scheduled_at)` index** enforces idempotent materialization under concurrency — still holds after a split (new rule has its own `recurrence_rule_id`, so no collisions with old).
- **Title denormalization**: when `recipe_id IS NOT NULL`, the materialized row's title is pulled from `recipes.name`. An edit that swaps `recipe_id` via "All" scope regenerates future rows with the new recipe's current name.
- **`tz_name` (IANA) is required** on every rule write — including `update_recurrence_rule`. Split preserves `tz_name`; new rule inherits old rule's `tz_name` unless the client overrides.
- **Destructive confirmations don't offer undo**. This epic's series-delete and rule-split paths are confirm-then-commit.
- **No feature flags.** Ships directly behind passing migrations.
- **Observability**: the worker job continues to cover monthly rules. No new logging surface in this epic.
- **Rollback SQL** from foundation (`UPDATE meal_recurrence_rules SET archived_at = NOW()...`) also rolls back this epic's changes — rules archived, future meal_events deleted. Past occurrences survive as detached rows.

## Story Map

| # | Story | Priority | Est. Effort | Depends on |
|---|-------|----------|-------------|------------|
| rm-edit-1 | Edit-scope prompt UX + route reschedule/unschedule through it | 🔴 P0 | 1 d | foundation epic done |
| rm-edit-2 | Backend "All" regeneration + "This and following" rule-split update handler | 🔴 P0 | 1 d | foundation epic done |
| rm-edit-3 | Monthly-nth-weekday grammar — model, materializer, Repeats UI | 🟡 P1 | 1 d | rm-edit-2 |
| rm-edit-4 | Recurring Plans manage screen under Profile/Settings | 🟡 P1 | 1 d | rm-edit-2 |

**Total estimated effort: 4 days.**

**Sequencing:** rm-edit-1 and rm-edit-2 in parallel (UI prompt and backend scope-handling are independent; stitched together at the service call). rm-edit-3 and rm-edit-4 follow; these two are independent and can run in parallel.

---

## Story rm-edit-1: Edit-scope prompt + Flutter routing

As Leo, I want the app to ask me whether my edit affects this one, this and following, or all occurrences, so I don't accidentally blow away my whole pizza-Friday series.

### Acceptance Criteria

1. A new `EditScopePrompt` widget renders three stacked choices in a bottom sheet with **action-flavored subtitles** that differ based on the `action: {reschedule | unschedule | recipe_swap}` parameter. Examples: for reschedule — "This occurrence" ("Only this Friday moves"), "This and following" ("This Friday and every future one change"), "All occurrences" ("Every Friday changes; past untouched"). For unschedule — "This occurrence" ("Only this Friday is removed"), etc. Cancel button at the bottom. "All occurrences" is tinted with the theme's warning color to signal its scope.
2. `MealDetailSheet.onReschedule` and `onUnschedule` — when `event.recurrenceRuleId != null` — await the prompt before doing anything. If cancelled, no write.
3. On "This occurrence": the existing single-event flow runs (detaches via foundation-epic's detach-on-edit path — reschedule → calls `rescheduleMealEvent`, unschedule → calls `deleteMealEvent`). Snackbar reads: "This occurrence moved" / "This occurrence removed. Series continues."
4. On "This and following": the client calls the new `updateRecurrenceRule` endpoint with `scope=this_and_following` and `occurrence_date = event.scheduledAt.toLocal().date`; on success, **reloads the full visible week range** via `_loadEvents()` (not just the current tile's day). Snackbar: "Series split. Past occurrences kept."
5. On "All occurrences": the client calls `updateRecurrenceRule` with `scope=all`; **reloads the full visible week range**. Snackbar: "All future occurrences updated."
6. When no rule is attached (`recurrenceRuleId == null`), the prompt is bypassed — behavior identical to the foundation epic's default single-event flow.
7. Accessibility: prompt is keyboard-traversable; each choice has a semantic label that explicitly narrates the scope ("This and following. Applies to this Friday and every future Friday."); Esc / swipe-down dismisses. The prompt is a focus-trapping modal so TalkBack / VoiceOver don't leak to backing content.
8. Widget test covers the three-choice routing (mocks service); golden-image test covers the layout.

### Key Files
- Create: `app/lib/features/calendar/widgets/edit_scope_prompt.dart`
- Modify: `app/lib/features/calendar/widgets/meal_detail_sheet.dart`
- Modify: `app/lib/features/calendar/services/meal_calendar_service.dart` (add `updateRecurrenceRule`)
- Tests: `app/test/features/calendar/edit_scope_prompt_test.dart`

---

## Story rm-edit-2: Backend rule-split + in-place update

As the system, I want to support "this and following" (split) and "all" (in-place) updates to a rule cleanly so that the Flutter client has a well-defined API to drive the scope prompt.

### Acceptance Criteria

1. New handler `UpdateRecurrenceRule` at `services/api/src/api/v1/recurrence_rule/update_recurrence_rule.py` accepts `{rule_id, scope, occurrence_date?, ...fields}`.
2. `scope == "all"`: applies the supplied field updates to the rule row (title, recipe_id, weekdays, interval, end_date, is_shared), then calls `materialize(rule, rule.materialized_through, db)` to regenerate all future materialized rows. Past occurrences untouched. **Auth**: caller must be the owner OR (`rule.is_shared == true` AND caller is a household member of the owner). Non-shared + non-owner → 403. Private rule, non-owner → 403. Non-household user on any rule → 404. `owner_id` is preserved across edits regardless of who called.
3. `scope == "this_and_following"`: validates `occurrence_date` is a future date **AND** falls on a scheduled weekday per current rule **AND** is not before `rule.start_date` **AND** is not after `rule.end_date` (if bounded) **AND** for monthly rules, matches the `monthly_nth` slot. If any check fails → 400 with a specific error code identifying which. If valid:
   - Original rule: `end_date = occurrence_date - 1 day` (local), materialize re-run with new end → deletes future rows beyond the split.
   - New rule: created with the supplied fields, `start_date = occurrence_date`, `owner_id` same, `is_shared` same, `tz_name` same (client may override). Materialized forward to `today + 9 weeks`.
   - Both writes run in a single transaction; rollback on any failure; no partial state. If an old rule already had `end_date < occurrence_date` (invalid premise for a split), the validator rejects before any write.
4. Returns the updated rule(s): for `all` just the one rule; for `this_and_following` returns both old and new rules (so the client can refresh the manage screen if it's open).
5. `DELETE /api/v1/recurrence-rules/{id}?scope=this_and_following&occurrence_date=YYYY-MM-DD` follows the same split semantics but the "new rule" step is skipped (end the series at `occurrence_date - 1 day`). `scope=this_occurrence` routes the request to `DeleteMealEvent` for the matching materialized row (fall-through to existing behavior). `scope=series` keeps existing foundation-epic behavior.
6. Idempotency: repeat this-and-following split with the same `occurrence_date` is a no-op (detects the existing split, returns 200).
7. Tests: (a) all-scope edits rule then materialized rows, past untouched; (b) this_and_following gap-free (day-before-new-rule's-start materializes on old rule; day-of materializes on new rule; no double); (c) this_and_following with invalid `occurrence_date` → 400; (d) delete with `scope=this_and_following` sets end-date cleanly; (e) transaction rollback on materializer failure; (f) **co-edit auth**: household member updates owner's shared rule successfully, `owner_id` unchanged; household member fails update on owner's private rule with 403; non-household user fails with 404; ownership is preserved when the split creates a new rule via co-edit (new `owner_id` = original owner's, not caller's).

### Key Files
- Create: `services/api/src/api/v1/recurrence_rule/update_recurrence_rule.py`
- Modify: `services/api/src/api/v1/recurrence_rule/delete_recurrence_rule.py` (add `scope` param)
- Modify: `services/api/src/routers/v1/recurrence_rule_router.py`
- Tests: `services/api/tests/test_recurrence_rule.py` (extend)

---

## Story rm-edit-3: Monthly-nth-weekday grammar

As Leo, I want "First Saturday of the month" as a recurrence option so I can set up a monthly date-night dinner without faking it as weekly.

### Acceptance Criteria

1. `meal_recurrence_rules` gains a `monthly_nth` column: nullable enum `{"first", "second", "third", "fourth", "last"}`. The `interval` column's allowed values extend to include `"monthly"`. Migration lands.
2. Model-level validator: when `interval == "monthly"`, `monthly_nth` must be non-null AND `weekdays` must contain exactly one weekday. When `interval != "monthly"`, `monthly_nth` must be null.
3. `materializer.py` computes monthly-nth expected dates correctly: first/second/third/fourth/last occurrence of the weekday in each calendar month within the range. "Fifth" is not an option; "last" handles the common case. Edge case: months with only 4 of a weekday — "fourth" = "last"; this is acceptable.
4. Repeats picker in `recurrence_field.dart`: adds a **Monthly** interval chip; when Monthly is selected, the weekday row limits to single-select and a new `nth` picker appears with options `First, Second, Third, Fourth, Last`. Preview text updates live ("First Saturday of the month, dinner").
5. Tests: monthly-first-Saturday across 3 months (each month has 1 row), monthly-last-Friday in a month with 4 Fridays (matches the 4th), monthly-last-Friday in a month with 5 Fridays (matches the 5th), monthly with end-date cutoff, monthly + nth change via `all` scope regenerates correctly.

### Key Files
- Modify: `libraries/utils/utils/models/meal_recurrence_rule.py`
- Modify: `libraries/utils/utils/recurrence/materializer.py`
- Modify: `services/api/src/api/v1/recurrence_rule/create_recurrence_rule.py` (accept `monthly_nth`)
- Modify: `services/api/src/api/v1/recurrence_rule/update_recurrence_rule.py`
- Create: `services/migrator/migrations/versions/<next>_add_monthly_recurrence.py`
- Modify: `app/lib/features/calendar/widgets/recurrence_field.dart`
- Tests: extend `libraries/utils/tests/test_materializer.py` and `services/api/tests/test_recurrence_rule.py`

---

## Story rm-edit-4: Recurring Plans management screen

As Leo, I want to see every recurring plan I have in one list so I can audit what's still running and clean up series I've forgotten about.

### Acceptance Criteria

1. A new list tile "Recurring plans" appears on the Profile/Settings screen, between the existing sections (exact position TBD during implementation — follow the existing pattern).
2. Tapping it opens `RecurringPlansScreen` — a scrollable list of rule rows. Each row shows: recipe thumbnail (or meal-type icon), title, summary line ("Every Mon, Wed · Dinner"), next-occurrence date (e.g., "Next: Mon Apr 20"), and an active-or-ended chip. Ended rules (`end_date < today`) render muted and below active ones.
3. Empty state: "No recurring meal plans yet. Create one from the calendar." + button deep-linking to Calendar.
4. Tapping a rule opens an edit sheet — a reused variant of the plan-meal sheet pre-populated with the rule's current fields and pinned to "All occurrences" scope (this surface has no notion of a specific occurrence). Saving writes through `updateRecurrenceRule?scope=all`.
5. The edit sheet here exposes a **Delete series** button. Tapping prompts "Delete this entire series? Past occurrences stay." → confirm → calls `deleteRecurrenceRule?scope=series`.
6. Refresh on reopen: the screen refetches on `didChangeAppLifecycleState: resumed` and on pull-to-refresh.
7. NFR39 holds: list renders for 50 rules under 200ms at P95 (uses existing recipe-cache for thumbnails; no extra fetch).
8. A share-nothing-private guard: rules `is_shared == false` created by other household members do not appear in Leo's list. Rules `is_shared == true` created by household members *do* appear, with a "Shared by Partner Name" subtitle, and the edit sheet opens **fully editable** (co-edit per design principle #10). `owner_id` is preserved on the server across edits — co-edit does not transfer ownership. The edit sheet surfaces a small "Created by Partner Name" caption so Leo knows which household member originally set the rule up.
9. **All-ended empty state**: when a user has no active rules but has at least one ended rule, the empty-state copy reads "No active recurring plans. (N ended plans hidden — tap to show.)" with a tap target that expands the list to include the muted ended rules. When there are zero rules of any kind, the standard empty state applies.
9. Tests: widget tests for empty state, single-rule render, mixed active/ended list, tap-to-edit wiring.

### Key Files
- Modify: `app/lib/features/profile/profile_screen.dart` (ListTile entry)
- Create: `app/lib/features/profile/recurring_plans/recurring_plans_screen.dart`
- Create: `app/lib/features/profile/recurring_plans/widgets/rule_row.dart`
- Modify: `app/lib/features/calendar/services/meal_calendar_service.dart` (add `listRecurrenceRules`)
- Modify: `app/lib/core/router/*.dart` (if route registration is explicit)
- Tests: `app/test/features/profile/recurring_plans_screen_test.dart`

---

## Definition of Done (Epic Level)

- Every recurring-occurrence edit action on the calendar routes through the This / Following / All prompt.
- "This and following" rule-split leaves no gap and no overlap.
- Monthly-nth-weekday rules can be created from the plan-meal sheet and render correctly for first/second/third/fourth/last.
- Leo can see every rule he owns from Profile → Recurring plans and edit/delete any of them.
- Foundation-epic behaviors (glyph, summary line, End series today, detach-on-single-edit) continue to work unchanged.
- All datetime writes UTC; TZ test case for America/Los_Angeles passes for monthly rules too.
- NFR38 (concurrent-edit convergence) + NFR39 (manage-screen load P95 200ms) pass.

## Open Questions for the User

- **"Last Saturday" semantics in a 4-Saturday month** — the AC treats "last" as "last in calendar month," so in a 4-Saturday month Last == Fourth. Confirm this matches intent, or prefer "always the 5th (skip month if <5)".
- **Manage-screen ended-rule visibility**: should archived/ended rules show at all (muted), or disappear entirely? The story ships muted; call out if disappeared is preferred.
<!-- Answered 2026-04-17: co-edit on shared rules. Implemented in rm-edit-2 auth + rm-edit-4 AC #8 + foundation rm-found-1 AC #6. -->

