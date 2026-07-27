---
hash: aam24
type: dev
created: 2026-07-27T17:16:00-06:00
title: Cutover — flip last sync holdouts (WS auth, chat SSE), remove sync shims, shrink sync pool
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: ready
blocked-by: [aam7, aam8, aam22, aam23]
branch: feat/dev-aam24
---

## Goal
Finish the migration: flip the last handlers still on sync deps (two WebSocket auth paths and the chat SSE stream), delete the remaining sync `Endpoint` surface from API scope, remove the sync MCP `call_endpoint`, deprecate the sync FastAPI deps, and shrink the sync pool now that only whitelisted paths use it.

## Acceptance criteria
- [ ] Remaining sync-dep holdouts flip to async: `recipe_book_router.py:229` WS handler (`database: Database = Depends(get_database)` used for WS-auth `find_by`) and `shopping_list_router.py:449` WS handler — both switch to `get_async_database` + awaited lookups, with the WS reconnect-burst regression probe from the aam-11/aam-13 QA walkthroughs re-run.
- [ ] `chat_router.py` `send_message` (line ~84, "Intentionally sync — blocked on aam-7") converts: async deps + async OpenAI provider chain + agent `tool.execute` calls made async-safe (threadpool-wrap tools that must stay sync).
- [ ] Last sync `Endpoint` subclass in API scope removed or converted: `services/api/src/api/v1/user/create_user.py` (not referenced by any router — confirm dead and delete, else convert).
- [ ] Sync `Endpoint` class kept in `libraries/utils/utils/api/endpoint.py` (worker + scripts use it) but a module-level assertion fails loudly if it is imported from `services/api/src/api/v1/**/*.py`.
- [ ] Sync `get_database` + `get_current_user` in `services/api/src/dependencies.py` marked deprecated with an import-time warning from API handler code; still callable from `manage.py` + whitelisted paths.
- [ ] Sync MCP helper `call_endpoint` (`mcp_server/server.py:54`) removed; only `call_endpoint_async` remains; sync `get_current_database` in `mcp_server/auth.py` removed if unused.
- [ ] Pool shrink (separate commit inside the story): `DB_POOL_SIZE` default 20 → 5, `DB_MAX_OVERFLOW` 40 → 10 in `libraries/utils/utils/constants.py` + explicit ECS task-definition env values; sync engine keeps headroom for whitelisted paths only.
- [ ] `analyze_latency.py --window 24h` snapshot pre-cutover + 24h post-cutover; every endpoint p95 flat or improved; `GET /v1/meals/{meal_id}` client-side p95 < 500ms for 24h post-cutover.
- [ ] Rollback commit hash documented in the QA walkthrough (post-cutover rollback is non-trivial — sync code is gone; name the last-good commit).
- [ ] `npx nx run api:lint` + `npx nx run api:test` + `npx nx run worker:test` green; coverage stays at 100%.

## Technical notes
- Epic Phase 5 story `aam-24-cutover-and-shim-removal`. Snippets: CHUNK-C4 in `aam-phase1-dev-snippets.md` ("pure delete PR" — no longer quite true, see below).
- Verification against main (2026-07-27): the aam-trunk sweep already absorbed most of the original scope. All Phase 3 domains (aam-10..21, 12a/12b, 28-30) are done; there is NO dual-registered sync router code left to delete — handlers were converted in-place. What actually remains sync: (1) two WS auth paths (`recipe_book_router.py:229`, `shopping_list_router.py:449` — `database.find_by(User, ...)` sync on the loop during WS upgrade), (2) `chat_router.py` send_message SSE (sync OpenAI + sync agent tools, explicitly deferred to "alongside aam-7"), (3) unrouted `api/v1/user/create_user.py` sync Endpoint, (4) sync `call_endpoint` in `mcp_server/server.py`, (5) undeprecated sync deps in `dependencies.py` (no `_deprecated` markers found), (6) pool still at 20/40 (`constants.py:117-118`).
- Blocked-by reflects the epic's phase ordering: aam-24 requires all Phase 2 (aam-7, aam-8 — aam-9 already landed, commit `13abbf1`) and Phase 4 (aam-22, aam-23) merged. The chat conversion concretely needs aam-7's AsyncOpenAI.
- The epic's "all Phase 3 observation windows closed green" precondition is satisfied — domains have been live on main well past 48h.
- Original BMAD story key: aam-24-cutover-and-shim-removal.

## Status log
- 2026-07-27T17:16 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; scope re-verified against main (see Technical notes)
