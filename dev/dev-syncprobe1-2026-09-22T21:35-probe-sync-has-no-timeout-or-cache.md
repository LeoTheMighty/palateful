---
hash: syncprobe1
type: dev
created: 2026-09-22T21:35:00-06:00
title: probe_sync has neither a total timeout nor the single-flight cache its async twin has
from: dev/dev-selfheal1-2026-09-20T11:45-503-only-when-a-restart-can-fix-it.md
status: ready
owner: null
branch: null
---

## Goal

`db_probe.probe_sync` is about to become a production health surface
(rsh107's worker health check consumes it), and it is missing two
protections its async twin documents at length.

**No total timeout.** `probe_async` wraps the whole attempt in
`asyncio.wait_for` because — per the module's own comment — libpq's
`connect_timeout` bounds *establishment only*, and a half-open TCP after an
RDS failover completes the handshake and then hangs in `SELECT 1`.
`probe_sync` sets `connect_timeout` and nothing else, so it can block
indefinitely inside `conn.execute`. A worker health check that never returns
scores like a failed one.

**No rate limit.** The whole "Rate limiting" section of the module docstring
describes `cached_verdict_async`. `probe_sync` is uncached and not
single-flight, so an rsh107 check on a 30s timer opens a fresh connection
every tick — and after rsh105 (FR-5), a `get_secret_value` every tick too.

## Acceptance criteria

- [ ] `probe_sync` is bounded by a total budget equivalent to
      `PROBE_TOTAL_TIMEOUT_S`, covering `SELECT 1`, not just connect. A
      hanging `execute` must classify `UNREACHABLE`, not block.
- [ ] A test that hangs the query (not the connect) and asserts the budget
      holds — the async twin's `test_probe_times_out_rather_than_hanging` is
      the model.
- [ ] A sync equivalent of the TTL + single-flight cache, or an explicit
      documented decision that rsh107's caller owns the rate limit.
- [ ] `_coerce_ttl` rejects `0` as it rejects `nan` (both defeat the budget),
      and `cached_verdict_async(ttl_s=...)` routes its argument through
      `_coerce_ttl` instead of trusting it.

## Technical notes

- Land before or with rsh107; after it, the gap is in production.
- Sync timeouts have no `wait_for`: likely `statement_timeout` on the
  connection plus libpq `connect_timeout`, which is a behaviour change worth
  stating in the module docstring.

## Status log
- 2026-09-22T21:35 — filed from selfheal1's Phase 4 review (Edge Case Hunter,
  "adjacent but newly load-bearing"). Not introduced by selfheal1; promoted to
  a spec because selfheal1 makes `probe_sync` carry a verdict rsh107 acts on.
