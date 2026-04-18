<!-- refined via party-mode 2026-04-18 -->

# Epic: User Feedback Inbox + Prod Fetch Script

## Overview

Add a user-facing "Send Feedback" affordance in the Flutter app, an admin inbox in the existing admin dashboard (Epic 12), push + badge alerts to admins on new feedback, and a prod script (`fetch_feedback.py`) for bulk export — mirroring the `promote_admin.py` shape. Read-only inbox for v1; reply UI explicitly deferred.

## Goal

A Palateful user thinking "this should work differently" has a two-tap path to telling Leo directly. Leo receives a push notification in real time, can see the feedback inside the admin dashboard with full context (body, app version, platform, route), triage it (Mark Read / Archive), and run a one-line shell command to pull the inbox into a CSV for offline review.

## End-User Flow

Two user personas — the feedback author (any signed-in Palateful user) and the admin (Leo).

**Author flow:**

1. User is browsing a recipe book. Something annoys them.
2. They tap the profile tab → Settings section.
3. A new row "Send Feedback" with a speech-bubble icon sits above Account. They tap it.
4. A bottom sheet slides up: title "Send feedback", a category dropdown (Bug / Idea / Praise / Other — optional), a multiline text field with placeholder "What's on your mind?" and a live char count (3940/4000), a Send button.
5. They type "the share sheet bounces me to home after approving" and tap Send.
6. The sheet closes. A snackbar says "Thanks — feedback sent."
7. If offline: the snackbar says "Saved — we'll send it when you're back online." The submission is queued and retries on next app resume (same pattern as `PostCookFeedbackSheet`).

**Admin flow:**

1. Three seconds later, Leo's phone buzzes. The push reads: "New Palateful feedback from Jane · bug — the share sheet bounces me to home after approving…"
2. Leo taps the push → deep-links to the admin dashboard → the Feedback card now shows a badge of "1".
3. He taps the card → `AdminFeedbackScreen`: filter chips at top (Unread · Read · Archived · All), Unread selected by default. A list renders: one item at the top with Jane's name, timestamp, category chip "bug", app version "1.0.13", platform "iOS", body preview.
4. Leo taps the item → a detail drawer slides in from the right: full body, full `context` JSON (app version, platform, route = `/recipes/import/review-list/…`, recipe_id if present), user email for out-of-band follow-up, Mark Read button, Archive button.
5. He taps Mark Read → drawer dismisses, item moves out of the Unread filter, badge on the dashboard decrements to 0.
6. Later, from his laptop, Leo wants the last 30 days of all feedback as a CSV. He runs `python services/api/scripts/fetch_feedback.py --since 30d --format csv > /tmp/feedback.csv`. The script streams rows to stdout without loading the full set into memory; opens in Numbers instantly.

## Frontend Changes

- **Profile entry**: `app/lib/features/profile/profile_screen.dart` — new "Send Feedback" row in the Settings section (placed after Notifications, before Account). Icon: `Icons.feedback_outlined`.
- **New widget**: `app/lib/features/profile/widgets/feedback_sheet.dart` — bottom sheet modeled on `PostCookFeedbackSheet`. Category dropdown, multiline TextField with char counter (max 4000), Send button, loading spinner while submit is in flight.
- **Offline queue**: reuses the existing cache-service pattern (`RecipeCacheService` is the exemplar). New `FeedbackCacheService` with `queueFeedback(FeedbackDraft)` and `flushQueue()` on `AppLifecycleState.resumed`.
- **New admin screen**: `app/lib/features/admin/admin_feedback_screen.dart` — mirrors `admin_errors_screen.dart`. Filter chips (Unread / Read / Archived / All), paginated `ListView.builder`, tap-to-expand detail drawer, Mark Read + Archive actions.
- **Admin dashboard**: new "Feedback" card on `admin_dashboard_screen.dart` with unread badge count. Tapping deep-links to `/admin/feedback`.
- **Deep-link**: push notifications for `NEW_FEEDBACK` route to `/admin/feedback`. Wiring in `push_notification_service.dart`.
- **Freezed models**: `UserFeedback`, `FeedbackCategory`, `FeedbackStatus`, `FeedbackContext` under `app/lib/features/profile/models/` (author side) + `app/lib/features/admin/models/admin_feedback.dart` (admin side).
- **Router**: new `/admin/feedback` route. Gated by `isAdminProvider`.
- **API client**: `app/lib/core/services/api_client.dart` gains `submitFeedback(body, category, context)`, `getAdminFeedback(status, offset, limit)`, `updateFeedbackStatus(id, status)`.
- **Empty / loading / error states**: shimmer list during load; "No feedback yet — your users will have plenty to say soon." empty state; inline `ErrorCard` with retry on fetch failure.

## Backend Changes

- **Migration** (`services/migrator/migrations/versions/<ts>_add_user_feedbacks.py`): create `user_feedbacks` table with the schema documented in the architecture addendum (2026-04-18). Add `'NEW_FEEDBACK'` to the `notification_type` enum via `ALTER TYPE`.
- **New SQLAlchemy model**: `libraries/utils/utils/models/user_feedback.py`. UUID id, `created_by` relation to `User`, `status` as a Python `Enum` mirroring the DB check constraint, `context` as JSONB.
- **User-facing endpoint** (`Endpoint` class pattern): `services/api/src/api/v1/user/create_user_feedback.py` — `POST /v1/user/feedback`. Params: `body (str, 1..4000)`, `category (optional enum)`, `context (optional dict)`. Response: `{"id": UUID, "status": "submitted"}`. Enqueues the notification fan-out task. Rate-limited per user: 10/hour (NFR52) via a new dependency `rate_limit_per_user(limit=10, window="1h")` — uses Redis incr pattern (Redis already in the stack for Celery broker).
- **Admin list endpoint**: `services/api/src/api/v1/admin/list_feedback.py` — `GET /v1/admin/feedback?status=…&offset=&limit=`. Joins `users` for display_name + email. Paginates. Default `limit=25`, `max_limit=100`.
- **Admin status-change endpoint**: `services/api/src/api/v1/admin/update_feedback_status.py` — `PUT /v1/admin/feedback/{feedback_id}/status`. Body: `{"status": "read"|"archived"|"unread"}`. Writes audit row to `error_logs` (`service="audit"`, `error_type="FeedbackStatusChange"`).
- **Admin stats extension**: `services/api/src/api/v1/admin/get_stats.py` — add `unread_feedback` count. Coordinates with the observability epic's other stats extensions.
- **Celery fan-out task**: `libraries/utils/utils/tasks/notification_tasks/notify_admins_new_feedback.py`. Params: `feedback_id`. Loads every `User` where `is_admin=true AND archived_at IS NULL`, calls `PushNotificationService.send_to_user(admin.id, type=NotificationType.NEW_FEEDBACK, title="New Palateful feedback", body=<first 120 chars>, data={"feedback_id": ..., "deep_link": "/admin/feedback"}, force=True)` for each. Respects `PushNotificationService`'s existing idempotency / retry semantics. One push per admin per feedback; idempotency key = `feedback_id + admin_id`.
- **Notification type extension**: add `NEW_FEEDBACK` to `NotificationType` enum in `libraries/utils/utils/models/notification.py`. Migration handles the DB-enum ALTER.
- **Router registration**: `services/api/src/routers/v1/admin_router.py` — register both admin endpoints. `services/api/src/routers/v1/user_router.py` (or equivalent) — register the user endpoint.
- **Prod script**: `services/api/scripts/fetch_feedback.py`. Mirrors `promote_admin.py`:
  - `--since` accepts `7d`, `30d`, `90d`, `all` (default: `7d`).
  - `--status` accepts `unread`, `read`, `archived`, `all` (default: `unread`).
  - `--format` accepts `csv` (default), `tsv`, `json` (JSON-lines — one object per row).
  - Reads `DATABASE_URL` from env; SQLAlchemy engine; `text()` queries, parameterized.
  - Streams rows to stdout (generator loop, not a buffered list — NFR54).
  - Writes one audit row to `error_logs` (`service="audit"`, `error_type="FeedbackExport"`) at end-of-run capturing filter args + row count.
  - Exit codes: 0 success, 1 other error, 2 no matching rows (informational, not a failure).
  - No `--yes` needed — this is read-only. Reserved `--yes` for a future bulk-archive extension.

## Infrastructure Changes

- **None.** No new AWS resources. Reuses existing RDS, Redis (for rate limiting, already deployed), Celery broker, FCM. The `NEW_FEEDBACK` notification type is a Python enum + DB enum ALTER, both handled in the migration. No Terraform changes.
- **Environment variables**: none new. The rate-limit window + threshold are Python constants in the new dependency.

## Design Principles (refined via party-mode 2026-04-18)

- **Minimum viable signal.** Free text + optional category is enough. No screenshots, no device diagnostic payloads, no automatic navigation stack capture. The Flutter app supplies `app_version`, `platform`, and `route` via the `context` blob — that's the full metadata envelope.
- **Hot-path bypass for admin fan-out.** `POST /v1/user/feedback` returns <500ms (NFR53); the Celery fan-out task absorbs FCM latency. Admin delivery is eventually-consistent.
- **Read-only inbox, full stop.** No reply, no assignment, no tagging. Mark Read / Archive only. Admin follows up out-of-band using the user's email (included in the admin list response). Reply is a future epic, surfaced only when real demand appears.
- **Offline-first author.** The queue flushes on both `AppLifecycleState.resumed` and on initial app launch. A cold-start where the user had offline-queued feedback still flushes. Same durability as `PostCookFeedbackSheet`.
- **Abuse-resistant.** Rate limit (NFR52) prevents flood. Auth-gated submission prevents drive-by spam. There is no delete-feedback endpoint — once submitted, feedback is archive-only (preserves audit trail).
- **Tight `context` schema.** `context` is a Pydantic model with strictly these optional fields: `app_version: str | None`, `platform: "ios" | "android" | "web" | None`, `route: str | None`, `recipe_id: UUID | None`. Unknown keys are rejected at submit time. Admin-visible in the detail drawer — users submit knowing this is an admin-reviewed channel (acceptable at friends-and-family scale).
- **Archived admins skipped on fan-out.** The Celery task selects `User.is_admin = true AND archived_at IS NULL` so an offboarded admin doesn't receive pushes. Also guards against "legal nightmare if we ever ship a tenant boundary."
- **Push payload carries routing.** The `NEW_FEEDBACK` notification's `data` payload carries `{"feedback_id": ..., "deep_link": "/admin/feedback"}`. Tapping the push deep-links to the inbox. If `PushNotificationService` does not currently pass custom `data` through to FCM, extending it to do so is a one-line addition folded into story 2.
- **Optimistic UI with rollback.** Mark Read / Archive apply locally first, fire the API call, and on failure revert + surface an error snackbar. No modal confirmation dance for ordinary actions.
- **Prod script over web UI export.** `fetch_feedback.py` matches the `promote_admin.py` ops pattern; an in-dashboard CSV export button is out of scope.

### Locked decisions inherited from sibling epic

- `epic-observability-latency` also extends `GET /v1/admin/stats`. Whichever epic merges second must rebase the stats response shape to union both contributions (`overall_p95_ms`, `slowest_endpoint`, `unread_feedback`).
- `require_admin` + `isAdminProvider` are the shared guards — no new gating primitives.
- Audit rows go to `error_logs` with `service="audit"` + structured `error_message`.

## File Structure

**Backend:**

```
services/migrator/migrations/versions/<ts>_add_user_feedbacks.py           (new)
services/api/src/api/v1/user/create_user_feedback.py                       (new)
services/api/src/api/v1/admin/list_feedback.py                             (new)
services/api/src/api/v1/admin/update_feedback_status.py                    (new)
services/api/src/api/v1/admin/get_stats.py                                 (modify)
services/api/src/routers/v1/admin_router.py                                (modify)
services/api/src/routers/v1/user_router.py                                 (modify)
services/api/src/dependencies.py                                           (modify — add rate_limit_per_user dep)
services/api/scripts/fetch_feedback.py                                     (new)
libraries/utils/utils/models/user_feedback.py                              (new)
libraries/utils/utils/models/notification.py                               (modify — add NEW_FEEDBACK)
libraries/utils/utils/tasks/notification_tasks/__init__.py                 (new)
libraries/utils/utils/tasks/notification_tasks/notify_admins_new_feedback.py (new)
services/api/tests/test_user_feedback.py                                   (new)
services/api/tests/test_admin_feedback.py                                  (new)
libraries/utils/tests/test_notify_admins_new_feedback.py                   (new)
services/api/scripts/tests/test_fetch_feedback.py                          (new)
```

**Frontend:**

```
app/lib/features/profile/widgets/feedback_sheet.dart                       (new)
app/lib/features/profile/profile_screen.dart                               (modify — add row)
app/lib/features/profile/models/user_feedback.dart                         (new)
app/lib/features/profile/providers/feedback_provider.dart                  (new)
app/lib/features/profile/services/feedback_cache_service.dart              (new)
app/lib/features/admin/admin_feedback_screen.dart                          (new)
app/lib/features/admin/admin_dashboard_screen.dart                         (modify — add card)
app/lib/features/admin/models/admin_feedback.dart                          (new)
app/lib/features/admin/providers/admin_feedback_provider.dart              (new)
app/lib/core/services/api_client.dart                                      (modify)
app/lib/core/services/push_notification_service.dart                       (modify — deep-link for NEW_FEEDBACK)
app/lib/core/router/app_router.dart                                        (modify — /admin/feedback)
app/test/features/profile/feedback_sheet_test.dart                         (new)
app/test/features/admin/admin_feedback_screen_test.dart                    (new)
```

## Stories

**`feedback-1-backend-model-and-submit-endpoint`** — Migration for `user_feedbacks` + `NEW_FEEDBACK` enum; SQLAlchemy model; `POST /v1/user/feedback` endpoint; rate-limit dependency; unit + integration tests.

ACs:
- Migration creates `user_feedbacks` with the schema in the architecture addendum and adds `NEW_FEEDBACK` to `notification_type` enum.
- `POST /v1/user/feedback` validates body (1..4000), category enum, **`context` against a strict Pydantic model** (optional `app_version`, `platform ∈ {ios, android, web}`, `route`, `recipe_id` UUID; unknown keys → 422); returns 201 with `{id, status: "submitted"}`.
- Rate limit: 10 submissions per user per rolling hour → 11th returns 429. Redis incr with 1h TTL.
- Unauthenticated request → 401.
- `body` at length 0 or >4000 → 422.
- Integration test covers: valid submission persists a row with `status="unread"`, all optional fields optional, user_id populated from JWT, unknown-`context`-key rejected.
- Celery fan-out task is enqueued (mocked in test — just verify the call); actual fan-out tested in story 2.

**`feedback-2-admin-endpoints-notification-fanout-and-stats`** — Admin list + status-change endpoints; notify-admins Celery task; admin-stats extension; audit writes.

ACs:
- `GET /v1/admin/feedback?status=unread&offset=0&limit=25` returns paginated list joined with users; non-admin → 403; invalid status → 400.
- `PUT /v1/admin/feedback/{id}/status` transitions status, returns the updated row with refreshed `updated_at`; audit row written to `error_logs` with `error_type="FeedbackStatusChange"` and `error_message` formatted as `feedback=<id> from=<old> to=<new> by_admin=<user_id>`.
- `GET /v1/admin/stats` adds `unread_feedback` field (rebased against the observability epic's additions if merging second).
- `notify_admins_new_feedback` task selects admins via `is_admin=true AND archived_at IS NULL`, calls `PushNotificationService.send_to_user(..., type=NEW_FEEDBACK, data={"feedback_id": ..., "deep_link": "/admin/feedback"}, force=True)` per admin; test verifies: one call per *active* admin, payload shape, `force=True` bypasses quiet hours.
- **If `PushNotificationService.send_to_user` does not currently forward a custom `data` arg to FCM, extend it in this story to pass through** — this is the first caller that needs routing-payload support.
- FCM error for one admin does not prevent delivery to others; archived-admin-in-the-middle is skipped, not failed on.
- NFR53: user-facing response time in integration test stays <500ms with fan-out enqueued (Celery in eager mode swapped out in test).

**`feedback-3-flutter-send-feedback-sheet`** — `FeedbackSheet` widget + Profile entry + offline queue + API client plumbing + widget tests.

ACs:
- Profile → Settings shows "Send Feedback" row above Account.
- Tapping opens the sheet; Send disabled until body is non-empty.
- Online submission calls `POST /v1/user/feedback`, closes sheet with "Thanks — feedback sent" snackbar.
- Offline submission queues via `FeedbackCacheService`, snackbar reads "Saved — we'll send it when you're back online."
- Queue flushes on both `AppLifecycleState.resumed` **and on app cold-start** (after auth is available); a cold-start-only user who queued offline and relaunched still has submission go through without a subsequent resume event.
- Successful background flushes emit a subdued snackbar ("Sent queued feedback").
- Character counter goes red at >3900; Send disabled at >4000.
- Widget test covers: typing → char counter updates, Send disabled → enabled, submission calls API, error path (offline queue), success snackbar.

**`feedback-4-flutter-admin-inbox-and-dashboard-card`** — `AdminFeedbackScreen` + dashboard Feedback card + deep-link from push + router + widget tests.

ACs:
- `/admin/feedback` route gated by `isAdminProvider`; non-admin → 404.
- Filter chips (Unread / Read / Archived / All), default Unread; tapping a chip re-queries and refreshes.
- List virtualizes via `ListView.builder`; each item shows display_name, timestamp, category chip, app_version, platform, body preview (first 120 chars).
- Tapping item opens detail drawer: full body, full `context` JSON rendered readably, user email, Mark Read button (hidden if already read), Archive button.
- Mark Read and Archive apply **optimistically** — local state flips immediately, API fires in background. On failure (non-2xx / network), local state **rolls back** and an error snackbar surfaces ("Couldn't update — tap to retry").
- Admin dashboard shows a "Feedback" card with the `unread_feedback` badge; tapping navigates to `/admin/feedback?status=unread`.
- Tapping a `NEW_FEEDBACK` push notification deep-links to `/admin/feedback`.
- Empty state: "No feedback in this filter yet." Error state: inline ErrorCard with retry.
- Widget test covers: list renders with mixed statuses, tap expands drawer, Mark Read optimistic update, push-tap deep-link.

**`feedback-5-prod-fetch-script`** — `services/api/scripts/fetch_feedback.py` + tests + docs update.

ACs:
- `python services/api/scripts/fetch_feedback.py --help` prints usage mirroring `promote_admin.py`.
- `--since 7d --status unread --format csv` prints CSV header + rows streaming to stdout; rows are correctly filtered.
- `--format json` prints JSON-lines (one object per line).
- `--since all --status all` emits every row; tested with a 10k-row seed to verify streaming (memory stays bounded).
- Audit row written to `error_logs` at end of run with filter + row count in `error_message`.
- Exit 0 on success, 2 on zero-row match (informational), 1 on DB / other errors.
- `CLAUDE.md` "Ops Scripts" section gets a new entry documenting the script, matching `promote_admin.py`'s write-up.
- Test harness uses a factory-created DB with seeded feedback rows; runs the script as a subprocess; asserts stdout contents.

## Dependencies

- **Blocks nothing** — terminal epic; no downstream consumer.
- **Blocked by nothing** — all primitives (admin dashboard, `require_admin`, `PushNotificationService`, Redis, Celery, `promote_admin.py` template, `error_logs` audit) exist.
- **Story ordering within the epic:** 1 → 2 → (3, 4 in parallel) → 5. Story 5 only needs the migration + model from story 1.
- **Parallelizable with `epic-observability-latency`** — different tables, different handlers, different screens. Coordinate on the `get_stats.py` shape (both epics extend it); whichever lands second rebases the stats response.

## Explicitly Out of Scope (surfaced in party-mode)

- **Recipe-detail "Send feedback about this recipe" entry point.** Would auto-populate `recipe_id` in the `context` blob. Valuable, but adds a second entry point + recipe-screen layout negotiation. Deferred to a follow-up story once the core surface proves itself.
- **Admin reply to user** in any form (one-way push, in-app inbox on user side, threaded). Confirmed deferred in the 2026-04-18 user batch.
- **Delete-feedback endpoint.** Archive is terminal. Preserves audit history.
- **Feedback search / full-text.** The inbox is filter-by-status only. A <50-user inbox doesn't justify Postgres FTS tooling; revisit past 1000 items.
- **SES / email-channel** for admin delivery. Push + badge covers the need; email bolt-on is a later layer.
- **Anonymizing `context` for admin view.** Admin sees the full blob. Call out in `docs/PRIVACY.md` (or wherever user data flow is documented) as a known scope — future work when tenant boundaries matter.

## Open Questions for the User

- None at draft time. None surfaced in party-mode.
