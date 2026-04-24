# aam-16 QA Walkthrough — Activity Domain Async

**Story**: aam-16 (Activity domain async)
**Epic**: epic-api-async-migration
**Last-good commit (pre-aam-16)**: `4ea2212` —
`feat(api): aam-foundations-notify-threadpool-helper — notify_via_threadpool bridge`
**Rollback procedure**: `git revert <aam-16-commit> && bin/prod-deploy`
(~10 min). aam-16 does NOT mount a `/_legacy_v1/activities` sibling —
same precedent as aam-10 / aam-21.

Four sections, in the order the runbook prescribes:

1. Lazy-load audit
2. Pre-merge latency baseline
3. Manual scenario checklist
4. Rollback + cross-domain blast radius

---

## 1. Lazy-load Audit

Goal: every ORM `.<attr>.<attr>` chain reachable from an activity-domain
handler is either (a) a scalar column on `UserActivity` itself, or (b)
resolved via an explicit SQL join/select, so no attribute access fires
`MissingGreenlet` on the async engine.

### 1.1 Model relationships — `UserActivity`

```
$ grep -nE "relationship\(" libraries/utils/utils/models/user_activity.py
```

No matches. `UserActivity` has no SQLAlchemy `relationship()` on the
model — every attribute the handler reads is a scalar column
(`user_id`, `type`, `title`, `subtitle`, `metadata_json`, `read`,
`action_url`, `created_at`, `updated_at`, `archived_at`, `id`). No
lazy-load surface.

### 1.2 Handler attribute access grep

```
$ grep -nE "(activity|a)\.(recipe|recipe_book|user|import|item|job)" \
    services/api/src/api/v1/user_activity/ \
    --glob '!*__pycache__*'
```

No matches. Handlers read only scalar columns on `UserActivity` — no
cross-model attribute traversal, no implicit lazy load.

### 1.3 `unread_count.py` — ImportItem × ImportJob join

The only join in the activity domain is
`ImportItem.join(ImportJob, ImportItem.import_job_id == ImportJob.id)`
for the imports_actionable count. This is an **explicit SQL join** in
the `select(...)` statement, not a Python-side attribute traversal —
the async engine renders it as a single SQL query with `INNER JOIN
import_jobs ON ...`, no greenlet round-trip.

### 1.4 Response builders

`ActivityItem` Pydantic model reads `a.id`, `a.type`, `a.title`,
`a.subtitle`, `a.metadata_json`, `a.read`, `a.action_url`,
`a.created_at`, `a.archived_at` — **all scalar columns**. No
relationship access. Safe on async.

**Lazy-load audit: CLEAN.** No eager-load needed, no `selectinload`
chains required.

---

## 2. Pre-merge Latency Baseline

Capture pre-merge baseline for `GET /v1/activities` before the PR
merges:

```bash
$ bin/prod-script services/api/scripts/analyze_latency.py \
    --window 24h --section endpoints --top 50 --format csv \
    > /tmp/aam-16-baseline-endpoints.csv
$ grep -i "GET.*activit" /tmp/aam-16-baseline-endpoints.csv
```

(To be captured and pasted here before PR opens — one of the dev-loop's
deferred-until-merge-time tasks.)

Post-merge (24h window): the primary target is `GET /v1/activities`
client-observed p95 **flat or improved**. Activity endpoints are
low-volume relative to `/v1/meals` — the expected signal is modest
improvement (single-digit ms tail reduction from removing the
threadpool hop on the sync handler).

Secondary targets:
- `GET /v1/activities/unread-count` — polled every Notifications-tab
  refresh, so it matters cumulatively. Post-merge p95 should be flat
  or improved.
- `PUT /v1/activities/read-all` — bulk UPDATE; post-async p95 should
  be flat (Core `UPDATE...WHERE` vs ORM `Query.update()` compiles to
  the same SQL).

Rollback trigger: any endpoint in this domain shows >20% p95
regression in the 24h observation window.

---

## 3. Manual Scenario Checklist

Run on staging after merge + deploy. Check each scenario in Flutter
app against the staging backend.

### 3.1 Activity list mount (Notifications tab)

- [ ] Tap the bell icon in the top bar. Notifications tab loads.
- [ ] Verify the list populates (if any recent partner_action rows
  exist) OR shows the empty state (if none).
- [ ] Verify no loading spinner hangs — response under 500ms server
  side.
- [ ] Pull-to-refresh — list refreshes without error.

### 3.2 Unread-count badge polling

- [ ] Bell icon shows correct badge count matching the number of
  unread partner_action rows + actionable imports.
- [ ] Trigger a new partner_action (invite a friend to a recipe book)
  — badge count increments within the poll window.
- [ ] Open the Notifications tab, verify the bell badge drops to 0
  after marking items read (poll-fresh).

### 3.3 Mark-all-read (bulk UPDATE)

- [ ] In Notifications tab, tap "Mark all read". All rows transition
  to read state.
- [ ] Reload the app — rows stay read (commit persisted, not just
  flushed).
- [ ] Bell badge drops to 0.

### 3.4 Single mark-read

- [ ] Tap on a single notification row → it navigates to the action
  URL AND the row transitions to read.
- [ ] Reload — single row stays read.

### 3.5 Archive + Unarchive

- [ ] Long-press a notification row → "Archive" action. Row disappears
  from the default list.
- [ ] Open See-all — archived row is still present under "Archived".
- [ ] Tap "Restore" on the archived row — it returns to the default
  list.

### 3.6 See-all count footer (pbq-5 / afh-2)

- [ ] Scroll to the bottom of the Notifications tab. Footer shows
  "See all (N) ›" where N = archived + read_and_older.
- [ ] Tap the footer — See-all sheet opens, lists archived + aged-out
  rows.

### 3.7 Cursor pagination (afh-1a)

- [ ] Seed > 50 partner_action rows (staging only; use admin tool).
- [ ] Scroll to the bottom of the first page — next page loads via
  cursor (Link header). `total` field on response is 0 (pbq-5).

### 3.8 See-all mode (include_archived + include_read + unbounded)

- [ ] In See-all sheet, scroll past the bottom — next page loads; the
  cursor encodes `archived_at` so the archived/non-archived boundary
  resumes correctly.

### 3.9 Admin debug flag

- [ ] As admin user, fetch
  `GET /v1/activities?include_system_types=true` — returns all types
  including `import_*` rows.
- [ ] As non-admin, same call → 403 with `Admin access required`.

---

## 4. Rollback + Cross-Domain Blast Radius

### 4.1 Rollback

`git revert <aam-16-commit> && bin/prod-deploy`. The revert is
side-effect-free:

- `create_activity_async` removal doesn't affect any existing caller
  (no async caller exists on this branch yet; aam-11 / aam-13 will
  introduce them).
- Sync `create_activity` unchanged — worker tasks and not-yet-flipped
  domains (recipe_book, shopping_list) keep working through the
  revert window.
- Router dep flips back to sync `get_database` + `get_current_user`
  — fully compatible with pre-merge client behavior.

### 4.2 Cross-domain blast radius

**Affected downstream consumers:**
- `services/worker/` — imports `create_activity` via
  `utils.services.activity_service`. Still sync. ✓
- `libraries/utils/utils/tasks/import_tasks/watch_parser_job_task.py`
  — uses sync `create_activity`. ✓
- `libraries/utils/utils/services/parser_batch_completion.py` — uses
  sync `create_activity`. ✓
- `services/api/src/api/v1/recipe_book/add_recipe_book_member.py` —
  uses sync `create_activity`; recipe_book domain still sync. ✓
- `services/api/src/api/v1/shopping_list/add_item.py` — uses sync
  `create_activity`; shopping_list domain still sync. ✓

**No consumer uses `create_activity_async` yet** — it's the async
surface for aam-11 and aam-13 to adopt when those domains flip.
Adding it now is purely additive; rollback is safe.

### 4.3 Flutter client contract

- `/v1/activities`: response shape unchanged (`total: int, limit,
  offset, items, next_cursor, unread_count`). `total=0` invariant
  preserved (pbq-5).
- `/v1/activities/unread-count`: response shape unchanged
  (`notifications, imports_actionable, count`).
- `/v1/activities/see-all-count`: response shape unchanged (`archived,
  read_and_older, total`).
- `/v1/activities/{id}/read`, `/read-all`, `/archive`, `/unarchive`:
  all return `success()` ack on 200 — unchanged.

**No Flutter-side change required.** No schema migration needed.
