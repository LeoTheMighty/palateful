---
hash: aam25
type: dev
created: 2026-07-27T17:17:00-06:00
title: Sync-in-async startup guard — fail fast if API handler code imports the sync Database
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: ready
blocked-by: [aam24]
branch: feat/dev-aam25
---

## Goal
Add a fail-fast guard that prevents sync SQLAlchemy from ever creeping back onto the event loop: at startup (and in CI), walk the API handler import graph and assert no module under the API/router trees imports the sync `Database` outside the whitelist.

## Acceptance criteria
- [ ] `services/api/src/main.py` startup registers an import-time check asserting no module under `services/api/src/api/v1/**/*.py` or `services/api/src/routers/v1/**/*.py` imports `from utils.services.database import Database` (sync).
- [ ] Whitelist: `services/api/src/middleware/error_tracking.py`, `services/api/src/middleware/latency_capture.py` (via writer), `services/api/src/main.py` (unit-alias pre-warm + error-log sub-pool init), `services/api/src/manage.py`.
- [ ] Test (`services/api/tests/test_sync_async_guard.py` per snippets CHUNK-C1): hand-crafted regression — add a sync import to an API handler file (temp module or monkeypatch) and assert startup raises.
- [ ] CI wiring: the guard runs as part of `npx nx run api:test`, so a regression fails CI at merge time, not prod startup.
- [ ] Coverage stays at 100%.

## Technical notes
- Epic Phase 6 story `aam-25-sync-in-async-startup-guard`. Snippets: CHUNK-C1 in `aam-phase1-dev-snippets.md` (note: snippets sequence C1 before C4; the epic puts it in Phase 6 after aam-24 — following the epic, since the guard would fire on today's legitimate holdouts (WS auth in `recipe_book_router.py:229` / `shopping_list_router.py:449`, `chat_router.py`, `api/v1/user/create_user.py`) until aam-24 removes them).
- Verification against main (2026-07-27): NOT landed — no guard code exists (`rg 'startup_guard|assert_no_sync'` over `services/api/src` is empty). The whitelist in the epic AC matches current reality: `error_tracking.py` will still import sync `Database` after aam-22 (threadpool-wrapped, sub-pool), which is exactly why it's whitelisted.
- Implementation hint: a static scan (rg/ast over the two trees) run from a startup hook AND exposed as a plain pytest is simpler and more deterministic than runtime session-enumeration; the epic's AC is phrased as an import-graph walk — either satisfies it as long as the hand-crafted regression test raises.
- Prefer pattern-matching aliased imports too (`import utils.services.database`, `from utils.services import database`) so the guard can't be dodged accidentally.
- Original BMAD story key: aam-25-sync-in-async-startup-guard.

## Status log
- 2026-07-27T17:17 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; scope re-verified against main (see Technical notes)
