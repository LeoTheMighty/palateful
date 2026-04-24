# QA walkthrough — aam-20 (admin domain async)

Scope: admin surface under `/v1/admin/*` now runs on the async engine
end-to-end. Everything below is covered by unit tests
(`tests/test_admin*.py`) but the walkthrough is the "poke the live
surface" smoke list for prod soak.

## 1. Admin gate (`require_admin_async`)

- [ ] Hit any `/v1/admin/*` endpoint **with a non-admin user** → expect
      `403 forbidden` with `error_code=FORBIDDEN`.
- [ ] Hit the same endpoint **as admin** → expect `200` / whatever the
      endpoint returns.

## 2. Stats header (`GET /v1/admin/stats`)

- [ ] Response carries `total_users`, `total_recipes`,
      `total_recipe_books`, `errors_24h`, `active_users_7d`,
      `unread_feedback`, `overall_p95_ms`, `slowest_endpoint`.
- [ ] `overall_p95_ms` comes back `null` on a cold DB with no
      `request_latencies` rows; non-null `int` once traffic flows.
- [ ] `slowest_endpoint.method` / `.normalized_path` / `.p95_ms` non-null
      after some traffic.

## 3. Error logs browser

- [ ] `GET /v1/admin/errors` → list + `total`.
- [ ] `GET /v1/admin/errors?service=api&limit=50&offset=0` → filtered + pagination.
- [ ] `GET /v1/admin/errors/{id}` → full row including `stack_trace`.
- [ ] `GET /v1/admin/errors/{bogus_uuid}` → `404 NOT_FOUND`.

## 4. User management

- [ ] `GET /v1/admin/users?limit=50&offset=0` → paginated.
- [ ] `PUT /v1/admin/users/{id}/admin` `{"is_admin": true}` → grants admin.
- [ ] `PUT /v1/admin/users/{self}/admin` `{"is_admin": false}` with **only
      one admin in the DB** → `400 VALIDATION_ERROR` ("Cannot remove
      admin from the last admin user").
- [ ] Same call when `admin_count > 1` → `200` success, self-demote
      applied.

## 5. CloudWatch logs (`GET /v1/admin/logs`)

- [ ] `?service=api&level=INFO&search=foo&start_time=…&end_time=…` →
      events list + count + log_group.
- [ ] If boto3 creds are missing (dev) → `200` with `events=[]`,
      `error="CloudWatch unavailable: …"`. (No longer blocks the event
      loop — wrapped in `run_in_threadpool`.)

## 6. Feedback inbox

- [ ] `GET /v1/admin/feedback` → defaults to `status=unread`, paginated
      (offset / limit).
- [ ] `GET /v1/admin/feedback?status=all` → drops the status filter.
- [ ] `GET /v1/admin/feedback?status=spam` → `400` validation error.
- [ ] `GET /v1/admin/feedback?limit=500` → `422` (FastAPI Query `le=100`).
- [ ] `PUT /v1/admin/feedback/{id}/status` `{"status":"read"}` → returns
      updated row; writes exactly one `service='audit'` `ErrorLog` row
      (`error_type=FeedbackStatusChange`, message includes
      `feedback=<id> from=unread to=read by_admin=<admin_id>`).
- [ ] Same-status no-op (unread → unread) still writes the audit row.

## 7. Latency metrics

- [ ] `GET /v1/admin/metrics/endpoints?window=24h` → rows with
      `method`, `normalized_path`, `p50_ms`, `p95_ms`, `p99_ms`, `count`,
      `error_rate`, 24-length `sparkline`.
- [ ] `?window=bogus` → `400`.
- [ ] Only `1h`, `24h`, `7d` accepted.
- [ ] `GET /v1/admin/metrics/tasks?window=24h` → same shape but
      `task_name` + `failure_rate`.

## 8. Client-latency metrics (cla-10a)

- [ ] `GET /v1/admin/metrics/client/routes?window=24h&platform=ios&app_version=1.0.13&route=/home`
      → rows sorted by `p95_ms desc`, SQL params correctly filtered.
- [ ] `GET /v1/admin/metrics/client/endpoints` → `method`, `endpoint`,
      `p50/p95/p99_ms`, `count`.
- [ ] `GET /v1/admin/metrics/client/jank` → `build_p95_ms` + `raster_p95_ms`.
- [ ] `GET /v1/admin/metrics/client/sparkline?metric=route_paint` →
      24-length buckets list. Invalid metric → `400`.

## 9. Push-health diagnostic (push-diag-3)

- [ ] `GET /v1/admin/notifications/health/{uuid}` →
      `notification_permission_status`, `push_tokens` (prefixes only),
      `push_tokens_count`, `recent_errors` (last N `service='push_notifications'`
      rows), `crashlytics_query_url`, `last_successful_send_*`=null.
- [ ] `GET /v1/admin/notifications/health/{email}` (case-insensitive) →
      same blob via email lookup.
- [ ] `GET /v1/admin/notifications/health/{unknown}` → `404`.
- [ ] `?error_limit=0` or `?error_limit=51` → `422` (FastAPI Query
      constraints).
- [ ] Non-admin caller → `403 FORBIDDEN`.
- [ ] Every call writes exactly one `service='audit'`, `error_type='AdminPushHealthCheck'`
      row.

## 10. Test-push (`POST /v1/admin/notifications/test-push`)

- [ ] Default body `{}` → fires to caller's own devices,
      `success_count=1` + `outcome=ok` path → writes one
      `service='audit'` row (`error_type=AdminTestPushAudit`, message
      includes `result=ok message_id=<fcm-msg-id>`).
- [ ] `{"target_user_id": "<uuid>"}` with custom title/body → pushes to
      that target instead. `target_user_id` missing → `404`.
- [ ] `?force=false` during quiet hours → `outcome=suppressed_quiet_hours`,
      `suppressed_by_quiet_hours=true`; no push sent.
- [ ] User with no push tokens → `outcome=no_tokens`,
      `tokens_registered=0`, `ok=true` (deterministic no-op).
- [ ] **Rate limit**: 10 consecutive calls within a minute all succeed,
      the 11th returns `429` with `data.error='rate_limited'` +
      `retry_after_s >= 1`. The rate-limited call does **not** write an
      audit row and does **not** invoke the push service.
- [ ] Event loop stays responsive during an FCM send (wrapped via
      `run_in_threadpool`); no 504s from slow admin calls blocking user
      requests.

## Smoke-level async correctness

- [ ] None of the admin endpoints hit the sync pool. Verify via
      CloudWatch: no `sqlalchemy.engine` rows with `service=api` for
      `/v1/admin/*` paths — all go through the async engine.
- [ ] `route_paint` p95 for admin pages in `client_latencies` does **not
      regress** against the pre-aam-20 baseline (per epic AC #9).
