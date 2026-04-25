# recipe-defaults-2 — QA Walkthrough

**Story:** `recipe-defaults-2-backend-new-user-provisioning-hook-seeds-trying-out-and-default`
**Date:** 2026-04-25

## Summary

Wires the auth-callback (sync + async) to seed a system Trying Out
recipe book on first authed request from a brand-new user, and to set
`users.default_recipe_book_id` to that book's id when the user does
not already have a default. Mirrors the existing
`_ensure_default_calendar` pattern: idempotent SELECT-before-INSERT
inside a SAVEPOINT, with an `IntegrityError` race fallback.

Also guards `complete_onboarding.py` so the user-facing "My Recipes"
book it creates does NOT overwrite a default that the auth-callback
hook already set. New users now finish sign-up with two books — Trying
Out (system, default) and "My Recipes" (user-created, switchable
default via the existing endpoints).

## Files

| File | Status | Purpose |
|---|---|---|
| `services/api/src/dependencies.py` | modified | Add `_ensure_system_trying_out` + async sibling, wire both into `get_current_user` / `get_current_user_async` |
| `services/api/src/api/v1/user/complete_onboarding.py` | modified | Set default only when currently None |
| `services/api/tests/test_dependencies.py` | modified | New `TestEnsureSystemTryingOut` class — 4 sync helper tests |
| `services/api/tests/test_async_auth_deps.py` | modified | 4 async helper tests |
| `services/api/tests/test_user.py` | modified | New onboarding test — preserves existing default |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | modified | flip `recipe-defaults-2-...: backlog → done` |
| `_bmad-output/implementation-artifacts/recipe-defaults-2-...md` | new | Story spec |
| `_bmad-output/implementation-artifacts/recipe-defaults-2-...-qa-walkthrough.md` | new | This file |

## Acceptance-criteria mapping

| AC | Verified by | Where |
|---|---|---|
| AC #1 Sync helper exists | function definition + 4 tests | `dependencies.py` / `test_dependencies.py::TestEnsureSystemTryingOut` |
| AC #2 Async helper exists | function definition + 4 tests | `dependencies.py` / `test_async_auth_deps.py` |
| AC #3 Sync wiring | inspection — single call after `_ensure_default_calendar` in both E2E + JWT branches | `get_current_user` |
| AC #4 Async wiring | inspection — single call after `_ensure_default_calendar_async` in both E2E + JWT branches | `get_current_user_async` |
| AC #5 Idempotency (sync) | `test_ensure_system_trying_out_returns_existing` | sync test |
| AC #6 Idempotency (async) | `test_ensure_system_trying_out_async_returns_existing` | async test |
| AC #7 Default-set semantics | `test_ensure_system_trying_out_creates_when_missing` (sets) + `test_ensure_system_trying_out_preserves_existing_default` (preserves) — both sync + async | both test files |
| AC #8 Race safety | `test_ensure_system_trying_out_handles_race_loss` — sync + async | both test files |
| AC #9 Onboarding doesn't override | `test_complete_onboarding_preserves_existing_default_recipe_book_id` | `test_user.py` |
| AC #10 Onboarding still sets when null | existing `test_complete_onboarding_success` still asserts default-book creation; mock_user starts with default=None and gets set | `test_user.py` (regression) |
| AC #11 Coverage | `dependencies.py` + `complete_onboarding.py` both 100% in `coverage.xml` | nx report |
| AC #12 Lint + tests | `nx run api:lint`, `nx run api:test`, `nx run utils:lint`, `nx run utils:test`, `alembic check` all green | local |
| AC #13 Sprint-status flipped | git diff sprint-status.yaml | `backlog → done` |

## Test inventory (9 new tests, all passing)

Sync (`TestEnsureSystemTryingOut` in `test_dependencies.py`):

| # | Test | What it proves |
|---|---|---|
| S1 | `test_ensure_system_trying_out_returns_existing` | Fast path — book present; helper returns it; no INSERT, no `update()` call. |
| S2 | `test_ensure_system_trying_out_creates_when_missing` | Miss path — book + membership both created; `database.update` called once with `default_recipe_book_id` kwarg. |
| S3 | `test_ensure_system_trying_out_preserves_existing_default` | After creation when user already has a custom default, `database.update` is NOT called. |
| S4 | `test_ensure_system_trying_out_handles_race_loss` | SAVEPOINT INSERT raises `IntegrityError` → caught; helper re-reads; returns winner; sets default once (winner exists, default was None). |

Async (in `test_async_auth_deps.py`):

| # | Test | What it proves |
|---|---|---|
| A1 | `test_ensure_system_trying_out_async_returns_existing` | sibling of S1 |
| A2 | `test_ensure_system_trying_out_async_creates_when_missing` | sibling of S2 — asserts `db.add.call_count == 2` and `db.flush.await_count == 2` |
| A3 | `test_ensure_system_trying_out_async_preserves_existing_default` | sibling of S3 |
| A4 | `test_ensure_system_trying_out_async_handles_race_loss` | sibling of S4 — uses `IntegrityError` injected on `db.flush` |

Onboarding (in `test_user.py`):

| # | Test | What it proves |
|---|---|---|
| U1 | `test_complete_onboarding_preserves_existing_default_recipe_book_id` | mock_user starts with default already set; after onboarding, "My Recipes" is created and returned in the response, but the user's default is unchanged. |

## Adversarial review notes

1. **Sync vs async API parity.** The two helpers must follow the exact
   same pattern as `_ensure_default_calendar` / `_ensure_default_calendar_async`
   to avoid surprising callers. Verified by inspection: both use
   `begin_nested()`, both catch `IntegrityError`, both re-read the
   winner, both treat `default_recipe_book_id=None` as the only trigger
   for the default-set write.

2. **`book.id` is populated post-flush.** The default-set write relies
   on `book.id` after the SAVEPOINT block exits. Since
   `database.db.flush()` populates the primary key on the instance, the
   id is available outside the `with` block. Mirrors
   `_ensure_default_calendar`'s `calendar.id` use in the membership
   row construction.

3. **No new query on the fast path.** The fast path is one SELECT
   (the JOIN-on-membership probe). FastAPI's `Depends` cache dedupes
   `get_current_user` invocations within a single request, so the
   helper fires at most once per request. Same property as
   `_ensure_default_calendar` (covered by the existing pbq-8 spike test).

4. **Onboarding behaviour is contract-preserving.** The conditional
   default-set retains the existing semantics for any code path that
   somehow reaches onboarding without a pre-set default (test
   fixtures, direct DB seeding). Real users hit the auth-callback hook
   first, so their default is already set when onboarding runs.

5. **No partial unique index.** Same deviation as story 1: the seed
   loop and the auth-callback hook both rely on app-level
   SELECT-before-INSERT idempotency. The `IntegrityError` catch is the
   safety net for genuinely-concurrent provisioning (two parallel
   requests for the same brand-new auth0_id) — handled by the
   re-read.

No findings deferred — all five review concerns above were verified by
inspection and tests.

## Manual QA (runtime sanity)

1. **Local DB end-to-end.** Same migrated `test` DB from story 1.
   `alembic check` → "No new upgrade operations detected."
2. **No new migration in this story.** Story 1's migration covers the
   schema; story 2 is purely API-layer behaviour.
3. **Pre-existing async E2E bypass test still passes.** The full
   `nx run api:test` run (2516 passed) confirms that the
   `test_get_current_user_async_e2e_bypass` test stays green with the
   added `_ensure_system_trying_out_async` call wired in.

## Risks known to oncall

- **Two extra SELECTs per request** (`_ensure_default_calendar` +
  `_ensure_system_trying_out`). Both are index-scoped, millisecond-class.
  No alerting changes needed.
- **`error_logs` could see new SAVEPOINT IntegrityError logs** — but
  only when two parallel auth-callback flows for the same brand-new
  user race; the existing race-loss path on `_ensure_default_calendar`
  already produces similar rows in this scenario, so triage queries
  are unchanged.

## Done

- [x] `nx run api:lint` green.
- [x] `nx run api:test` — 2516/2516 pass; touched files (`dependencies.py`, `complete_onboarding.py`) at 100% coverage.
- [x] `nx run utils:test` — 602/602 pass.
- [x] `alembic check` (local test DB) — no drift.
- [x] `sprint-status.yaml` flipped `recipe-defaults-2-...: backlog → done`.
- [x] Adversarial review complete; no findings deferred.
- [x] Atomic commit — only story-scoped files staged.
