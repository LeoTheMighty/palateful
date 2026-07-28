---
hash: aam8
type: dev
created: 2026-07-27T17:13:00-06:00
title: Firebase messaging.send threadpool wrap — async-safe push send variant plus sync-on-loop audit
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: in-progress
owner: /devx-loop-2026-07-27T21-15-34-312-36147
blocked-by: []
branch: feat/dev-aam8
---

## Goal
Guarantee no Firebase Admin `messaging.send*` call ever runs on the event loop. Add an async variant (`send_push_async` or equivalent `run_in_threadpool` wrap) to `libraries/utils/utils/services/push_notification.py` and audit every async-path caller in `services/api/src/` to confirm it reaches Firebase via a threadpool hop (either the new variant or the existing `notify_via_threadpool` bridge).

## Acceptance criteria
- [ ] `libraries/utils/utils/services/push_notification.py` exposes both a sync send path (unchanged — worker keeps using it) and an async path that dispatches `messaging.send(...)` (line ~316) and `messaging.send_each_for_multicast(...)` (line ~375) via `await run_in_threadpool(...)`. Neither variant deprecated.
- [ ] Audit (grep, pasted into QA walkthrough): every caller of the push service reachable from an `AsyncEndpoint`/async router handler goes through `notify_via_threadpool` or the new async variant — no direct sync `messaging.send` on the event loop anywhere in `services/api/src/`.
- [ ] Existing push_notification tests stay green; new test verifies the async path invokes the threadpool (mocked `messaging`), mirroring `libraries/utils/test/test_notifications_bridge.py` patterns.
- [ ] `npx nx run worker:test` green against the library diff (worker contract frozen — epic design principle 13).
- [ ] Coverage stays at 100%.

## Technical notes
- Epic Phase 2 story `aam-8-firebase-threadpool-wrap`. Snippets: CHUNK-C6 in `aam-phase1-dev-snippets.md` — "already partially done by the domain chunks via `notify_via_threadpool`; grep for any remaining sync `messaging.send` call on the event loop".
- Verification against main (2026-07-27): the heavy lifting mostly landed indirectly. `notify_via_threadpool` bridge exists (`libraries/utils/utils/services/notifications_bridge.py:57`, commit `4ea2212` aam-foundations-notify-threadpool-helper) and domain notification helpers use it; several direct callers (e.g. `services/api/src/api/v1/admin/send_test_push.py:139`, `invitations/send_invitation.py:174`, `invitations/accept_invitation.py:114`) already wrap via `run_in_threadpool`. But `push_notification.py` itself still calls `messaging.send` / `send_each_for_multicast` directly with no async variant — the epic's "28 callsites" figure is stale; this story is now mostly an audit + the in-library async variant + tests.
- aam-19 (user/push-tokens, formerly blocked by aam-8) already landed on main — so this lands as hardening, not a blocker for domain work.
- Original BMAD story key: aam-8-firebase-threadpool-wrap.

## Status log
- 2026-07-27T17:13 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; scope re-verified against main (see Technical notes)
- 2026-07-28T09:51:06-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
