---
hash: apisweep
type: debug
created: 2026-09-22T09:00:00-06:00
title: "Something is enumerating the prod API: unauthenticated sweeps of ~65 endpoints in ~5 s"
from: debug/debug-cartdec-2026-09-22T09:00-shopping-cart-decimal-quantity-crash.md
spawned: []
status: ready
owner: null
branch: null
---

## Goal

`request_latencies` shows bursts of unauthenticated requests across ~65
endpoints in ~5 seconds — all GET, 0–2 ms, including POST-only routes (hence
405) and routes missing the auth dependency's inputs (hence 422). Seen on
2026-09-11 21:42 and 2026-09-14 10:02 (measured by palateful-4f; first noticed
here as a 405/422 cluster on shopping routes while root-causing
debug-cartdec, where it was a false lead).

It is not the cart failure. It is worth knowing what it is: a scanner, an
uptime or monitoring tool misconfigured to hit every route, or something of
Leo's own.

## Acceptance criteria

1. Identify the source (IP / user agent / cadence from API access logs).
2. Decide: expected (document and exclude from metrics) or not (block / rate-limit).
3. If it is excluded from metrics, make sure the exclusion cannot hide a real
   client's failures — the cart outage was already invisible to server metrics.

## Status log

- 2026-09-22T09:00-06:00 — filed from debug-cartdec. Evidence is palateful-4f's
  measurement plus the 405/422 cluster in `request_latencies`; source not yet
  identified. Only unauthenticated GETs observed; no writes.
