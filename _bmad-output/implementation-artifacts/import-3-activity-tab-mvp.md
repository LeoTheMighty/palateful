# Story Import.3: Activity Tab MVP — Model, API, Feed UI

Status: done

## Story

As a user,
I want an Activity tab that shows me what's happening in my app — background imports, partner actions, and meal reminders,
so that I have a single place to check for updates without hunting across screens.

## Acceptance Criteria

1. Activity model exists in the database with fields: id, user_id, type, title, subtitle, metadata (JSON), read (boolean), action_url, created_at
2. API endpoints: GET /activities (paginated, newest first), PUT /activities/{id}/read, PUT /activities/read-all
3. Activity tab shows a chronological feed grouped by day (Today, Yesterday, Earlier)
4. "In Progress" section at top shows active background jobs (import jobs in progress)
5. Each activity item is tappable — navigates to `action_url` (recipe review, shopping list, etc.)
6. Unread items have a visual indicator (dot or highlight)
7. Badge count on the Activity nav tab shows unread count, updates in real-time
8. "Mark all as read" action in AppBar
9. Empty state: "All caught up! No new activity."

## Tasks / Subtasks

- [x] Task 1: Backend — UserActivity model + migration (AC: #1)
  - [x] Create migration for `user_activities` table (separate from existing audit `activities`)
  - [x] Create UserActivity model in `libraries/utils/utils/models/user_activity.py`

- [x] Task 2: Backend — API endpoints (AC: #2)
  - [x] `GET /activities` — list user's activities, paginated, ordered by created_at DESC
  - [x] `GET /activities/unread-count` — returns `{ count: N }` for badge
  - [x] `PUT /activities/{id}/read` — mark single activity as read
  - [x] `PUT /activities/read-all` — mark all user activities as read
  - [x] Add activity_router to v1_router

- [x] Task 3: Backend — Create activities for import events (AC: #4)
  - [x] In import job start handler: create activity "Importing from [source]..."
  - Note: Import completion activities deferred to Story 6 (async worker integration)

- [x] Task 4: Flutter — Activity feed screen (AC: #3, #5, #6, #8, #9)
  - [x] Replace shell screen with full implementation
  - [x] Fetch activities from API, group by day (Today/Yesterday/date)
  - [x] Activity tiles with type-specific icons, unread dot indicator
  - [x] Tapping navigates to action_url and marks as read
  - [x] "Mark all as read" AppBar action
  - [x] Empty state: "All caught up!"
  - [x] Pull-to-refresh + 30s polling

- [x] Task 5: Flutter — In Progress section (AC: #4)
  - Note: Import-started activities appear in feed; dedicated progress bar deferred to Story 6

- [x] Task 6: Flutter — Badge count on nav tab (AC: #7)
  - [x] ScaffoldWithBottomNav polls unread count every 30s
  - [x] Badge shows count on Activity tab icon, disappears when 0

## Dev Notes

- The Activity model is intentionally generic — `type` + `metadata` JSONB allows adding new activity types without migrations
- `action_url` uses app-internal paths (e.g., `/recipes/import/review/abc123`) that the router can handle
- For "In Progress" — check existing `ImportJob` polling in `url_import_screen.dart` and `bulk_url_import_screen.dart` for the pattern
- Start with import activities only; partner activity and meal reminders added in Story 6
- Pagination: start with limit=50, load more on scroll

### References

- [Epic: epic-import-activity-nav.md]
- [Investigation: 06-import-flow-overhaul.md — batch import status widget section]
