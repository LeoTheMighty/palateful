# Story Import.6: Activity Feed Integration — Import Status, Partner Activity, Reminders

Status: done

## Story

As a user,
I want my Activity feed to show import progress, partner actions, and meal reminders,
so that the Activity tab feels like a living hub of everything happening in my kitchen.

## Acceptance Criteria

1. Import job progress updates appear in Activity feed in real-time (or near real-time via polling)
2. When a partner adds/removes items from a shared shopping list, an activity is created
3. When a partner joins a shared recipe book, an activity is created
4. Meal reminders appear as activities (e.g., "Tonight's dinner: Honey-Glazed Salmon")
5. Partner activities show the partner's name and what they did
6. Each activity type has a distinct icon for visual scanning
7. Activities older than 30 days are auto-cleaned (backend job or query filter)

## Tasks / Subtasks

- [x] Task 1: Import job activity updates (AC: #1)
  - [x] Update import pipeline tasks to create/update activities at each stage:
    - `ParseSourceTask` start → activity "Importing X recipes..."
    - Progress updates → update existing activity subtitle with "32/50 complete"
    - `ExtractRecipeTask` complete (all) → new activity "Import complete! X succeeded, Y need review"
    - Individual item flagged → activity "[Recipe Name] needs your input"
  - [x] Use `metadata` JSONB to store `import_job_id` for linking to review screen

- [x] Task 2: Partner shopping list activities (AC: #2, #5)
  - [x] When items are added to a shared shopping list by another user:
    - Create activity for all other members: "[Partner Name] added X items to [List Name]"
    - Batch: if 5 items added in quick succession, create one activity not five
    - `action_url`: link to the shopping list
  - [x] When items are checked off: "[Partner Name] checked off X items from [List Name]"

- [x] Task 3: Partner recipe book activities (AC: #3, #5)
  - [x] When someone joins a shared recipe book via invite:
    - Create activity for the owner: "[Name] joined [Book Name]"
    - `action_url`: link to the book members screen
  - [x] When a new recipe is added to a shared book:
    - Create activity for other members: "[Partner Name] added [Recipe Name] to [Book Name]"

- [x] Task 4: Meal reminder activities (AC: #4)
  - [x] Create a scheduled task or trigger that creates meal reminder activities
  - [x] Morning (8am): "Today's meals: Breakfast — [Name], Lunch — [Name], Dinner — [Name]"
  - [x] Or individual reminders per meal based on notification preferences
  - [x] `action_url`: link to calendar screen or recipe detail

- [x] Task 5: Activity type icons (AC: #6)
  - [x] Define icon mapping in Flutter:
    - `import_started` → download/import icon
    - `import_complete` → checkmark icon
    - `import_needs_review` → warning/flag icon
    - `partner_action` → person icon
    - `meal_reminder` → calendar/food icon
    - `system` → info icon
  - [x] Use appropriate colors from theme (success green, warning amber, etc.)

- [x] Task 6: Activity cleanup (AC: #7)
  - [x] Add `created_at` filter to GET /activities query: only return last 30 days
  - [x] Optionally: add a periodic cleanup task to delete old activities (or just filter at query time)

## Dev Notes

- Partner activity creation happens server-side in the API handlers for shopping list and recipe book mutations
- Be careful with activity volume — batch related actions (5 items added = 1 activity) to avoid spam
- Meal reminders could be created by a Celery beat task that runs each morning, or generated on-demand when the Activity feed is loaded
- The `metadata` JSONB field is flexible — store whatever context each activity type needs
- Consider a `create_activity()` utility function in `libraries/utils/` to standardize activity creation across services

### References

- [Epic: epic-import-activity-nav.md]
- [Investigation: 06-import-flow-overhaul.md]
