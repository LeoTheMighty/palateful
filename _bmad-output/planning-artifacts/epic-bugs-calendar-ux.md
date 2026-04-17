<!-- refined via party-mode 2026-04-16 -->
# Epic: Calendar Meal UX — From Read-Only Grid to Action Surface

## Overview

The calendar today shows meals but does almost nothing with them. Tapping a meal jumps straight to the recipe detail page with no chance to reschedule, unschedule, mark as cooked, or even see day-level context. Recurrence columns exist on `meal_event` but the Flutter sheet never surfaces a recurrence control. Planning a meal lets the user type free text with no link to the recipes they already own. This epic closes those three gaps and makes the calendar feel like a planning tool, not a display-only grid.

**Goal:** When Leo opens the calendar, every interaction (tap a meal, tap a day, plan a new meal) is actionable in one or two taps — and every planned meal is tied to a real recipe unless the user deliberately chooses free text.

## Design Principles (refined via party-mode 2026-04-16)

1. **Primary action is ranked** (Sally) — the meal detail sheet has one big button (Open Recipe) plus a secondary icon row for reschedule/unschedule/cooked. Not four buttons of equal visual weight.
2. **Recent meals are the fast path** (Sally) — recipe autocomplete shows recent-meals chips on empty input and replaces them with search results as the user types. Leo replans the same meals weekly.
3. **Free-text escape hatch is explicit** (John) — no match → render a "Save '<typed text>' as free-text meal" row as the fallback. Not a keyboard-hint whisper.
4. **Bottom sheets don't stack** (Sally) — day-detail sheet inline-expands meal rows or dismisses before meal-detail opens. No sheet-on-sheet.
5. **All datetime writes are UTC; reads render in device-local.** Time-zone test case is mandatory.
6. **Audit before build** (Winston) — recurrence rendering depends on whether the backend expands server-side. Don't speculate the implementation path; gate bugs-cal-3 on the audit.
7. **"Never" is the default label** for opt-in recurrence. Not "Does not repeat."
8. **Destructive on single-element = silent collapse.** Unschedule a series with 1 remaining occurrence = deletes the series without prompting "this vs all."

## Inherited Locked Decisions (from workshops 1+2)

- No feature flags, no backwards-compat shims.
- Admin-only gates live on `is_admin`.
- Destructive user actions use snackbar-undo (3s).
- Audit-log all admin-invoked mutations.
- Idempotent writes over wider transactions.
- Directories: ops scripts → `services/api/scripts/`; migrations → `services/migrator/migrations/`; Flutter feature subdirs → `app/lib/features/<area>/widgets/`.
- No stories for capabilities without a named user ask.
- Tab-open / surface-open marks all loaded items read; server wins on cold-start reconcile.
- Deep-link query params are canonical and enum-extended.
- Constructive actions don't get snackbar-undo (applies to approve, schedule, add). Destructive do.
- Field-render policy: every backend-returned field is rendered or annotated-not-shown.

## File Structure (expected)

```
app/lib/features/calendar/
├── widgets/
│   ├── meal_detail_sheet.dart           # NEW — primary Open Recipe + secondary icons
│   ├── day_detail_sheet.dart            # NEW — inline-expandable meal rows, no sheet nesting
│   ├── plan_meal_sheet.dart             # MODIFIED — autocomplete + recurrence field
│   ├── recipe_autocomplete_field.dart   # NEW — 300ms debounce, recipe-scoped, 2s timeout → local cache
│   └── recurrence_field.dart            # NEW — "Repeats: Never | Daily | Weekly | Monthly" + end date
└── calendar_screen.dart                 # MODIFIED — tap routes to meal_detail_sheet, not recipe

services/api/src/api/v1/meal_event/
├── update_meal_event.py                 # AUDIT — partial-update shape for scheduled_at
└── list_meal_events.py                  # AUDIT — server-side recurrence expansion or not
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| bugs-cal-1 | Meal detail sheet + day detail sheet (tap-to-act) | 🔴 P0 | 1–2 d | None |
| bugs-cal-2 | Recipe autocomplete in plan-meal sheet | 🔴 P0 | 1 d | None (parallel) |
| bugs-cal-3 | Recurrence UI in plan-meal sheet | 🟡 P1 | 0.5–1 d (gated) | bugs-cal-2; backend audit |
| bugs-cal-3b | *(conditional)* Backend server-side recurrence expansion | 🟡 P1 | 1 d | Only if audit in bugs-cal-3 reveals missing server expansion |

**Total estimated effort: 2.5–5 days** (range depends on the bugs-cal-3 audit outcome).

**Sequencing:** bugs-cal-1 and bugs-cal-2 run in parallel. bugs-cal-3 starts with the audit; if server-side expansion is missing, bugs-cal-3b is spawned and bugs-cal-3 defers.

---

## Story bugs-cal-1: Meal detail sheet and day detail sheet

As Leo,
I want tapping a calendar meal to open a disclosure sheet with a primary Open Recipe action and secondary quick actions,
so that I can reschedule, unschedule, or mark cooked without losing my place on the calendar.

### Acceptance Criteria

1. Tapping a meal tile opens a bottom sheet with:
   - **Header:** recipe thumbnail (if attached) + meal title + scheduled local datetime
   - **Primary button** (prominent, full-width): **Open Recipe** (disabled + grayed when no recipe attached)
   - **Secondary icon row** below: Reschedule, Unschedule, Mark as Cooked
2. **Reschedule** opens a date+time picker pre-filled with current local-time `scheduled_at`, writes UTC on submit, dismisses the sheet, and the calendar reflects the new position.
3. **Unschedule** calls `DeleteMealEvent` with 3s snackbar-undo (per locked decision #3). Optimistic removal from calendar.
4. **Mark as Cooked** — scoped gate: the story implementation begins by confirming Epic 6's post-cook feedback flow is invokable from here. If yes, this action launches that flow. If no, **this action is cut from the story and filed as a follow-up** (`bugs-cal-1a-mark-as-cooked-wiring`). Do not ship a half-built cook-logging button.
5. Tapping an empty day cell opens a day detail sheet listing all meals for that day as **inline-expandable rows** (not nested sheets — locked decision #14). Empty days show an inline "Plan a meal" CTA.
6. Tapping a meal row inside the day detail sheet either (a) inline-expands the row to show the same actions as the meal detail sheet, or (b) dismisses the day sheet and opens the meal detail sheet. Implementer picks one — no sheet-on-sheet.
7. Bare tap on meal always opens the sheet. Direct navigation to recipe on tap is removed.
8. Recurring-series destructive actions (Unschedule, Reschedule) prompt "This occurrence / All occurrences" — **except when the series has only 1 remaining occurrence**, in which case the action applies silently to the series (locked decision #20).
9. **UTC / local TZ test case:** user in `America/Los_Angeles` creates a meal at 7pm local; background app for 6 hours; foreground; meal still renders at 7pm local, not 1am next day.

### Key Files
- Create: `app/lib/features/calendar/widgets/meal_detail_sheet.dart`
- Create: `app/lib/features/calendar/widgets/day_detail_sheet.dart`
- Modify: `app/lib/features/calendar/calendar_screen.dart`
- Audit: `services/api/src/api/v1/meal_event/update_meal_event.py`, `delete_meal_event.py`
- Audit: Epic 6 post-cook feedback flow reachability

---

## Story bugs-cal-2: Recipe autocomplete in plan-meal sheet

As Leo,
I want the plan-meal sheet to show my recent meals first and autocomplete against my recipes as I type,
so that planning a weekly meal takes one tap and every new meal is tied to a real recipe unless I explicitly opt out.

### Acceptance Criteria

1. The plan-meal sheet's title/name input becomes an autocomplete field.
2. **On empty input**: show recent-meals chips (existing feature preserved and promoted to fast-path position at the top of the results area).
3. **On typing** (300ms debounce, aligned with existing app-wide search debounce): recent chips replace with up to 8 recipe matches. Each row shows thumbnail + title + book badge.
4. Autocomplete queries `unified_search` **scoped to recipes only** (explicit scope param — locked decision #17). No user results accidentally surfacing.
5. P95 ≤ 300ms for recipe collections ≤ 5,000 recipes.
6. **Network degradation fallback:** if the autocomplete request exceeds 2s, fall back to showing matching recent-meals from the local cache. Sheet never blocks on a slow request.
7. **No-match state:** when the user has typed and no recipes match, the results area shows a single row: **"Save '<typed text>' as free-text meal"**. Tapping it submits the meal with `recipe_id: null` and `title` = typed text.
8. Tapping a matched recipe result fills the title field with the recipe's name and shows a tappable **"Linked to [Recipe]"** chip below the input.
9. **Chip tap = detach**: detaching downgrades the meal to free-text while preserving the typed title. (Not "change linked recipe" — that's re-typing.)
10. Autocomplete is keyboard-friendly on web (arrow keys + enter) and uses native select on mobile.

### Key Files
- Create: `app/lib/features/calendar/widgets/recipe_autocomplete_field.dart`
- Modify: `app/lib/features/calendar/widgets/plan_meal_sheet.dart`
- Reuse: `services/api/src/api/v1/search/unified_search.py` (with explicit recipe scope param)

---

## Story bugs-cal-3: Recurrence UI in plan-meal sheet

As Leo,
I want a simple recurrence control on the plan-meal sheet,
so that I can set up a "pizza Friday" without editing each week manually.

### Acceptance Criteria

1. **Audit task (gating):** before implementation, audit `ListMealEvents` to determine whether the backend expands recurring occurrences server-side or returns the RRULE and expects client expansion.
   - **If server-side expansion exists:** this story proceeds as written below.
   - **If it doesn't:** spawn `bugs-cal-3b-backend-recurrence-expansion` as a new backlog story; this story defers until bugs-cal-3b lands.
2. The plan-meal sheet exposes a **"Repeats: [Never ▼]"** dropdown with options: **Never** (default), **Daily**, **Weekly**, **Monthly**.
3. Selecting anything other than Never reveals an "Ends on" date picker, optional (defaults to no end).
4. Submit writes iCalendar RRULE (`FREQ=WEEKLY`, `FREQ=DAILY`, `FREQ=MONTHLY`), `is_recurring=true`, and `recurrence_end_date` when set. All existing columns — no migration.
5. Calendar renders recurring occurrences via the server-side expansion (confirmed in AC#1).
6. **Editing an existing recurring meal:** the current rule is pre-selected; changing to "Never" **preserves all existing future occurrences as independent one-offs** (no data loss). Persist the existing occurrences as one-off meal_events before clearing the rule.
7. No split-series editing UX ("edit this and all future"). Editing a recurring meal's rule from the plan-meal sheet edits the whole series from the edit point forward. Editing a single occurrence of a series is done via the unschedule-this-occurrence + create-one-off flow in bugs-cal-1.
8. Recurrence UI does not appear when editing a single converted one-off from a series.
9. Deletion of a recurring occurrence is governed by bugs-cal-1 AC#8.

### Key Files
- Modify: `app/lib/features/calendar/widgets/plan_meal_sheet.dart`
- Create: `app/lib/features/calendar/widgets/recurrence_field.dart`
- Audit: `services/api/src/api/v1/meal_event/list_meal_events.py` (server-side recurrence expansion)
- Reuse: `libraries/utils/utils/models/meal_event.py` (columns already present)

## Definition of Done (Epic Level)

- Calendar meal tap never black-holes the user on the recipe page — a sheet always appears with a ranked primary action.
- Every meal Leo plans after this epic lands is attached to a recipe unless he explicitly taps "Save as free-text meal."
- At least one recurring meal (e.g., "pizza Friday") is set up and rendering correctly on Leo's calendar for the next four weeks.
- Time-zone test case passes: meals stay at their original local time across app backgrounds.
- Bugs-cal-3 either ships directly (if server-side expansion exists) or bugs-cal-3b is spawned and this story defers.
