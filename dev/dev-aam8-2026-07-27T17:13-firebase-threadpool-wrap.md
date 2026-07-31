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
- 2026-07-28T15:57:17.748Z — loop iteration 1: Implemented the four async send variants in push_notification.py dispatching via run_in_threadpool, with 6 new tests proving threadpool dispatch and off-loop FCM execution; utils push/bridge tests, lint, and worker:test all green.
  - Change: libraries/utils/utils/services/push_notification.py now exposes send_to_token_async / send_to_tokens_async / send_to_user_async / send_to_users_async, each wrapping the full sync body (FCM send + error_logs write + token-cleanup commit) in await run_in_threadpool; sync methods unchanged so the worker contract stays frozen (AC-1)
  - Change: New libraries/utils/test/test_push_notification_async.py (6 tests) mirroring test_notifications_bridge.py patterns: threadpool-dispatch assertions per variant, a real-threadpool test asserting messaging.send runs off the event-loop thread, and a log-only round-trip (AC-3)
  - Change: Verified npx nx run worker:test green against the library diff (AC-4), utils:lint green, all 40 push/bridge tests passing, and coverage.xml shows zero missed lines in the new async block
  - Learning: utils full test suite is red on origin/main itself: commit 5a6174de committed red-stage TDD tests (test_db_credential_provider.py, test_rotation_redeploy_handler.py) for modules that don't exist yet — baseline is 5 failed + 23 errors confined to those two files; do not treat them as regressions or try to fix them under this spec
  - Learning: Fresh worktree env setup: utils:test runs 'poetry run pytest' from the WORKSPACE ROOT env, so root 'poetry install' is required (utils:install alone is insufficient); worker:test runs in services/worker and needs its own 'npx nx run worker:install' first — 'unrecognized arguments: --cov' means missing deps, not a config bug
  - Learning: Repo ruff style groups first-party 'utils.*' imports with third-party (no blank line after 'import pytest') — ruff --fix handles it; run ruff on new test files since utils:lint only checks the utils/ package dir
- 2026-07-28T16:03:20.623Z — loop iteration 2: Completed the aam-8 event-loop audit (AC-2) with a full caller-by-caller census in the QA walkthrough and retired the stale 'aam-8 hasn't landed' comments at the four API callsites, with all suites, lint, and 100% coverage verified green.
  - Change: Authored _bmad-output/implementation-artifacts/aam-8-qa-walkthrough.md containing the AC-2 audit: grep proof that messaging.send* exists only inside push_notification.py, plus a four-bucket callsite census (sync domain notify helpers, direct endpoint sends, utils meal_event_notifications, user/push_tokens) verifying every async-handler path reaches Firebase via notify_via_threadpool or run_in_threadpool, alongside the manual verification checklist and production-safety/observability notes.
  - Change: Retired stale 'aam-8 hasn't landed' comments in services/api/src/api/v1/invitations/accept_invitation.py, invitations/send_invitation.py, invite_links/join_via_link.py, and routers/v1/invitations_router.py, rewording them to state the run_in_threadpool wraps are equivalent to the new send_to_user_async variant and intentionally stay (comment-only, no behavior change).
  - Change: Verified the full gate set green against the combined diff: utils push/bridge suites (40 tests), npx nx run worker:test (worker contract frozen), npx nx run api:test at 100% coverage, and utils/api lint.
  - Learning: The invitations router docstring previously promised aam-8 would remove the handler-level run_in_threadpool wraps; the audit concluded the explicit wraps should stay (they are the same hop the async variants perform internally), so no callsite migration to the *_async variants is needed for this spec — it lands dark.
  - Learning: The epic's '28 callsites' figure is fully stale: the census found every async-reachable push path already hops through a threadpool, so aam-8 reduces to the in-library async variants (landed in iteration 1) plus this audit and comment cleanup.
