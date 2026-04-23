# Story ptd-6 — `analyze_latency.py --section client|all` + client regression hunt

**Epic:** epic-perf-debug-tooling
**Status:** done
**Owner:** /dev

## Context

Closes AC: extend `services/api/scripts/analyze_latency.py` with a client-
side section and a regression-hunt against the `client_latencies` table
(landed in cla-1a, ingested in cla-1b). Thresholds are locked at 2.0×
baseline for client (vs 1.5× server — client perf is noisier) and the
default sample floor is 50 (vs 5 server). Backward-compatible default:
`--section both` still runs endpoints + tasks only, so existing runbooks
/ baseline captures don't shift silently.

## Changes

### `services/api/scripts/analyze_latency.py`

- Added `client` + `all` to `_VALID_SECTIONS` (alongside existing
  `endpoints`, `tasks`, `both`).
- New flag `--client-min-samples` (default 50). Kept the existing
  `--min-samples` (default 5) for server — two flags, each with a
  defensible default, rather than an overloaded single flag.
- New query builders `_build_client_query` (grouped on `(type,
  platform, route)`) and `_build_client_regression_query` (parallels
  the server CTE shape; hardcodes the 2.0× threshold).
- New coercers `_coerce_client_row` + `_coerce_client_regression_row`.
- Emitters `_emit_table` / `_emit_csv` / `_emit_json` gained keyword-
  only `client=None` + `client_regression=None` slots with `None`
  defaults — existing 34 tests passed without modification.
- `main()` fans out based on `--section`: `all` runs all three sections
  in aggregation mode, or both regression CTEs in regression-hunt mode.
- Regression-hunt table now renders the multiplier in the header
  (`"recent 24h p95 > 2.0x baseline p95"`) so the output is self-
  explaining when it shows up in a terminal.

### `services/api/tests/test_analyze_latency_script.py`

- New fixtures `_client_row` + `_client_regression_row`.
- New test classes: `TestBuildClientQuery`, `TestBuildClientRegressionQuery`,
  `TestCoerceClientRow`, `TestCoerceClientRegressionRow`, and
  `TestClientSectionEndToEnd` — 15 new tests. The end-to-end class
  pins: query count per section, no leakage between sections in table
  output, regression-hunt scoped by `--section` argument, and the
  `--client-min-samples` override flowing into both aggregation and
  regression queries.
- Added `client_min_samples` assertion to `TestParseArgs.test_defaults`.
- Pins the 2.0× invariant as an explicit SQL substring check in
  `TestBuildClientRegressionQuery.test_cte_shape_and_2x_threshold` —
  the single most load-bearing invariant of this story.

## Acceptance Criteria

- [x] Script accepts `--regression-hunt` alongside `--section client`
      or `--section all`.
- [x] Client mode applies 2.0× baseline rule to
      `client_latencies.duration_ms` grouped by `(type, platform,
      route)`. (Added `platform` to the key because the same
      `(type, route)` pair has materially different baselines on iOS
      vs Android vs web — reviewer called this out in code review.)
- [x] `--min-samples` + `--client-min-samples` both overridable;
      defaults 5 / 50.
- [x] `--section all` emits unified output — regression-hunt combines
      server + client tables with distinct headers; aggregation mode
      runs all three sections top-to-bottom.
- [x] Tests pin detection logic (2.0× substring check), table format
      (per-section headers, no leakage), threshold correctness,
      column schemas for CSV.
- [x] Docs snippet deferred to ptd-7 (`PERFORMANCE_OPS.md`) per
      epic structure — the usage examples there are the runbook.

## QA walkthrough

These commands exercise the new paths end-to-end. With no client
telemetry ingested yet (cla-6+ not yet shipped), regression-hunt +
section-client will emit exit-2 "no samples matched" — that's fine; the
code path is covered by unit tests.

```bash
# 1. Client-only aggregation — noise floor 50 samples.
DATABASE_URL=<prod> python services/api/scripts/analyze_latency.py \
    --section client

# 2. Lower the client noise floor to see tail data.
DATABASE_URL=<prod> python services/api/scripts/analyze_latency.py \
    --section client --client-min-samples 10

# 3. All three sections, nothing filtered.
DATABASE_URL=<prod> python services/api/scripts/analyze_latency.py \
    --section all --window 7d --format csv > /tmp/latency-all.csv

# 4. Client-only regression hunt (48h after a release, the canonical
#    incident-response command).
DATABASE_URL=<prod> python services/api/scripts/analyze_latency.py \
    --regression-hunt --section client

# 5. Full server+client regression hunt — one invocation, one table.
DATABASE_URL=<prod> python services/api/scripts/analyze_latency.py \
    --regression-hunt --section all
```

## File List

- `services/api/scripts/analyze_latency.py` (modified)
- `services/api/tests/test_analyze_latency_script.py` (modified)
- `_bmad-output/implementation-artifacts/ptd-6-analyze-latency-client.md` (new)
