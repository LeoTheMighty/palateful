# QA walkthrough — afh-1a cursor helper + list_activities See-all mode

Backend-only story. No Flutter surface yet — verify via `curl` or admin-
dashboard request inspector.

## Preconditions

- Pulled main at / past the afh-1a commit.
- `docker compose up` running; `migrator` has applied all migrations.
- Seeded user with some `user_activities` rows of type `partner_action`,
  including at least one `archived_at IS NOT NULL` row and one
  `read = true AND created_at < NOW() - INTERVAL '30 days'` row.

## Checks

- [ ] `GET /v1/activities` (default) → 200, `items` contains active
      partner_action rows; archived and >30d rows absent; `next_cursor`
      is null when there are ≤50 rows.
- [ ] `GET /v1/activities?limit=9999` → 200; response `limit` clamped to
      `100`.
- [ ] `GET /v1/activities?cursor=abc&offset=5` → 400, error_message
      `cursor_and_offset_mutually_exclusive`.
- [ ] `GET /v1/activities?cursor=garbage!!` → 400, error_message
      `invalid_cursor`.
- [ ] `GET /v1/activities?since_days=` → 200; response includes rows
      older than 30d (retention window disabled). Confirm with a row
      whose `created_at` is >30d ago.
- [ ] `GET /v1/activities?since_days=yesterday` → 400 (non-integer is
      rejected at the router).
- [ ] See-all mode:
      `GET /v1/activities?include_archived=true&include_read=true&since_days=&limit=5`
      → 200; ordering is `archived_at DESC NULLS LAST, created_at DESC`.
      First rows are recently-archived; trailing rows are read-but-older.
- [ ] When >5 rows match, response has `next_cursor` string AND `Link:
      …?cursor=<next>; rel="next"` response header.
- [ ] Pass that `next_cursor` back in a second request; confirm no rows
      are duplicated or skipped between pages.
- [ ] Archive a row mid-scroll (hit `POST /v1/activities/{id}/archive`
      between page fetches) and confirm the next page either contains or
      omits it, but never duplicates it — the row-value WHERE clause
      handles the `archived_at` flip cleanly.
- [ ] Legacy `offset=`: `GET /v1/activities?limit=5&offset=10` → 200;
      rows are a slice of the ordered list. (Will be dropped in a
      future release.)
- [ ] `?cursor=` requests return `total: 0` (COUNT is intentionally
      skipped on the cursor path).

## Regression checks

- [ ] Bell / badge count from `GET /v1/activities/unread-count` is
      unchanged (afh-1a only touched `list_activities`, not
      `unread_count`).
- [ ] Non-admin passing `?include_system_types=true` still → 403.
- [ ] Admin passing `?include_system_types=true` still bypasses the
      allow-list.
