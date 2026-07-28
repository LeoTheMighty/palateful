---
hash: aam7
type: dev
created: 2026-07-27T17:12:00-06:00
title: Swap sync OpenAI client to AsyncOpenAI at all API callsites and drop the threadpool bridge
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: in-progress
owner: /devx-loop-2026-07-27T21-15-34-312-36147
blocked-by: []
branch: feat/dev-aam7
---

## Goal
Replace every synchronous `OpenAI(...)` client in `services/api/src/` with `AsyncOpenAI(...)` and `await` every call, removing the `run_in_threadpool` bridge that aam-17 left in place. The search endpoints are already `AsyncEndpoint` (aam-17 landed), so this story is the pure SDK swap — no endpoint-class conversion needed anymore.

## Acceptance criteria
- [ ] `services/api/src/api/v1/search/generate_recipe_embedding.py` (2 callsites, lines 25 and 57) uses `AsyncOpenAI`; every call is `await`ed.
- [ ] `services/api/src/api/v1/search/unified_search.py` `_sync_generate_query_embedding` (line ~558) becomes a native async call on `AsyncOpenAI`; the `run_in_threadpool` bridge at line ~551 and its explanatory comment ("aam-7 swaps to AsyncOpenAI in Phase 2") are removed.
- [ ] Every remaining `client.chat.completions.create(...)` / embeddings call in `services/api/src/` is `await`ed on the async client (grep `from openai import OpenAI` returns zero hits under `services/api/src/`, chat SSE path excepted only if explicitly deferred — see notes).
- [ ] Net behavior unchanged; no response-shape change.
- [ ] Coverage stays at 100% (`npx nx run api:test`).

## Technical notes
- Epic Phase 2 story `aam-7-openai-async` (epic file, Phase 2 section). Snippets: CHUNK-C5 in `_bmad-output/planning-artifacts/aam-phase1-dev-snippets.md` — "Every callsite of `OpenAI(...)` client in `services/api/src/` → `AsyncOpenAI(...)`".
- Verification against main (2026-07-27): aam-17 (search domain async, commit `dcbf825`) already converted the wrapping endpoints to `AsyncEndpoint` but kept the sync `OpenAI` client behind `run_in_threadpool` — `unified_search.py:545` comment explicitly defers to aam-7. So the original AC "wrapping Endpoint subclasses may stay sync... until aam-17" is obsolete; the story is now the client swap + bridge removal only.
- `services/api/src/routers/v1/chat_router.py` `send_message` (line ~84) is intentionally sync — its docstring says it is blocked on aam-7 plus an agent-tool async rewrite. This story unblocks it but the chat SSE conversion itself belongs to aam-24 cutover (or a dedicated follow-up); do not scope-creep the agent-tool rewrite in here. Do swap any sync `OpenAI` client construction the chat provider uses only if it can be done without the agent-tool rewrite; otherwise document the residual in the status log for aam-24.
- `services/worker` OpenAI usage stays sync — out of scope (worker is whitelisted sync per epic design principle 1).
- Original BMAD story key: aam-7-openai-async.

## Status log
- 2026-07-27T17:12 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; scope re-verified against main (see Technical notes)
- 2026-07-28T09:24:19-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-28T15:41:01.544Z — loop iteration 1: Completed the full aam7 SDK swap: all OpenAI callsites in services/api/src now use AsyncOpenAI with awaited calls, the unified_search run_in_threadpool bridge is removed, and tests/lint/coverage verify green except pre-existing rshred1 health-test breakage on main.
  - Change: Converted generate_recipe_embedding and assign_vibes_for_recipe to async AsyncOpenAI calls and awaited them at their create_recipe.py and update_recipe.py callsites
  - Change: Replaced unified_search.py's _sync_generate_query_embedding + run_in_threadpool bridge with a native async AsyncOpenAI call and removed the unused import and deferral comment
  - Change: Updated test_search.py helper/endpoint tests to async with openai.AsyncOpenAI + AsyncMock patches; replaced the obsolete threadpool-failure test with an async API-error degradation test
  - Change: Refreshed chat_router.py docstrings to record that aam-7 landed and the remaining sync SSE path is blocked only on the agent-tool async rewrite (sync client lives in libraries/agent, out of scope)
  - Learning: npx nx run api:test in a fresh worktree needs npx nx run api:install first AND a copy of the gitignored repo-root .env (Settings validation fails en masse without it); running pytest directly via .venv/bin/python is NOT equivalent to poetry run pytest and produces thousands of spurious errors
  - Learning: api:test currently cannot pass on any branch: tests/test_health.py (1 failed + 17 errors) imports utils.services.db_probe which exists nowhere in the repo — the rshred1 RED-stage breakage from commit 5a6174d — and its erroring tests leave health_router.py:25-27 uncovered, capping total coverage at 99 vs the fail-under=100 gate; every file touched by aam7 is individually at 100%
  - Learning: Patches of the helpers in test_recipe.py/test_coverage_gaps.py needed no changes because unittest.mock.patch auto-detects async targets and substitutes AsyncMock
  - Learning: Residual for aam-24: the chat provider's sync OpenAI client is in libraries/agent/agent/llm/openai.py (outside services/api/src), so the chat SSE path is untouched by design
