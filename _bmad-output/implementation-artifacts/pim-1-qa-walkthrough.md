# QA walkthrough — pim-1 `analyze_latency.py`

## What shipped

Read-only ops script `services/api/scripts/analyze_latency.py`. Streams
nothing because the aggregation collapses to `<= --top` rows server-
side; materializes results, coerces cells, emits one of three formats
(`table`, `csv`, `json`).

## Before/after numbers

**N/A — pim-1 is the hard gate. It ships the measurement primitive; it
has no p95 delta of its own.** The first real baseline capture happens
before pim-2 merges (see pim-2 QA walkthrough).

## How to verify in prod

### 1. Local test suite is green

```bash
cd services/api && poetry run pytest tests/test_analyze_latency_script.py -v
# 34 passed
```

### 2. Run against prod with a short window

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 1h --format table
```

Expected: `endpoints` section lists the hottest paths with p50/p95/p99;
`tasks` section lists Celery tasks with their latency breakdown.
Exit code 0 if rows exist; 2 if the 1h window is empty (common on a
quiet cluster); 1 only if the DB isn't reachable.

### 3. Pin the CSV baseline for the perf initiative

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --top 15 --format csv > /tmp/pim-1-baseline-$(date +%Y%m%d).csv
```

Save this file at repo root (temporarily) or paste its contents into
the pim-2 QA walkthrough. Every downstream perf story will diff
against this snapshot.

### 4. Run a regression hunt

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --format table
```

Expected: either the "no regressions over threshold" line (if every
endpoint's recent-24h p95 is within 1.5× its 7-to-30d baseline), or a
small set of rows sorted by `% increase` desc. Anything above 50%
increase is a candidate for `epic-perf-backend-query-tuning`.

### 5. Confirm exit codes

```bash
# Missing DATABASE_URL → exits 1
unset DATABASE_URL && python services/api/scripts/analyze_latency.py ; echo $?
# → 1

# Empty window → exits 2 (dev DB with no traffic)
DATABASE_URL=<dev-url> python services/api/scripts/analyze_latency.py \
    --window 1h --min-samples 100 ; echo $?
# → 2 (floor is so high nothing qualifies)

# Normal run with data → exits 0
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py ; echo $?
# → 0
```

## Acceptance criteria — all met

- AC1 ✅ default flags = top-15 endpoints + tasks by p95, 24h window
- AC2 ✅ `--format csv` emits RFC-4180 CSV with `section` column;
  `--format json` emits NDJSON (one object per line)
- AC3 ✅ `--window all` drops the `created_at` filter;
  `1h/24h/7d` interpolated into `NOW() - INTERVAL '...'`
- AC4 ✅ `--regression-hunt` CTE matches the architecture addendum
  (recent-24h vs 7-to-30d-baseline, `recent.cnt >= 10`, `recent.p95 >
  baseline.p95 * 1.5`)
- AC5 ✅ `--min-samples 0` drops `HAVING`; default `5` applied
- AC6 ✅ `--section endpoints|tasks|both` limits queries + output
- AC7 ✅ Default sort `ORDER BY p95_ms DESC NULLS LAST` (documented
  in `--help` via description text)
- AC8 ✅ Exit codes 0/1/2
- AC9 ✅ `DATABASE_URL` unset → SystemExit(1) with explicit stderr
- AC10 ✅ Microbenchmark asserts 1000 endpoint + 1000 task rows format
  in <1s
- AC11 ✅ `docs/PERFORMANCE_OPS.md` documents every flag, baseline
  capture, post-change diff, regression-hunt recipe, and low-traffic
  drill-in

## Follow-ups

- pim-2 merges the parameter group + PI + slow-query log; before it
  merges, paste the 24h top-15 CSV into `pim-2-qa-walkthrough.md`.
- pim-3 (instance upgrade) captures the same CSV immediately before
  and >=1h after the maintenance-window reboot; the brag metric is the
  `p95` delta on `GET /v1/meals?scope=home` and the four other hot
  paths.
