<!-- refined via party-mode 2026-04-21 -->

# Epic: Performance — Backend Query Tuning

## Overview

The Phase-2 backend audit (code-verified) surfaced several converging N+1 / redundant-query patterns on hot list endpoints. Two stand out:

- **`list_meals`** — `MealService._readable_book_ids(user_id)` runs once per meal inside `build_meal_summary` / `build_meal_response`. For the 30-meal home page that's 30 identical `SELECT FROM recipe_book_users WHERE user_id=...` queries. Verified at `meal_service.py:208–218` + `_response.py:15,50`.
- **`list_shopping_lists`** — the response loop iterates `sl.items` and `sl.members` without eager loading, triggering 2N lazy loads per response. Verified at `list_shopping_lists.py:77–84`.

Alongside those: `unified_search` calls `_get_my_book_ids()` twice per request; `list_calendars` member-count subquery aggregates the entire `calendar_users` table; `list_activities` runs a heavy `COUNT(*)` on every cursor-less request; `list_meal_events` accesses `event.participants` without eager loading. Each is drop-in fixable without changing the endpoint's response shape.

Party-mode (2026-04-21) culled one draft story that was a phantom win (`pbq-3` — bulk-favorite fetch is already implemented at `list_recipes.py:82–94`), split `pbq-4` into separate memo + selectinload stories, added a test-helper story `pbq-0`, and deferred `pbq-8` pending a functional trace.

## Goal

Every list endpoint named in the stories below returns under 300ms p95 on prod data volume. No response shape change except the explicit `total`-dropped-on-cursor change in `pbq-5`. No new routes. Coverage at 100% for `services/api`.

## End-User Flow

End user sees exactly what they see today, but faster.

1. Leo opens Home. The meals grid populates measurably faster per `analyze_latency.py` — the specific number goes in pbq-2's QA walkthrough.
2. He swipes to Shopping. The list screen renders measurably faster per the same tool (pbq-1's walkthrough).
3. He opens Activity. The initial mount no longer triggers a heavy `COUNT(*)`; the spinner is gone sooner; the response now carries `total=0` on cursor-less paths (documented in `docs/api-reference.md`).
4. He pulls to refresh each screen. Latency drop holds on the second render too — no warm-up-only wins.
5. From the admin perspective, Leo runs `analyze_latency.py --regression-hunt` the day after each story lands; the targeted `normalized_path` is no longer in the regression list.

## Frontend Changes

**None.** Every fix is server-side and preserves the existing response shape except:

- **`pbq-5` — `GET /v1/activities` cursor-less path drops `total` to `0`.** Pre-merge grep confirms zero Flutter consumers read this field from this endpoint (`notifications_tab.dart` and `activity_read_provider.dart` read only `items`; the see-all total comes from a separate `/v1/activities/see-all-count` endpoint). Grep is bundled as a hard pre-merge AC in `pbq-5`, not a follow-up.

No other story changes response serialization order, default values, null-vs-empty-array, or field availability.

## Backend Changes

Per-story details under Stories. Cross-cutting primitives:

- **`pbq-0` ships the query-count test helper** — a `count_queries` context manager in `services/api/tests/conftest.py` using SQLAlchemy's `before_cursor_execute` event listener. Every subsequent story's query-count AC uses it. Grep confirms no existing helper.
- **`hydrate_components` signature change (`pbq-2`)** — adds `readable_book_ids: set | None = None` kwarg with `None` fallback to today's self-fetch behavior. Grep confirms 2 prod callsites (`_response.py:15,50`) and 5 test callsites in `test_meal_service.py`; all compatible with the `None` default.
- **Memoization pattern (`pbq-4a`)** — `self._my_book_ids` attribute set on first call, read on subsequent. No module-global cache; memo lives on the request-scoped service instance. Disposed at request end.
- **Per-request cache pattern (`pbq-8`, iff proven necessary)** — attach flag to `request.state` via dependency context; no new cache primitive. Spike first.
- **EXPLAIN bar**: required only where the plan materially changes (`pbq-6` scoped subquery). One-liner eager-load fixes (`pbq-1`, `pbq-7`, `pbq-4b`) need only p50/p95 before/after.

## Infrastructure Changes

- **None at the epic level.** Per inherited lock #5, this epic does not touch `terraform/`.
- **Per-story migrations only**: if a story needs an index (currently only a risk in `pbq-6`), the story owns the migration using `CREATE INDEX CONCURRENTLY` in an autocommit block. No consolidated-migration pattern.

## Design Principles (refined via party-mode 2026-04-21)

- **One request, bounded DB round-trips.** Every targeted list endpoint hits the DB a fixed small number of times (typically 2–3) regardless of page size. Integration tests make this a contract.
- **No contract changes except documented.** Only `pbq-5` drops a field; it does so explicitly with a docs update and a Flutter-consumer grep.
- **Measure each fix with `pim-1`.** Hard AC: p50/p95 before/after in every story's QA walkthrough.
- **Smallest change wins.** Don't refactor endpoints; close the specific gap. Don't move business logic unless the fix requires it.
- **Draft correctness gate.** Before implementing a story, re-read the target file to confirm the fix isn't already landed. Guards against `pbq-3`-style phantom wins.
- **Per-story rollback.** Every fix reverts in a single commit: delete a memoization attr, remove a kwarg pass (defaults handle it), restore a COUNT, revert a subquery scope. No data migrations.
- **Split fix + refactor.** Stories that bundle two distinct concerns (memoize + eager-load in `pbq-4`) split by default.
- **selectinload for 1-to-many, joinedload for 1-to-1.** Items / members / participants / components → selectinload (one `IN` query, bounded). Fanout multiplicity never gets `joinedload` here.

## File Structure

```
services/api/tests/conftest.py                                          (modify — add count_queries helper)
services/api/src/api/v1/shopping_list/list_shopping_lists.py            (modify)
services/api/src/api/v1/meal/list_meals.py                              (modify)
services/api/src/api/v1/meal/_response.py                               (modify — thread readable_book_ids)
libraries/utils/utils/services/meal_service.py                          (modify — optional kwarg on hydrate_components)
services/api/src/api/v1/search/unified_search.py                        (modify)
services/api/src/api/v1/user_activity/list_activities.py                (modify)
services/api/src/api/v1/calendar/list_calendars.py                      (modify)
services/api/src/api/v1/meal_event/list_meal_events.py                  (modify)
services/api/src/dependencies.py                                        (conditional — pbq-8 only if spike proves necessary)
services/api/tests/test_shopping_list.py                                (modify — query-count test)
services/api/tests/test_meal.py                                         (modify — query-count test)
services/api/tests/test_search.py                                       (modify — query-count test)
services/api/tests/test_user_activity.py                                (modify — total-dropped test)
services/api/tests/test_calendar.py                                     (modify — query-count test)
services/api/tests/test_meal_event.py                                   (modify — query-count test)
services/api/tests/test_dependencies.py                                 (conditional — pbq-8 only)
services/migrator/migrations/versions/<ts>_pbq6_index.py                (conditional — only if pbq-6 EXPLAIN shows missing index)
docs/api-reference.md                                                   (modify — note total=0 on list_activities cursor path)
```

## Stories

**`pbq-0-query-count-test-helper`** — prerequisite for every subsequent story's AC.

ACs:
- `services/api/tests/conftest.py` adds `count_queries()` context manager using SQLAlchemy `before_cursor_execute` event on the test engine.
- Yields a `QueryCounter` object with `.total`, `.select`, `.insert`, `.update`, `.delete` attributes.
- One representative test in `test_shopping_list.py` (or similar) demonstrates the helper working end-to-end.
- Documented with a docstring showing typical usage: `with count_queries() as qc: ...; assert qc.select <= 4`.

**`pbq-1-list-shopping-lists-eager-load`** — selectinload items + members.

ACs:
- Main query gains `.options(selectinload(ShoppingList.items), selectinload(ShoppingList.members))`.
- Response shape byte-identical to current.
- Integration test using `count_queries`: N lists in DB, `qc.select <= 4` (main + items selectin + members selectin + default_shopping_list user lookup).
- `member_count` computation stays in-Python against the eager-loaded `sl.members` list — no separate aggregate query unless EXPLAIN shows benefit.
- p50/p95 before/after for `GET /v1/shopping-lists` pasted into QA walkthrough.

**`pbq-2-list-meals-readable-book-ids-hoisted`** — compute `_readable_book_ids` once per request. **Highest leverage in epic.**

ACs:
- `hydrate_components(meal, *, user_id, readable_book_ids: set | None = None)` — when passed, skips the per-meal fetch.
- `_response.py` both `build_meal_response` and `build_meal_summary` accept + thread the kwarg.
- `list_meals.py` computes once and passes.
- 5 test-callers in `test_meal_service.py` unchanged (verified — use `None` default).
- Integration test: 30-meal page triggers **1** `_readable_book_ids`-shaped query, not 30 (asserted via `count_queries`).
- Non-list callers (`create`/`update`/`get` meal) unchanged — regression test in `test_meal_service.py`.
- p50/p95 before/after for `GET /v1/meals?scope=home`.

**`pbq-4a-unified-search-memoize-book-ids`** — single-instance memoization.

ACs:
- `_get_my_book_ids()` sets `self._my_book_ids` on first call; subsequent calls return the cached attr.
- Integration test: `/v1/search?q=...` with a term hitting exact + fuzzy triggers **one** `_get_my_book_ids`-shaped query (asserted via `count_queries`).
- p50/p95 before/after for `GET /v1/search`.

**`pbq-4b-unified-search-semantic-tier-selectinload`** — close the semantic-tier ingredient lazy-load gap.

ACs:
- Semantic-tier query gains `selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient)`.
- Integration test: semantic-tier response triggers no per-result lazy loads on ingredients (asserted via `count_queries`).
- EXPLAIN of the new semantic query captured in QA walkthrough to confirm no plan regression.
- p50/p95 before/after for `GET /v1/search` (semantic tier, via a query that routes to it).

**`pbq-5-list-activities-drop-total-on-cursor-path`** — drop the heavy COUNT; rename reflects honest behavior.

ACs:
- **Pre-merge grep** (hard AC): `grep -r 'response.total\|\.total\b' apps/flutter/lib/features/activity/ apps/flutter/lib/features/notifications/` returns no consumer of `/v1/activities` response `total`. Grep output pasted into QA walkthrough.
- On cursor-less requests, `total=0` is returned; the heavy `COUNT(*)` query is removed.
- Response-model docstring in `list_activities.py` explicitly notes `total=0` semantics on cursor paths.
- `docs/api-reference.md` gains a one-line note for `/v1/activities`: "`total` is `0` on cursor-paginated responses; use `items.length` and `next_cursor` for pagination."
- Integration test: cursor-less request with 10k+ seeded rows completes in < 200ms on local Postgres.
- p50/p95 before/after for `GET /v1/activities`.

**`pbq-6-list-calendars-scoped-member-count`** — subquery no longer scans entire `calendar_users` table.

ACs:
- `member_count_subq` scoped to the user's calendar IDs (`CalendarUser.calendar_id.in_(...)` or correlated subquery).
- EXPLAIN plan captured: index scan on `calendar_users.calendar_id`, no hash aggregate over the whole table.
- **Index check**: confirm `calendar_users.calendar_id` has an index (likely via the existing FK). If missing, add via `CREATE INDEX CONCURRENTLY` in the same story's migration.
- Integration test: result values unchanged against a seed of 50+ calendars / 5+ users.
- p50/p95 before/after for `GET /v1/calendars`.

**`pbq-7-list-meal-events-eager-load-participants`** — sibling selectinload addition.

ACs:
- Main query gains `selectinload(MealEvent.participants)` as a **sibling** `.options()` entry, alongside the existing `meal.components.recipe` chain (explicitly not nested under `meal`).
- Integration test: `count_queries` shows participants populated without per-event lazy loads.
- p50/p95 before/after for `GET /v1/meal-events`.

**`pbq-8-dependencies-ensure-default-calendar-spike-first`** — SPIKE, then implement only if the trace proves duplicate invocations.

ACs (spike phase):
- Add a request-tracing test: a single authenticated request that resolves the full dependency chain counts actual `_ensure_default_calendar` invocations. FastAPI's built-in `Depends` cache typically deduplicates within a single request — verify in the test.
- If count is exactly 1: close the story as "FastAPI dep-cache already protects us; no change needed." Ship the trace test as regression coverage. No code change.
- If count is >1: proceed — attach a flag to `request.state` (`request.state.default_calendar_ensured=True`) in `services/api/src/dependencies.py`; short-circuit on repeat.
- p50/p95 before/after only if the implementation branch fires.

## Dependencies

- **Blocks**: nothing.
- **Blocked by**: `pim-1` (soft — QA walkthroughs cite `analyze_latency.py` output).
- **Internal**: `pbq-0` (test helper) is a hard gate for `pbq-1`/`pbq-2`/`pbq-4a`/`pbq-4b`/`pbq-6`/`pbq-7`/`pbq-8`.
- **Shares with**: nothing.

## Inherited Decisions Applied

1. Pool arithmetic — no reference. Compliant.
2. Every story has p50/p95 before/after via `analyze_latency.py` — hard AC.
3. Redis not referenced — compliant.
4. Any new index uses `CREATE INDEX CONCURRENTLY` in autocommit block (only `pbq-6` at risk of needing one).
5. Zero terraform touches — compliant.
6. Fail-open N/A here.

## Locked Decisions (propagate to epic 3)

1. **`count_queries` test helper** at `services/api/tests/conftest.py` is the one place for DB-round-trip assertions. If epic 3 needs an equivalent for Flutter-side, scope it separately.
2. **One-liner eager-load fixes** require only p50/p95 before/after in QA. EXPLAIN reserved for plan-shape changes.
3. **Per-story migrations, not consolidated.** Each story that needs DDL owns its own migration file.
4. **Draft correctness gate**: re-read the target file before implementing. Avoid phantom wins.

## Risks + Mitigations

- **Phantom wins from stale drafts** (`pbq-3` was already implemented): pre-implementation re-read gate.
- **`pbq-2` kwarg threading regression**: test-callers exercise None-fallback; 5 existing test callsites verified.
- **`pbq-7` options() misplacement**: AC pins selectinload at the root `.options()` as a sibling.
- **`pbq-5` schema doc drift**: `docs/api-reference.md` update is a hard AC; Flutter consumers verified clear.
- **`pbq-6` missing index**: AC verifies existence; creates via CONCURRENTLY if absent.
- **`pbq-8` non-issue**: spike-first protects against spending implementation effort on a non-problem.
- **Query-count helper scope creep**: `pbq-0` scope locked to context manager + docstring + one usage example. No framework.

## Open Questions for the User — RESOLVED (2026-04-21)

1. **`pbq-3` cut**: confirmed — already implemented at `list_recipes.py:82–94`. Marked `deleted` in sprint-status.
2. **`pbq-8` spike-first**: confirmed — story lands as a spike; if FastAPI's built-in `Depends`-cache already deduplicates per-request (expected), the spike closes as a no-op with the trace test retained as regression coverage.
