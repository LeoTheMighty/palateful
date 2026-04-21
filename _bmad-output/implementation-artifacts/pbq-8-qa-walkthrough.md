# QA walkthrough — pbq-8 `_ensure_default_calendar` spike

## What shipped

**No source code change.** The spike's hypothesis held: FastAPI's
built-in `Depends` cache dedupes `get_current_user` invocations
within one request, so `_ensure_default_calendar` (called inside
it) already fires exactly once per request. The story closes as a
no-op with a new regression test pinning the assumption.

## Before/after numbers

**N/A — no code change.**

- Request count of `_ensure_default_calendar`: **1** (pre- and
  post-spike). Asserted by the new test.
- `latency baseline`: no deployment; p50/p95 unchanged.

## How to verify

### 1. Local tests green

```bash
npx nx run api:test -- tests/test_dependencies.py::TestEnsureDefaultCalendarDepCaching --no-cov
# 1 passed
```

### 2. What the trace test proves

`test_dep_cache_dedupes_ensure_default_calendar` builds a minimal
FastAPI app with a route that depends on `get_current_user` through
two parameter paths (direct + aliased via a sub-dependency). It
stubs Auth0 + DB, installs a counter spy on
`_ensure_default_calendar`, and asserts the spy was called exactly
once.

The hard assertion:

```python
assert call_count["n"] == 1, (
    f"Expected 1 invocation of `_ensure_default_calendar` per "
    f"request (FastAPI Depends cache dedupes), got "
    f"{call_count['n']}. If >1, the spike's assumption no "
    f"longer holds and an explicit request.state cache is "
    f"needed (see pbq-8 story)."
)
```

If a future refactor breaks dep-caching (e.g. adding
`use_cache=False` to any `Depends(get_current_user)` callsite, or
wrapping the callable in a non-cacheable closure), this test trips
with a pointer to the story for context.

### 3. Plan-B (iff spike fails in future)

Per the epic, if count ever becomes >1, the implementation branch
would:

1. Short-circuit subsequent invocations by flagging
   `request.state.default_calendar_ensured = True` inside
   `_ensure_default_calendar`.
2. Require the `Request` be injected — add
   `request: Request = Depends(...)` to `get_current_user`.

Not needed today. Documented here so future-us has the context
without re-deriving.

## Checklist

- [x] Regression test asserts exactly 1 invocation under FastAPI's
      built-in dep cache.
- [x] No change to `services/api/src/dependencies.py`.
- [x] Story closes as no-op per epic's spike-phase decision
      branch.
- [x] Plan-B documented for future reference.

## Rollback

```bash
git revert <pbq-8-commit>
```

Drops the regression test. No functional behavior changes either
way.
