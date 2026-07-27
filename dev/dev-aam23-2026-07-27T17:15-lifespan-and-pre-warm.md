---
hash: aam23
type: dev
created: 2026-07-27T17:15:00-06:00
title: Lifespan pre-warm — warm every async pool connection before healthcheck flips green
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: ready
blocked-by: []
branch: feat/dev-aam23
---

## Goal
Expand the single-connection async-engine warm-up that aam-1 left in `main.py` into a full pool pre-warm: fire `SELECT 1` on every async pool connection (up to `DB_ASYNC_POOL_SIZE`) at startup, before the healthcheck can go green, masking asyncpg's ~100-300ms per-connection prepared-statement cache build from real requests. Add a lifespan test with a time budget.

## Acceptance criteria
- [ ] `services/api/src/main.py` lifespan warms every async pool connection (up to `pool_size`) with a trivial `SELECT 1`, replacing the current single-connection warm-up at lines ~49-66 (whose comment says "aam-23 expands this to warm every connection in the pool").
- [ ] Startup ordering preserved: sync engine first (unit-alias pre-warm stays sync, one-shot, before the async warm-up — already the case), async second; dispose order reversed (already implemented at lines ~93-109 — verify, don't rewrite).
- [ ] `/v1/health` unchanged in shape; it flips green only after the pre-warm completes (warm-up runs inside lifespan before `yield`, so the app serves no requests until done — assert this in the test).
- [ ] Expected added startup time < 500ms for 20 connections; lifespan test validates warm-up runs and completes within a 5s budget (`services/api/tests/test_lifespan.py` per snippets CHUNK-C3).
- [ ] Coverage stays at 100%.

## Technical notes
- Epic Phase 4 story `aam-23-lifespan-and-pre-warm`. Snippets: CHUNK-C3 in `aam-phase1-dev-snippets.md`.
- Verification against main (2026-07-27): PARTIALLY landed via aam-1. Already done: async engine creation/config (`utils/services/database.py`, `DB_ASYNC_POOL_SIZE=20/40`), single-connection warm-up, reverse-order dispose on shutdown, sync-first ordering with the unit-alias cache pre-warm (`main.py:28-47`). Remaining: the every-connection loop, the health-gate assertion, and the lifespan test. Do not re-implement what exists — the epic's first two ACs are effectively done; cite them as pre-landed in the QA walkthrough.
- Implementation hint: check out `pool_size` connections concurrently (e.g. `asyncio.gather` over `async_db_engine.connect()`) so each distinct pooled connection gets primed, then release; a sequential loop over one connection only warms one.
- Keep the warm-up best-effort (log-and-continue on failure) as today — a DB blip at boot must not crash-loop the task.
- Parallel-safe with aam-7/aam-8/aam-22; required before aam-24.
- Original BMAD story key: aam-23-lifespan-and-pre-warm.

## Status log
- 2026-07-27T17:15 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; scope re-verified against main (see Technical notes)
