<!-- refined via party-mode 2026-04-21 -->
# Epic: Partner Activity Notifications

## Overview

Phase 2 audit revealed that "social presence" in shared books is mostly silent. The wired surface is narrow: book shared (works), recipe added (broken arity bug — fixed in Epic A), friend request received/accepted (works), invitation received/accepted (works), meal-event invite (works to invitee but no ack back to inviter when they accept).

The user's framing in the original prompt was "make sure I'm not missing anything" and "include any long tap easy actions if there are any". For partner activity, the value is *presence* — knowing someone you cook with did something — not *interactivity*. The "high-signal only" decision in the 2026-04-21 batch keeps this from becoming a noise generator.

This epic ships:
1. **Partner forked your recipe** — when someone in a shared book copies your recipe to another book.
2. **Partner added a note to your recipe** — when someone notes one of your recipes.
3. **Partner cooked your recipe** — when someone in a shared book completes a cook log of one of your recipes.
4. **Partner accepted your meal invite** — back-fan to the inviter (today only the invitee gets a push).
5. **Post-cook feedback prompt** — 2-hour Celery-delayed push to the cooker: "How did your X turn out?"

All consume Epic A's category pref (`partner_activity`), copy library, and image-attachment pattern. No new categories, no new infra beyond one Celery-delay queue (the post-cook 2h delay).

**Goal:** when a partner does something meaningful with your stuff (your recipe, your meal invite), you find out within seconds. When you finish a cook, you get a gentle prompt 2 hours later to log how it went.

## Locked Decisions (inherited + added)

**Inherited (do not re-litigate):**
- iOS-first; Android continues on `firebase_messaging` defaults.
- ErrorReporter for failures.
- Per-category prefs (Epic A) — these all sit under `prefs.categories.partner_activity`.
- Notification copy lives in `notification_copy.py` (Epic A).
- Recipe / book / cook-log image attachment uses the recipe's existing `cover_image_url` field where present.
- Two-row audit pattern doesn't apply here — these are user-event-triggered notifications, not admin actions.

**Locked for this epic (from 2026-04-21 user batch + sensible defaults):**
- **High-signal only.** Forks, notes, cook logs, meal-invite acceptance, post-cook prompt. No edits, no version bumps, no individual additions besides RECIPE_ADDED (which is Epic A's path).
- **Self-actions don't notify the actor.** When you fork/note/cook your own recipe, you don't get a push for it.
- **Recipient = the recipe owner**, NOT every member of the shared book. (Notifying the whole book on every fork/note/cook would re-create the noise problem.) The book's other members can see activity in the activity tab if they navigate there.
- **Post-cook prompt is opt-out via `partner_activity` category.** Sensible default; can be split into a separate category (`cook_followups`) in a follow-up if user feedback says otherwise.
- **2-hour delay for post-cook prompt** uses Celery's `apply_async(countdown=7200)` (or scheduled `eta`). No new beat task.
- **Quiet hours respected per recipient** — the existing per-user check in `send_to_user`.
- **No app-wide announcement / system broadcast** — `NotificationType.SYSTEM` stays deferred per the addendum.
- **No deferred prompt for users who never logged a cook** — only fires for actual `cooking_log` rows.
- **Need new NotificationType enum values:**
  - `RECIPE_FORKED` (new) — partner forked your recipe.
  - `RECIPE_NOTE_ADDED` (new) — partner added a note to your recipe.
  - `RECIPE_COOKED_BY_PARTNER` (new) — partner cooked your recipe in a shared book.
  - `MEAL_EVENT_INVITE_ACCEPTED` (new) — your invitee accepted.
  - `COOK_FEEDBACK_PROMPT` (new) — 2h-delayed "how did it turn out" prompt to the cooker.
  - All five route through `prefs.categories.partner_activity` per `_category_for_type` (Epic A).

## Refinements via party-mode 2026-04-21

**Lens-by-lens cross-examination findings — incorporated into ACs below:**

- **PM:** High-signal-only is the right call (locked from user batch). Resist any temptation to fan out edits / version bumps in this epic — the user already validated the line.
- **UX:** Note snippet in the push body (max 120 chars) — privacy is OK because the recipient is the recipe owner who already has access to the note. Don't show actor's email or any other PII; first_name only.
- **UX:** Cook-feedback-prompt copy emoji ("🍴") and tone ("How did your X turn out?") tested as inviting-not-pushy. Keep.
- **Frontend:** `recipe_forked` deep-link routes to Sarah's COPY (forked_recipe_id), not Leo's original (source_recipe_id). Reasoning: Leo wants to see what Sarah has, not re-look at his own recipe. Folded into partner-5 AC.
- **Backend:** **Actor name fallback chain (locked):** `actor.first_name` → `actor.username` → `actor.email.split("@")[0]` → `"Someone"`. Apply uniformly across all five copy functions. Folded into partner-1 AC 4.
- **Backend:** Verify during dev that `add_recipe_note.py:71-95` (cited in Phase 2 audit) is still the correct location for the note-creation handler. If the file moved, update partner-2 file path.
- **Backend:** Cook-feedback-prompt task uses Celery `apply_async(countdown=7200)`. At-least-once delivery semantics — broker holds the task across worker restarts. Idempotency via `cooking_log.rating IS NOT NULL` check at task start.
- **Infra/Devops:** No new infra. The 2h-delayed task path is exercised by existing import tasks; broker is reliable enough for this use case.
- **QA:** Manual smoke per type (5 types × Leo+Sarah test accounts). Worker-restart test for cook-feedback prompt: enqueue task, restart worker, confirm task fires after restart.

**Cross-epic locked decisions added by this workshop:**

1. **Actor name fallback chain.** `first_name → username → email_local_part → "Someone"`. Applies to every notification copy function that takes an actor name. Add as a helper in `notification_copy.py` so each function uses `_resolve_actor_name(actor)` not raw `actor.first_name`.
2. **Self-actions never notify the actor.** Always check `actor.id != recipient.id` before send. Pattern lives at the callsite.
3. **Image attachment uses the recipe's `cover_image_url`** (consistent with Epic A's import pattern for the post-promotion case).

## End-user flow

### Flow A — Sarah forks Leo's Sweet Potato Quiche

1. Leo created "Sweet Potato Quiche" in shared book "Weeknight Dinners".
2. Sarah opens the recipe, taps "Save to my book" (or whatever the existing fork UI is — see `fork_recipe.py:18-163`), forks it to her personal "Sarah's Recipes" book.
3. Backend (`fork_recipe.py`): after the fork commits, fires `RECIPE_FORKED` to Leo (the source recipe owner).
4. Leo's phone: "🔱 Sarah forked your Sweet Potato Quiche", body "She saved it to Sarah's Recipes." Image: recipe cover.
5. Tap → `/recipes/{forked_recipe_id}` (Sarah's copy) so Leo can see what she has now.

### Flow B — Sarah notes Leo's recipe

1. Sarah opens Leo's "Sweet Potato Quiche" in the shared book and adds a note: "Add more cinnamon next time, was a hit."
2. Backend (`add_recipe_note.py`): after note commits, fires `RECIPE_NOTE_ADDED` to Leo.
3. Leo's phone: "Sarah noted your Sweet Potato Quiche 📝", body `Sarah: "Add more cinnamon next time, was a hit."` (truncated to ~120 chars if long).
4. Tap → `/recipes/{recipe_id}` (Leo's recipe, scrolls to the notes section if implemented).

### Flow C — Sarah cooks Leo's recipe

1. Sarah opens "Sweet Potato Quiche" in the shared book, enters cook mode, completes the cook → cook_log row created.
2. Backend (`cooking_log/create_cooking_log.py`): if the recipe is in a SHARED book AND the cooker is NOT the recipe owner, fire `RECIPE_COOKED_BY_PARTNER` to the owner.
3. Leo's phone: "🍳 Sarah cooked your Sweet Potato Quiche!", body "Tap to see how it went."
4. Tap → `/recipes/{recipe_id}` (or a future cook-log detail screen).

### Flow D — Sarah's 2-hour post-cook prompt

1. Sarah completes the cook in Flow C. Cook_log row commits.
2. Backend enqueues `cook_feedback_prompt_task.apply_async((cook_log_id,), countdown=7200)` — fires 2 hours later.
3. 2 hours later, the task fires `COOK_FEEDBACK_PROMPT` to Sarah:
   - "How did your Sweet Potato Quiche turn out? 🍴"
   - Body: "Tap to add a quick rating + note."
4. Tap → `/recipes/{recipe_id}` (or a dedicated post-cook feedback screen if Story 6.5 shipped one).
5. If Sarah already added a rating/note before the 2h hit (the cooking-log row has a non-null rating field), the task is a no-op (logged but not sent).

### Flow E — Sarah accepts Leo's meal invite (back-fan)

1. Leo creates a meal "Saturday brunch", invites Sarah. Sarah gets a MEAL_EVENT_INVITE push (existing).
2. Sarah opens it, taps Accept → her participant status becomes `accepted`.
3. Backend (the accept-invite handler): fire `MEAL_EVENT_INVITE_ACCEPTED` to Leo (the inviter).
4. Leo's phone: "🥞 Sarah's coming to Saturday brunch!", body "She just RSVP'd yes."
5. Tap → `/calendar/meals/{meal_event_id}` (Epic A's deep-link).
6. Decline: by symmetry, also fires (so Leo knows). Body: "She RSVP'd no — tap to swap recipes if needed."
7. Maybe: also fires. Body: "She's a maybe — tap to follow up."

## Frontend changes

- **`app/lib/core/services/push_notification_service.dart`** (MODIFIED — `_routeForNotification`)
  - Add cases for new types:
    - `recipe_forked`, `recipe_note_added`, `recipe_cooked_by_partner` → `/recipes/{recipe_id}` (or forked_recipe_id for forked).
    - `cook_feedback_prompt` → `/recipes/{recipe_id}`.
    - `meal_event_invite_accepted` → `/calendar/meals/{meal_event_id}` (uses Epic A's route).
  - All payload data keys defensive (fallback to `/` if id missing).

## Backend changes

- **`libraries/utils/utils/services/push_notification.py`** (MODIFIED — Epic A's nfn-1 file)
  - Add to `NotificationType` enum:
    - `RECIPE_FORKED = "recipe_forked"`
    - `RECIPE_NOTE_ADDED = "recipe_note_added"`
    - `RECIPE_COOKED_BY_PARTNER = "recipe_cooked_by_partner"`
    - `MEAL_EVENT_INVITE_ACCEPTED = "meal_event_invite_accepted"`
    - `COOK_FEEDBACK_PROMPT = "cook_feedback_prompt"`
  - Extend `_category_for_type` mapping:
    - All five → `"partner_activity"`.

- **`libraries/utils/utils/services/notification_copy.py`** (MODIFIED — extend Epic A's module)
  - Add functions:
    - `recipe_forked(actor_name, recipe_name, target_book_name)` → `("🔱 {actor_name} forked your {recipe_name}", "She saved it to {target_book_name}.")` (use gender-neutral "They" if actor's pronouns aren't known).
    - `recipe_note_added(actor_name, recipe_name, note_snippet)` → `("{actor_name} noted your {recipe_name} 📝", '{actor_name}: "{note_snippet}"')`. Truncate snippet to ~120 chars.
    - `recipe_cooked_by_partner(actor_name, recipe_name)` → `("🍳 {actor_name} cooked your {recipe_name}!", "Tap to see how it went.")`.
    - `meal_event_invite_accepted(actor_name, event_title, status)` → branches on status:
      - "accepted": `("🥞 {actor_name}'s coming to {event_title}!", "They just RSVP'd yes.")`.
      - "declined": `("{actor_name} can't make {event_title}", "Tap to swap recipes if needed.")`.
      - "maybe": `("{actor_name} might join {event_title}", "They marked themselves as a maybe.")`.
    - `cook_feedback_prompt(recipe_name)` → `("How did your {recipe_name} turn out? 🍴", "Tap to add a quick rating + note.")`.

- **`services/api/src/api/v1/recipe/fork_recipe.py`** (MODIFIED)
  - After commit: if `original_recipe.owner_id != current_user.id`, fire `RECIPE_FORKED` to `original_recipe.owner_id` via `send_to_user`.
  - Use `notification_copy.recipe_forked(...)`, image from `original_recipe.cover_image_url`, data payload `{"forked_recipe_id": new_id}`.

- **`services/api/src/api/v1/recipe_note/add_recipe_note.py`** (or wherever notes are created — check during dev) (MODIFIED)
  - After commit: if `recipe.owner_id != current_user.id` AND `recipe` is in a SHARED book (else there's no "partner" relationship to ping), fire `RECIPE_NOTE_ADDED` to `recipe.owner_id`.
  - Use `notification_copy.recipe_note_added(actor_name, recipe_name, note_snippet=note.content[:120])`, data payload `{"recipe_id": recipe.id, "note_id": note.id}`.

- **`services/api/src/api/v1/cooking_log/create_cooking_log.py`** (MODIFIED)
  - After commit: if `recipe.owner_id != current_user.id` AND the recipe is in a SHARED book the cooker has access to, fire `RECIPE_COOKED_BY_PARTNER` to `recipe.owner_id`.
  - Use `notification_copy.recipe_cooked_by_partner(...)`, image from recipe.
  - ALSO: enqueue `cook_feedback_prompt_task.apply_async((cooking_log.id,), countdown=7200)` for the cooker.

- **`libraries/utils/utils/tasks/cook_feedback_tasks/cook_feedback_prompt.py`** (NEW)
  - Celery task `cook_feedback_prompt(cook_log_id)`:
    - Loads the cooking_log + recipe + user.
    - Idempotency: if the cooking_log has a non-null `rating` or `notes` field already, log INFO ("user already rated, skipping") and return.
    - Calls `notify_cook_feedback_prompt(database, user, recipe)` which dispatches the push.
  - Wrap in try/except + log on failure.

- **`libraries/utils/utils/services/cook_feedback_notifications.py`** (NEW)
  - `notify_cook_feedback_prompt(database, user, recipe)`:
    - Construct PushNotification with copy from `notification_copy.cook_feedback_prompt(recipe.name)`, image from `recipe.cover_image_url`, data `{"recipe_id": recipe.id, "source": "cook_feedback_prompt"}`.
    - `send_to_user(user, notification, db_session, force=False)`.

- **`services/api/src/api/v1/meal_event/respond_to_invite.py`** (or wherever the participant accepts/declines/maybes — check during dev) (MODIFIED)
  - After status change commits: fire `MEAL_EVENT_INVITE_ACCEPTED` to the meal event's owner (the inviter), excluding self-RSVPs (if owner can RSVP to their own event, don't fire for that).
  - Use `notification_copy.meal_event_invite_accepted(actor_name, event_title, status)`. Image: `event.recipe.cover_image_url` if present.
  - Data payload includes `meal_event_id` for Epic A's deep-link.

## Infrastructure changes

- **No new infra resources.** No Terraform, no new tables, no new beat schedules. The 2h-delayed task uses the existing Celery infrastructure (`apply_async(countdown=...)`).
- **Idempotency for cook-feedback prompt:** the task itself checks the cooking_log row for an already-set rating; no de-dup table needed.

## Initial Design Principles (pre-party-mode)

1. **Recipient = recipe owner**, never the whole book. Avoids re-creating the edit-spam problem.
2. **Self-actions don't notify the actor.** Always check `recipe.owner_id != current_user.id`.
3. **Shared-book gate.** Some events (notes, cook logs) only make sense in a shared context. Don't fire for solo books.
4. **Image attachment is opportunistic.** Use `cover_image_url` if present; gracefully skip if missing.
5. **Idempotency for delayed tasks.** Cook-feedback prompt checks the cook log for an existing rating before firing.
6. **Inherit from prior epics.** Per-category prefs gate every send; copy library is the single source.

## File structure (expected)

```
app/lib/core/services/
└── push_notification_service.dart                          # MODIFIED — _routeForNotification adds new types

libraries/utils/utils/services/
├── push_notification.py                                    # MODIFIED — 5 new NotificationType enum values + _category_for_type mapping
├── notification_copy.py                                    # MODIFIED — 5 new copy functions
└── cook_feedback_notifications.py                          # NEW — notify_cook_feedback_prompt

libraries/utils/utils/tasks/cook_feedback_tasks/
└── cook_feedback_prompt.py                                 # NEW — 2h-delayed task

services/api/src/api/v1/recipe/
└── fork_recipe.py                                          # MODIFIED — fire RECIPE_FORKED

services/api/src/api/v1/recipe_note/
└── add_recipe_note.py                                      # MODIFIED — fire RECIPE_NOTE_ADDED

services/api/src/api/v1/cooking_log/
└── create_cooking_log.py                                   # MODIFIED — fire RECIPE_COOKED_BY_PARTNER + enqueue cook-feedback prompt

services/api/src/api/v1/meal_event/
└── respond_to_invite.py                                    # MODIFIED — fire MEAL_EVENT_INVITE_ACCEPTED

(no migration; no new tables)
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| partner-1 | New NotificationType enum values + category mapping + copy functions | 🔴 P0 | 0.25 d | nfn-1 (prefs), nfn-2 (copy library) |
| partner-2 | RECIPE_FORKED in fork_recipe + RECIPE_NOTE_ADDED in add_recipe_note | 🔴 P0 | 0.5 d | partner-1 |
| partner-3 | RECIPE_COOKED_BY_PARTNER + COOK_FEEDBACK_PROMPT (2h delay) in cooking_log create | 🔴 P0 | 0.5 d | partner-1 |
| partner-4 | MEAL_EVENT_INVITE_ACCEPTED in respond_to_invite | 🟡 P1 | 0.25 d | partner-1 |
| partner-5 | Frontend: deep-link routes for new notification types | 🟡 P1 | 0.25 d | partner-1 (defines payload shape) |

**Total estimated effort: 1.5–1.75 days**

---

## Story partner-1: New NotificationType values + category mapping + copy functions

As the codebase,
I want the new five notification types to be defined, mapped to the partner_activity category, and have their copy functions ready,
so that the per-callsite stories (partner-2 through partner-4) are simple plug-ins.

### Acceptance Criteria

1. `NotificationType` enum gains: `RECIPE_FORKED`, `RECIPE_NOTE_ADDED`, `RECIPE_COOKED_BY_PARTNER`, `MEAL_EVENT_INVITE_ACCEPTED`, `COOK_FEEDBACK_PROMPT`. Each value matches the snake_case string convention.
2. `_category_for_type` mapping (Epic A) extended: all five → `"partner_activity"`.
3. The exhaustiveness assertion in Epic A's nfn-1 still passes (every new type has a category).
4. `notification_copy.py` has the five copy functions, each returning `(title, body)` tuples per the templates above. Each uses a shared helper `_resolve_actor_name(actor)` with the locked fallback chain: `actor.first_name → actor.username → actor.email.split("@")[0] → "Someone"`. The helper lives in `notification_copy.py` and is used by every copy function that takes an actor.
5. Backend unit tests:
   - Test A: each copy function returns expected strings for typical inputs.
   - Test B: `recipe_note_added` truncates a 200-char note to 120 chars + ellipsis.
   - Test C: `meal_event_invite_accepted` branches on status (accepted/declined/maybe).
   - Test D: pref check — user with `categories.partner_activity = false` → all five new types suppressed via Epic A's check.

### Key Files
- Modify: `libraries/utils/utils/services/push_notification.py`
- Modify: `libraries/utils/utils/services/notification_copy.py`
- Test: `libraries/utils/tests/services/test_notification_copy.py`, extend `test_push_notification.py`

### Risks / notes
- Naming collision: ensure no existing type uses the same snake_case string. (Phase 2 confirmed clean.)

---

## Story partner-2: RECIPE_FORKED + RECIPE_NOTE_ADDED callsites

As Leo,
I want a push when Sarah forks one of my recipes or adds a note to it,
so that I know my stuff is being used (and can react to her note).

### Acceptance Criteria

1. `fork_recipe.py`: after the fork commits successfully, if `original_recipe.owner_id != current_user.id`, send `RECIPE_FORKED` to the original owner.
   - Copy via `notification_copy.recipe_forked(actor_name=current_user.first_name or current_user.username, recipe_name=original_recipe.name, target_book_name=target_book.name)`.
   - Image: `original_recipe.cover_image_url`.
   - Data payload: `{"forked_recipe_id": new_recipe.id, "source_recipe_id": original_recipe.id}`.
2. `add_recipe_note.py`: after note commits, if `recipe.owner_id != current_user.id` AND `recipe.recipe_book.is_shared`, send `RECIPE_NOTE_ADDED` to `recipe.owner_id`.
   - Copy via `notification_copy.recipe_note_added(actor_name=..., recipe_name=recipe.name, note_snippet=note.content[:120])`.
   - Image: `recipe.cover_image_url`.
   - Data payload: `{"recipe_id": recipe.id, "note_id": note.id}`.
3. Each recipient's `prefs.categories.partner_activity` and quiet hours apply.
4. Backend tests:
   - Test A: Sarah forks Leo's recipe → Leo's user gets `send_to_user` called once with RECIPE_FORKED.
   - Test B: Leo forks his own recipe → no notification (self-fork).
   - Test C: Sarah notes Leo's recipe in a shared book → Leo gets RECIPE_NOTE_ADDED.
   - Test D: Sarah notes Leo's recipe in HER OWN private book (after fork) → no notification (book not shared with Leo).
   - Test E: note content > 200 chars → snippet truncated.
5. Manual verification: Leo + Sarah on a shared book; Sarah forks → Leo's phone gets push within seconds. Sarah notes → another push.

### Key Files
- Modify: `services/api/src/api/v1/recipe/fork_recipe.py`
- Modify: `services/api/src/api/v1/recipe_note/add_recipe_note.py` (or actual location — confirm during dev)
- Test: `services/api/tests/api/v1/recipe/test_fork_recipe.py`, `services/api/tests/api/v1/recipe_note/test_add_recipe_note.py`

### Risks / notes
- The exact location of the note-creation handler should be verified — the audit found `add_recipe_note.py:71-95` but it might be folded into a different file.
- Don't fire RECIPE_NOTE_ADDED for notes on a recipe in a non-shared book — there's no "partner" to be a partner.

---

## Story partner-3: RECIPE_COOKED_BY_PARTNER + 2h post-cook prompt

As Leo,
I want a push when Sarah cooks one of my recipes (so I know it got used) AND a personal nudge 2 hours after I finish a cook (so I add a rating).

### Acceptance Criteria

1. `cooking_log/create_cooking_log.py`: after commit, two firings:
   - **A:** if `recipe.owner_id != current_user.id` AND the recipe is in a SHARED book the cooker has access to, send `RECIPE_COOKED_BY_PARTNER` to `recipe.owner_id`.
   - **B:** ALWAYS (regardless of who owns the recipe), enqueue `cook_feedback_prompt_task.apply_async((cooking_log.id,), countdown=7200)` for the cooker. This is the 2-hour delayed prompt.
2. `cook_feedback_prompt_task` (Celery task in `cook_feedback_tasks/cook_feedback_prompt.py`):
   - Loads the `cooking_log` + recipe + user.
   - Idempotency: if `cooking_log.rating IS NOT NULL OR cooking_log.notes IS NOT NULL`, log INFO "user already rated, skipping" and return.
   - Calls `notify_cook_feedback_prompt(database, user, recipe)`.
3. `notify_cook_feedback_prompt`:
   - Constructs PushNotification with copy from `notification_copy.cook_feedback_prompt(recipe_name=recipe.name)`, image from `recipe.cover_image_url`, data `{"recipe_id": recipe.id, "source": "cook_feedback_prompt"}`.
   - `send_to_user(user, notification, db_session, force=False)`.
4. `RECIPE_COOKED_BY_PARTNER` copy: `("🍳 {actor_name} cooked your {recipe_name}!", "Tap to see how it went.")`.
5. Backend tests:
   - Test A: Sarah cooks Leo's recipe in shared book → Leo gets RECIPE_COOKED_BY_PARTNER, Sarah gets cook-feedback-prompt enqueued (not fired immediately).
   - Test B: Sarah cooks her own recipe → no RECIPE_COOKED_BY_PARTNER, but cook-feedback-prompt still enqueued.
   - Test C: Sarah cooks Leo's recipe in a non-shared book → no RECIPE_COOKED_BY_PARTNER (book not shared).
   - Test D: cook-feedback-prompt task fires 2h later → if rating already set, no push; else push fires.
   - Test E: Celery `apply_async(countdown=7200)` is invoked correctly (verify via mock).
6. Manual verification: Leo logs a cook → 2h later (or simulate by setting countdown=10 in dev), gets the "How did your X turn out?" push.

### Key Files
- Modify: `services/api/src/api/v1/cooking_log/create_cooking_log.py`
- Create: `libraries/utils/utils/tasks/cook_feedback_tasks/cook_feedback_prompt.py`
- Create: `libraries/utils/utils/services/cook_feedback_notifications.py`
- Modify: `libraries/utils/utils/services/notification_copy.py`
- Test: `services/api/tests/api/v1/cooking_log/test_create_cooking_log.py`, `libraries/utils/tests/tasks/test_cook_feedback_prompt.py`

### Risks / notes
- 2-hour delay: Celery's `countdown` is robust for delays of this scale. If the worker is down at the scheduled time, the task fires when the worker resumes (the broker holds it).
- If a user cooks the same recipe multiple times in 2 hours, multiple prompts queue. Acceptable — each is for a different cooking_log id.
- Don't fire the prompt if the user opted out of `partner_activity` — but that's an Epic A check inside `send_to_user`.

---

## Story partner-4: MEAL_EVENT_INVITE_ACCEPTED back-fan

As Leo,
I want a push when Sarah accepts (or declines, or maybes) my meal-event invite,
so that I'm not refreshing the calendar to see if she's coming.

### Acceptance Criteria

1. The respond-to-invite handler (or wherever participant status changes — `respond_to_invite.py` per the audit; verify during dev): after status change commits, send `MEAL_EVENT_INVITE_ACCEPTED` to the meal_event's owner.
2. Skip if the actor IS the owner (owner can RSVP to their own event but no notification).
3. Copy via `notification_copy.meal_event_invite_accepted(actor_name=..., event_title=event.title, status=new_status)`.
4. Image: `event.recipe.cover_image_url` if attached.
5. Data payload: `{"meal_event_id": event.id}` for Epic A's deep-link to `/calendar/meals/:id`.
6. Owner's `prefs.categories.partner_activity` and quiet hours apply.
7. Backend tests:
   - Test A: Sarah accepts → Leo gets push with title "🥞 Sarah's coming to {event_title}!".
   - Test B: Sarah declines → push title "Sarah can't make {event_title}".
   - Test C: Sarah maybes → push title "Sarah might join {event_title}".
   - Test D: Leo (owner) RSVPs to his own event → no push.
   - Test E: Owner has `prefs.categories.partner_activity = false` → suppressed.
8. Manual verification: Leo invites Sarah → Sarah accepts → Leo gets push immediately.

### Key Files
- Modify: `services/api/src/api/v1/meal_event/respond_to_invite.py` (or actual location — confirm during dev)
- Test: `services/api/tests/api/v1/meal_event/test_respond_to_invite.py`

### Risks / notes
- The exact handler is named per Phase 2 audit — confirm during dev. Might be a method on the meal-event update path with a `status` field.
- Existing MEAL_EVENT_INVITE goes the other direction (inviter → invitee). This story is the back-fan. Don't accidentally double-fire on the existing path.

---

## Story partner-5: Frontend deep-link routes for new types

As Leo,
I want tapping any of the new partner-activity pushes to land me on the right screen,
so that I can act immediately without hunting.

### Acceptance Criteria

1. `_routeForNotification` in `push_notification_service.dart` adds cases:
   - `recipe_forked` → `/recipes/{forked_recipe_id}` (the new copy in Sarah's book) if present, else `/recipes/{source_recipe_id}` (Leo's original) as fallback.
   - `recipe_note_added` → `/recipes/{recipe_id}`.
   - `recipe_cooked_by_partner` → `/recipes/{recipe_id}`.
   - `cook_feedback_prompt` → `/recipes/{recipe_id}`.
   - `meal_event_invite_accepted` → `/calendar/meals/{meal_event_id}` (uses Epic A's route).
2. Each case defensively falls back to `/` if the relevant ID is missing.
3. Flutter unit test for each new case.
4. Manual verification: tap each notification type during the QA walkthrough; confirm the right screen opens.

### Key Files
- Modify: `app/lib/core/services/push_notification_service.dart`
- Test: `app/test/services/push_notification_service_test.dart`

### Risks / notes
- Cold-start vs background tap: existing `_navigateToRoute` already handles both. New cases inherit that behavior.

## Dependencies

- All five stories depend on **Epic A** (per-category prefs, copy library, meal-event deep-link route).
- partner-1 blocks partner-2, partner-3, partner-4, partner-5.
- partner-2/3/4 are parallel after partner-1.
- partner-5 is parallel with partner-2/3/4 (frontend doesn't need backend code shipped first; just needs the payload shape locked).

## Open questions for the user

- **Note-snippet inclusion in the push body.** Today's draft includes the truncated note text. Privacy-wise this is fine (the recipe owner is going to see it anyway), but if you'd rather the body just say `"Sarah added a note. Tap to read."` without showing the snippet, flag it. Default: include the snippet.
- **Cook-feedback prompt category split.** Today the prompt is gated by `partner_activity`. Should it have its own category (`cook_followups`)? Default: bucket with partner_activity. Easy to split later if user feedback says otherwise.
- **Meal-event decline / maybe back-fan.** Default: fire for all three (accept / decline / maybe), each with its own copy variant. If decline is too noisy, can be disabled. Confirm if you only want the accept case to fire.

## Definition of Done (Epic Level)

- A partner forking your recipe lands a push on your phone within seconds.
- A partner noting your recipe in a shared book lands a push with the truncated note.
- A partner cooking your recipe in a shared book lands a push.
- The cooker themself gets a "how did it turn out?" push 2 hours after the cook log lands.
- A meal invitee's accept/decline/maybe lands an appropriate push on the inviter's phone.
- All five notifications are gated by `prefs.categories.partner_activity`.
- All five include image attachments where the underlying recipe has a cover.
- Tap routing lands on the correct screen for each new type.
- Manual smoke test exercises each path with Leo + Sarah test accounts.
