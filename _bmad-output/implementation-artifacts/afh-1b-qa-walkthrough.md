# QA walkthrough — afh-1b cursor on list_import_items + list_import_jobs

Backend-only story. Verify via `curl` or admin dashboard.

## Preconditions

- `docker compose up`; migrator applied.
- Seeded user with ≥60 import_items under one import_job (so a 50-item
  page has a `next_cursor`), including at least one archived item.
- Seeded user with ≥60 import_jobs, some archived.

## Checks — import_items

- [ ] `GET /v1/import-jobs/{job_id}/items` (default) → 200; items in
      ASC created_at order (legacy behavior preserved); `next_cursor`
      null if ≤50 items.
- [ ] `GET /v1/import-jobs/{job_id}/items?cursor=abc&offset=5` → 400,
      error_message `cursor_and_offset_mutually_exclusive`.
- [ ] `GET /v1/import-jobs/{job_id}/items?cursor=!!!` → 400,
      error_message `invalid_cursor`.
- [ ] See-all mode:
      `GET /v1/import-jobs/{job_id}/items?include_archived=true&limit=5`
      → 200; ordering is `archived_at DESC NULLS LAST, created_at DESC,
      id DESC`. `next_cursor` present when >5 items match. `Link:
      …?cursor=<next>; rel="next"` header present.
- [ ] Pass `next_cursor` back: no rows duplicated or skipped between
      pages.
- [ ] Archive an import_item mid-scroll; next page either contains it
      at its new archived position or omits it — never duplicated.
- [ ] `limit=9999` clamps to 100.
- [ ] Cursor-path requests return `total: 0` (intentional — COUNT
      skipped).

## Checks — import_jobs

- [ ] `GET /v1/import-jobs` (default) → 200; DESC created_at;
      `next_cursor` null if ≤20 items.
- [ ] `GET /v1/import-jobs?cursor=abc&offset=5` → 400.
- [ ] `GET /v1/import-jobs?cursor=!!!` → 400.
- [ ] `GET /v1/import-jobs?include_archived=true&archived_only=true`
      → 200; See-all ordering applied (`archived_at DESC NULLS LAST,
      created_at DESC, id DESC`). Archived-only = the returned set has
      every `archived_at` non-null.
- [ ] Contradictory `archived_only=true&include_archived=false` → 400
      (existing behavior preserved).
- [ ] Pass `next_cursor` back: rows stable under concurrent archive.

## Regression checks

- [ ] Default list behavior unchanged for callers that don't pass
      `cursor` — legacy ASC ordering on import_items, DESC on
      import_jobs.
- [ ] `include_archived=true` without cursor still works.
- [ ] Existing `has_more` field still present on both responses.
