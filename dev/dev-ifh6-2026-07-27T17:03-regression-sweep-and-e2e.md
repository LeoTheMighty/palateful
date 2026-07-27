---
hash: ifh6
type: dev
created: 2026-07-27T17:03:00-06:00
title: Regression sweep + e2e
from: _bmad-output/planning-artifacts/epic-import-flow-hardening.md
status: ready
blocked-by: [ifh3, ifh4, ifh5]
branch: feat/dev-ifh6
---

## Goal
End-to-end verification of the hardened import pipeline: transient failures self-heal invisibly, permanent failures surface immediately with friendly copy and (on iOS) a system notification, pre-epic App Group records remain compatible, the Decimal cast regression stays dead, and reconciler performance is unchanged. Closes out the epic with a staging spot-check that request_id propagation is live.

## Acceptance criteria
- [ ] e2e: import a URL that returns 502 → reconciler backs off, retries, eventually succeeds; user sees no failure UI.
- [ ] e2e: import a file with `unsupported_mime` (415) → record marked failed immediately, FailedImportsBanner appears with friendly copy on next foreground; UNUserNotification fires on iOS if permission granted.
- [ ] e2e: PUT to S3 fails with network error inside extension → record persists with `failed: true, error_code: s3_put_failed, retryable: false`; user sees the failure surface in app.
- [ ] e2e: import a recipe whose ingredients include a non-null `quantity_normalized` → recipe-detail screen renders without throwing the `as num?` cast error. (Regression for the cart bug class on the recipe surface.)
- [ ] e2e: backwards-compat — App Group records written by the pre-epic share extension (no `failed`/`retryable` fields) are still picked up by the reconciler and treated as retryable until first response.
- [ ] Performance: reconciler tick latency unchanged within ±5ms on a list of 10 pending records (microbenchmark in test).
- [ ] Spot-check via `audit_errors.py --drill api:APIException` after staging deploy: at least one drill row has a non-null `request_id` from the `/v1/recipe-books/.../import` path.
- [ ] Sprint-status updated, retrospective: optional.

## Technical notes
- Exercises the full surface delivered by ifh-1..ifh-5; must land last (blocked-by ifh3, ifh4, ifh5 — ifh-1/ifh-2 already on main as 88c04d7 / 51f76f1).
- The staging spot-check uses `services/api/scripts/audit_errors.py` drill mode (read-only, safe to run freely); requires a staging deploy after the backend stories — see epic "Stories → ifh-6" section.
- Backwards-compat scenario pins the epic's additive-App-Group-schema guarantee (epic "Infrastructure changes": Swift writes and Dart reads both default missing fields to safe values).
- Decimal regression e2e complements the unit/wire tests pinned in ifh-2; this one goes through the actual recipe-detail screen render.
- Original BMAD story key: ifh-6-regression-sweep-and-e2e. Full context: the story's section in the epic file.

## Status log
- 2026-07-27T17:00 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; predecessor stories ifh-1 (88c04d7), ifh-2 (51f76f1) already on main
