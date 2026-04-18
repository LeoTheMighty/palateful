# QA Walkthrough — obs-latency-1

## Setup
- Run `docker compose up`. Ensure the API + worker + DB containers all come up cleanly.
- Run migrations: `docker compose --profile migrate up migrator`. Verify log line
  `Running upgrade u1f2e3e4d5b6 -> o1b2s3l4a5t1, Add request_latencies + task_latencies tables.`

## Happy path — API capture
- [ ] Hit any authed endpoint (e.g. `GET /v1/user/me` with a valid Bearer token).
      Wait 2–3 seconds.
- [ ] `psql -U postgres palateful -c "SELECT method, normalized_path, status_code, duration_ms FROM request_latencies ORDER BY created_at DESC LIMIT 1;"`
      → one row with `method=GET`, `normalized_path=/v1/user/me`, a sensible `duration_ms`.
- [ ] Hit a parameterized route (e.g. `GET /v1/recipes/<uuid>`) — repeat.
      Confirm `normalized_path = /v1/recipes/{recipe_id}` (template, not the raw UUID).

## Health / ready hard-skip
- [ ] Hit `GET /v1/health` 10×. Wait 2 s.
- [ ] `SELECT COUNT(*) FROM request_latencies WHERE normalized_path = '/health';` → 0.
- [ ] Same for `/ready`.

## 404 skip
- [ ] Hit `GET /v1/does-not-exist`. Wait 2 s.
- [ ] Confirm `SELECT * FROM request_latencies WHERE normalized_path IS NULL;` → 0 rows.
      Unmatched routes must be skipped, not logged with a NULL or "UNMATCHED" path.

## Celery task capture
- [ ] Trigger any Celery task that runs on the default queue (e.g. trigger a recipe
      import: `POST /v1/import/url` with a test URL). Wait for it to complete.
- [ ] `SELECT task_name, status, duration_ms FROM task_latencies ORDER BY created_at DESC LIMIT 5;`
      → one row per task lifecycle with non-zero `duration_ms`.

## Retry lifecycle
- [ ] Pick a task that retries on failure (e.g. artificially fail an import).
      Confirm two rows appear for the same `task_id`: one with `status='retry'`,
      later one with `status='success'` (or another `retry` / `failure` depending on outcome).

## Chaos: DB unreachable
- [ ] `docker compose stop db`. Hit the API. Confirm:
      - Requests still return their normal responses (no 500).
      - API container logs include a WARN/ERROR from
        `utils.services.observability.batched_latency_writer` (`failed to flush`).
- [ ] `docker compose start db`. Wait 5 s, hit the API again. New samples land.

## Graceful shutdown drain
- [ ] Pound the API with ~200 requests, then `docker compose stop api` (sends SIGTERM).
- [ ] Bring the API back up. `SELECT COUNT(*) FROM request_latencies;` — count matches
      (or is within a few rows of) the requests sent. Drain should have caught the
      last 2 s on the way down.
