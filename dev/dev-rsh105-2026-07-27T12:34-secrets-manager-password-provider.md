---
hash: rsh105
type: dev
created: 2026-07-27T12:34:00-06:00
title: Secrets Manager password provider — connect-time credential resolution
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: done
owner: /devx-rsh105 (session_012ayskbK7fN9sYRXQpAdJzu)
branch: feat/dev-rsh105
---

## Goal

The credential machinery as a standalone, fully-tested library surface, with
**zero call sites wired**. Merging this changes no runtime behavior anywhere —
which is what makes rsh106's wiring reviewable on its own terms.

## Acceptance criteria

- [ ] `libraries/utils/utils/services/db_credentials.py` (created in rsh102)
      gains `SecretPasswordProvider(secret_arn, ttl_s=300, client=None)` with
      `.current()` and `.invalidate()`, plus `resolve_password_provider()` and
      `register_rotating_credentials(engine) -> bool`.
- [ ] Exactly **1** re-resolution and **1** retry per auth failure; the
      retried connection succeeds (E-6).
- [ ] A second consecutive auth failure **propagates** rather than looping.
- [ ] A **non**-auth exception propagates with **0** re-resolutions.
- [ ] With `DB_PASSWORD_SECRET_ARN` unset: **0** Secrets Manager calls, **0**
      boto3 clients constructed, **0** listeners registered, and
      `register_rotating_credentials` returns `False`.
- [ ] Within the TTL, repeated `.current()` calls make **0** additional
      `get_secret_value` calls; past it, exactly 1. `.invalidate()` forces
      exactly one re-resolution.
- [ ] **Composed failure**: an auth failure *and* `get_secret_value` raising →
      the retry does **not** silently re-present the stale `DB_PASSWORD`, and
      the failure is distinguishable (distinct exception or logged verdict).
- [ ] `DB_SECRET_TTL_S` configurable, default 300.
- [ ] T2.8's coverage assertion extended to `db_credentials.py`'s new surface.
- [ ] `poetry run pytest libraries/utils/` passes and `git diff --stat`
      touches only `db_credentials.py` and its test — **no call sites**.

## Technical notes

- **Do not put the Secrets Manager client in `aws.py`.** `AWSService.__init__`
  (`libraries/utils/utils/services/aws.py:13-37`) builds `_s3` and `_batch`
  **unconditionally**, sharing one `Config(signature_version="s3v4",
  read_timeout=2.0, retries={"max_attempts": 2})` tuned to an S3 NFR budget.
  Adding the SM client there would construct it on every `AWSService()`
  instantiation regardless of `DB_PASSWORD_SECRET_ARN` — directly violating
  E-6's zero-client threshold, and saddling a connect-path credential fetch
  with an S3 signature version and a 2s read timeout. Construct it **lazily
  inside `db_credentials.py`** with its own `Config`. The module still
  imports `boto3` at module scope (that is the seam the tests spy on); it is
  the *client* that is lazy, not the import.
- The registration helper attaches SQLAlchemy's `do_connect`:
  ```
  do_connect(dialect, conn_rec, cargs, cparams):
      cparams["password"] = provider.current()
      try:
          return dialect.connect(*cargs, **cparams)
      except Exception as exc:
          if not is_auth_error(exc):
              raise
          provider.invalidate()                        # exactly one
          cparams["password"] = provider.current()
          return dialect.connect(*cargs, **cparams)    # exactly one retry
  ```
  Returning a connection from `do_connect` suppresses SQLAlchemy's own
  connect — that is what makes the single retry expressible here instead of in
  every caller. For async engines the listener attaches to
  `engine.sync_engine`. The exception here is the **raw DBAPI error**, which
  is why rsh102's `is_auth_error` must match unwrapped exceptions.
- **`resolve_password_provider()` returns `None` when `DB_PASSWORD_SECRET_ARN`
  is unset, and the helper is then a total no-op** — no boto3 client
  constructed, no listener registered. This is the byte-identical path CAP-6
  requires for local, docker-compose and CI.
- **The `DB_PASSWORD` fallback must not silently poison the retry.**
  `.current()` falls back to the env var when resolution raises — legal on the
  **first** resolution, because it keeps a Secrets Manager outage at boot no
  worse than today. On the *retry* path it would return the very password that
  just failed, making an SM outage indistinguishable from "no rotation
  occurred" — the exact ambiguity that produced the six-day outage.
- **FR-5 does not touch `libraries/utils/utils/constants.py:19-42`.**
  `_build_database_url()` stays the single place URLs are composed; the
  listener overrides `cparams["password"]` per connection. Forking URL
  assembly here would undo the 2026-04-15 credential refactor.
- Follow `libraries/utils/test/test_db_pool_constants.py`'s established
  `monkeypatch.setenv` + `importlib.reload` pattern for env-derived state.
- The cached password lives only in memory — never logged, never on disk.
- The RED artifact drives the `do_connect` listener through
  `engine.pool._creator()` on a SQLite engine rather than `engine.connect()`:
  that closure is exactly the do_connect chain plus `dialect.connect`, whereas
  `connect()` also fires `first_connect` → `dialect.initialize()` and would run
  real SQL against the stub. Neither psycopg2 nor asyncpg is pinned in
  `libraries/utils`, and the listener is dialect-agnostic.
- RED artifact (do **not** re-author):
  `libraries/utils/test/test_db_credential_provider.py` (E-6, clause 1).
- Full context: `_devx/workstreams/rotation-self-heal/plan/agent.md` §Phase 5.

## Status log

- 2026-07-27T12:34 — emitted from plan 462355 at RED-gate PASS. E-6 observed
  RED right-reason (`ModuleNotFoundError: utils.services.db_credentials`); see
  `_devx/workstreams/rotation-self-heal/evals/RED-report.md`.
- 2026-09-22 — claimed by /devx (claim held locally on main — lane frozen by coordinator; not pushed). Worktree `.worktrees/dev-rsh105` on `feat/dev-rsh105` off `origin/main` @ faf35fa1.
- 2026-09-22 — phase 2: spec ACs direct (v2 native); 10 ACs; workstream=rotation-self-heal; red-artifacts=libraries/utils/test/test_db_credential_provider.py. Re-ran RED: 13 failed + 3 errors, right reason (AttributeError on the provider names; 3 call-site tests fail on the absent rsh106 wiring).
- 2026-09-22 — phase 3: implemented provider / resolver / registration + `CredentialResolutionError` in db_credentials.py. Artifact's two call-site tests (T6.3b, rsh106's) moved verbatim to `test_db_credential_wiring.py`, registered under rsh106; rsh105 registry entry deleted. Fixture fix in the artifact: blocks asyncpg import so its stated premise holds in the root venv (no assertion changed). Edge-case tests in `test_db_credentials_provider_edges.py` for the T2.8 gate.
- 2026-09-22 — phase 4: 1-agent single-pass adversarial review; 3 findings (0 HIGH, 1 MED, 2 LOW); ALL fixed in-place. MED: SM-outage-on-retry error chain decides rsh102's probe verdict; made deliberate (auth error kept out of the chain, so the probe fails open) and pinned by a test. LOW: from-imported exception class goes stale under the artifact's importlib.reload (tests now look names up on the module); UP031 in new test. Re-review clean.
- 2026-09-22 — phase 5: `npx nx run utils:test` 776 passed / 7 skipped, coverage gate OK (db_probe.py + db_credentials.py at 100% line+branch); `utils:lint` clean. Wiring file still RED (3 failed) under PYTEST_RUN_RED=1, as intended.
- 2026-09-22 — phase 7: PR https://github.com/LeoTheMighty/palateful/pull/45 at deef7b7d. Merge held: main is a serialized deploy lane; needs Leo's approval relayed by the coordinator.
- 2026-09-23 — merged via PR #45 (squash → b5dcc333). Deployed and verified in prod: run 35786099652 all legs success; api + worker both 1/1 ACTIVE on b5dcc333; `/v1/health` → `{"status":"ok","db":"OK"}` (unchanged, which is the point — zero call sites wired); no secretsmanager/db_credentials/boto/CredentialResolution/failing-open lines in 120 log lines per service.
- 2026-09-23 — deviations from the ACs, all recorded in PR #45: `tools/red-artifacts.txt` entry moved to rsh106 with the two call-site tests split verbatim into `test_db_credential_wiring.py`; the E-6 artifact's asyncpg fixture premise fixed (no assertion changed); `test_db_credentials_provider_edges.py` added for the T2.8 100% gate.
- 2026-09-23 — follow-ups filed: `chainctx1` (PR #59) **blocks rsh106** — the listener is what first puts a *resolved* auth error in scope for the classifier; `ncfgverdict1` (PR #59).
