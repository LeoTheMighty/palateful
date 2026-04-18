# QA walkthrough: irrd-1 — backend stage + retry fields

Backend-only story. No Flutter surface to drive manually — verification is
automated tests + a direct API poke if you want to see the payload.

## Pre-flight

- `docker compose up` — stack running on local ports.
- Apply migrations: `npx nx run migrator:migrate` (or
  `docker compose --profile migrate up migrator`).
- Confirm `alembic current` prints `irrd1fields0`.

## 1 — Column + CHECK constraint landed

```sql
\d+ import_items
```

Expect two new columns:
- `last_retry_at           | timestamp with time zone       | nullable`
- `awaiting_review_reason  | character varying(32)          | nullable`

And a CHECK constraint `ck_import_items_awaiting_review_reason` that pins
the value to `{low_confidence, unmatched_ingredients, missing_title,
manual}` (or NULL).

```sql
-- Reject an invalid value.
INSERT INTO import_items (id, import_job_id, source_type,
                          awaiting_review_reason, raw_data, retry_count,
                          ai_cost_cents)
VALUES (gen_random_uuid(), '<some-existing-job-id>', 'url',
        'totally-bogus', '{}'::jsonb, 0, 0);
-- → ERROR:  new row for relation "import_items" violates check
--   constraint "ck_import_items_awaiting_review_reason"
```

Clean up the partial row if the constraint somehow let it through (it
shouldn't).

## 2 — GetImportItem exposes the three fields

Fetch any existing import item:

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/v1/import-items/<item-id> | jq '.'
```

Expect the response to include:

```json
{
  "last_successful_stage": "extracted" | "matched" | null,
  "last_retry_at": "2026-04-18T…Z" | null,
  "awaiting_review_reason": "low_confidence" | … | null,
  …
}
```

## 3 — List items exposes the three fields too

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/v1/import-jobs/<job-id>/items" | jq '.items[0]'
```

Same three keys on each item summary.

## 4 — Retry stamps `last_retry_at` + clears `awaiting_review_reason`

1. Find a failed import item (or flip one's status manually in a
   throwaway job).
2. Pre-set `awaiting_review_reason = 'low_confidence'` directly in the DB.
3. `POST /v1/import-items/{id}/retry` with an owner token.
4. Re-fetch the item → `last_retry_at` is within 1s of now;
   `awaiting_review_reason` is `null`; `retry_count` incremented by 1.

## 5 — Routing reason is stamped on each path

Exercised by `libraries/utils/test/test_awaiting_review_reason.py`:

- `unmatched_ingredients` — any needs_review ingredient with
  `matched_ingredient_id = null`.
- `low_confidence` — needs_review ingredient with a match but below
  `HIGH_CONFIDENCE_THRESHOLD`.
- `missing_title` — recipe has no `name`/`title` (or whitespace-only).
  Wins over both match-based reasons.
- `manual` — no current code path sets this; follow-up.

Run locally: `poetry run pytest libraries/utils/test/test_awaiting_review_reason.py`.

## 6 — Migration round-trip

```bash
cd services/migrator
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test \
  poetry run alembic downgrade -1
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test \
  poetry run alembic upgrade head
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test \
  poetry run alembic check
```

Expect: clean downgrade, clean upgrade, `No new upgrade operations detected.`

## Known gaps (documented, not bugs)

- `list_import_jobs` does **not** expose the three fields per-item because
  the endpoint doesn't eager-load items at all. If a future story wires in
  eager loading, re-check AC6.
- `manual` is an allowed value but no code path sets it today.
