# Story aam-5: Migration runbook

**Status**: done
**Epic**: epic-api-async-migration
**Phase**: 1 — Foundations

## Acceptance Criteria

1. New `docs/async-migration-runbook.md` exists at repo root.
2. Per-handler conversion recipe (8-step loop) — base class swap, query
   rewrite, `selectinload` rule, `await`-every-DB-call, `run_in_threadpool`
   for sync SDKs, MCP-tool flip, test conversion.
3. `selectinload` / `joinedload` / `noload` decision matrix.
4. Greenlet-bridge-forbidden rule + whitelist of OK-to-stay-sync paths.
5. **Lazy-load audit procedure**: explicit grep one-liner for the
   response-builder path + structured eyeball-audit checklist for the
   QA walkthrough.
6. **Dual-register + observation-window procedure**: how to register
   the async router under canonical path + sync sibling under ignored
   prefix; how to flip back in <5 min.
7. **Rollback procedures** (during observation window AND after) with
   specific commands.
8. **Session-per-request lifecycle diagram** + invariants
   (session-per-request, no shared session in `asyncio.gather`).
9. **Per-domain story checklist** structured for direct paste into
   each story's QA walkthrough.
10. **MCP-specific section**: `call_endpoint_async` swap recipe + MCP
    smoke test command.
11. Decision log capturing the party-mode-locked choices so future
    runbook amendments don't accidentally undo them.
12. Referenced from every Phase 3 story's ACs (handled by the epic
    file, not this story directly).

## File List

- `docs/async-migration-runbook.md` (new)
