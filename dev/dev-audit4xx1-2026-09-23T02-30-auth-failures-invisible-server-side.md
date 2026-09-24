---
hash: audit4xx1
type: dev
created: 2026-09-23T02:30:00-06:00
title: Every authentication failure is invisible to the server-side recorder
from: dev/dev-envspell1-2026-09-22T21:30-environment-spelling-divergence.md
status: ready
owner: null
branch: null
---

## Goal

**No authentication failure has ever produced a server-side row.** Not one
expired token, not one rejected login, in the life of the deployment. The
recorder that exists to capture 4xx diagnostics cannot see them, by
construction.

**Measured 2026-09-22 against prod** (`bin/prod-script`, read-only):

| service | rows, all time | newest |
|---|---|---|
| `client` | 96 | 2026-09-22 19:09 |
| `worker` | 60 | 2026-09-22 03:00 |
| **`api`** | **1** | 2026-09-20 19:40 |

The single `api` row is `status=400 APIException path=/v1/recipe-books/…/import
msg='s3_key is required for image import'` — the writer works. It is simply
almost never reached.

**Why.** `_log_api_error_to_db` fires only from inside
`Endpoint.run` / `AsyncEndpoint.run`'s `except APIException` blocks
(`libraries/utils/utils/api/endpoint.py:172`, `:417`) — i.e. only for an
`APIException` raised **inside an endpoint body**. An `APIException` raised
in a *dependency* — `get_current_user`, so every expired or invalid token —
is caught instead by the app-level handler at `services/api/src/main.py:166`,
which returns a `JSONResponse` and **writes nothing**. That handler's own
comment explains it was added so these would stop being logged as 500s by the
error-tracking middleware. They were silenced as noise, and the audit writer
that shipped later never picked them back up.

**The cost, concretely.** Leo's "login failed" reports left no durable
server-side row — and the client-side mirror cannot cover the gap either.
Confirmed against `main` by palateful-79, who owns the client half
(`authrep1`): `ErrorReporter.reportPreAuth` passes `mirror: false` at all 8
pre-auth call sites, deliberately, because the mirror POSTs
`/v1/users/me/client-errors` behind `get_current_user_async` — a client with
no usable session cannot authenticate the report of having no usable session,
and `_postMirror` swallows the resulting 401.

So **`error_logs` receives nothing from the client for this class, by design,
and this story is the only way it ever will.** After both halves land, an auth
failure appears in Crashlytics (the client's view) and `error_logs` (the
server's); `audit_errors.py` will only ever see the latter.

The two views are not complementary here — for the auth class they are
**disjoint by construction**, because the failures that matter most are
precisely the ones that could not authenticate a report of themselves. A
reader who knows that can reason about what is missing; a reader who only
knows "there is another view" cannot. `service='client'` rows are only the
subset of failures that held a usable token at the moment they failed.

**This is not a docstring bug**, though there is one: the writer's docstring
says it exists because `APIException.code` carries "the real diagnostic
signal … which currently leave no durable row behind", and after it shipped,
dependency-raised APIExceptions still leave no durable row. Stated purpose and
actual coverage disagree. Fixing the coverage fixes the docstring; the reverse
is not true, and Leo's ruling (2026-09-22) is **record auth 4xx**, not narrow
the claim.

## Acceptance criteria

- [ ] A dependency-raised `APIException` leaves a row. Widen at
      `main.py:166`, which is the path that currently drops them.
- [ ] **A volume cap, with its behaviour stated.** Routine token expiry is
      high-frequency and must not turn `error_logs` into a firehose. Say what
      the cap is, what it drops when hit, and **how an operator can tell
      dropping happened** — a cap that silently discards is the same failure
      class this story is about.
      **Do not copy the client half's shape:** palateful-79 confirms
      `ErrorReporter` has no dedupe, no cooldown and no seen-set — that is an
      absence, not a design, tolerable there only because Crashlytics groups
      server-side and rows are free. `error_logs` is a table and this side
      pays per row. A **per-user-per-error-code cooldown** is the suggested
      shape, since the failure being guarded is one device retrying in a loop.
- [ ] The original intent of that handler is preserved: these must still not
      be logged as 500s by the error-tracking middleware.
- [ ] A test asserting a dependency-raised 401 produces a row. The current
      gap is invisible to every existing test, which is why it survived.
- [ ] Handle the client rows that **do** arrive for this class. 79's sink
      choice keys on **token validity at the moment of failure**
      (`AuthService._canMirrorReport`), not on call site — so a proactive
      refresh that fails inside the 5-minute buffer still holds a live token
      and *does* mirror. A small number of auth failures therefore already
      reach `error_logs` as `service='client'`. Do not assume every such row
      duplicates a server row, and do not build dedupe on that assumption.

## Out of scope, and stated so nobody reads this as "4xx are now recorded"

Widening the dependency path leaves three classes still invisible:

- FastAPI `RequestValidationError` (422) — never enters an endpoint body.
- 404s for unmatched routes.
- Any route not built on the `Endpoint` base class, **including the MCP
  surface**, which has its own auth middleware.

Each is a deliberate non-goal here, not an oversight.

## Duplicates: settled, do not build a winner-takes-all rule

Pre-auth events never reach `error_logs` from the client, so a failed login
produces exactly one row — this side's. Where both halves *can* describe one
event is a post-auth 5xx, which already happens today (client mirror + server
middleware) and has never caused a problem: the two rows carry different
vantage points, the client's knowing what the user was doing and the server's
knowing what the handler did. Keep that. `request_id` is the join key if
anyone ever needs to collapse them.

## Technical notes

- The measurement that found this was a *control*, not the check:
  a before/after count of `0 → 0` around an unrelated deploy is consistent
  with working and with broken alike, and looking at why the number was so
  low is what surfaced the gap. Worth remembering — the baseline earned its
  keep by being suspicious, not by being green.
- An active probe against prod (a deliberate 4xx on the import endpoint)
  exercises the **in-endpoint** path, so a green probe confirms the path that
  already works and says nothing about this gap.

## Status log
- 2026-09-23T02:30 — filed from envspell1's post-merge verification. 41
  directed that the auth-invisibility lead rather than the docstring
  mismatch; Leo ruled that auth 4xx should be recorded rather than the claim
  narrowed.
