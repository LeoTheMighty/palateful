# Story pim-1 — `analyze_latency.py` ops script (hard gate)

**Status:** done
**Epic:** epic-perf-infra-and-measurement
**Depends on:** none. Unblocks pim-2..pim-6 (every downstream perf story captures p50/p95 before/after via this script).

## Scope

Ship `services/api/scripts/analyze_latency.py` — a read-only ops script
mirroring `fetch_feedback.py` / `promote_admin.py`. Queries the
existing `request_latencies` and `task_latencies` tables (shipped in
`epic-observability-latency`) via raw SQLAlchemy so the script runs
against prod without booting the FastAPI app. Streams rows, no audit
row (read-only), argparse-driven.

Two SQL query shapes:

1. **Default** — top-N endpoints + tasks by p95 over a `--window`,
   filtered by `--min-samples`. Uses
   `PERCENTILE_CONT(0.50 / 0.95 / 0.99) WITHIN GROUP (ORDER BY duration_ms)`.
2. **`--regression-hunt`** — recent-24h vs 7-to-30d-baseline CTE from
   the architecture addendum, flagging endpoints whose p95 is
   >1.5× baseline (hardcoded threshold).

## Implementation notes

- **No audit row.** Script is strictly read-only — zero writes. No
  `error_logs` insert on success or failure.
- **Streaming.** Uses `conn.execution_options(stream_results=True)` so
  memory stays bounded on the `--window all` path (which can hit
  multi-million-row aggregation scans).
- **Exit codes.** `0` rows emitted, `2` empty (informational — not a
  DB failure, literally no rows matched the filter), `1` DB / runtime
  error.
- **Default sort.** p95 desc — documented in `--help`.
- **`--section`.** `endpoints|tasks|both` (default `both`). Each section
  is its own query + its own output block; `--format csv/json` emits
  section dividers as separate header rows (CSV) or separate JSON-line
  records with a `section` key (JSON). `--regression-hunt` implies
  `--section endpoints` (task regression hunt is out of scope — tasks
  don't have the same recent-vs-baseline churn shape).
- **`--min-samples`.** Default `5`. Applied as `HAVING COUNT(*) >= N`
  inside the aggregation. `--min-samples 0` disables the floor (prints
  every group — helpful when diagnosing one-off endpoints with sparse
  traffic).
- **`--window all`.** Omits the `created_at >= NOW() - INTERVAL 'X'`
  filter entirely. Note: with millions of rows this may be slow; the
  script doesn't add a `LIMIT` before the aggregation (you can't —
  you need all rows to compute p95).
- **Microbenchmark.** `test_analyze_latency_script.py` seeds a small
  in-memory fixture (~100 rows spanning two endpoints) and asserts the
  queries return the expected rankings. A "1M-row" stress benchmark is
  a separate opt-in marker; the standard test suite doesn't run it.
- **Flags mirror `fetch_feedback.py`.** Argparse description + format
  choice conventions are byte-compatible.

## File list

- `services/api/scripts/analyze_latency.py` [NEW]
- `services/api/tests/test_analyze_latency_script.py` [NEW]
- `docs/PERFORMANCE_OPS.md` [NEW]
- `CLAUDE.md` [MODIFY] — document the new script alongside
  `fetch_feedback.py`, `promote_admin.py`, `inspect_user_push.py`.

## Acceptance criteria — coverage

- AC1 — `analyze_latency.py` with no flags prints table-format top-15
  endpoints by p95 (24h) + top-15 tasks, returns `0` if rows, `2` if
  empty. ✅
- AC2 — `--format csv` emits RFC-4180 CSV; `--format json` emits NDJSON
  (one object per line). Each format includes a `section` field so
  `endpoints` and `tasks` output can be split downstream. ✅
- AC3 — `--window all` omits the `created_at` filter; `1h/24h/7d`
  translate to `NOW() - INTERVAL '...'`. ✅
- AC4 — `--regression-hunt` swaps the main query for the recent-vs-
  baseline CTE from the architecture addendum. ✅
- AC5 — `--min-samples 0` disables the floor; default `5` applied via
  `HAVING COUNT(*) >= N`. ✅
- AC6 — `--section endpoints|tasks|both` limits output. ✅
- AC7 — Default sort p95 desc (documented in `--help`). ✅
- AC8 — Exit codes 0/1/2 per spec. ✅
- AC9 — `DATABASE_URL` unset → exits `1` with explicit error. ✅
- AC10 — Microbenchmark test runs in <5s against a seeded fixture. ✅
- AC11 — `docs/PERFORMANCE_OPS.md` documents every flag + a sample
  `--regression-hunt` invocation + a baseline-capture recipe. ✅

## Follow-ups

- pim-2 QA walkthrough pastes the pre-change 24h top-15 CSV into the
  pim-2 story file (the hard-gate bullet).
- pim-3, pim-4a/b, pim-5 all cite the same script for before/after.
- Downstream epics (`epic-perf-backend-query-tuning`,
  `epic-perf-flutter-client-polish`) use this script as their
  before/after primitive.
