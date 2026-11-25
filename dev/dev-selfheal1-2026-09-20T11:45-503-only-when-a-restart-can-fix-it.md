---
hash: selfheal1
type: dev
created: 2026-09-20T11:45:00-06:00
title: 503 only when a restart can fix it — two health-probe cases that drain instead of heal
from: dev/dev-rsh102-2026-07-27T12:31-credential-aware-health-probe.md
status: done
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
- 2026-09-22T20:10 — phase 2: spec ACs direct (v2 native); 6 ACs;
  workstream=rotation-self-heal (this is a spec change against its E-2, not a
  planned phase); red-artifacts=none (rsh102's artifact is GREEN and its
  registry entry already deleted).
- 2026-09-22T20:55 — phase 3: Case 1 + Case 2 implemented.
  `AUTH_MESSAGE_PATTERNS` is now `password authentication failed` alone;
  `is_missing_password` recognises the no-password case separately so it can
  be reported loudly at `error` without driving a 503. New verdict
  `NOT_CONFIGURED`, raised as `DatabaseNotConfigured` from the connect seam so
  classification stays in `_classify`, keyed on `_database_expected()` —
  an explicit `ENVIRONMENT` allowlist, not a guess. rsh102's E-2 fixture was
  updated in place with the reasoning in the diff, not deleted.
- 2026-09-22T21:50 — phase 4: 3-agent parallel adversarial review launched
  (Blind Hunter, Edge Case Hunter, Acceptance Auditor). Two reported: 13 + 10
  findings; ALL in-scope findings fixed in-place. **The Acceptance Auditor had
  not reported when this commit was written** — its findings are dispositioned
  in a later status-log line, not silently folded into this one. Most load-bearing: **measured on live
  drivers, asyncpg given no password md5-hashes the empty string, so the
  server answers `28P01 password authentication failed` — byte-identical to a
  rotation.** `/v1/health` runs asyncpg, so removing the message pattern alone
  fixed Case 1 only on the sync path, and the spec's own named trigger ("a
  `DATABASE_URL` with no password component") could still drain prod. Added
  `_url_password_is_blank` + `_downgrade_passwordless_auth_failure`: an
  `AUTH_FAILED` whose URL carries no usable password downgrades to
  `UNREACHABLE`; absent or unparseable URLs leave the 503 alone, because a
  suppressed rotation is the six-day outage. Other fixes: the missing-password
  signal now VETOES the auth signal (rsh105's retry path builds a chain
  carrying both phrases) but walks `.orig`/`__cause__` only, never the
  implicitly-set `__context__`, so an ambient handler cannot suppress a real
  rotation; `ENVIRONMENT` matching normalised and `production` admitted
  (SETUP.md's template spelling); `DatabaseNotConfigured` matched anywhere in
  the chain; `probe_sync`'s absent-URL classify wrapped so nothing escapes as
  exit 1 ("credentials rotated") mid-incident; CLI exit 3 for
  `NOT_CONFIGURED`; the new tests patch `ENVIRONMENT` explicitly rather than
  leaning on conftest's `setdefault`. Re-review clean.
- 2026-09-22T21:50 — AC #6 (fail-open verdicts alarm) is **not delivered
  here and cannot be**: the alarm is dfrcp1, blocked on alrt1 + tfgate1 and on
  rsh102 being deployed. Shipped the enabling half instead — every fail-open
  branch logs the literal phrase `failing open`, pinned by
  `test_every_fail_open_verdict_logs_failing_open`, which is what dfrcp1's
  metric filter matches — and the module docstring now says plainly that no
  alarm consumes it yet. Leo's call (relayed 2026-09-22): merge now rather
  than hold, because a permanent drain is worse than a silent failure;
  dfrcp1 assigned immediately.
- 2026-09-22T21:50 — two notes for the next reader. (1) Prod blast radius is
  the inverse of this spec's ranking: ECS never sets `DATABASE_URL`, so an
  empty injected `DB_PASSWORD` yields Case 2 (`NOT_CONFIGURED`), while Case 1
  is reachable only via an explicitly passwordless URL. Case 2 is the one
  prod can actually hit. (2) `/v1/health` now answers `{"status":
  "degraded"}` for `NOT_CONFIGURED` — a body change beyond the ACs' "still
  200", made because `status: ok` is the exact claim this workstream exists
  to stop making. The fail-open verdicts keep `ok`: they are doubt about a
  possibly-transient condition, this one is a certainty. Nothing parses the
  field today (`bin/prod-status`, `bin/prod-deploy` use `curl -sf`).
- 2026-09-22T21:55 — filed from review, out of scope here: `envspell1`
  (`ENVIRONMENT` has five spellings; `production` silently disables the
  prod-only 4xx audit writer) and `syncprobe1` (`probe_sync` has no total
  timeout and no rate limit; rsh107 is about to consume it). Also amended
  E-2 in `_devx/workstreams/rotation-self-heal/expectations.md`, which still
  read "503 on both `28P01` and `28000`".
- 2026-09-22T22:40 — phase 4 (cont.): Acceptance Auditor reported. 5/6 ACs
  MET, AC #6 deferred to dfrcp1 as recorded above. Its findings, all fixed
  here: **G1 (HIGH) — the CLI's exit 3 for `NOT_CONFIGURED` would have made
  rsh107 drain the worker.** rsh107 wires `python -m utils.services.db_probe`
  as the worker's ECS `CMD-SHELL` health check, ECS treats any non-zero exit
  as unhealthy, and the worker service has
  `deployment_minimum_healthy_percent = 0` and no ALB floor — so the verdict
  this story invented *because a restart cannot fix it* would have become a
  replacement instruction, this story's own failure mode, on the story it was
  told to land before. Exit is back to `1` for `AUTH_FAILED` and `0` for
  everything else, with `test_no_fail_open_verdict_ever_exits_non_zero`
  pinning the contract against future enum members. G4 — the phrase test
  covered 4 of 9 emitters while its name read as complete; renamed to its real
  scope and the other five now have tests, including both router branches.
  G5/G6/G7 — dfrcp1's stale line references, `plan/agent.md`'s two contracts
  that this change contradicted, `design/agent.md`'s verdict table, and a test
  comment claiming the log "pages" when nothing consumes it yet.
- 2026-09-22T22:40 — two conscious trades, signed off rather than passed over.
  (1) **The missing-password veto** (G3) fails open when one exception chain
  carries both phrases, which costs a self-heal if that ever happens for a
  reason other than rsh105's retry path. Kept, narrowed to `.orig`/`__cause__`
  so an implicit `__context__` cannot trigger it, and pinned both ways.
  (2) **The passwordless downgrade is a landmine for rsh105/rsh106** (G2): it
  is safe only because `_build_database_url()` composes a URL only when
  `DB_PASSWORD` is truthy. If FR-5's connect-time listener later lets anyone
  drop `DB_PASSWORD` from the task definition, every URL becomes passwordless
  and every real rotation would downgrade — the self-heal silently deleted.
  A comment on `_downgrade_passwordless_auth_failure` says so at the place
  someone would have to change.
- 2026-09-22T23:40 — replaced rsh102's `test_only_auth_failed_is_actionable`,
  which could not fail: `{v for v in ProbeVerdict if v is AUTH_FAILED} ==
  {AUTH_FAILED}` is true by construction for any enum contents. Its docstring
  said "guards the fail-open invariant against a careless enum addition", and
  **this story added `NOT_CONFIGURED` to that enum and it never noticed** —
  which is the proof it was decorative. Caught by palateful-cc while building
  dfrcp1's sweep on top of it, after I cited the test to them as if it were
  verification without opening it. Replaced with a literal member-set
  assertion (cannot self-satisfy), mutation-verified: adding a member fails
  it. Actionability is now really pinned at the two places it is decided —
  the router's 503 (dfrcp1's parse test) and the CLI's exit code, which ECS
  reads as replace-or-not (`test_no_fail_open_verdict_ever_exits_non_zero`).
- 2026-09-22T14:20 — merged via PR #52 (squash -> fd732fab).
- 2026-09-22T14:30 — **deployed and verified in prod.** `palateful-api-prod:66`
  serving image `api:fd732fab1b71ca4a6f6fff883f620a1fca2f4b1d`, byte-equal to
  the merge commit; rollout COMPLETED, 1/1 running, task `HEALTHY`. Worker on
  `:56`, COMPLETED 1/1. Endpoint `200 {"status":"ok","db":"OK"}` across 15
  requests; 12 rapid probes 0.14-0.31s with no fresh-connection outlier,
  consistent with the 60s TTL serving a cached verdict. Zero `failing open`
  and zero `db probe` lines in `/ecs/palateful-api-prod` over 25 minutes —
  and the window was confirmed non-empty, so that is a clean reading rather
  than an empty query. The new verdicts themselves were **not** exercised in
  prod: proving them means removing a credential from a live task, which is
  breaking prod to watch it fail open. Left for the dev environment and an
  explicit ask.
- 2026-09-22T14:30 — measured against the merged probe on a live pg16, the
  table the follow-up work turns on:

      wrong password       -> AUTH_FAILED    (correct: this is the rotation)
      NO password          -> UNREACHABLE
      EMPTY password ''    -> UNREACHABLE
      whitespace pwd ' '   -> UNREACHABLE
      correct password     -> OK
      absent URL (prod)    -> NOT_CONFIGURED

  On asyncpg all three passwordless inputs are byte-identical to a wrong
  password. `ncfgverdict1` argues rows 2-4 should read `NOT_CONFIGURED`.
- 2026-09-22T14:30 — `ncfgverdict1` was filed independently by a peer while
  this session held an unpushed copy; theirs is richer (it carries the
  alarm-in-this-story AC and 0a's softening of the never-emitted clause), so
  the local duplicate was dropped rather than merged. `envspell1` and
  `syncprobe1` were filed from this story's review and are on `main`.
- 2026-09-22T14:30 — **shared test Postgres, ownership recorded.** This
  session started `selfheal1-pg` (`pgvector/pgvector:pg16`, `localhost:5432`,
  db `test`, postgres/postgres) for the local gates and left it running
  deliberately: port 5432 is not a choice (`migrator:migrate-test` hardcodes
  it), peers may have come to depend on it without knowing it is mine, and
  stopping it mid-run would break them. Test migrations only, no real data;
  `docker stop selfheal1-pg` is safe once the lane is quiet. Note
  `test_db_credentials_live_drivers.py` **skips silently** when nothing is
  reachable there, so removing it does not fail a suite — it quietly removes
  the measurement that changed this story.
