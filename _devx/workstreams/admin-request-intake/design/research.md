# Research — Admin Request Intake

<!-- Answers to research-questions.md, one section per question; each claim
     cites `path:line`. NOT BLIND: the skill wants these answered by a
     subagent given only research-questions.md. This session has no Agent
     tool, and a headless read-only `claude -p` was refused by the
     permission classifier, so the authoring session (which has read the
     PRD) answered them. Treat the answers as checked citations, not as an
     independent read. Read against palateful origin/main 80e5d005. -->

## Q1 — Model registration; newest migration

- Models are re-exported from the package: `libraries/utils/utils/models/__init__.py:56` imports `UserFeedback`, listed in `__all__` at `:108`.
- `bin/prod-script`'s prelude walks `utils.models` with `pkgutil.walk_packages` and exposes every class with a `__table__` (`bin/prod-script:114-136`), so any module under `utils/models/` is visible there whether or not `__init__` exports it.
- Migrations: `services/migrator/migrations/versions/`, named `YYYYMMDDHHMMSS_<slug>.py` with a short string `revision` (e.g. `20260418020000_add_user_feedbacks.py:29-30`).
- The single head today is `idupbookname1` in `20260425020000_add_recipe_lower_name_index.py:47` (63 revisions; computed from every `revision`/`down_revision` in the directory).

## Q2 — Model/migration agreement checks

- CI's `test` job applies migrations to its Postgres before the suite: `npx nx run migrator:migrate-test` (`.github/workflows/ci.yml:239-240`).
- A `check-models` job runs `npx nx run migrator:check-models` (`.github/workflows/ci.yml:330-331`) but is `continue-on-error: true` "Pre-existing model/migration drift" (`:273`). Drift does not fail CI.

## Q3 — Admin endpoint wiring

- Endpoint classes subclass `AsyncEndpoint` and return `success(data=…, status=…)` / `failure(status=…, error_code=…, …)` (`services/api/src/api/v1/user/create_user_feedback.py:23`, `:99`, `:141`).
- Classes are exported from `services/api/src/api/v1/admin/__init__.py:16-19`, `:34-37`.
- Routes are functions on `admin_router = APIRouter(prefix="/admin", …)` (`services/api/src/routers/v1/admin_router.py:26`), e.g. `@admin_router.get("/feedback")` at `:171` and `@admin_router.put("/feedback/{feedback_id}/status")` at `:189`, each taking `user: User = Depends(require_admin_async)` (`:37`).

## Q4 — Auth resolution and test overrides

- `require_admin_async` depends on `get_current_user_async` and raises `APIException(403, …, ErrorCode.FORBIDDEN)` when `user.is_admin` is false (`services/api/src/dependencies.py:523-537`).
- `get_async_database` yields an `AsyncDatabase()` per request (`services/api/src/dependencies.py:69-85`).
- The `client` fixture imports `from main import app` and sets `app.dependency_overrides` for `get_database`, `get_async_database`, `get_current_user`, `get_current_user_async` (`services/api/tests/conftest.py:1236-1274`).

## Q5 — Async URL and driver

- `utils/services/database.py` imports `ASYNC_DATABASE_URL` (`libraries/utils/utils/services/database.py:17`) and probe-imports `asyncpg` before building the async engine (`:66-84`).
- `AsyncDatabase(db=None, engine=None)` accepts an explicit `AsyncEngine` (`libraries/utils/utils/services/async_database.py:118-135`).
- `asyncpg = "^0.30"` is an api dependency (`services/api/pyproject.toml:13`).

## Q6 — `bin/prod-script`

- Takes exactly one argument: `SCRIPT="${1:-}"` (`bin/prod-script:14`); nothing else reaches the script.
- Prelude: keepalive thread writing `\x1b[0C` to stderr every 0.5 s (`:85-95`); an `atexit` sentinel line (`:103-111`); `db` session, `database`, every model and enum in globals (`:131-136`).
- Payload: prelude + script concatenated, base64, run as `python -u -c "exec(base64…)"` via `aws ecs execute-command --interactive` (`:147-171`); local `awk` strips `\r` and stops at the sentinel (`:172-180`); exit code is aws's (`:181-183`).
- No test exercises `bin/prod-script` or `bin/prod-console` (grep of `services/api/tests`, `libraries/utils/test`, `tools`, `.github` for `prod-script`/`prod_script`: only `libraries/utils/test/test_database_api_frozen.py`, which mentions it in prose).

## Q7 — Script audit rows and connections

- `promote_admin.py` builds its engine from `DATABASE_URL` (`services/api/scripts/promote_admin.py:36-41`), uses `engine.connect()` + `conn.begin()` (`:146`, `:182`), and writes the audit row with a raw `INSERT INTO error_logs (…)` (`:75-110`).
- `inspect_user_push.py` is read-only, writes no audit row, builds its own engine and ignores the prelude's variables (`services/api/scripts/inspect_user_push.py:26-29`, `:52`).
- `ErrorLog` columns: `error_type`, `error_message` (both non-null), `stack_trace`, `error_code`, `method`, `path`, `status_code`, `user_id`, `service` (default `"api"`), `request_id`, `import_item_id`, `stage` (`libraries/utils/utils/models/error_log.py:17-32`).
- Scripts parse arguments with `argparse` and expose `main(argv)` (`services/api/scripts/promote_admin.py:113`, `:142`).

## Q8 — Lint rules

- Root ruff config: `line-length = 100`, `select = ["E","F","I","UP","B","SIM"]`, `ignore = ["E501","B008"]` (`pyproject.toml:60-66`); `ruff = "^0.11"` in the api project (`services/api/pyproject.toml:28`). No per-file ignores found in either file.
- `docs/HELPFUL_SCRIPTS.md:20-22`: scripts run by `bin/prod-script` must not use `from __future__`, because the prelude is concatenated above them.

## Q9 — Unicode normalization helpers

- None found: grep for `unicodedata` / `NFKC` under `libraries/utils/utils` and `services/api/src` returns nothing.

## Q10 — Extensions for `create_all`

- Measured 2026-11-24 against the local `pgvector/pgvector:pg16` container: `Base.metadata.create_all` on an empty database fails with `operator class "gin_trgm_ops" does not exist` until `pg_trgm` is created; with `vector` and `pg_trgm` it creates 51 tables in 0.56 s.

## Q11 — Live-database tests

- `libraries/utils/test/test_db_credentials_live_drivers.py:15-35` connects to `PALATEFUL_LIVE_DB_HOST/PORT/USER/NAME/PASSWORD` (defaults `localhost`, `5432`, `postgres`, `test`, `postgres`) and skips when no server answers (`pytestmark = pytest.mark.skipif(…)` at `:59`; driver import-or-skip at `:38`, `:133`).
- No test creates or drops a database (grep for `CREATE DATABASE` / `DROP DATABASE` in `services/api/tests`, `libraries/utils/test`).
- CI's `test` job runs a `pgvector/pgvector:pg16` service at `localhost:5432` with `postgres`/`postgres`/`test` (`.github/workflows/ci.yml:181-196`).

## Q12 — RED registry

- `collect_ignore_for(conftest)` returns registry filenames in the conftest's own directory unless `PYTEST_RUN_RED` is set (`libraries/utils/utils/testing/red_registry.py:60-74`); a registered path that does not exist raises (`:52`).
- `services/api/tests/conftest.py:13`, `:34` opt in; so does `libraries/utils/test/conftest.py`.
- No CI step reads `tools/red-artifacts.txt` other than through pytest collection (grep of `.github` and `tools/*.sh`).

## Q13 — Flutter admin surfaces

- The admin dashboard is web-only, routed outside the shell (`app/lib/core/router/app_router.dart:633-638`); every `/admin*` location redirects non-admins to `/` (`:225-227`).
- The feedback tile is `_buildFeedbackTile`, keyed `admin_feedback_card`, pushing `/admin/feedback` (`app/lib/features/admin/admin_dashboard_screen.dart:771-781`).
- `api_client.dart` calls admin endpoints through `_dio`, e.g. `_dio.get('/v1/admin/feedback', …)` (`app/lib/core/services/api_client.dart:1104`) and the status PUT at `:1113`.
- Admin screen tests live in `app/test/features/admin/` (`admin_feedback_screen_test.dart` and two others).

## Q14 — Keeping a failing Flutter test out of CI

- None found. The `flutter-test` job runs bare `flutter test` in `app/` (`.github/workflows/ci.yml:399-401`); no `dart_test.yaml` tags or exclusion list exists.

## Q15 — The app object and route enumeration

- Tests import the app with `from main import app` (`services/api/tests/conftest.py:1244`).
- `services/api/tests/test_main.py:41` already enumerates `[r.path for r in app.routes]`.
