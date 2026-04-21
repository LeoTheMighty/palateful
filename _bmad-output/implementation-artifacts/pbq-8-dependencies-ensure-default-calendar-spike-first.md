# Story pbq-8 — `_ensure_default_calendar` spike (no-op, regression test only)

**Status:** done
**Epic:** epic-perf-backend-query-tuning
**Depends on:** pbq-0 (query-count test helper — not actually used,
since this spike tests FastAPI dep-cache behavior directly rather
than mock query counts).

## Scope

Verify (per epic spike framing) that FastAPI's built-in `Depends`
cache already dedupes `get_current_user` invocations within one
request, so `_ensure_default_calendar` — called inside
`get_current_user` — does NOT fire multiple times even when a route
references the dependency through multiple parameter paths. Close
as a no-op with a regression test pinning the assumption.

## Implementation notes

- **Trace test, no code change.** The spike outcome was the
  expected one: FastAPI caches dependency results by callable
  identity within a single request (`use_cache=True` default on
  `Depends`). A minimal FastAPI test app with a route that depends
  on `get_current_user` TWICE (direct + aliased via a sub-
  dependency) triggers exactly one `_ensure_default_calendar`
  invocation. Test asserts `call_count == 1`.
- **No `request.state` cache added.** The epic's "If count is >1"
  implementation branch did NOT fire. `services/api/src/
  dependencies.py` is unchanged.
- **Stub surface.** The test stubs `utils.services.auth0
  .get_auth0_verifier` (async `verify_token` returns a minimal
  claims dict) + `get_database` override + spy on
  `_ensure_default_calendar` via `patch.object`. Doesn't require a
  live DB — exercises the FastAPI dep resolution path end-to-end.
- **Failure mode — if this test ever trips.** Count >1 means a
  recent refactor broke the dep-cache contract (e.g. someone
  wrapped `get_current_user` with a non-cached closure, or added
  a `Depends(get_current_user, use_cache=False)` callsite). The
  fix then is to restore cacheability; only if that's not
  viable should we fall back to the `request.state` short-circuit
  from the epic's plan-B branch.

## File list

- `services/api/tests/test_dependencies.py` [MODIFY] — adds
  `TestEnsureDefaultCalendarDepCaching::test_dep_cache_dedupes_
  ensure_default_calendar` as the spike's regression coverage.

No source code change.

## Acceptance criteria — coverage

Spike-phase ACs:

- AC1 — Request-tracing test counts actual
  `_ensure_default_calendar` invocations. ✅
- AC2 — If count is exactly 1: close the story as "FastAPI dep-
  cache already protects us; no change needed." Ship the trace
  test as regression coverage. ✅ COUNT IS 1. Story closes as
  no-op.
- AC3 — If count is >1: implementation-branch guard. N/A — did
  not fire.
- AC4 — p50/p95 before/after only if the implementation branch
  fires. N/A — no prod code change, no latency delta to measure.

## QA walkthrough

See `pbq-8-qa-walkthrough.md`.

## Rollback

```bash
git revert <pbq-8-commit>
```

Single commit that only adds a test file. Revert drops the
regression test; no functional change either way.
