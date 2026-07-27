---
hash: aam7
type: dev
created: 2026-07-27T17:12:00-06:00
title: Swap sync OpenAI client to AsyncOpenAI at all API callsites and drop the threadpool bridge
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: ready
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
