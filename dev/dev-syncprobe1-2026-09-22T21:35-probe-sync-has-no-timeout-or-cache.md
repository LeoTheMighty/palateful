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
- [ ] **No sync cache.** Ship the documented absence plus a CI assertion
      (see below), not a TTL/single-flight port. Resolved 2026-09-22 with
      the filer (3b) and the author of both probe paths (0a) — supersedes
      the original "or" in this AC, which was written before the consumer
      was established.
- [ ] A bound constant lives here, and a test asserts rsh107's worker
      `healthCheck.interval` is not below it — failing if someone later
      drops the interval. Model: `test_probe_budget_fits_inside_the_tightest_health_check`
      in `test_db_probe.py`, which pins `PROBE_TOTAL_TIMEOUT_S < 3.0`
      against the ALB's `timeout = 3`. Wiring `interval` to that same
      source is a **request** to rsh107, which has a different owner — not
      a fait accompli.
- [ ] `_coerce_ttl` rejects `0` as it rejects `nan` (both defeat the budget),
      and `cached_verdict_async(ttl_s=...)` routes its argument through
      `_coerce_ttl` instead of trusting it.

## Why the obvious fix is wrong

**A module-global TTL cache in a process that starts fresh every 60
seconds rate-limits nothing, passes its tests, looks correct, and never
prevents a single connection.**

[M, 0a] rsh107 consumes the probe as a container health check —
`CMD-SHELL` running `python -m utils.services.db_probe`, `interval = 60`.
That is a new interpreter per tick, so `_cached` / `_inflight` module
globals start empty every invocation. The async cache works only because
uvicorn is one long-lived process serving `/v1/health`.

[M, 3b] Outside `db_probe.py` and its own tests, **nothing in the repo
calls `probe_sync`** — not `libraries`, `services`, `terraform` or `bin`.
So there is no in-process consumer for a cache to serve.

[I, 0a] At `interval = 60` the invocation rate already *is* one per
minute, which is what `DB_PROBE_TTL_S = 60` buys the async side. The
schedule is the rate limit — which is why the assertion above, not a
comment, is what keeps that true.

## Technical notes

- Land before or with rsh107; after it, the gap is in production.
- Sync timeouts have no `wait_for`: likely `statement_timeout` on the
  connection plus libpq `connect_timeout`, which is a behaviour change worth
  stating in the module docstring.

## Status log
- 2026-09-22T21:35 — filed from selfheal1's Phase 4 review (Edge Case Hunter,
  "adjacent but newly load-bearing"). Not introduced by selfheal1; promoted to
  a spec because selfheal1 makes `probe_sync` carry a verdict rsh107 acts on.
- 2026-09-22T22:25 — claimed by palateful-98. AC #3 resolved to the
  documented-absence branch with 3b (filer) and 0a (wrote both probe
  paths); rationale + measurements folded into the body above.
