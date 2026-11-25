---
hash: cldb01
type: debug
created: 2026-07-27T11:41:00-06:00
title: POST /v1/client-latencies returned 500 "password authentication failed for user palateful"
from: btri01
status: ready
owner: unassigned
branch: unassigned
---

## Goal
A live prod 500 surfaced while gathering error evidence for btri01. One
occurrence so far — corroborate or close as transient before spending fix
effort.

## Evidence
Row from prod `error_logs` (read via `bin/prod-script`, 2026-07-27T17:35Z):

```
id:            c281cbd8-8054-4c4a-8795-84ccac8ec3f9
created_at:    2026-07-27 16:49:00.426357+00:00
service:       client
error_type:    DioException
status_code:   500
method:        POST
path:          /v1/client-latencies
user_id:       34589ac4-f6ef-4adf-9b3b-299084cbc947   (admin)
error_message: POST /v1/client-latencies → 500 [code=1]:
               password authentication failed for user "palateful"
stack_trace:   {"area": "api", "extras": {"http.method": "POST",
               "http.path": "/v1/client-latencies", "server.error_code": 1}}
```

This is a client-mirrored row (`service='client'`), so the app's own
`/v1/client-errors` POST to the same host succeeded moments later — prod DB
writes were working. That points at a per-connection credential failure (a
freshly-opened pool connection picking up a stale/rotated secret) rather than a
global outage.

Context worth checking: the DB credential refactor landed 2026-04-15 (`ed09d34`)
with an old-secret deletion scheduled for 2026-05-15.

It is the **only** non-audit error row in prod `error_logs` in the last 30 days
(total table: 21 rows, 20 of them `service='worker'` daily audit rows).

## Acceptance criteria
- [ ] Determine whether the failure recurs (re-query `error_logs` for
      `error_message ILIKE '%password authentication failed%'`; check
      `bin/prod-logs` around 2026-07-27 16:49 UTC for the server-side traceback)
- [ ] If recurring: identify which credential/pool path is using the stale
      password and fix it
- [ ] If a one-off: close with the CloudWatch evidence recorded here

## Technical notes
- `bin/prod-logs` for the API task covering 16:49 UTC 2026-07-27 should carry
  the server-side stack; the client row only has the response detail.
- `services/api/src/middleware/error_tracking.py` is what would have written a
  matching `service='api'` row — its absence is itself a signal (the handler
  failed before/around the middleware's own DB write, or the API-side row was
  lost to the same DB failure).

## Status log
- 2026-07-27T11:41 — filed from btri01 legacy-BUGS triage evidence gathering
