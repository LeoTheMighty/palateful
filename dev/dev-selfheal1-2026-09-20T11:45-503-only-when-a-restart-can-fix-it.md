---
hash: selfheal1
type: dev
created: 2026-09-20T11:45:00-06:00
title: 503 only when a restart can fix it — two health-probe cases that drain instead of heal
from: dev/dev-rsh102-2026-07-27T12:31-credential-aware-health-probe.md
status: in-progress
owner: /devx-selfheal1-manual
branch: feat/dev-selfheal1
---

## Goal

Change two `/v1/health` verdicts that rsh102 shipped **as specified**, and
that I believe are wrong for the same reason a third case — which was
accepted and fixed inside rsh102 — was wrong.

This is a spec change, filed as a spec change. rsh102's RED artifact is
locked precisely so an implementation cannot move the goalposts mid-story,
and that property is worth more than getting these two right one story
earlier. So the code today matches the spec, and the disagreement lives here.

## The principle these three cases share

A 503 from `/v1/health` is not a report. It is an **instruction to destroy
and recreate the task**: the ALB deregisters the target and the ECS container
health check kills the container. That instruction is only correct when a
restart can actually change the outcome.

An RDS-managed secret rotation is the case where it can — the password was
resolved into the task environment at task start, so a replacement task
resolves the new one and recovers. That is the whole self-heal.

When a restart **cannot** change the outcome, the same 503 becomes a loop:
the replacement re-reads the same configuration, fails identically, and 503s
again. Both services set `deployment_minimum_healthy_percent = 0`
(`terraform/modules/ecs/main.tf:371`, `:473`), so there is no floor. Every
task fails the probe on the same tick, the service drains to zero, and every
replacement drains again. That is not churn — it is a permanent outage,
manufactured out of a configuration error, by the mechanism installed to
prevent outages.

**The strongest evidence that this principle is right is that it has already
been accepted once.** rsh102's AC said "503 for both `28P01` and `28000`". I
narrowed `28000` to require a corroborating auth message, because PostgreSQL
also raises `28000` for a pg_hba rejection and for a missing role, and a
restart fixes neither. That narrowing was reviewed and landed inside rsh102
(see its status log, 2026-09-20). The two cases below fail the identical
test and were held only because the RED artifact pins them.

## Measured evidence: the two drivers disagree about what they report

Taken against a live Postgres with a deliberately wrong password
(`libraries/utils/test/test_db_credentials_live_drivers.py`, rsh102 T2.3):

    psycopg2: OperationalError     pgcode=None       message='... FATAL:  password authentication failed for user "postgres"'
    asyncpg:  InvalidPasswordError sqlstate='28P01'  message='password authentication failed for user "postgres"'

Three things follow, and they matter for both cases below.

**The SQLSTATE is not reliably present.** psycopg2's real connect-time
rejection carries **no SQLSTATE at all** — libpq raises it without a
`PGresult`. A classifier keyed on SQLSTATE alone silently misses a genuine
rotation on the sync path. That is a *missed* self-heal: the probe says
`UNREACHABLE`, the task is never replaced, and the six-day-outage shape
returns.

**The attribute differs.** asyncpg exposes `.sqlstate`; psycopg2 exposes
`.pgcode`. Reading one misses the other.

**Therefore the message is the load-bearing signal**, and it is the only one
available on the driver the sync probe (and rsh107's worker health check)
uses. That cuts directly against admitting `no password supplied` as an auth
message: the message channel is precisely the one carrying the most weight,
so what is allowed into it deserves the most scrutiny — and
`no password supplied` describes the *client* having nothing to send, not
the server rejecting anything. It is the weakest possible reason to destroy
a task, riding on the strongest available signal.

This measurement is a better argument than the reasoning it replaces,
because it is a fact about the drivers rather than an inference about
PostgreSQL's error taxonomy.

## Case 1 — `"no password supplied"` → 503

**Status today:** `db_credentials.AUTH_MESSAGE_PATTERNS` includes
`no password supplied`, so it classifies as `AUTH_FAILED` → 503. Mandated by
rsh102's AC and by the E-2 fixture in
`services/api/tests/test_health_credential_probe.py`.

**The objection.** libpq emits `fe_sendauth: no password supplied` when the
*client* had no password to send — an unset or empty `DB_PASSWORD`, or a
`DATABASE_URL` with no password component. That is a deployment
configuration error, not a rotated credential. A replacement task reads the
same empty value from the same task definition and fails the same way. This
is the pg_hba case exactly, wearing a different message: indistinguishable at
the probe, identical in consequence, and already rejected once on that basis.

**Proposed change.** Drop `no password supplied` from the auth-message
patterns; let it classify `UNREACHABLE`, log at `error`, and alarm. Keep
`password authentication failed`, which is the signal that the server
evaluated a credential and rejected it — the only phrasing that actually
distinguishes "wrong password" from "no password".

**Cost of being wrong in this direction:** an operator who genuinely unsets
`DB_PASSWORD` gets a loud alarm and a stable, failing service instead of a
drained one. That is strictly the better failure.

## Case 2 — absent `DATABASE_URL` → verdict `OK`

**This case is genuinely weaker than Case 1 and deserves to be argued
separately, not bundled with it.** A reviewer who rejects it should not be
able to take Case 1 down with it.

**Status today:** `db_probe._connect_once` returns early when `_probe_url()`
is falsy, so `probe_async` yields `OK` and the endpoint answers
`200 {"status": "ok", "db": "OK"}`. Mandated by rsh102's AC ("Unset probe URL
classifies OK") and asserted by
`test_unset_database_url_is_ok_not_a_failure`.

**Why the current behaviour is defensible, stated fairly.** `OK` here is not
an oversight. `utils.constants.ASYNC_DATABASE_URL` is `None` wherever the DB
environment is absent, and `database.py` already treats that as a legitimate
state rather than an error. An absent URL is a *configuration* condition, not
a *credential* one, and this endpoint's contract is credential validity — so
reporting "no credential problem" is arguably literally true. It also keeps
the endpoint usable in environments that have no database at all, which is
what `test_main.py` and `test_async_client_fixture.py` depend on.

**Why I still think it is wrong, on its own terms.** The objection is not
that `OK` is a lie about credentials. It is that the *task* is not okay, and
`/v1/health` is the only thing ECS asks. A production task with no
`DATABASE_URL` reports healthy forever while every real request 500s — the
precise "stale task stays HEALTHY while every request 5xx's" failure that
this workstream exists to eliminate, reintroduced through a different door.
Note this is reachable without anyone deleting a variable:
`constants._build_database_url()` requires **all four** of `DB_HOST`,
`DB_USERNAME`, `DB_PASSWORD`, `DB_NAME` and otherwise falls through to
`DATABASE_URL`, which prod does not set — so an empty injected `DB_PASSWORD`
yields `None`, not an error.

**Proposed change, deliberately narrow.** Keep `OK` when a database is not
expected; return a distinct non-`OK`, still-200 verdict (`NOT_CONFIGURED`)
when one is. "Expected" should key on an explicit signal — `ENVIRONMENT` not
being `test`, or a dedicated `DB_REQUIRED` flag — never on guessing. Still
fails open, so it cannot drain a service; it just stops asserting health that
was never checked. If even that is rejected, the fallback is to leave the
verdict alone and alarm on it, which captures most of the value.

## Acceptance criteria

- [ ] Case 1: `no password supplied` no longer yields `AUTH_FAILED`.
      Classifies `UNREACHABLE`, logs at `error`, alarms.
- [ ] rsh102's E-2 fixture in `test_health_credential_probe.py` is updated in
      the same commit — it is the thing that pins the current behaviour, and
      leaving it would make this story fail its own suite. Update it
      deliberately, with the reasoning in the diff; do not delete the case.
- [ ] Case 2: a distinct verdict for "a database was expected and none is
      configured", still 200, keyed on an explicit signal rather than a guess.
- [ ] `test_main.py` and `test_async_client_fixture.py` still pass unchanged
      — they hit `/v1/health` with no database and must keep working.
- [ ] A test per case asserting the *non*-replacement outcome, named for the
      condition rather than the mechanism.
- [ ] The fail-open verdicts (`UNREACHABLE`, `UNKNOWN`, `NOT_CONFIGURED`)
      alarm somewhere a human sees. Fail-open means nothing else pages, so
      without this the design trades a six-day outage for a silent one — an
      adversarial reviewer raised this against rsh102 and it is out of scope
      there, but it is the precondition that makes both changes above safe.

## Technical notes

- Do not widen `AUTH_SQLSTATES`. `28P01` alone is correct and the reasoning
  is in `db_credentials.py`'s module docstring.
- The three cases are one principle; if a reviewer accepts the pg_hba
  reasoning already shipped in rsh102 and rejects Case 1, ask what
  distinguishes them, because I do not think anything does.
- Case 2 is separable. Landing Case 1 alone is a real improvement.
- Related: rsh107 (worker health check) consumes `probe_sync` and will
  inherit whatever these verdicts become — worth landing before it.

## Status log

- 2026-09-20T11:45 — filed from rsh102. Leo's ruling was ship-as-specified
  and file the disagreement as a spec change rather than route around a
  locked RED artifact in the implementation; this is that filing. The third
  case (`28000` without an auth message) was accepted and landed inside
  rsh102 under the same reasoning, which is the strongest argument these two
  deserve the same treatment. Case 2's asymmetry is argued in its own section
  at Leo's request rather than bundled with Case 1.
- 2026-09-22T11:24 — claimed by /devx (hand claim: devx-helper claim pushes to main, which the coordinator has frozen; claim commit held locally, unpushed). Worktree .worktrees/dev-selfheal1 on feat/dev-selfheal1 off origin/main faf35fa1.
