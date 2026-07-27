# Plan-stage critique — Rotation Self Heal

- **Date**: 2026-07-27
- **Stage**: Plan
- **Lenses**: pm, architect, dev, qa (`engine.critique.lenses`)
- **Why it ran**: `thoroughness: send-it` skips the critique unless the plan
  touches ≥ `engine.critique.min_surfaces` (2) config/stack layers. This plan
  touches five — Flutter app, Python API, `libraries/utils`, Terraform, and
  GitHub Actions — so the critique was mandatory, not optional.
- **Grounding rule applied**: every lens claim citing a file:line was
  grep/Read-verified against the repo before acceptance. All HIGH findings
  below were additionally re-verified by the skill author before the plan was
  rewritten.

## Accepted — HIGH

1. **Phase 1's exit criterion was structurally unreachable.** *(pm, dev,
   architect — independent concordance)* `detect-changes` emits
   `services_to_build=[]` unless api/worker/migrator/parser is nx-affected
   (`ci.yml:592-604`); `deploy-images` gates on it (`:641-643`);
   `terraform-prod` needs `deploy-images.result == 'success'` (`:703-705`);
   `deploy-services` additionally needs `api == 'true' || worker == 'true'`
   (`:845-851`). An `app/`-only commit reaches **none** of them, so
   "`deploy-services` reaches `success`" could never have passed in Phase 1.
   → E-1 now spans phases 1–2; Phase 1's exit is `flutter-test` green +
   `deploy-web` success + `detect-changes` not skipped. Explicitly **not**
   fixed by forcing a service to be affected — that would ship the un-fixed
   `health_router.py` mass-replacement hazard ahead of Phase 2.

2. **The first `terraform apply` was attributed to the wrong phase.** *(pm,
   dev, architect)* `terraform-prod` runs `terraform apply -auto-approve`
   (`ci.yml:748`) with nothing consuming the plan output (`:739`), on every
   `main` push where a service is affected. Phase 2 touches `services/api`
   and `libraries/utils` → the 90-day cadence from `e74303f` lands **there**,
   not at Phase 4. The plan's single line-by-line review gate (old T4.5) fired
   two phases too late. → Review moved to Phase 2 as a blocking pre-merge task
   (T2.1); Phase 4's context corrected; the cadence change promoted out of a
   phase Context block into a top-level "Behavior changes shipped
   incidentally" section.

3. **Terraform-only phases never apply via CI.** *(architect)* Phases 4 and 7
   touch only `terraform/`, so `deploy-images` skips → `terraform-prod` skips
   → nothing applies. `.github/workflows/force-deploy.yml` exists for exactly
   this ("secret rotation, recover from a broken deploy") and the
   `ci.yml:698-701` comment names it. The plan had never mentioned it. →
   Explicit Force Deploy tasks added to Phases 4, 6 (enablement) and 7.

4. **The `archive` provider is declared and locked nowhere.** *(architect)*
   `terraform/environments/prod/main.tf:6-11` declares only `hashicorp/aws`;
   the lock file has one provider block. `data "archive_file"` would fail at
   `terraform init` (`ci.yml:734`). → T4.2 declares it and commits the
   regenerated lock.

5. **Phase 9 had no positive control.** *(qa)* Every engine sets
   `pool_recycle=3600` (`database.py:48`, `:96`, `:125`), and
   `rds/main.tf:113-116` documents that the pool masks the failure "for
   hours/days". A completely broken FR-5 would still show zero 5xx in an
   attended 30-minute watch — the same false-negative that produced the
   six-day outage. → Mandatory positive control (post-rotation
   `pg_stat_activity.backend_start` / in-task probe) plus an observation
   window ≥ `pool_recycle`.

6. **`.current()`'s `DB_PASSWORD` fallback silently poisons the retry.**
   *(qa)* On the retry path, a Secrets Manager failure returns the env-var
   password that just failed, making an SM outage indistinguishable from "no
   rotation occurred". `design.md:114-118` claimed this was "proven by E-6";
   no E-6 threshold composed the two. → Contract added: fallback legal on
   first resolution, distinguishable failure on the retry path, with a
   composed test case.

7. **Phase 7's `CMD-SHELL` probe could crash-loop the worker.** *(architect)*
   `python -m utils.services.db_probe` exits non-zero on *any* startup
   failure. `libraries/utils/pyproject.toml` declares neither psycopg2 nor
   asyncpg (only `services/worker/pyproject.toml:11,18` do), and
   `deployment_minimum_healthy_percent = 0` (`ecs/main.tf:473`) with no ALB
   makes that unbounded. → CLI contract: catch `BaseException` including
   import failure → exit 0; exit 1 only on classified `AUTH_FAILED`. Explicit
   fail-open-against-self-failure criterion added.

## Accepted — MED

8. **E-2/E-3/E-4's test seam was wrong.** *(qa, dev)* The plan said "mock at
   the probe layer", which tests an enum→status mapping, not the SQLSTATE
   thresholds the expectations state. Also `services/api/tests/conftest.py:15`
   sets `DATABASE_URL=""`, so no real connect exists in that suite. → Seam
   respecified as **the connection attempt**: patch connect to raise real
   `OperationalError`s carrying `28P01`/`28000`, so `is_auth_error` executes
   for real through the API test. Makes E-4 countable at the same seam. **No
   `devx revise` needed** — the `Verified by` paths in `expectations.md` are
   unchanged and now actually provable.

9. **`is_auth_error`'s matching strategy would miss the case it matters most
   for.** *(dev)* In `do_connect` the exception is the raw DBAPI error, never
   SQLAlchemy-wrapped; and psycopg2 connect-time `OperationalError`s often
   carry `pgcode = None`. → Contract widened: check `exc` → `.orig` →
   `__cause__`, match SQLSTATE **or** message pattern, verified against a live
   psycopg2/asyncpg failure rather than a constructed mock.

10. **`aws.py` is the wrong home for the Secrets Manager client.** *(architect,
    dev, qa)* `AWSService.__init__` (`aws.py:13-37`) builds its clients
    unconditionally with an S3-tuned `Config` (`signature_version="s3v4"`,
    `read_timeout=2.0`). Putting SM there violates E-6's "0 clients
    constructed" threshold outright. → T5.2 dropped; client constructed
    lazily inside `db_credentials.py` with its own `Config`.

11. **The T6.3 enumeration guard was mis-scoped.** *(architect, dev, qa)*
    Scoping to `libraries/` catches `libraries/test-helper/test_helper/conftest.py:29`
    and `async_db.py:52` — pytest fixtures that must never be registered — so
    it fails on day one. And `utils` / `agent` are separate nx projects, so a
    guard in `libraries/utils/test/` never runs on an agent-only edit, which
    is the exact miss it exists to catch. → Scope narrowed to
    `libraries/utils/utils/` + `libraries/agent/agent/`, test-helper excluded
    by name, guard required to run under both projects' test targets.

12. **"Five engine construction sites" was unqualified and incomplete.**
    *(architect, pm, qa)* Repo-wide there are 14; the five named are the
    correct **long-lived-process** set. The eight short-lived ones
    (`services/api/src/manage.py:72`, five `services/api/scripts/*`,
    `scripts/backfill_vibes.py`, `services/migrator/migrations/env.py`) were
    neither registered nor excluded. → Qualified as "long-lived-process", and
    the short-lived set named in "NOT doing" with the accepted cost stated:
    **an operator running those ops scripts during a rotation window hits the
    auth failure directly.**

13. **Phase 4's success criteria couldn't detect a non-matching event
    pattern.** *(qa)* An `ENABLED` rule with a wrong pattern is
    indistinguishable from a working one. The end-to-end proof existed only as
    a task, not a criterion. → Promoted: a published test event must produce a
    Lambda invocation and two `UpdateService` calls.

14. **G-2's detection-path number would never be produced.** *(qa, pm)* With
    FR-5 live, FR-2 never trips, so the ~4-minute worst case that Design
    flagged as having "little margin" stays unmeasured. → Phase 9 split into
    Leg A (`DB_PASSWORD_SECRET_ARN` unset — detection path) and Leg B (steady
    state).

15. **Verdict cache is process-global and three other tests hit `/v1/health`.**
    *(dev)* `test_main.py:46`, `test_async_client_fixture.py:15`,
    `conftest.py:1485`. → `_reset_verdict_cache()` seam + autouse fixture.

16. Also accepted: E-2's **503 body** was unspecified while the threshold
    requires it identify the failure (qa); the probe's **URL source and
    unset-URL verdict** were unstated (dev); **`run-migrator`** is a gating
    job that runs for the first time since 2026-04-26 whenever `libraries/utils`
    is touched (pm); the **`deployment_minimum_healthy_percent = 0` blast
    radius** needed stating as accepted risk (dev); **CAP-3 was never verified
    for the API** (pm) → T6.8; the **parser failure had no contingency** while
    being pre-declared out of scope (pm) → T2.10 + narrowed NOT-doing bullet;
    **G-1's deadline appeared nowhere** (pm) → "Deadline shape" section;
    the **Flutter date fuse** could re-light mid-workstream (pm) → T1.4 guard;
    **worker probe cross-process cache cost** ~2,880 SM calls/day (qa) → T7.7;
    **worker image must predate the healthCheck apply** (architect) → T7.3;
    **Phase 7's break-the-credentials test is unrunnable once FR-5 is on**
    (qa) → run with the variable unset, rollback stated; **Lambda runtime +
    handler string** were unpinned (dev) → T3.4; **import guard should be AST,
    not a `utils.*` grep** (qa) → T3.3; **G-3 failed by construction** since
    the trigger is itself a keystroke (qa) → carved out; **G-4 measured when
    trivially true** (qa) → deferred to the armed outcome.

## Accepted — citation corrections

- Fixture range `:510-525` → `:518`, `:525`. `:510` is `item-buried-review`
  (`awaiting_review`), which T1.2 explicitly leaves alone.
- Masked assertions: `:543` **and** `:544`, not `:544` alone.
- `flutter-action` block is `ci.yml:467-470`, not `:466-469`.
- `db_master_secret_arn` is `terraform/environments/prod/main.tf:228`, not
  `:229`.
- `ci.yml:8-10` is a header comment, not the reviewer-gate mechanism; the real
  keys are `:463`, `:706`, `:852`.
- `asyncio_mode = "auto"` applies via `libraries/utils/pyproject.toml:9-11`
  (its own `[tool.pytest.ini_options]` makes it pytest's rootdir), **not** via
  the root `pyproject.toml:68-70`. Same outcome, wrong mechanism — and it
  matters because `:10` also injects `--cov` with cwd-relative report paths.

## Rejected / noted without change

- **"Add `fail_under = 100` to `libraries/utils`"** (qa). Rejected as stated —
  imposing a package-wide floor is a larger blast radius than this workstream
  should take. Accepted in narrowed form: T2.8 adds a targeted coverage
  assertion over `coverage/libraries/utils/coverage.xml` for the new modules.
- **"Phase 1 should be labelled tests-after"** (qa). The tests exist and
  already fail, which is what tests-first means operationally here. Kept
  `tests-first` with a parenthetical noting it is fixture repair against a
  pre-existing RED.
- **"Move `probe_sync`/`__main__` out of Phase 2"** (pm, LOW). Kept in Phase 2
  deliberately — one implementation, two consumers — and the trade is now
  stated. Phase 7 hardens it.
- **E-7/E-8 coverage marked `full` against not-yet-existing `evals/*.md`.**
  Legal: E-7 is P2 and E-8 is P1 (`expectations.md:91`, `:103`), and the P0
  floor holds — E-1, E-2, E-3, E-5, E-6 all name runnable artifacts. Left as
  `full`; the artifacts land in their phases.
- **"3 of 1524" failure count** — confirmed empirically by the dev lens
  running `flutter test`: `01:17 +1521 -3: Some tests failed`, and the three
  failures are exactly the ones named.
