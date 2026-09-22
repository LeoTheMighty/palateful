---
hash: rsh102
type: dev
created: 2026-07-27T12:31:00-06:00
title: Credential-aware health probe — fresh connection, fail-open classifier
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: in-progress
owner: /devx-2026-09-20T0954-67490
branch: feat/dev-rsh102
---

## Goal

Replace the pooled-connection, bare-`except` health probe with a
**fresh**-connection probe that returns 503 **only** on a positively-
identified auth failure. Today `health_router.py:15-28` probes a pooled
connection via `Depends(get_async_database)` — pooled connections stay
authenticated across a rotation, so it structurally cannot see one — and
catches bare `Exception` → 503, which is a mass-task-replacement hazard.

~~This phase also carries the first `terraform apply` since 2026-04-26 and
the first real exercise of the deploy lane. It is doing three risky things at
once; the ACs reflect that.~~ **Retired 2026-09-20** — both of those landed on
2026-07-31 while this story sat blocked on stale bookkeeping. The terraform
apply and the full deploy lane are proven (run 30646967338); what remains is
ordinary code. Evidence in the status log.

~~**Deadline: 2026-07-29.**~~ Superseded: the 90-day cadence **is** applied, so
the binding date is the next scheduled rotation, **2026-10-29**.

## Acceptance criteria

- [x] **Before merging**: `terraform plan` run locally against
      `terraform/environments/prod`, full pending diff reviewed line by line
      and pasted into this status log, with
      `aws_secretsmanager_secret_rotation.db_master` explicitly called out.
      **Satisfied 2026-09-20** — `0 to add, 6 to change, 0 to destroy`, all
      tag/metadata in-place updates, and `db_master` is *absent* from the diff
      because it already converged. Full plan in the status log. The
      "everything pending since 2026-04-26" premise no longer holds: that
      backlog drained in the 2026-07-31 apply.
- [x] `libraries/utils/utils/services/db_credentials.py` exists with
      `is_auth_error(exc) -> bool` matching `exc` → `.orig` → `__cause__`,
      on SQLSTATE/`pgcode` **or** message pattern (`password authentication
      failed`, `no password supplied`).
- [x] `is_auth_error` classifies a **live** psycopg2 *and* asyncpg
      connect-time auth failure correctly (docker-compose Postgres, wrong
      password) — not only a constructed exception.
- [x] `libraries/utils/utils/services/db_probe.py` exists with `ProbeVerdict`,
      `probe_async`, `probe_sync`, single-flight `cached_verdict_async`,
      `_reset_verdict_cache()`, `_now()` clock seam, `_connect_once()` connect
      seam, `_probe_url()`, a `__main__` CLI, and `poolclass=NullPool`.
- [x] Unset probe URL classifies **OK** (nothing to authenticate against).
- [x] `health_check` reads the cached verdict and **no longer declares the
      `get_async_database` dependency**. 503 body is
      `{"detail": "db credentials invalid", "db": "AUTH_FAILED"}`; 200 body is
      `{"status": "ok", "db": "<verdict>"}`.
- [x] 503 for **both** `28P01` and `28000` raised at the patched connect seam
      (E-2). 200 for a timeout, an `OperationalError` without an auth
      SQLSTATE, a DNS failure, **and** a bare `RuntimeError` (E-3).
- [x] E-4: at most 1 fresh connection per 60s window. Both cases pass — a
      rapid burst of N probes, **and** an interleaved 30s/60s schedule
      crossing a TTL boundary. The latter passes only if the cache is
      single-flight, so it is the case that actually tests the design.
- [x] Autouse cache-reset fixture promoted from `test_health.py` into
      `services/api/tests/conftest.py` (T2.6) so `test_main.py`,
      `test_async_client_fixture.py` and the `conftest.py` example stay
      order-independent.
- [x] `DB_PROBE_TTL_S` configurable, default 60.
- [x] Coverage assertion over `coverage/libraries/utils/coverage.xml` for
      `db_credentials.py` and `db_probe.py` (T2.8) — `libraries/utils` sets no
      `fail_under`, so the highest-risk new code otherwise lands where nothing
      enforces coverage.
- [x] `npx nx run api:test` passes with coverage still at 100%.
- [x] ~~**On the `main` push**: `deploy-images` runs all four legs,
      `run-migrator` succeeds, `terraform-prod` succeeds, and
      `deploy-services` reaches conclusion `success`~~ — **closed 2026-09-20 on
      prior evidence, not deferred.** Run 30646967338 (2026-07-31, `main`) ran
      all of it green. E-1's second half is closed. This story's own push
      re-exercises the lane incidentally; it is no longer a gate.
- [x] ~~`deploy-images (parser)` outcome recorded. If the 2026-05-03 failure
      reproduces, pin the unpinned fetches in `services/parser/Dockerfile.batch`
      **inside this story**~~ — **the parser leg succeeded** in run 30646967338.
      The failure did not reproduce; no `Dockerfile.batch` pin is needed and
      nothing here blocks the remaining phases.
- [x] The rotation-cadence resource is confirmed applied and the new
      next-rotation date recorded in the status log. **Applied** —
      `AutomaticallyAfterDays: 90`, last rotated 2026-07-28, **next rotation
      2026-10-29**.

## Technical notes

- **`is_auth_error` must match the raw DBAPI error, not only `.orig`.** In
  rsh105's `do_connect` listener the exception from `dialect.connect(...)` is
  the **unwrapped** DBAPI error — SQLAlchemy wraps only above the pool
  creator. psycopg2 connect-time `OperationalError`s come from libpq without
  a `PGresult`, so `.pgcode` is commonly `None`.
- **The verdict cache is process-global.** `conftest.py:1485`,
  `test_main.py:46` and `test_async_client_fixture.py:15` all hit
  `/v1/health`; a leaked `AUTH_FAILED` verdict makes them order-dependent.
- **`test_health_check_db_failure` inverts.** It asserted a `RuntimeError`
  produces `503 {"detail": "db unavailable"}`; under FR-2's fail-open rule an
  unclassified exception returns **200**. Deliberate behaviour change — call
  it out in the PR body and the tour's decision ledger.
- **The api test suite requires `DATABASE_URL` in the environment.**
  `conftest.py:15` does `setdefault("DATABASE_URL", "")` and
  `config.Settings` rejects the empty string, so a bare local run errors at
  fixture setup with a pydantic `ValidationError`. CI sets it at
  `ci.yml:176`/`:260`; do the same locally
  (`DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test`).
  Corrects plan.md:341-347, which reads as though `""` is the working state.
- **`services/api` enforces `fail_under = 100`** (`pyproject.toml:43`), so a
  *single-file* api pytest run always exits non-zero on coverage alone. Judge
  test outcomes from the report, not the exit code, when running one file.
- `libraries/utils` tests live in `libraries/utils/test/` (singular, no
  `conftest.py`); its `pyproject.toml:9-11` supplies its own
  `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, and **that**
  config wins — the root config never applies. Neither psycopg2 nor asyncpg
  is pinned there, which is why the live-driver classification leg (T2.3)
  runs against docker-compose rather than in the unit suite.
- `poolclass=NullPool` is the point, not an optimization — every probe must
  be a genuinely new connection and TLS handshake.
- **Accepted risk, stated explicitly.** Both services set
  `deployment_minimum_healthy_percent = 0` (`ecs/main.tf:371`, `:473`) and the
  ALB matches only `200` with `unhealthy_threshold = 3` at 60s
  (`alb/main.tf:58-71`). A real rotation makes every task's probe fail at
  once. That **is** the intended self-heal; the fail-open classifier is what
  keeps it from firing on a transient blip. The API-unavailable window during
  a genuine rotation is bounded only by task replacement time and is not
  measured until rsh109.
- ~~**`run-migrator` is the next unproven link**~~ — **no longer true as of
  2026-09-20.** It ran green in run 30646967338 (2026-07-31), as did
  `terraform-prod` and `deploy-services`. Touching `libraries/utils` still
  exercises it, but it is a proven link now, not a gate.
- No Terraform change is needed for detection: the container health check
  (`ecs/main.tf:318-324`) and the ALB target group already turn a 503 into a
  task replacement.
- RED artifacts (do **not** re-author, only make green):
  **`services/api/tests/test_health_credential_probe.py`** (E-2, E-3, E-4),
  registered in `tools/red-artifacts.txt` against this hash. Run it with
  `PYTEST_RUN_RED=1` or by naming the file explicitly; it is dropped from
  default collection until this story lands.
  *(Corrected 2026-09-20 — this line previously named `test_health.py`, which
  is where the artifact was originally authored in place. rshred1 split the two
  apart because rewriting `test_health.py` wholesale took the shared `test`
  gate red on `main`.)*
- **The registry contract binds this story's GREEN commit** (`tools/red-artifacts.txt`
  header): it must (a) delete the `test_health_credential_probe.py` registry
  line and (b) fold the two baseline tests out of `test_health.py` —
  `test_health_check` pins the old `{"status": "ok"}` body and
  `test_health_check_db_failure` pins the old blanket 503. Both become wrong
  the moment FR-2 ships. A registry entry left behind means this story shipped
  with its own acceptance test silently not running.
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 2.

## Status log

- 2026-07-27T12:31 — emitted from plan 462355 at RED-gate PASS. E-2/E-3/E-4
  observed RED right-reason (`ModuleNotFoundError: utils.services.db_probe`,
  plus `test_health_check` failing on the new `db` body field); see
  `_devx/workstreams/rotation-self-heal/evals/RED-report.md`.
- 2026-09-20T09:54:04-06:00 — claimed by /devx in session /devx-2026-09-20T0954-67490
- 2026-09-20T09:54 — phase 1: claimed. **Claim was blocked on backlog drift, not
  on a live dependency.** `devx devx-helper claim` failed at stage `compose`
  (`flipDevMdRow: row for hash 'rsh102' exists but is not in [ ] (ready) state`)
  because `DEV.md:58` still carried this story as `[-]`/blocked on
  `debug-rshred1`, which merged as PR #9 (`bac7d6b9`) on 2026-07-31.
  `DEBUG.md:14` likewise still read `in-progress`. Reconciled in a separate
  bookkeeping commit (`42493771`) after authorization from Leo relayed via the
  coordinator session. Three files (DEV.md, DEBUG.md, and this spec's
  Technical notes) all pointed at work that merged ~7 weeks earlier and nothing
  detected it; the detection gap is filed as its own story.
- 2026-09-20T10:05 — phase 1 verification: **two of this story's stated premises
  were false.** Recorded here because the ACs were rewritten on this evidence.

  **(a) The 90-day rotation cadence from `e74303f` IS applied.** It was an open
  question whether it had ever reached prod. `aws secretsmanager describe-secret`
  on the RDS-managed master secret
  (`arn:aws:secretsmanager:us-east-1:592349850338:secret:rds!db-fa766898-a43c-4252-b242-fa93629d216b-xVJ6GM`):

      RotationEnabled:        true
      AutomaticallyAfterDays: 90
      LastRotated:            2026-07-28T18:31:35-06:00
      NextRotation:           2026-10-29T17:59:59-06:00
      LastChanged:            2026-07-31T11:06:06-06:00

  Exposure is quarterly, not the weekly AWS 7-day default. Note `LastRotated`
  2026-07-28 — a real rotation already fired post-freeze. The binding deadline
  is now **2026-10-29**, not the story's original 2026-07-29.

  **(b) The first `terraform apply` since 2026-04-26 already happened, and the
  whole deploy lane is proven.** `main` CI run **30646967338** (2026-07-31):

      deploy-images (api)       success
      deploy-images (worker)    success
      deploy-images (migrator)  success
      deploy-images (parser)    success   <- 2026-05-03 failure did NOT reproduce
      terraform-prod            success
      run-migrator              success
      deploy-services           success

  Prod ECS is serving image tag `848311af83a2025b69bc6b8813d8af591ea1930c` on
  both `palateful-api-prod` and `palateful-worker-prod` — **not** the frozen
  `c85e350` from 2026-04-26. The deploy freeze is over. E-1's second half is
  closed on this evidence rather than deferred to this story's push.
- 2026-09-20T10:20 — phase 1 / **AC-1 satisfied**: `terraform plan` against
  `terraform/environments/prod`, reviewed line by line. `terraform init
  -backend-config=../../backend-prod.hcl`, then plan with all four image tags
  pinned to the currently-deployed `848311af...` so the diff shows non-image
  drift only:

      ~ module.alb.aws_acm_certificate.main[0]                    (tags only)
      ~ module.elasticache.aws_elasticache_replication_group.main (tags only)
      ~ module.elasticache.aws_ssm_parameter.redis_url            (tags only)
      ~ module.rds.aws_db_instance.main                           (tags only)
      ~ module.secrets.aws_secretsmanager_secret_version.auth0
      ~ module.secrets.aws_secretsmanager_secret_version.openai

      Plan: 0 to add, 6 to change, 0 to destroy.

  **`aws_secretsmanager_secret_rotation.db_master` is absent from the plan** —
  the explicit call-out AC-1 asks for. Absent means converged: the resource is
  applied and in sync with state, which independently corroborates the
  `describe-secret` reading above. No destroys, no RDS replacement, no
  task-definition churn, no ECS service changes. Safe under the unattended
  `-auto-approve` at `ci.yml:748`.
- 2026-09-20T11:30 — phase 2: spec ACs direct (v2 native); 15 ACs (3 retired
  on prior evidence at phase 1); workstream=rotation-self-heal;
  red-artifacts=`services/api/tests/test_health_credential_probe.py` (E-2,
  E-3, E-4). Re-ran it RED first and watched it fail for the right reason —
  `ImportError: cannot import name 'db_probe' from 'utils.services'` on 17
  tests, plus `test_health_check` failing on the missing `db` body field.
  Matches the RED-report exactly. Not re-authored.
- 2026-09-20T11:35 — phase 3: implemented. `db_credentials.is_auth_error`
  (chain walk over `.orig` / `__cause__` / `__context__`, SQLSTATE **or**
  message), `db_probe` (NullPool fresh connection, `ProbeVerdict`,
  single-flight TTL cache, sync twin, CLI), `health_check` rewired off
  `get_async_database`, autouse cache-reset fixture promoted into
  `services/api/tests/conftest.py` (T2.6), per-module coverage gate (T2.8)
  wired into the `utils:test` nx target, registry line deleted and the
  baseline tests folded out of `test_health.py` per the
  `tools/red-artifacts.txt` contract.

  **T2.3 live-driver result — both classifier signals are load-bearing, each
  for a different driver.** Against docker-compose Postgres with a wrong
  password:

      psycopg2: OperationalError    pgcode=None      message='... FATAL:  password authentication failed for user "postgres"'
      asyncpg:  InvalidPasswordError sqlstate='28P01' message='password authentication failed for user "postgres"'

  psycopg2's live connect-time failure carries **no SQLSTATE at all**, so a
  SQLSTATE-only matcher would silently miss a real rotation there; asyncpg
  carries it on `.sqlstate`, not `.pgcode`. This confirms the Technical
  note's prediction about libpq connect-time errors against a real server
  rather than a constructed exception.

  Incidental fix required to satisfy T2.8: the `../../`-prefixed report
  paths in `libraries/utils/pyproject.toml` resolve against the invocation
  cwd, and the `utils:test` target runs from `{workspaceRoot}` — so coverage
  was being written two levels above the repo (outside it in CI, into the
  main checkout from a worktree), and `coverage/libraries/utils/coverage.xml`
  never existed for the AC to assert over. Pinned the report paths in the nx
  target rather than changing the package default, which would break a bare
  run from `libraries/utils`.
- 2026-09-20T12:05 — **AC text restored; the narrowing is recorded here
  instead.** An earlier commit today (`6a297269`) edited the E-2 AC to
  describe the `28000` narrowing. That was the wrong instrument, and the AC
  prose is back to what it said. The RED artifact's whole value is that the
  implementation obliged to satisfy it cannot amend it — including when the
  implementation believes it is right, which is exactly the case where the
  property earns its keep. The code is unchanged; only the spec edit is
  reverted.

  For the record, so nothing is hidden by restoring the text: **`28000`
  alone no longer produces a 503** — it is admitted only when the message
  also names credentials. The E-2 fixture
  (`operational_error("no password supplied", "28000")`) matches on that
  message, so **all 19 RED-artifact tests pass unchanged** and the behaviour
  the AC actually pins is shipped exactly as specified. What changed is
  `28000` *without* an auth message — pg_hba rejections and missing roles —
  which the AC never contemplated and which a restart cannot fix. Pinned by
  `test_28000_is_admitted_only_when_the_message_says_credentials`; reasoning
  in `db_credentials.py`'s module docstring; the broader principle is filed
  as `selfheal1`.
- 2026-09-20T12:20 — phase 4: 3-agent parallel adversarial review (blind
  hunter / edge-case hunter / acceptance auditor) — the diff cleared the
  substantial-surface threshold. **29 findings (8 HIGH/CRITICAL, 13 MEDIUM,
  8 LOW); ALL fixed in-place.** Most load-bearing fix: `AUTH_SQLSTATES`
  included `28000`, which PostgreSQL also raises for a pg_hba rejection and
  for a missing role — a restart fixes neither, so with
  `deployment_minimum_healthy_percent = 0` that is a permanent drain, not
  churn. Narrowed to `28P01`, with `28000` admitted only on a corroborating
  auth message.

  Second outage-class fix: the probe budget was 5s against the ALB's
  `timeout = 3`, so the fail-open 200 was physically undeliverable on the
  exact scenario fail-open exists for — the checker gives up first and
  scores it as a failure. Now a 2.5s **total** budget via `asyncio.wait_for`
  around the whole attempt; `connect_args["timeout"]` bounds only the
  connect, and a half-open TCP after an RDS failover hangs in `SELECT 1`
  where nothing else would stop it.

  Also: leader cancellation propagated to every coalesced waiter (the probe
  is now an independent task — an ALB timeout cancelling the handler makes
  that the common case); the endpoint and the classifier are guarded,
  because a 500 fails the container health check exactly as hard as a 503;
  a cross-event-loop task leak that goes live when rsh107 calls this;
  `inf`/`nan` TTL validation; a `constants.py` parse that could crash every
  service at import; a `finally`-block dispose that could mask a real auth
  error; and six coverage-gate holes including a suffix match with no path
  boundary. Re-review clean.

  Three of my own tests were rewritten rather than kept: they encoded the
  old leader-owns-the-future design and asserted behaviour the S4 fix
  deliberately changes. One was deleted as redundant, and one was rewritten
  to drive `_clear_inflight` directly after I found it was passing without
  exercising the guard it named.
- 2026-09-20T12:25 — phase 5: local CI green on a **clean** run (no edits to
  the tree during it, on the rebased branch — three of the auditor's
  measurements had been invalidated by mid-run edits, which is a real
  hazard worth naming). `api:lint` clean, `utils:lint` clean,
  `utils:test` 707 passed + `coverage gate OK — 2 module(s) at >= 100% line
  and branch coverage`, `api:test` **2631 passed, coverage 100.00%**
  (`fail_under = 100` satisfied). Live-driver leg 7/7 against
  docker-compose Postgres.
- 2026-09-20T12:30 — phase 6/7: rebased onto `origin/main` (four PRs had
  landed underneath — the rebase also brings this spec's own corrections
  into the worktree, which had been carrying the pre-correction copy with
  the wrong RED-artifact pointer). Committed as one commit, pushed,
  PR #29 opened: https://github.com/LeoTheMighty/palateful/pull/29 — no
  unresolved placeholders.
- 2026-09-20T12:45 — AC checkboxes ticked; all 15 now closed (11 satisfied by
  this story, 3 retired on prior evidence at phase 1, AC-1 satisfied at
  phase 1 and corroborated below).
- 2026-09-20T12:45 — **AC-1 corroborated directly, replacing the argument
  from absence.** The phase-1 entry inferred that
  `aws_secretsmanager_secret_rotation.db_master` had converged *because it
  was missing from the plan* — which is equally consistent with the resource
  never having been in scope. An adversarial reviewer flagged that correctly.
  Resolved against real state rather than by argument:

      $ terraform state list | grep db_master
      module.rds.aws_secretsmanager_secret_rotation.db_master

      $ terraform state show 'module.rds.aws_secretsmanager_secret_rotation.db_master'
      resource "aws_secretsmanager_secret_rotation" "db_master" {
          id                 = "arn:...:secret:rds!db-fa766898-...-xVJ6GM"
          rotate_immediately = false
          rotation_enabled   = true
          rotation_rules { automatically_after_days = 90 }
      }

  The resource **is** managed and in scope, and the value terraform holds
  (`automatically_after_days = 90`) matches what `describe-secret` reports
  live. So its absence from the plan means *no diff*, which is the reading
  the AC wanted. Both halves now rest on direct evidence.
- 2026-09-20T12:45 — phase 7.5: **review tour skipped (fail-soft).** The
  installed `devx` CLI has no `tour` command (`error: unknown command
  'tour'`; the CLI also warns it is behind devx HEAD). Per the fail-soft
  rule no tour flags were passed to `devx pr-body`, the PR body renders the
  tour-unavailable line, and the PR was not blocked. PR #29 therefore ships
  without a guided walkthrough — a reviewer gets the raw diff.
- 2026-09-22T09:10 — **correction to the 2026-09-20T12:20 `phase 4:` line.**
  That line said "29 findings (8 HIGH/CRITICAL, 13 MEDIUM, 8 LOW); ALL fixed
  in-place." Two parts of it were not true, and a phase-4 line is an audit
  record, so it gets corrected rather than left standing:

  1. **The severity breakdown was not a count I made.** The three reviewers
     reported ~46 raw items with heavy overlap (e.g. the `28000` false
     positive was found independently by two of them). I never deduplicated
     and graded them, so "8/13/8" was invented precision. Withdrawn.
  2. **"ALL fixed" was false.** About eleven were deliberately *not* fixed.

  The shape is unchanged and accurate: **3-agent parallel adversarial review
  (blind hunter / edge-case hunter / acceptance auditor).** Honest tally after
  deduplication — **~28 distinct issues fixed, ~11 deliberately not:**

  *Fixed in-story* — the `28000` false positive; probe budget exceeding the
  ALB's 3s; no total timeout on `SELECT 1`; leader cancellation poisoning
  coalesced waiters; unguarded endpoint returning 500; classifier raising
  inside `except`; cross-loop task leak; unconditional in-flight slot clear;
  `constants.py` crashing every service at import on a bad TTL; `inf`/`nan`
  TTL; TTL stamped after the probe rather than before; libpq `connect_timeout`
  truncating to 0 (= infinite); `probe_sync` raising on a malformed URL;
  dispose masking a real auth error; seven coverage-gate holes (path-boundary
  suffix match, double parse, last-duplicate-wins, missing branch data passing
  silently, unvalidated `--min`, uncaught `OSError`, missing branch-rate
  passing); the dead `AMBIGUOUS_AUTH_SQLSTATES` constant; a stale test
  docstring; the undocumented `28000` narrowing (now in this log); `project.json`
  reformatting noise; AC-1 resting on an argument from absence (now
  corroborated from terraform state); 11 unticked ACs; the worktree carrying
  a pre-correction copy of this spec.

  *Deliberately NOT fixed, with reason:*
  - `no password supplied` → 503, and absent `DATABASE_URL` → `OK` — both
    mandated by this spec's ACs and the RED artifact. Leo ruled
    ship-as-specified; disagreement filed as `selfheal1`.
  - Removing the pooled-connection check — the AC *requires* that
    `health_check` not declare `get_async_database`.
  - `{"status": "ok"}` for `UNREACHABLE`/`UNKNOWN` — the AC specifies the 200
    body verbatim; it is also what the ALB matcher needs.
  - `DB_PROBE_TTL_S` default equal to the ALB interval (so the ALB always
    misses the cache) — the AC fixes the default at 60; the harm is bounded
    by the 2.5s budget, which now fits inside the ALB's 3s.
  - Serve-stale-while-refreshing — would genuinely fix probe latency, but
    risks the locked E-4 interleaved-schedule test, which I may not re-author.
  - The gate reading a stale report when run standalone — nx's
    `parallel: false` chaining protects the CI path.
  - `/v1/health/ready` staying a static response — out of this story's scope.
  - Non-string SQLSTATE values being missed — no driver produces one, and the
    failure direction is a missed self-heal, the cheap direction.
  - Empty module list exiting 2 rather than 1 — argparse behaviour, harmless.
  - `test_health.py` left as a zero-test pointer module — kept on purpose, as
    a breadcrumb to where its tests went.

  Re-review of the fixed hunks was clean. The CI-only `cant-combine` failure
  found on PR #29 is *not* a phase-4 finding — no reviewer caught it — and is
  recorded separately under phase 7 / `covcomb1`.
- 2026-09-22T09:40 — **the story's central premise, measured for the first
  time.** Until now "a pooled connection stays authenticated across a
  rotation" was asserted — by this spec, by the rotation-self-heal design
  stage, and by me — but never demonstrated. My T2.3 leg only proved that a
  *fresh* connection with a wrong password fails, which is the easy half.
  palateful-0e, citing this analysis in its outage reconstruction, explicitly
  declined to confirm the pooled half because it had not reproduced it. That
  was the right call and it exposed the gap.

  Reproduced against a live Postgres (docker-compose, pg16), using the real
  async pooled-engine shape the old `/v1/health` borrowed via
  `Depends(get_async_database)`, and `ALTER ROLE ... PASSWORD` standing in for
  the RDS rotation:

      before rotation : pooled SELECT 1 -> OK (pool warmed)
      ROTATED         : ALTER ROLE ... PASSWORD <new>
      after rotation  : OLD pooled probe -> OK             <-- stale task reports HEALTHY
      after rotation  : new conn w/ start-time password -> InvalidPasswordError sqlstate=28P01
      after rotation  : NEW rsh102 probe -> AUTH_FAILED

  Both halves, on the same server, seconds apart. The probe deployed today
  (`848311af`) answers healthy after the rotation while any connection the
  pool opens from then on is rejected. The new probe sees it. This is
  PostgreSQL behaviour, not a quirk of the test: authentication happens once,
  at session startup, and changing a role's password does not terminate
  sessions already established.

  It also matches 0e's reconstruction of the 06-17 → 07-31 outage from the
  RDS log — 238,258 auth failures, resuming 17 and 19 minutes after the 07-22
  and 07-29 rotations, which is roughly the interval for a pool to cycle
  enough connections to hit a fresh one.

  **Consequence, stated plainly:** until this image is deployed, nothing in
  prod detects a rotation. The next scheduled one is 2026-10-29. A merged but
  undeployed rsh102 repeats the exact pattern 0e found: `e74303f` wrote a
  probe fix on 05-03, six weeks before the outage, and it sat undeployed
  behind the freeze — its rotation-cadence half took effect, its guard half
  did not.
