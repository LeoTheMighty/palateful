# QA walkthrough — afh-2 see-all-count endpoints + partial indexes

Backend-only. Verify via `curl`.

## Preconditions

- `docker compose --profile migrate up migrator` — applies
  `afh2seeallidx1`.
- Seeded user with a mix of:
  - Some archived `partner_action` user_activities.
  - Some read partner_actions older than 30 days (not archived).
  - Some active unread partner_actions.
  - Some archived import_items (across any job the user owns).
  - Some completed import_items older than 30 days (not archived).

## Checks

- [ ] `GET /v1/activities/see-all-count` → 200, returns
      `{archived: <int>, read_and_older: <int>, total: <int>}`, with
      `total == archived + read_and_older`.
- [ ] Unread recent rows NOT counted (they're in the active list, not
      See-all).
- [ ] Rows with types outside `NOTIFICATION_TAB_TYPES` (legacy
      `import_*`) NOT counted — allow-list applies on both buckets.
- [ ] `GET /v1/import-items/see-all-count` → 200, returns
      `{archived, read_and_old_completed, total}`. Sum invariant holds.
- [ ] Active `awaiting_review` items NOT counted.
- [ ] Items from other users' import_jobs NOT counted (tenant
      isolation via the `import_jobs` join).
- [ ] p95 under 50ms on a seeded user with a few hundred rows. Run:
      `time curl -sS http://localhost:8000/v1/activities/see-all-count`
      repeatedly; even without warm cache the median should be well
      under 50ms.

## Migration checks

- [ ] After `docker compose --profile migrate up migrator`, both
      indexes exist:
      `\d+ user_activities` shows `ix_user_activities_user_read_old`;
      `\d+ import_items` shows `ix_import_items_job_completed_old`.
- [ ] `alembic downgrade -1` drops the indexes cleanly; `upgrade head`
      re-adds them.
- [ ] `EXPLAIN ANALYZE` of the `read_and_older` count query on a
      seeded table shows an `Index Only Scan` or `Bitmap Index Scan`
      using the new partial index.

## Regression checks

- [ ] `GET /v1/activities/unread-count` (bell) still returns the same
      triple shape (notifications, imports_actionable, count).
- [ ] `GET /v1/activities` default list behaviour unchanged.
- [ ] `GET /v1/import-jobs/{job_id}/items` default list behaviour
      unchanged.
- [ ] `/import-items/see-all-count` does NOT collide with
      `/import-items/{item_id}` — the See-all route is registered
      first.
