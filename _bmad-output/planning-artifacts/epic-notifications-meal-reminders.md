<!-- refined via party-mode 2026-04-21 -->
# Epic: Meal-Time Reminders

## Overview

Today the meal calendar models `scheduled_at` as a full datetime and the Flutter client picks a default per-slot time (`_mealDefaultTime` in `plan_meal_sheet.dart:404-415` → 8:00 / 12:00 / 18:30 / 15:00). What's missing is (a) the user can't override that per meal, (b) `MEAL_EVENT_REMINDER` is a defined notification type with a callsite that is never triggered (no Celery beat task scans upcoming events), and (c) `MEAL_EVENT_UPDATED` exists but `update_meal_event.py` never calls it even on shared events. The `MealEvent` model already supports participants and an `is_shared` flag — fan-out is a query, not a redesign.

The user explicitly framed this in the original ask: "we have it say 'lunch' time, we might need to configure a notification time (12pm) in the meal plan screen." This epic delivers exactly that — plus the missing scheduler + the missing UPDATED callsite + participant fan-out.

**Goal:** at the configured (or defaulted) reminder time, every accepted participant of a meal event gets a push naming the recipe; tapping opens the meal detail screen Epic A built.

## Locked Decisions (inherited + added)

**Inherited (do not re-litigate):**
- iOS-first; Android continues on `firebase_messaging` defaults.
- ErrorReporter for failures; no user toasts on push delivery problems.
- Per-category prefs (Epic A) — meal reminders sit under `prefs.categories.meals`.
- Notification copy library (Epic A) — meal reminder copy lives in `notification_copy.py`.
- `/calendar/meals/:id` deep-link is the tap target (Epic A).

**Locked for this epic (from 2026-04-21 user batch + sensible defaults):**
- **Per-meal "Remind me at" wall-clock time.** New nullable `meal_event.meal_reminder_time` (TIME) column. NULL = use slot default (matches the existing client-side `_mealDefaultTime` mapping). User can override per-meal via a new time picker in `plan_meal_sheet.dart`.
- **Slot defaults are documented constants on the backend.** `MEAL_SLOT_DEFAULT_TIMES = {"breakfast": time(8, 0), "lunch": time(12, 0), "dinner": time(18, 30), "snack": time(15, 0)}`. The scheduler uses these when `meal_reminder_time` is NULL. Mirrors the Flutter constant; both should be kept in sync (one comment cross-referencing).
- **Reminder fires AT the configured time, not "N minutes before."** Existing `notify_prep_start` (60min default) and `notify_cook_start` (30min default) offsets remain separate; this epic doesn't change them. The new reminder is the meal-time ping itself.
- **Fan-out: all accepted participants.** When a meal_event has `is_shared=True`, every participant with `status='accepted'` gets the push. Owner gets it too if they're not in the participants table (defensive — typically the owner is auto-added).
- **Celery beat every 5 minutes.** Task `send_meal_reminders` queries meal_events whose effective reminder time is in the [now, now + 5min] window, dispatches pushes, and marks them sent in a new `meal_event.last_reminder_sent_at` column to prevent duplicates.
- **MEAL_EVENT_UPDATED wired in this epic.** While we're touching the meal-event surface, fix the callsite gap: when `update_meal_event.py` mutates a shared meal's title, scheduled_at, recipe_id, or meal_reminder_time, fire `MEAL_EVENT_UPDATED` to all accepted participants (excluding the actor).
- **Quiet hours respected per recipient.** The existing `_is_quiet_hours` check applies — a participant in quiet hours doesn't get the reminder (unless `force=True` which doesn't apply here). Document that this is intentional: meals at 6:30 PM aren't quiet-hours material; meals at 11:30 PM might be.
- **Recurring meals.** The reminder time is stored on the parent meal_event row (or each materialized instance — confirm during dev which model the recurrence epic landed). One reminder per instance.

## Refinements via party-mode 2026-04-21

**Lens-by-lens cross-examination findings — incorporated into ACs below:**

- **PM:** The reminder fires AT the configured time (not "N minutes before") — the user explicitly wanted "12:00 PM for lunch", not "5 min before lunch". Existing `notify_prep_start` and `notify_cook_start` offsets stay separate (different mental model: prep workflow vs meal-time ping). Locked.
- **UX:** "Remind me at" label tested better than "Reminder time" or "Notification time". Slot-default caption ("Lunch default") is subtle/grey to avoid making the picker look pre-set. Reset-to-default affordance is an inline text button, not a long-press (long-press is undiscoverable here).
- **UX:** Allow reminder time AFTER scheduled_at (e.g., "remind me 30 min late") — valid use for follow-up nudges or "did you start yet?" pings. No upper bound; the picker spans 24h.
- **Frontend:** When user changes meal-type chip with no override set, the displayed default updates to the new slot's default. With override set, override wins (don't surprise-reset on chip change). Folded into meal-2 AC 3.
- **Backend:** **Timezone resolution contract: the RECIPIENT's user timezone wins** for resolving the wall-clock reminder time, not the meal's `scheduled_at` tz. (Meals can be planned across tz boundaries; reminders must hit local time.) Folded into meal-3 risks.
- **Backend:** DST transitions on the reminder date may shift the wall-clock hour by 1. Use `zoneinfo`/`pytz`; accept OS interpretation. Document as known behavior — don't bend backwards to "preserve" a 12:00 AM moment across a fall-back day.
- **Backend:** The composite index in meal-1 must include both `scheduled_at` AND `last_reminder_sent_at` for the scan query to be cheap. Already in AC 1; reinforce.
- **Backend:** Recurring meals — confirm during dev whether the per-instance row carries its own `meal_reminder_time` (preferred) or inherits from a parent rule. The Phase 2 audit suggested per-instance materialization happens; verify.
- **Infra/Devops:** 5-min beat cadence × today's-events-only query × index → bounded cost. Acceptable. Worst-case lag = 5 min (document in task docstring per QA's ask).
- **QA:** Manual smoke-test path: Leo creates a meal at "now + 2 minutes" → push lands within ~5 min of beat tick. This is the dogfood checklist. The 5-min slop is fine for the "reminder me at lunch" UX.
- **QA:** Multi-participant fan-out — test with 3 accepted + 1 declined → 3 pushes, declined excluded. Test with one participant in quiet hours → 2 pushes, that one suppressed (per nfn-1 path).

**Cross-epic locked decisions added by this workshop (propagate to E):**

1. **Celery beat scheduled-reminder tasks share the same idempotency pattern.** Column on parent entity (e.g., `meal_event.last_reminder_sent_at`, `shopping_list.last_deadline_reminder_sent_at`), gated by date comparison in the recipient's timezone. (Epic E adopts this pattern; party-mode flagged a per-user-vs-per-list gap in Epic E that needs fixing — see Epic E refinements.)
2. **Recipient-timezone-wins for all wall-clock-resolved reminders.** The user's `users.timezone` pref is the source of truth, not the source entity's timezone.
3. **DST is the OS's responsibility.** Use `zoneinfo`/`pytz`; don't second-guess.

## End-user flow

### Flow A — Leo creates a meal with a custom reminder time

1. Leo opens the calendar, taps "+ Plan a meal" → meal-create sheet opens.
2. He picks a recipe (Sweet Potato Quiche), date (Saturday), meal-type chip (Lunch). The existing `_mealDefaultTime` populates `scheduled_at` to 12:00 PM.
3. **NEW UI:** below the meal-type chips, a "Remind me at" row appears with a time picker showing the slot default ("12:00 PM (Lunch default)" — the default is shown but greyed/hint-styled). Tapping opens a Material time picker.
4. He sets it to 11:45 AM and saves.
5. Backend persists `meal_event.meal_reminder_time = "11:45"`.
6. On Saturday at 11:45 AM, the Celery beat task picks up the event → fires a push: title "Lunch in 15 — Sweet Potato Quiche 🍳", body "Tap to open the recipe and start prepping." Image attached if recipe has a cover.
7. Tap → `/calendar/meals/{event_id}` (Epic A's detail screen) → Leo sees the meal, taps the recipe card → recipe detail.

### Flow B — Sarah invites Leo to a shared brunch

1. Sarah creates a shared meal: "Saturday brunch — Sweet Potato Quiche", scheduled 11:00 AM, marks Leo as a participant.
2. Leo accepts (existing flow). His participant status becomes `accepted`.
3. The reminder time defaults to the slot default (Brunch isn't a slot — it's typically Breakfast or Lunch; assume Lunch → 12:00 PM, BUT Sarah's `scheduled_at` is 11:00 AM, so the reminder time naturally becomes 11:00 AM — see "Open question" about whether the default tracks scheduled_at or slot).
4. At the reminder time, BOTH Sarah AND Leo get a push (both are accepted participants). Title: "Brunch in 5 — Sweet Potato Quiche 🥞" (or whatever the slot mapping says). Body: "Sarah is also cooking now — tap to coordinate."
5. Tap → meal detail screen, both can see who else is in.

### Flow C — Sarah moves the meal time; Leo is notified

1. Sarah edits the brunch — changes scheduled_at from Saturday 11:00 AM to Saturday 12:30 PM.
2. `update_meal_event.py` detects the change, fires `MEAL_EVENT_UPDATED` to all accepted participants (excluding Sarah).
3. Leo gets: title "Brunch moved to 12:30 PM 🥞", body "Sarah updated 'Saturday brunch'". Tap → meal detail.
4. The reminder time is NOT auto-adjusted (it's a separate user choice). Backend respects whatever Leo / Sarah set; if Sarah's edit also changed the reminder_time field, that's persisted.

### Flow D — User opts out of meal reminders entirely

1. User opens Profile → Notifications → toggles "Meal reminders" off.
2. Backend stores `prefs.categories.meals = false`.
3. Next time the Celery beat task runs, the per-recipient `send_to_user` call hits the category check (Epic A's nfn-1) and is suppressed.
4. The MEAL_EVENT_INVITE flow (existing) ALSO falls under `prefs.categories.meals` and is suppressed — confirm during dev that this is the desired pairing or split into separate keys (`meals_reminders` vs `meals_invites`).

## Frontend changes

- **`app/lib/features/calendar/widgets/plan_meal_sheet.dart`** (MODIFIED)
  - New "Remind me at" section below the meal-type chips. Layout matches the existing chip row pattern: label "Remind me at", `SizedBox(height: 8)`, then a tappable row showing the current time + a small caption "Lunch default" when the user hasn't overridden.
  - Tap opens `showTimePicker(...)`. Selected time updates local state; on save, included in the `MealEventCreate` payload as `meal_reminder_time` (formatted as "HH:MM").
  - When meal-type chip changes, if `meal_reminder_time` is null, the displayed default updates to the new slot's default. If user has overridden, the override is preserved across slot switches (override wins).
  - "Reset to default" inline action (small text button) appears when override is set.

- **`app/lib/features/calendar/models/meal_event.dart`** (MODIFIED)
  - Add `mealReminderTime: String?` field (HH:MM or null).
  - Update `fromJson` / `toJson`.
  - Update `MealEventCreate` / `MealEventUpdate` request DTOs.

- **`app/lib/features/calendar/services/meal_calendar_service.dart`** (MODIFIED)
  - Pass `mealReminderTime` through to API calls.

- **`app/lib/features/calendar/screens/meal_detail_screen.dart`** (MODIFIED — Epic A creates this; this epic adds the reminder time row)
  - Show the reminder time on the detail screen ("Remind at 11:45 AM" or "Remind at default for Lunch (12:00 PM)").
  - Edit affordance opens the same time picker.

- **No changes to `_routeForNotification`** — Epic A already added the `/calendar/meals/:id` deep-link.

## Backend changes

- **Migration: add `meal_event.meal_reminder_time` (TIME, nullable) + `meal_event.last_reminder_sent_at` (DateTime, nullable)** in `services/migrator/migrations/2026XXXX_meal_event_reminder_fields.py`.
  - Index on `(scheduled_at, last_reminder_sent_at)` to make the scheduler's "find upcoming events that haven't been notified" query cheap.

- **`libraries/utils/utils/models/meal_event.py`** (MODIFIED)
  - Add `meal_reminder_time = Column(Time, nullable=True)`.
  - Add `last_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)`.
  - Add a `reminder_time` property that returns `meal_reminder_time` if set, else `MEAL_SLOT_DEFAULT_TIMES[meal_type]`.

- **`services/api/src/schemas/meal_event.py`** (MODIFIED)
  - `MealEventCreate` + `MealEventUpdate` accept optional `meal_reminder_time: time | None`.
  - Validation: if provided, must be a valid 24h time string.

- **`services/api/src/api/v1/meal_event/update_meal_event.py`** (MODIFIED)
  - After commit, if event `is_shared` AND any of `(title, scheduled_at, recipe_id, meal_id, meal_reminder_time)` changed, dispatch `MEAL_EVENT_UPDATED` to all accepted participants (excluding the actor).
  - Use `notification_copy.meal_event_updated(actor_name=..., event_title=..., changed_fields=[...])` for title/body. Suggested copy:
    - If only scheduled_at changed: title `"{title} moved to {new_time}"`, body `"{actor} updated '{title}'"`.
    - If multiple fields changed: title `"{title} updated"`, body `"{actor} made changes to '{title}'"`.
  - Use `image_url` from the recipe (if any).

- **`libraries/utils/utils/services/meal_event_notifications.py`** (NEW or MODIFIED — create if absent)
  - `notify_meal_event_reminder(database, event)`:
    1. Load all accepted participants (and the owner if not in the list).
    2. For each, call `notification_copy.meal_event_reminder(meal_type=event.meal_type, recipe_name=event.recipe.name if event.recipe else None, scheduled_at=event.scheduled_at, is_shared=event.is_shared, partner_name=...)` to get title/body.
    3. Pass `image_url=event.recipe.cover_image_url` if recipe attached.
    4. Send to each participant via `send_to_user` (category check applies via nfn-1).
    5. Update `event.last_reminder_sent_at = now()` to prevent duplicate fires.
  - `notify_meal_event_updated(database, event, actor, changed_fields)`: similar shape.
  - Both functions guard on `event.notification_preferences_for_meals_disabled` etc. only at the recipient level (per-user check) — not at the event level.

- **`libraries/utils/utils/services/notification_copy.py`** (MODIFIED — Epic A creates this)
  - Add `meal_event_reminder(meal_type, recipe_name, scheduled_at, is_shared, partner_name=None)`:
    - Single-person: `("{Slot} in 5 — {recipe_name} 🍳", "Tap to open the recipe and start prepping.")` where `{Slot}` is "Lunch" / "Dinner" etc., and the "5" is computed as minutes until `scheduled_at` from the reminder time (could be 0 if reminder == scheduled).
    - Shared: `("{Slot} in 5 — {recipe_name} 🍳", "{partner_name} is also cooking — tap to coordinate.")`.
    - No recipe attached: `("{Slot} time! 🍳", "Tap to open the meal you planned.")`.
  - Add `meal_event_updated(actor_name, event_title, scheduled_at_changed=False, new_time=None)`:
    - If only time changed: `("{event_title} moved to {new_time}", "{actor_name} updated '{event_title}'")`.
    - Otherwise: `("{event_title} updated", "{actor_name} made changes to '{event_title}'")`.

- **`libraries/utils/utils/tasks/meal_event_tasks/send_meal_reminders.py`** (NEW)
  - Celery task `send_meal_reminders`:
    1. Query meal_events where:
       - `scheduled_at` is today (in the meal's timezone — defer to user timezone if not stored on event).
       - The effective reminder time (`meal_reminder_time` or slot default) falls within `[now, now + 5min]`.
       - `last_reminder_sent_at` is NULL OR < today's reminder window start (allows re-firing for recurring instances).
       - `status` is not `completed` or `skipped`.
    2. For each, call `notify_meal_event_reminder(database, event)`.
    3. Wrap each in a try/except so one bad event doesn't kill the batch; log failures via `logger.exception`.

- **`services/worker/celery_beat.py`** (MODIFIED — or wherever the beat schedule lives; check if it exists, create if not)
  - Add: `'send-meal-reminders': {'task': 'utils.tasks.meal_event_tasks.send_meal_reminders', 'schedule': crontab(minute='*/5')}`.

- **`libraries/utils/utils/services/push_notification.py`** (MODIFIED — Epic A's nfn-1 file)
  - Add to `_category_for_type`:
    - `MEAL_EVENT_INVITE → "meals"`
    - `MEAL_EVENT_REMINDER → "meals"`
    - `MEAL_EVENT_UPDATED → "meals"`

## Infrastructure changes

- **One Celery beat schedule entry.** `send-meal-reminders` runs every 5 minutes. Marginal cost; well within the existing worker capacity.
- **No new infra resources.** Celery beat already provisioned (the import-tasks pipeline uses it).
- **Migration is small** (two nullable columns, one composite index). Safe to apply concurrently.

## Initial Design Principles (pre-party-mode)

1. **The `meal_reminder_time` column is the user's wall-clock preference; the slot default is the fallback.** No magic offset math except within the copy ("in 5 minutes" if reminder == scheduled - 5min).
2. **One source of truth for slot defaults.** Constant on backend, mirrored in Flutter; one comment cross-referencing both files.
3. **Idempotency via `last_reminder_sent_at`.** Beat task running every 5 min must NOT double-fire.
4. **Fan-out is per-recipient suppression-aware.** Each `send_to_user` call independently consults that user's prefs and quiet hours.
5. **MEAL_EVENT_UPDATED is the partner-presence ping.** Don't push for trivial edits (description tweaks); push when title / time / recipe / reminder changes.
6. **Inherit from prior epics.** Epic A's category pref + copy library + deep-link route are the foundation; this epic consumes them.

## File structure (expected)

```
app/lib/features/calendar/
├── widgets/plan_meal_sheet.dart                            # MODIFIED — "Remind me at" picker
├── models/meal_event.dart                                  # MODIFIED — mealReminderTime field
├── services/meal_calendar_service.dart                     # MODIFIED — pass through mealReminderTime
└── screens/meal_detail_screen.dart                         # MODIFIED — show reminder time row

libraries/utils/utils/models/
└── meal_event.py                                           # MODIFIED — add columns + reminder_time property

libraries/utils/utils/services/
├── notification_copy.py                                    # MODIFIED — meal_event_reminder, meal_event_updated copy
├── meal_event_notifications.py                             # NEW — notify_meal_event_reminder, notify_meal_event_updated
└── push_notification.py                                    # MODIFIED — _category_for_type extends

libraries/utils/utils/tasks/meal_event_tasks/
└── send_meal_reminders.py                                  # NEW — Celery task

services/api/src/api/v1/meal_event/
└── update_meal_event.py                                    # MODIFIED — fire MEAL_EVENT_UPDATED on changes

services/api/src/schemas/
└── meal_event.py                                           # MODIFIED — meal_reminder_time field

services/migrator/migrations/
└── 2026XXXX_meal_event_reminder_fields.py                  # NEW

services/worker/
└── celery_beat.py                                          # MODIFIED — add send-meal-reminders schedule
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| meal-1 | Schema: add meal_reminder_time + last_reminder_sent_at columns + API + Flutter model | 🔴 P0 | 0.5 d | nfn-1 (epic A foundation) |
| meal-2 | Frontend: "Remind me at" time picker in plan_meal_sheet | 🔴 P0 | 0.5 d | meal-1 |
| meal-3 | Celery beat task + send_meal_reminders + notify_meal_event_reminder + notification copy | 🔴 P0 | 1 d | meal-1, nfn-2 (copy library) |
| meal-4 | Wire MEAL_EVENT_UPDATED in update_meal_event + copy variants | 🟡 P1 | 0.25 d | nfn-2 |
| meal-5 | meal_detail_screen reminder row + edit affordance | 🟡 P1 | 0.25 d | nfn-5 (epic A detail screen) |

**Total estimated effort: 2.5 days**

---

## Story meal-1: Schema: add columns + API + Flutter model

As a backend,
I want `meal_event` to persist a per-meal reminder time and a last-sent timestamp, with the API + Flutter model accepting/returning the new field,
so that the scheduler has a place to read from and the user has a place to write to.

### Acceptance Criteria

1. New migration `2026XXXX_meal_event_reminder_fields.py` adds:
   - `meal_reminder_time` (TIME, nullable).
   - `last_reminder_sent_at` (DateTime with timezone, nullable).
   - Composite index `idx_meal_event_reminder_scan` on `(scheduled_at, last_reminder_sent_at)`.
2. `MealEvent` model has `meal_reminder_time` + `last_reminder_sent_at` columns AND a `reminder_time` property returning `meal_reminder_time` if set else `MEAL_SLOT_DEFAULT_TIMES[meal_type]`.
3. `MEAL_SLOT_DEFAULT_TIMES` constant defined in `meal_event.py` model module:
   ```python
   MEAL_SLOT_DEFAULT_TIMES = {
       "breakfast": time(8, 0),
       "lunch": time(12, 0),
       "dinner": time(18, 30),
       "snack": time(15, 0),
   }
   ```
   Comment cross-referencing `app/lib/features/calendar/widgets/plan_meal_sheet.dart:404-415`.
4. `MealEventCreate` + `MealEventUpdate` schemas accept `meal_reminder_time: time | None`. Output DTOs include `meal_reminder_time` and `reminder_time` (the resolved value).
5. Flutter `MealEvent` model: `mealReminderTime: String?` field, parsed/serialized as "HH:MM".
6. `MealCalendarService.createMealEvent` / `updateMealEvent` pass through the field.
7. Backend tests:
   - Test A: create meal with `meal_reminder_time = "11:45"` → DB row has the value.
   - Test B: create meal without it → column is NULL, `reminder_time` property returns slot default.
   - Test C: update meal with new reminder_time → persisted, last_reminder_sent_at unchanged.
   - Test D: invalid time string → 400.

### Key Files
- Create: `services/migrator/migrations/2026XXXX_meal_event_reminder_fields.py`
- Modify: `libraries/utils/utils/models/meal_event.py`
- Modify: `services/api/src/schemas/meal_event.py`
- Modify: `app/lib/features/calendar/models/meal_event.dart`
- Modify: `app/lib/features/calendar/services/meal_calendar_service.dart`
- Test: `services/api/tests/api/v1/meal_event/test_create_meal_event.py`, `test_update_meal_event.py`

### Risks / notes
- TIME column is timezone-naive (just hour:minute). Combine with the event's date and the user's timezone to resolve the wall-clock moment — don't store a full datetime.
- Recurring meals: the `reminder_time` lives on each materialized instance per the existing recurrence model. Confirm during dev which row is being updated.

---

## Story meal-2: Frontend "Remind me at" time picker

As Leo,
I want to set a custom reminder time when I'm planning a meal — defaulting to the slot's standard time but easy to override,
so that I get pinged when I actually want to start cooking, not always at exactly 12:00 for lunch.

### Acceptance Criteria

1. `plan_meal_sheet.dart` adds a "Remind me at" section below the meal-type chips. Layout: label "Remind me at" + a tappable row showing the resolved time + a small caption "Lunch default" (or appropriate slot name) when not overridden.
2. Tap opens `showTimePicker`. Selected time updates local state.
3. When user changes meal-type chip:
   - If `mealReminderTime` is null (not overridden), the displayed default updates to the new slot's default (8/12/18:30/15).
   - If user has set an override, the override is preserved (override wins; show "Custom" or the explicit time without the "Lunch default" caption).
4. A "Reset to default" inline text button appears when an override is set; tapping it clears `mealReminderTime` to null.
5. On save, `mealReminderTime` is included in the create/update payload as "HH:MM" or omitted if null.
6. Default behavior matches the backend — when `mealReminderTime` is null, the backend resolves to slot default. The Flutter UI displays the same default for visual consistency.
7. Flutter widget tests:
   - Test A: open sheet, pick Lunch chip → "Remind me at" shows "12:00 PM" with "Lunch default" caption.
   - Test B: pick Dinner chip → "6:30 PM" with "Dinner default" caption.
   - Test C: tap row → time picker → set 11:45 AM → caption disappears, shows "11:45 AM" with Reset button.
   - Test D: switch to Snack chip with override set → still shows 11:45 AM (override preserved).
   - Test E: tap Reset → returns to "3:00 PM" (Snack default) with caption.
   - Test F: save with override → payload includes `meal_reminder_time: "11:45"`.
   - Test G: save without override → payload omits `meal_reminder_time` (or sends null).

### Key Files
- Modify: `app/lib/features/calendar/widgets/plan_meal_sheet.dart`
- Test: `app/test/features/calendar/plan_meal_sheet_test.dart` (or equivalent)

### Risks / notes
- The slot defaults must match the backend's `MEAL_SLOT_DEFAULT_TIMES` — keep a one-line comment cross-referencing the backend constant.
- The time picker's locale should respect the device locale (12h/24h format follows OS settings).

---

## Story meal-3: Celery beat task + reminder fan-out + copy

As a meal participant,
I want to actually receive a push at the meal's reminder time, naming the recipe and noting whether others are also cooking,
so that the entire reminder feature stops being vapor.

### Acceptance Criteria

1. New Celery task `send_meal_reminders` in `libraries/utils/utils/tasks/meal_event_tasks/send_meal_reminders.py`:
   - Queries: meal_events where today's date matches `scheduled_at::date` AND the resolved reminder time falls within `[now, now + 5min]` AND `last_reminder_sent_at IS NULL OR last_reminder_sent_at < today's window start` AND `status NOT IN ('completed', 'skipped')`.
   - For each: call `notify_meal_event_reminder(database, event)`.
   - Wrap each event in try/except; on error, log via `logger.exception` AND write an `error_logs` row with `service="push_notifications"`, `error_type="MealReminderTaskError"`. Don't kill the batch.
2. `notify_meal_event_reminder(database, event)`:
   - Loads accepted participants (+ owner if not in participants table).
   - For each user: resolves copy via `notification_copy.meal_event_reminder(meal_type=..., recipe_name=..., scheduled_at=..., is_shared=event.is_shared, partner_name=other_participant_first_name)`.
   - Constructs `PushNotification` with image from `event.recipe.cover_image_url` if present.
   - Calls `send_to_user(user, notification, db_session, force=False)` — category check + quiet hours apply per recipient.
   - After fan-out: `event.last_reminder_sent_at = now()`; `database.commit()`.
3. `notification_copy.meal_event_reminder` returns:
   - Single (no other participants): `("{Slot} in 5 — {recipe_name} 🍳", "Tap to open and start prepping.")`. Or "{Slot} time! 🍳" if no recipe.
   - Shared (multiple participants): `("{Slot} in 5 — {recipe_name} 🍳", "{partner_name} is also cooking — tap to coordinate.")`.
   - Special-case `meal_type=snack`: emoji `🥨`, no time-prefix variant.
4. Celery beat schedule entry: `crontab(minute='*/5')` for `send-meal-reminders`.
5. Backend tests:
   - Test A: meal at 12:00 PM today, `meal_reminder_time=null`, slot=lunch, no participants → at 12:00 PM, owner gets push, `last_reminder_sent_at` is set.
   - Test B: meal at 12:00 PM today, `meal_reminder_time="11:45"` → at 11:45 PM, push fires; at 12:00 PM, no second push (last_reminder_sent_at gates it).
   - Test C: shared meal with 2 accepted + 1 declined participants → 2 pushes (declined excluded).
   - Test D: participant has `prefs.categories.meals=false` → suppressed for them, others still fire.
   - Test E: participant in quiet hours → suppressed for them.
   - Test F: meal is `status=skipped` → no push.
   - Test G: task crashes mid-batch on event B → events A and C still get pushes; error_logs row written for B.
   - Test H: idempotency — task runs at 12:00 PM, then again at 12:05 PM for the same window → push fires once.
6. Manual verification: Leo creates a meal for "Lunch in 2 minutes from now" with himself as the only accepted participant. Push lands within ~5 min (next beat tick).

### Key Files
- Create: `libraries/utils/utils/tasks/meal_event_tasks/send_meal_reminders.py`
- Create: `libraries/utils/utils/services/meal_event_notifications.py` (or extend existing)
- Modify: `libraries/utils/utils/services/notification_copy.py`
- Modify: `services/worker/celery_beat.py`
- Modify: `libraries/utils/utils/services/push_notification.py` (add MEAL_EVENT_* to _category_for_type)
- Test: `libraries/utils/tests/services/test_meal_event_notifications.py`, `libraries/utils/tests/tasks/test_send_meal_reminders.py`

### Risks / notes
- **Timezone contract (locked by party-mode):** the RECIPIENT's user timezone wins for resolving the wall-clock reminder moment, NOT the meal's `scheduled_at` timezone. (Cross-tz planning is supported; reminders hit each recipient's local clock.) For each accepted participant, combine the meal's `event_date` (or `scheduled_at::date`) + their timezone + the resolved `reminder_time` to compute the UTC moment, compare against the [now, now+5min] window.
- **DST transitions (locked by party-mode):** the wall-clock minute may shift by 1 hour on DST switch days. Use `zoneinfo`/`pytz`; accept OS interpretation. Don't try to "preserve" the original-intent moment across the switch.
- **Recurring meals:** confirm during dev whether the materialized instance carries its own `meal_reminder_time` (preferred) or inherits from a parent recurrence rule. If the latter, decide whether instance-level overrides are allowed (recommendation: yes — store per-instance).
- Beat lag: a 5-min cadence means worst-case 5 min late. Acceptable per UX (the user picked a wall-clock minute, not a precise nanosecond). Document the cadence in the task docstring.
- Don't query all events every tick — restrict to today's events with the composite index `(scheduled_at, last_reminder_sent_at)` from meal-1 AC 1.

---

## Story meal-4: Wire MEAL_EVENT_UPDATED on shared meal edits

As Sarah,
I want my partner to be notified when I move our shared dinner from 7pm to 8pm,
so that they don't show up at the wrong time and the existing-but-dormant MEAL_EVENT_UPDATED enum starts firing.

### Acceptance Criteria

1. `update_meal_event.py` (or wherever PATCH/PUT meal_event lives) detects field changes by comparing the request payload against the loaded event.
2. After commit, if `event.is_shared == True` AND any of `(title, scheduled_at, recipe_id, meal_id, meal_reminder_time)` changed, call `notify_meal_event_updated(database, event, actor=current_user, changed_fields=[...])`.
3. The fan-out excludes `actor` (don't notify yourself of your own edit).
4. Copy via `notification_copy.meal_event_updated(actor_name, event_title, scheduled_at_changed, new_time)`:
   - If only scheduled_at changed: `("{event_title} moved to {new_time}", "{actor_name} updated '{event_title}'")`.
   - Otherwise: `("{event_title} updated", "{actor_name} made changes to '{event_title}'")`.
5. Image: `event.recipe.cover_image_url` if attached.
6. Each recipient's `prefs.categories.meals` and quiet hours apply (per nfn-1).
7. Backend tests:
   - Test A: shared event, change title → other accepted participants get push, actor doesn't.
   - Test B: shared event, change scheduled_at → push title is "{event} moved to {new_time}".
   - Test C: shared event, change description only → no push (description not in trigger set).
   - Test D: non-shared event, change title → no push.
8. Manual verification: Sarah edits a shared meal's time → Leo's phone gets the push.

### Key Files
- Modify: `services/api/src/api/v1/meal_event/update_meal_event.py`
- Modify: `libraries/utils/utils/services/meal_event_notifications.py` (notify_meal_event_updated function)
- Modify: `libraries/utils/utils/services/notification_copy.py`
- Test: `services/api/tests/api/v1/meal_event/test_update_meal_event.py`

### Risks / notes
- The "did this field change" check should be done BEFORE committing (load original, compare to request) so we don't have to do a re-read post-commit.
- Don't push for participant-list mutations (those have their own enum: MEAL_EVENT_INVITE on add, future MEAL_EVENT_PARTICIPANT_LEFT on remove).

---

## Story meal-5: Meal detail screen — reminder time row + edit

As Leo,
I want to see the reminder time on the meal detail screen and tap to change it,
so that I don't have to open the full edit sheet just to tweak when I get pinged.

### Acceptance Criteria

1. `meal_detail_screen.dart` (created in nfn-5) adds a "Reminder" row showing:
   - The resolved time (`meal_reminder_time` if set, else slot default).
   - Caption "(Lunch default)" when not overridden.
2. Tap opens `showTimePicker`; selecting a time saves immediately via `MealCalendarService.updateMealEvent` with `mealReminderTime` updated.
3. Long-press OR a small "Reset" affordance reverts to slot default (sets `mealReminderTime` to null).
4. Saving triggers MEAL_EVENT_UPDATED to other accepted participants if event is shared (Story meal-4 path).
5. Loading + error states match the rest of the detail screen.

### Key Files
- Modify: `app/lib/features/calendar/screens/meal_detail_screen.dart`
- Test: `app/integration_test/meal_detail_screen_test.dart`

### Risks / notes
- Quick-save UX: don't require a "Save" button just for the reminder edit. Auto-save on picker dismiss matches calendar-app conventions.

## Dependencies

- Depends on **Epic A (foundation)**: nfn-1 (per-category prefs + `_category_for_type` extension), nfn-2 (notification_copy.py), nfn-5 (meal detail screen).
- meal-1 blocks meal-2, meal-3, meal-5.
- meal-3 blocks meal-5 (the screen shows the reminder time the scheduler reads from).
- meal-4 is parallel after Epic A's nfn-2.

## Open questions for the user

- **Scheduled-at vs slot default for the reminder.** When the user picks a meal-type chip but their `scheduled_at` (set via the date picker) implicitly already has a time component (e.g., they're rescheduling an existing meal to 11:00 AM), should the default `reminder_time` track `scheduled_at`'s time, or always the slot default? Defaulting to slot makes the UX predictable but may not match the user's intent for a one-off reschedule. Default for now: slot default; "Reset to default" is the user's escape valve.
- **Pairing of MEAL_EVENT_INVITE with the meals category toggle.** Today the enum value is wired (Phase 2 audit confirms). With Epic A's category mapping, MEAL_EVENT_INVITE → "meals". Should an opt-out of meal *reminders* also opt out of meal *invites*, or split into `meals_reminders` vs `meals_invites`? Default: one bucket. Can be split if user feedback says otherwise.

## Definition of Done (Epic Level)

- A meal created with no override gets a reminder push at the slot's default time, naming the recipe.
- A meal with a `meal_reminder_time` override gets the push at the override time.
- A shared meal fires reminders to every accepted participant (not just owner).
- Editing a shared meal's title or time fires MEAL_EVENT_UPDATED to other accepted participants.
- The meal detail screen shows the reminder time and allows in-place edit.
- `last_reminder_sent_at` prevents double-fires within the same beat tick window.
- Per-recipient category prefs and quiet hours are respected.
- Manual smoke test: Leo creates a meal for 5 minutes from now, gets the push within ~5 min.
