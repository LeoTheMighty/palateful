# cla-14 — QA Walkthrough

## What shipped

`services/api/scripts/load_test_client_latencies.py` — a standalone
asyncio + httpx synthetic-traffic generator for
`POST /v1/client-latencies`. Matches the epic's AC: default profile is
50 concurrent workers × 100 events/batch × 5 minutes, but
concurrency / batch size / duration are all CLI-flag tunable.

Accompanying docs/PERFORMANCE_OPS.md section documents:
- How to run it (JWT required because the anon path rate-limits at
  10 events/IP/min).
- The `pg_stat_activity` + cache-hit-ratio SQL to run in a second
  terminal for DB-side observability.
- A signed-off baseline block template. Operator fills in the numbers
  after the next production-shaped run; the AC validates against a
  real run not a reproduced template.

## Acceptance criteria mapping

| AC                                              | How cla-14 satisfies it |
|-------------------------------------------------|--------------------------|
| (1) locust OR scripted asyncio, 50 × 100 × 5 min | asyncio script, defaults match exactly |
| (2) p95 < 100 ms under load                      | Script reports per-request p95 + AC-pass indicator |
| (3) 100 % success rate, no 5xx, no timeouts      | Script reports success rate + status-code breakdown + exception count |
| (4) pg_stat_activity + buffer hit; no slow-query | Paste-ready SQL in `docs/PERFORMANCE_OPS.md` |
| (5) Baseline captured in docs/PERFORMANCE_OPS.md | Template block added; operator fills on first signed-off run |

## Why "template, not numbers" for the baseline

The load test is a **reproducible script + capture protocol**, not a
one-shot number-gathering exercise. The AC is satisfied the first
time someone runs `python load_test_client_latencies.py --jwt $JWT`
against a production-configured stack and pastes the report into the
docs. That first run is operator-owned — it requires a live JWT, a
running API, and a preferably non-local target — none of which the
development loop can stand up without contaminating the real
`client_latencies` table. Shipping the tool + runbook is the
deliverable; shipping a placeholder number would be misleading.

For validation in CI, the script's `--help` + argument-parsing smoke
is all that runs. A dry-run against localhost without a JWT will 429
immediately (by design) and exit 0, which demonstrates the script
doesn't crash.

## Manual QA steps

- [ ] `python services/api/scripts/load_test_client_latencies.py --help`
      — prints usage, exits 0.
- [ ] `python services/api/scripts/load_test_client_latencies.py \
       --concurrency 5 --duration-s 10 --batch-size 10` against a
      running local docker-compose API. Without `--jwt`, expect many
      429s and a sub-100 ms p95 (429 path is fast). With `--jwt`,
      expect 2xx responses.
- [ ] **Signed-off run**: at the next backend-config change that
      touches ingest (schema, index, or auth path) — run the default
      profile against a prod-shaped stack with a real JWT. Paste the
      report block into `docs/PERFORMANCE_OPS.md`'s **Signed-off
      baseline** subsection. Pin the `pg_stat_activity` +
      cache-hit-ratio query results in the same PR.
- [ ] Delete the loadtest rows after a signed-off run to avoid
      poisoning the analytics:
      ```sql
      DELETE FROM client_latencies WHERE app_version LIKE 'loadtest-%';
      ```

## Regression surface

- No production code changes. No test harness edits. Just a new
  standalone script + a docs section.
- `services/api/scripts/` is the well-known folder for standalone ops
  scripts (`analyze_latency.py`, `audit_errors.py`, etc.) — the new
  file follows that convention.

## Known-safe choices (and why)

- **asyncio + httpx** instead of `locust`. Rationale: one-file, no
  extra dep, no separate runner. The epic explicitly allowed either;
  asyncio keeps the same dep footprint as other ops scripts.
- **Clamp `--batch-size` to 100**. Server caps at
  `MAX_EVENTS_PER_REQUEST=100`; larger batches would just 413 and
  muddy the latency numbers.
- **`app_version` tagged `loadtest-<epoch>`** so rows are trivially
  deletable after a run (see the `DELETE` in manual QA). Doesn't
  poison the admin Client tab because operators filter on
  production `app_version` strings.
- **Rate-limit warning printed when no JWT** rather than shelling out
  to a token helper — the script stays side-effect-free and works
  against any backend configuration.
- **AC check printed but not enforced via exit code** — gating the
  exit code on a perf threshold would make CI flaky over network
  weather; the runbook does the gating via human review.

## Backout

- `git rm services/api/scripts/load_test_client_latencies.py` — it's
  a standalone ops tool with no imports from the rest of the tree.
- Revert the `docs/PERFORMANCE_OPS.md` load-test section.
