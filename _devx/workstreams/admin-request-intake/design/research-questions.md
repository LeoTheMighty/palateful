# Research questions — Admin Request Intake

<!-- Before drafting. Factual, code-answerable, no intent ("which
     approach?" is design, not research). Answered blind in research.md.
     Add on re-entry; never renumber. -->

1. How is a new SQLAlchemy model registered so the app, the migrator and
   `bin/prod-script`'s prelude all see it (package `__init__` exports,
   imports)? Which file and revision id is the newest Alembic migration, and
   how are migration files named?
2. Does CI or any test check that the SQLAlchemy models and the Alembic
   migrations agree (autogenerate drift, `alembic check`, a schema test)?
3. How is an admin HTTP endpoint wired end to end: the `AsyncEndpoint`
   class, `success`/`failure`, export from `api/v1/admin/__init__.py`, the
   route function in `routers/v1/admin_router.py`, and how the router is
   mounted under `/v1`?
4. How does `get_current_user_async` resolve a user, and what does
   `require_admin_async` read from it? How do the API tests override auth and
   the database (`client` fixture, `dependency_overrides`)?
5. How does `utils/services/database.py` derive the async database URL and
   engine from `DATABASE_URL`? Is `asyncpg` a dependency of the api project?
6. How does `bin/prod-script` build its payload, which globals does its
   prelude define, and does any test exercise `bin/prod-script` or
   `bin/prod-console`?
7. Which columns do the existing `services/api/scripts/*.py` audit writers
   fill in `error_logs`, and how do those scripts obtain a database
   connection and parse arguments?
8. What lint and format rules apply to `services/api/scripts/` and
   `services/api/tests/` (ruff config, per-file ignores), and does anything
   forbid `from __future__` in scripts run by `bin/prod-script`?
9. Is there any existing Unicode normalization or control-character
   stripping helper in `libraries/utils` or `services/api`?
10. Which Postgres extensions do the models need for
    `Base.metadata.create_all` on an empty database (vector, pg_trgm, any
    other)?
11. Does any existing test create or drop a Postgres database, or connect to
    the CI `postgres` service at `localhost:5432`? How do the live-database
    tests in `libraries/utils/test/` decide to skip?
12. How does `tools/red-artifacts.txt` reach pytest (the loader, which test
    roots opt in), and does CI check the registry beyond collection (paths
    exist, entries removed)?
13. In the Flutter app: where are the admin dashboard tiles and admin routes
    defined, how does the app hide admin-only entries from non-admins, how
    does `api_client.dart` call admin endpoints, and how do existing admin
    screen tests mock the API client?
14. Is there a Flutter equivalent of the RED-artifact registry, or any
    mechanism that keeps a failing Flutter test out of the CI
    `flutter-test` job?
15. How does the API's FastAPI `app` object get imported in tests, and is
    there an existing test that enumerates registered routes?
