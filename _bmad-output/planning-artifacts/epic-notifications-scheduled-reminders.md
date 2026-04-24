<!-- refined via party-mode 2026-04-21 -->
# Epic: Scheduled Reminders Backend — Shopping Deadlines + Import Failures

## Overview

Two small backend gaps the Phase 2 audit surfaced:

1. **`SHOPPING_DEADLINE_REMINDER` is dead enum.** The notification type is defined and the Flutter side has a deep-link case for it, but no backend code ever invokes the send. Shopping list items have a `due_at` field; nothing scans them. The user manually checks deadlines in the in-app UI today.
2. **Import-failure notifications are silent.** Per the abi-2a comment in `extract_recipe_task.py:239` and `create_recipe_task.py`, full-job failure (every item failed extraction) does NOT push. Failures only surface in the Imports tab. For the user's reasonable expectation that "every notification we might want" includes a "your import failed" ping, we add a single full-job-failure push.

Both share the same execution model — Celery-driven, fire on a backend trigger, no frontend changes. They get one epic together because they're small and similar.

**Goal:** users with deadline-tagged shopping items get a morning summary push the day items are due; users whose entire bulk import fails get one consolidated "couldn't import" push instead of silent failure.

## Locked Decisions (inherited + added)

**Inherited (do not re-litigate):**
- iOS-first; Android continues on `firebase_messaging` defaults.
- ErrorReporter for failures.
- Per-category prefs (Epic A).
  - Shopping deadline reminders sit under `prefs.categories.shopping`.
  - Import failures sit under `prefs.categories.imports`.
- Notification copy library lives in `notification_copy.py` (Epic A).

**Locked for this epic (from 2026-04-21 user batch + sensible defaults):**
- **One push per list per morning** — not per item. If "Weekend BBQ" has 3 items due today, a single push: "🛒 3 items on Weekend BBQ are due today". Per-item pushes would spam.
- **"Morning of" timing** — the beat task runs at 8:00 AM in each user's timezone. (Use the existing `users.timezone` field.) The 5-minute beat cadence is fine — the task fires once per user per day.
- **Idempotency** via a new `shopping_list.last_deadline_reminder_sent_at` (DateTime) column. Set when fired; cleared when a new item is added that pushes a future date.
- **Full-job-failure push only** for imports. Per-item failures stay in the Imports tab (the abi-2a decision stands). When `ImportJob.status` transitions to `failed` (every item terminal-failed), one push fires.
- **Failure copy includes the source identifier** when available (URL hostname, file name, "your bulk import").
- **No retry button in the notification** (action buttons on push are out of scope for this epic). The Flutter route deep-links to the import-job detail screen where the user can tap retry.
- **No new NotificationType** — `SHOPPING_DEADLINE_REMINDER` already exists; for the import failure, add `IMPORT_FAILED` (new).

## Refinements via party-mode 2026-04-21

**Lens-by-lens cross-examination findings — incorporated into ACs below:**

- **🔴 Backend (sharp gap caught by party-mode):** Storing `last_deadline_reminder_sent_at` on `shopping_list` is **wrong for shared lists** — one user's morning push would silence the other user's morning push (different timezones → different mornings). **Idempotency must be per-user-per-list-per-day.** Two design options:
  - **Option A (preferred):** new lightweight table `shopping_list_user_reminder_state(user_id, shopping_list_id, last_deadline_reminder_sent_at)` with composite PK. One row per (user, list) pair; updated on each successful fire. Migration is small.
  - **Option B:** JSONB map on `shopping_list.deadline_reminder_state = {"<user_id>": "<iso_timestamp>"}`. Less explicit but no new table.
  - **Default: Option A** for queryability and clarity. Migration adds the new table; original `last_deadline_reminder_sent_at` column on shopping_list is NOT added.
- **Backend:** Efficient "is it 8 AM in user's tz?" query — pre-group users by timezone (single SELECT DISTINCT timezone), iterate only the timezone groups currently in the [8:00 AM, 8:05 AM] window. Avoids a per-user-per-tick check.
- **Backend:** Verify during dev that the import job's `"failed"` terminal-status transition actually fires reliably (the `_update_job_counts` pattern handles it; confirm by reading the actual transition lines). If items can drop silently into a non-`failed` state without firing the transition (e.g., `cancelled` after partial work), the IMPORT_FAILED hook misses them.
- **UX:** Failure copy "We couldn't extract" is appropriately neutral (not blame-y). Source label included for context. Hostnames in title truncated to 30 chars with ellipsis if needed.
- **Infra/Devops:** No new resources beyond one Celery beat schedule entry + one new table. Within `$50/mo` cost cap.
- **QA:** Critical test (added by party-mode): two users sharing the same list — both get their respective morning push, neither suppresses the other.
- **QA:** Test for `cancelled` import jobs — no IMPORT_FAILED push (user knows; they cancelled).

**Cross-epic locked decisions added by this workshop:**

1. **Per-user-per-entity idempotency for shared-resource scheduled reminders.** Don't put `last_X_sent_at` on the shared parent if the reminder is per-user. Use a join table or JSONB map. (Epic B's meal_event uses parent-row column because reminders fire per-event-fan-out, but each fan-out is gated only on `last_reminder_sent_at` — confirm during meal-3 dev whether shared meals need per-participant gating too. Likely yes; add a sub-row idempotency mirror if user feedback says reminders are missing for some participants.)

## End-user flow

### Flow A — Leo wakes up Sunday with shopping items due that day

1. Leo planned a Weekend BBQ on Sunday. He added 5 items to the "Weekend BBQ" shopping list with `due_at = Sunday`. Two items are checked off Saturday night.
2. Sunday morning, 8:00 AM in Leo's timezone (America/Denver per his prefs), the Celery beat task `send_shopping_deadline_reminders` fires.
3. The task scans shopping_list_items where `due_at::date = today (in user tz) AND is_checked = false AND user_id = X`, groups by list, finds Leo has 3 unchecked items on "Weekend BBQ".
4. Push to Leo: title "🛒 3 items on Weekend BBQ are due today", body "Tap to see what's left.". No image (shopping lists don't have covers).
5. Tap → `/cart` (existing route).
6. The shopping_list row gets `last_deadline_reminder_sent_at = now()`. If Leo adds another due-today item Sunday afternoon, the next morning's task won't double-fire (today is already done).

### Flow B — Sarah's bulk import of 5 URLs all fail extraction

1. Sarah pastes 5 URLs into a bulk import. Worker processes each.
2. Two URLs return blank pages (extraction returns nothing). Two URLs return "URL unreachable". One URL is paywalled.
3. All 5 items end in `status = "failed"`. `ImportJob` transitions to `status = "failed"`.
4. `create_recipe_task._update_job_counts` (or the existing terminal-state handler) detects the full-failure transition and fires `IMPORT_FAILED` to Sarah.
5. Push: title "🛑 Bulk import failed", body "We couldn't extract any of the 5 recipes. Tap to retry."
6. Tap → `/recipes/import/review-list/{job_id}` (existing route — review-list shows the failed items with retry/dismiss affordances).

### Flow C — Leo's single-URL import fails

1. Leo pastes a single URL of a paywalled recipe blog. Worker tries extraction, gets nothing, marks the item `failed`.
2. `ImportJob` transitions to `failed` (single item, all failed).
3. Same path as Flow B. Push: title "🛑 Couldn't import from {hostname}", body "We couldn't extract a recipe from {url_hostname}. Tap to retry."

## Frontend changes

- **`app/lib/core/services/push_notification_service.dart`** (MODIFIED — `_routeForNotification`)
  - Add case for `import_failed`: route to `/recipes/import/review-list/{import_job_id}` (same as the existing import_needs_review case — falls back to `/` if missing).
  - SHOPPING_DEADLINE_REMINDER case already exists routing to `/cart` — no changes.

## Backend changes

- **Migration: new `shopping_list_user_reminder_state` table** (party-mode-corrected; replaces the original "column on shopping_list" approach which was wrong for shared lists) in `services/migrator/migrations/2026XXXX_shopping_list_user_reminder_state.py`.
  - Schema:
    - `user_id` (UUID, FK to users.id, indexed)
    - `shopping_list_id` (UUID, FK to shopping_lists.id, indexed)
    - `last_deadline_reminder_sent_at` (DateTime with timezone, nullable)
    - Composite PK: `(user_id, shopping_list_id)`
  - Cascade on user/list delete.

- **`libraries/utils/utils/models/shopping_list_user_reminder_state.py`** (NEW)
  - SQLAlchemy model for the join table.

- **`libraries/utils/utils/services/push_notification.py`** (MODIFIED — Epic A's nfn-1 file)
  - Add `IMPORT_FAILED = "import_failed"` to `NotificationType` enum.
  - Extend `_category_for_type` mapping:
    - `IMPORT_FAILED → "imports"`
    - `SHOPPING_DEADLINE_REMINDER → "shopping"` (already mapped per Epic A nfn-1 since the enum value already exists; confirm during dev).

- **`libraries/utils/utils/services/notification_copy.py`** (MODIFIED — extend Epic A's module)
  - Add functions:
    - `shopping_deadline_reminder(list_name, item_count)` →
      - 1 item: `("🛒 1 item on {list_name} is due today", "Tap to see what's left.")`
      - N>1: `("🛒 {N} items on {list_name} are due today", "Tap to see what's left.")`.
    - `import_failed(source_label, item_count)` →
      - Single (count==1): `("🛑 Couldn't import from {source_label}", "We couldn't extract a recipe. Tap to retry.")`
      - Bulk (count>1): `("🛑 Bulk import failed", "We couldn't extract any of the {count} recipes. Tap to retry.")`
      - source_label is a hostname for URL imports, file name for file imports, or "your bulk import" as a generic fallback.

- **`libraries/utils/utils/services/shopping_notifications.py`** (MODIFIED — extend the existing module that handles SHOPPING_*)
  - `notify_shopping_deadline_reminder(database, user, shopping_list, due_items)`:
    - Constructs PushNotification via `notification_copy.shopping_deadline_reminder(list_name=shopping_list.name, item_count=len(due_items))`.
    - Data payload: `{"shopping_list_id": shopping_list.id, "item_count": str(len(due_items))}`.
    - `send_to_user(user, notification, db_session)`.

- **`libraries/utils/utils/tasks/shopping_list_tasks/send_shopping_deadline_reminders.py`** (NEW)
  - Celery task `send_shopping_deadline_reminders` (party-mode-refined for per-user idempotency):
    - **Step 1: efficient TZ bucketing.** `SELECT DISTINCT timezone FROM users WHERE timezone IS NOT NULL`. For each TZ, check whether wall-clock time in that TZ is currently in [8:00 AM, 8:05 AM] window. Skip TZ if not.
    - **Step 2: for each in-window TZ:** load users in that TZ. For each user:
      - Query shopping_lists owned by or shared with the user where any item has `due_at::date = today (in user tz) AND is_checked = false`.
      - For each such list:
        - Lookup or insert `shopping_list_user_reminder_state(user_id, shopping_list_id)`.
        - If `state.last_deadline_reminder_sent_at IS NULL OR state.last_deadline_reminder_sent_at::date (in user tz) < today (in user tz)`, fire `notify_shopping_deadline_reminder(database, user, list, due_items)`.
        - Update `state.last_deadline_reminder_sent_at = now()`.
    - Wrap each user/list in try/except; log on failure (one bad user doesn't kill the batch).

- **`libraries/utils/utils/services/import_notifications.py`** (MODIFIED)
  - Add `notify_import_failed(database, job)`:
    - Determines source_label from `job.source_type` + `job.source_url` (hostname) or `job.source_filename`.
    - Calls `notification_copy.import_failed(source_label, item_count=job.total_items)`.
    - Data payload: `{"import_job_id": job.id}`.
    - `send_to_user(user, notification, db_session)`.

- **`libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`** (MODIFIED)
  - In `_update_job_counts` (or wherever the terminal-state transition is detected), when `job.status` transitions to `"failed"` (every item terminal-failed), call `notify_import_failed(database, job)`.
  - Add to extract_recipe_task too if it has the equivalent terminal-state handler. (Confirm during dev which path actually transitions to `"failed"`.)

- **`services/worker/celery_beat.py`** (MODIFIED)
  - Add: `'send-shopping-deadline-reminders': {'task': 'utils.tasks.shopping_list_tasks.send_shopping_deadline_reminders', 'schedule': crontab(minute='*/5')}`.

## Infrastructure changes

- **One Celery beat schedule entry** (`send-shopping-deadline-reminders`).
- **One small migration** (one nullable column on shopping_list).
- **No new tables, no Terraform changes, no new ECS tasks.**

## Initial Design Principles (pre-party-mode)

1. **One push per user per list per day** for shopping deadlines. No per-item firehose.
2. **Morning timing in user's local timezone** — respect the existing `users.timezone` field.
3. **Idempotency via column on the parent (shopping_list, ImportJob)** — no de-dup table.
4. **Full-job-failure only** for imports, not per-item failures. Per-item is the Imports tab's job.
5. **Inherit from prior epics.** Per-category prefs gate sends; copy library is the source.
6. **Source label in failure copy.** Don't push "Import failed" generic — say "Couldn't import from epicurious.com" so the user knows which import broke.

## File structure (expected)

```
app/lib/core/services/
└── push_notification_service.dart                          # MODIFIED — _routeForNotification adds import_failed

libraries/utils/utils/models/
└── shopping_list.py                                        # MODIFIED — last_deadline_reminder_sent_at column

libraries/utils/utils/services/
├── push_notification.py                                    # MODIFIED — IMPORT_FAILED enum + _category_for_type
├── notification_copy.py                                    # MODIFIED — shopping_deadline_reminder, import_failed copy
├── shopping_notifications.py                               # MODIFIED — notify_shopping_deadline_reminder
└── import_notifications.py                                 # MODIFIED — notify_import_failed

libraries/utils/utils/tasks/shopping_list_tasks/
└── send_shopping_deadline_reminders.py                     # NEW — Celery beat task

libraries/utils/utils/tasks/import_tasks/
└── create_recipe_task.py                                   # MODIFIED — fire IMPORT_FAILED on full-failure transition

services/migrator/migrations/
└── 2026XXXX_shopping_list_last_deadline_reminder.py        # NEW

services/worker/
└── celery_beat.py                                          # MODIFIED — add send-shopping-deadline-reminders schedule
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| sched-1 | Schema + Celery beat task for SHOPPING_DEADLINE_REMINDER | 🔴 P0 | 0.5–1 d | nfn-1 (per-category prefs), nfn-2 (copy library) |
| sched-2 | IMPORT_FAILED enum + callsite in create_recipe_task + frontend route | 🔴 P0 | 0.5 d | nfn-1, nfn-2 |

**Total estimated effort: 1–1.5 days**

---

## Story sched-1: Shopping deadline reminders — schema + beat task + copy

As Leo,
I want a morning push when items on my shopping list are due that day, summarized per list,
so that I don't show up to Sunday brunch having forgotten to buy half the ingredients.

### Acceptance Criteria

1. New migration adds `shopping_list_user_reminder_state` table per the party-mode-refined Backend Changes section (composite PK `(user_id, shopping_list_id)`, `last_deadline_reminder_sent_at` column, FK cascades).
2. New SQLAlchemy model `ShoppingListUserReminderState` matches the table.
3. Celery task `send_shopping_deadline_reminders` runs every 5 min via beat. Schedule entry `'send-shopping-deadline-reminders': {'task': '...', 'schedule': crontab(minute='*/5')}`.
4. Task logic (party-mode-refined for per-user idempotency):
   - **Step 1:** `SELECT DISTINCT timezone FROM users WHERE timezone IS NOT NULL`. For each TZ, check if current wall-clock in that TZ falls in [8:00 AM, 8:05 AM]. Skip otherwise.
   - **Step 2:** for each in-window TZ, load users in that TZ. For each user, query shopping_lists owned by or shared with them where any item has `due_at::date = today (user tz) AND is_checked = false`.
   - **Step 3:** for each (user, list) pair, lookup or upsert `ShoppingListUserReminderState`. If `state.last_deadline_reminder_sent_at IS NULL OR < today (user tz)`, fire `notify_shopping_deadline_reminder(database, user, shopping_list, due_items)` and update state.
   - Wrap each (user, list) in try/except; log on failure.
5. `notify_shopping_deadline_reminder`:
   - Constructs PushNotification via `notification_copy.shopping_deadline_reminder(list_name, item_count)`.
   - `send_to_user(user, notification, db_session)`.
   - Per-recipient prefs (`categories.shopping`) and quiet hours apply.
6. Backend tests:
   - Test A: list with 3 unchecked due-today items + user at 8:02 AM in their tz → 1 push fires, state row created with `last_deadline_reminder_sent_at` set.
   - Test B: same list, run again at 8:07 AM same day → no 2nd push (state-row idempotency).
   - Test C: list with all items checked → no push.
   - Test D: list with items due tomorrow → no push today.
   - Test E: user at 9:00 AM in their tz → no push (window passed).
   - Test F: user with `prefs.categories.shopping = false` → suppressed.
   - **Test G (party-mode-added — critical for shared lists):** Leo and Sarah share a list with due-today items. Leo is in MST (8:00 AM = 14:00 UTC); Sarah is in EST (8:00 AM = 12:00 UTC). At 12:00 UTC, beat task runs → Sarah gets her push, Leo's state row is unaffected. At 14:00 UTC, beat task runs → Leo gets his push, both state rows have today's `last_deadline_reminder_sent_at`. Neither user's push silences the other.
7. Manual verification: Leo creates a shopping list with 2 items due today. Wait for next 8:00 AM tick (or simulate by adjusting beat or running task manually). Push lands.

### Key Files
- Create: `services/migrator/migrations/2026XXXX_shopping_list_last_deadline_reminder.py`
- Modify: `libraries/utils/utils/models/shopping_list.py`
- Modify: `libraries/utils/utils/services/notification_copy.py`
- Modify: `libraries/utils/utils/services/shopping_notifications.py`
- Create: `libraries/utils/utils/tasks/shopping_list_tasks/send_shopping_deadline_reminders.py`
- Modify: `services/worker/celery_beat.py`
- Test: `libraries/utils/tests/services/test_shopping_notifications.py`, `libraries/utils/tests/tasks/test_send_shopping_deadline_reminders.py`

### Risks / notes
- Timezone handling: the user's `timezone` (string like "America/Denver") needs to be resolved with `pytz` or `zoneinfo`. The 8:00 AM check is wall-clock in that timezone.
- If a user has no timezone set, default to UTC (push fires at 8:00 AM UTC). Could surprise some users; flag if this is the wrong default.
- Beat cadence (every 5 min) means worst-case 5 min late. Acceptable.
- Don't accidentally push when 8:00 AM happens DURING quiet hours (a user with quiet hours 22:00-09:00 wouldn't get the push). The existing per-user check handles this.

---

## Story sched-2: IMPORT_FAILED enum + full-job-failure callsite + route

As Sarah,
I want a single push when my entire bulk import has failed (or my single recipe couldn't be extracted), naming the source,
so that I'm not silent-failed on bad URLs.

### Acceptance Criteria

1. `NotificationType.IMPORT_FAILED = "import_failed"` added to enum.
2. `_category_for_type[IMPORT_FAILED] = "imports"` (and the existing exhaustiveness assertion still passes per Epic A).
3. `notification_copy.import_failed(source_label, item_count)`:
   - count==1: `("🛑 Couldn't import from {source_label}", "We couldn't extract a recipe. Tap to retry.")`
   - count>1: `("🛑 Bulk import failed", "We couldn't extract any of the {count} recipes. Tap to retry.")`
4. `notify_import_failed(database, job)`:
   - Resolves source_label from `job.source_type`:
     - `url`: parse hostname from `job.source_url`.
     - `url_list`: "your bulk import".
     - `spreadsheet`: file name from `job.source_filename` or "your spreadsheet".
     - `pdf` / `photo` / `text` / others: "your import".
   - Constructs PushNotification with the copy + data `{"import_job_id": job.id}`.
   - `send_to_user(job.user, notification, db_session)`.
5. `create_recipe_task._update_job_counts` (or `extract_recipe_task` — confirm during dev which one transitions to `"failed"`): when the job status flips to `"failed"`, call `notify_import_failed(database, job)`.
   - Idempotency: only fire on the transition (compare `previous_status != "failed"` and `new_status == "failed"`). Existing pattern mirrors how `notify_import_needs_review` is gated on `awaiting_review` transitions.
6. `_routeForNotification` in Flutter adds `'import_failed'` case routing to `/recipes/import/review-list/{import_job_id}`.
7. Backend tests:
   - Test A: bulk job with 5 URLs all failing extraction → status transitions to "failed" → notify_import_failed fires once.
   - Test B: single-URL job that fails → notify_import_failed fires once with hostname in the title.
   - Test C: bulk job where 3 fail and 2 awaiting review → status stays "awaiting_review", IMPORT_FAILED does NOT fire.
   - Test D: re-running _update_job_counts after status is already "failed" → no second fire (transition gate).
   - Test E: user with `prefs.categories.imports = false` → suppressed.
8. Frontend test: simulate `import_failed` notification tap → routes to `/recipes/import/review-list/{job_id}`.
9. Manual verification: Sarah submits a bulk import of 3 paywalled URLs → wait for processing → push lands "Bulk import failed". Tap → review-list shows the failed items.

### Key Files
- Modify: `libraries/utils/utils/services/push_notification.py` (enum + _category_for_type)
- Modify: `libraries/utils/utils/services/notification_copy.py`
- Modify: `libraries/utils/utils/services/import_notifications.py` (add notify_import_failed)
- Modify: `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` (and/or extract_recipe_task — confirm)
- Modify: `app/lib/core/services/push_notification_service.dart`
- Test: `libraries/utils/tests/services/test_import_notifications.py`, `libraries/utils/tests/tasks/test_create_recipe_task.py`

### Risks / notes
- Confirm during dev which task is responsible for the terminal "failed" transition. The audit found both `extract_recipe_task.py` and `create_recipe_task.py` have the `_update_job_counts` pattern; the actual transition might happen in either.
- Don't push for "cancelled" jobs (user manually cancelled — no surprise to them).
- Source label: hostnames in the title might be long for some URLs. Consider truncating to 30 chars with ellipsis.

## Dependencies

- Both stories depend on **Epic A** (per-category prefs, copy library).
- sched-1 and sched-2 are independent; can ship in parallel after Epic A.

## Open questions for the user

- **Default timezone fallback.** If a user has no timezone set, the deadline reminder defaults to UTC 8:00 AM (could be 1:00 AM local). Should the fallback be the user's last-known device timezone (per Flutter), or skip the user entirely until they set a timezone in prefs? Default: skip if unset (don't surprise users; they can set it in prefs to opt in).
- **Cancelled imports.** Today the `cancelled` status is distinct from `failed`. Cancelled = user clicked cancel. Default: no push for cancelled. Confirm this is right.

## Definition of Done (Epic Level)

- A user with shopping items due today gets one push at 8:00 AM in their timezone, naming the list and the count.
- A user whose bulk import fully fails gets one push naming the source and offering retry via tap.
- Both notifications are gated by their respective per-category prefs.
- Idempotency holds: re-running the beat task within the same morning window does NOT double-push.
- Per-user quiet hours respected.
- Manual smoke test: Leo creates a list with due items today → next morning gets the push. Sarah submits a bad URL → gets the failure push.
