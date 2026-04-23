# Performance Ops

Operator runbook for the Palateful Performance Health Initiative.

All performance-related decisions (parameter-group tunes, instance-class
upgrades, pool bumps, client-polling merges) are grounded in before/after
numbers captured via `services/api/scripts/analyze_latency.py`. Every
perf story's QA walkthrough pastes the CSV output of this script for
the target endpoint's `normalized_path` — no fix lands without a
measured delta.

## `analyze_latency.py`

Read-only script. Queries `request_latencies` + `task_latencies` (the
Postgres-backed tables shipped by `epic-observability-latency`) and
surfaces the top-N slowest endpoints + tasks by p95. Writes nothing,
no audit row.

### Flags

| Flag | Default | Description |
|---|---|---|
| `--window` | `24h` | `1h`, `24h`, `7d`, or `all`. Controls the `created_at >=` filter. |
| `--top` | `15` | Rows per section. Clamped to `[1, 100]`. |
| `--format` | `table` | `table` (human-readable), `csv` (RFC-4180), `json` (NDJSON, one object per line). |
| `--regression-hunt` | off | Swaps the main query for a recent-24h vs 7-to-30d-baseline CTE. Flags endpoints whose recent p95 is > 1.5× baseline p95 with >= 10 recent samples. Default scope: endpoints (`--section endpoints`). Combine with `--section client` / `all` to extend. |
| `--min-samples` | `5` | `HAVING COUNT(*) >= N` noise floor for endpoints/tasks. `0` disables. |
| `--client-min-samples` | `50` | Noise floor for the client section. Client perf is noisier (network variance, device heterogeneity) so the default is higher than server. `0` disables. |
| `--section` | `both` | `endpoints`, `tasks`, `client`, `both` (endpoints + tasks — backward-compatible default), or `all` (endpoints + tasks + client). |

**Default sort**: p95 desc across every shape.

### Exit codes

- `0` — rows emitted.
- `1` — DB / runtime error, or `DATABASE_URL` unset.
- `2` — zero rows matched (informational — not a failure).

### Recipes

#### Capture the pre-change baseline

Run this before any infra change (pim-2/pim-3/pim-4a/pim-4b/pim-5)
lands. Paste the resulting CSV into the target story's QA walkthrough.

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --top 15 --format csv > /tmp/baseline-$(date +%Y%m%d).csv
```

#### Capture the post-change delta

After the change has been live for >= 1h (enough to settle), rerun the
same command as `post.csv` and diff:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --top 15 --format csv > /tmp/post-$(date +%Y%m%d).csv

diff /tmp/baseline-*.csv /tmp/post-*.csv | less
```

The brag metric is the delta from the pinned pre-change baseline for
the five hot-path endpoints:

- `GET /v1/meals?scope=home`
- `GET /v1/recipes`
- `GET /v1/shopping-lists`
- `GET /v1/activities`
- `GET /v1/calendars`

#### Is it backend or frontend? (`--section all`)

Once `epic-perf-client-analytics` has 24h of data in `client_latencies`,
one invocation prints server + client tables together. Use this when
the app "feels slow" and you don't know which side is to blame:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section all --window 24h --top 20
```

Example output (abbreviated):

```
endpoints (top by p95 desc)
  METHOD  PATH                             COUNT   P50   P95   P99   MAX
  GET     /v1/recipes/{recipe_id}            450   120   340   920  1800

tasks (top by p95 desc)
  TASK                     STATUS   COUNT   P50    P95    P99    MAX
  worker.import.ocr_extract  success  100  40000  55000  85000 120000

client (top by p95 desc)
  TYPE          PLAT   ROUTE                  COUNT   P50   P95   P99   MAX
  route_paint    ios   /recipes/:id            180   200  1100  2400  4500
  first_paint    web   /home                    95   380   820  1200  1600
```

Compare the client row's p95 against the matching server path — if
the server-side p95 is stable but the client paint jumped, the
regression is in Flutter (or network); if both jumped, it's backend.

#### Client-side regression hunt

Once client samples are flowing, extend the regression hunt to the
client table. Client threshold is **2.0×** (not server's 1.5×) because
client metrics are noisier; sample floor defaults to 50 instead of 10.

```bash
# Client only.
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --section client --format table

# Server + client in one emission.
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --section all --format json \
    > /tmp/regressions-$(date +%Y%m%d).jsonl
```

The client regression block groups by `(type, platform, route)`, so
an iOS-only `route_paint` regression on `/home` is a distinct row from
the Android version — useful when a platform-specific bug hits only
one client.

#### Hunt for regressions

Run this daily (or after every deploy) to catch endpoints that drifted
in the last 24h vs their 7-to-30d baseline. Anything with `pct_increase
> 50` feeds directly into `epic-perf-backend-query-tuning`.

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --regression-hunt --format table
```

Sample output:

```
regression_hunt (recent 24h p95 > 1.5x baseline p95, sorted by % increase)
  METHOD  PATH                                                 BASE_P95    CUR_P95        %    COUNT
  GET     /v1/meals                                               150.0      500.0    233.3       57
  GET     /v1/shopping-lists                                       80.0      200.0    150.0       42
```

#### Drill into a specific endpoint (no noise floor)

When you suspect a low-traffic endpoint, bypass the `HAVING COUNT(*)
>= 5` floor so every group is emitted. Use with `--top` generously.

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section endpoints --window 1h --min-samples 0 --top 100
```

#### Task-side hot spots

Celery tasks live in a sibling `task_latencies` table and follow the
same PERCENTILE_CONT aggregation. Use `--section tasks` to surface
slow worker tasks independently.

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --section tasks --window 7d --format table
```

### Design choices

- **Streaming not buffered.** The aggregation collapses to `<= --top`
  rows inside Postgres, so the Python path isn't memory-bound.
- **No audit row.** Read-only: nothing to record.
- **Interval literals are hardcoded in SQL, not bound params.**
  `NOW() - INTERVAL '...'` doesn't accept a bind parameter in the
  `INTERVAL` literal; we interpolate from a closed enum of
  `{1h, 24h, 7d, all}` so there's no injection surface.
- **`--window all` allows no `created_at` filter.** On prod this means
  a full-table aggregate scan — expect seconds, not milliseconds. Use
  sparingly.

## Redis + Auth0 JWKS cache

Shipped in pim-5. ElastiCache (`cache.t4g.micro`, single node, no
multi-AZ) holds the Auth0 JWKS so it's warm across task restarts and
across concurrent task cold-starts.

**Fail-open semantics are non-negotiable.** If Redis is unreachable
(timeout, connect-refused, hostname invalid), the Auth0 verifier falls
back to its original in-memory `_jwks: dict` cache and the request
succeeds. Zero 5xx from Redis downtime — a Redis outage manifests as
"first request per task pays the cold-fetch penalty again," not
"requests fail."

If Redis itself is genuinely degraded (not just unreachable) and you
suspect stale JWKS, you can force a fresh fetch by bouncing the API
task — the new task starts with no Redis cache entry, the fail-open
path triggers, and fresh JWKS get repopulated into both tiers.

**ElastiCache single-node caveat**: one-zone deployment means an AZ
failure takes Redis with it. That's acceptable *only* because the
JWKS cache is fail-open. Any future use of Redis for application data
(session state, generic caching, etc.) would require revisiting the
multi-AZ decision.

## Parameter group — palateful-prod-pg16-perf

Introduced in pim-2. Static params (require reboot):

- `shared_buffers = 256MB`
- `max_connections = 80`

Dynamic params (hot-apply):

- `work_mem = 8MB`
- `maintenance_work_mem = 128MB`
- `effective_cache_size = 1500MB`
- `log_min_duration_statement = 100` (every query >100ms hits the
  slow-query log)

**Slow-query log consumption**: CloudWatch Logs Insights against the
`/aws/rds/instance/palateful-prod-db/postgresql` log group.

### Post-apply verification

```sql
SHOW shared_buffers;        -- expect 256MB
SHOW max_connections;       -- expect 80
SHOW work_mem;              -- expect 8MB
SHOW log_min_duration_statement;  -- expect 100
```

### Rollback

Parameter group is its own resource. Revert the terraform module to
remove the custom parameter group and the RDS instance falls back to
the default `postgres16` parameter group. Static params require one
reboot to unwind.

## RDS instance — db.t4g.small

Upgraded from `db.t4g.micro` in pim-3. Applies during the tue 07:00-08:00
UTC maintenance window.

### Rollback

```hcl
instance_class = "db.t4g.micro"
apply_immediately = true
```

~5 minute reboot. `deletion_protection=true` stays on throughout.

**CPUCreditBalance alarm**: post-upgrade, a CloudWatch alarm fires if
`CPUCreditBalance < 100` to catch any regression back to burst-credit
exhaustion.

## Connection pool

Shipped in pim-4b.

- `DB_POOL_SIZE = 20` (was 10) — env-overridable
- `DB_MAX_OVERFLOW = 40` (was 20) — env-overridable

Fits under `max_connections = 80` with 20 reserved for
beat/worker/migrator/`psql` sessions.

**Gate**: pim-4b cannot merge until pim-2's static-param reboot has
completed and `SHOW max_connections;` returns `80` in prod.

## ALB health check

Shipped in pim-4b.

- `interval = 60s` (was 30s)
- `timeout = 3s` (was 5s)

Trims health-check volume on the hot path. Hung-task detection still
fires within 2 min; ECS deployment circuit breaker still gates failed
deploys.

## Client-latency ingest kill-switch (`cla-1c`)

Shipped in cla-1c as the escape hatch for the client-side analytics
pipeline (`epic-perf-client-analytics`).

The pipeline ships ~125k rows/day into `client_latencies` at normal
scale. If the Postgres instance starts pushing against IOPS / storage
/ connection budget *during an incident*, we need to stop the writes
instantly — without shipping a new Flutter build (TestFlight / Play
review lag measured in days).

### Contract

- `GET /v1/flags/perf` returns `{ingest_enabled: bool, sampling_rate: float}`.
- Unauthenticated. Anonymous pre-login clients honor the switch too.
- Flutter fetches once per cold-start (after Firebase init), caches
  the result for 5 min, and **treats any error / timeout / unreachable
  response as defaults-on**. The endpoint therefore never returns a
  4xx / 5xx on the happy path.

### Environment variables (ECS task definition)

| Env var | Default | Effect |
|---|---|---|
| `CLIENT_LATENCY_INGEST_ENABLED` | `true` | When `false`, Flutter drops every enqueue on the floor — no retry, no disk buffer. Backend ingest endpoint keeps accepting (in case late-cached clients still POST), but write volume collapses within 5 min as clients refresh their flag cache. |
| `CLIENT_LATENCY_SAMPLING_RATE` | `1.0` | Fraction in `[0.0, 1.0]`. Client samples events at this rate BEFORE batching. Soft lever — use this when volume is annoying but not an incident (e.g. drop to `0.1` during a traffic burst). |

### Runbook: flip the kill-switch

1. Confirm the pain source. `bin/prod-script audit_errors.py --service api --window 1h` + `bin/prod-logs` + CloudWatch RDS CPU / IOPS.
2. ECS → `palateful-api-prod` service → Task definitions → create new revision.
3. Container env: set `CLIENT_LATENCY_INGEST_ENABLED=false` (or `CLIENT_LATENCY_SAMPLING_RATE=0.1` for the softer lever).
4. Update service to the new revision. Rolling deploy — zero downtime.
5. Within 5 min every client refreshes its flag cache and stops enqueuing.
6. Row-rate drop visible via `psql -c "SELECT count(*) FROM client_latencies WHERE created_at > now() - interval '5 minutes';"` — should trend to ~0.

### Re-enable

Reverse step 3 (`CLIENT_LATENCY_INGEST_ENABLED=true`, sampling back to `1.0`) and redeploy. Expect up to 5 min before field clients refresh.

### Reference

- Endpoint: `services/api/src/api/v1/flags/get_perf_flags.py`
- Router: `services/api/src/routers/v1/flags_router.py`
- Config: `services/api/src/config.py` (`client_latency_ingest_enabled`, `client_latency_sampling_rate`)
- Tests: `services/api/tests/test_perf_flags.py`

---

## Web renderer caveat (cla-9)

`WebPerfBridge` (`app/lib/core/services/web_perf_bridge.dart`) reads
browser `PerformanceNavigationTiming` + Paint Timing entries on web
only. When interpreting the dashboard, note:

- **Canvas renderer** (CanvasKit / Skia-over-WebGL): the app draws on a
  single `<canvas>` so the browser sees one paint event covering the
  whole shell. `first-paint` and `first-contentful-paint` therefore
  fire together at ~frame 1, regardless of content being ready.
- **HTML renderer**: each Flutter widget maps to DOM nodes. The browser
  sees successive paint events as real content mounts, so
  `first-contentful-paint` tracks closer to what users perceive as
  "content showed up."

When cross-comparing web vs. mobile in the admin Client tab, filter to
one renderer (via `platform=web` + `app_version`) at a time. A
regression that only moves the FP line on canvas builds is an engine /
bundle-size issue; one that moves FCP on the HTML renderer is usually
a widget-tree problem.

---

## Firebase Performance Monitoring (cla-11 / cla-12)

**Secondary source of truth.** The custom `client_latencies` pipeline
is primary; Firebase is a cross-check we don't author, don't control the
sampling of, and never read during an incident.

### What's enabled

- **HTTP tracing** via `FirebaseHttpMetricInterceptor` — every Dio
  request (except those with `Options.extra['_perf_skip']`) is wrapped
  in `FirebasePerformance.instance.newHttpMetric(url, method)` so the
  Firebase console shows the same surface as our `/admin/metrics`
  **Endpoints** section.
- **App-start** — Firebase SDK auto-captures and posts this with no
  code required.
- **Scope lockdown (cla-12)**: iOS `Info.plist` sets
  `firebase_performance_collection_enabled=true` (pins the opt-in);
  Android `AndroidManifest.xml` mirrors that plus a best-effort
  `firebase_performance_auto_activity_trace_enabled=false` aimed at
  silencing the `_st_*` screen traces. **Caveat**: Firebase's public
  SDK contract does not expose a build-time key for disabling only
  screen-rendering collection (we confirmed this at cla-12 time
  against https://firebase.google.com/docs/perf-mon/disable-sdk ).
  The Android flag may or may not be honored by a given SDK version.
  Verify 24 h after each rollout by checking the Firebase Console →
  Performance → Screen rendering tab is empty (or treated as
  noise) — our incident response never reads it anyway.

### Platform scope

- **iOS**: enabled (release + debug). Collection toggle via
  `FirebasePerformance.instance.setPerformanceCollectionEnabled(true)`
  during app boot.
- **Android**: enabled (release + debug). Same toggle.
- **Web**: **disabled** (AC3 soft-fail). `firebase_performance` 0.10.x
  tree-shakes badly on `dart2js --release` — the `kIsWeb` guard in
  `main.dart` skips initialization on web entirely. Web users still
  produce `web_navigation` + `first_paint` + `first_contentful_paint`
  rows from the custom pipeline (`cla-9`); nothing is lost.
- **kE2EMode**: **disabled**. Consistent with how we skip Firebase Core
  initialization in the E2E test token flow.

### Where to find the data

- Firebase Console → Performance → **Network requests**: URL-keyed p50
  / p95 latency, status code split, payload sizes.
- Firebase Console → Performance → **App start**: platform-split
  time-to-first-frame.
- There is **no** Firebase screen-rendering tab — we disabled that
  source in cla-12 on purpose (see Scope lockdown above).

### Comparing Firebase vs. custom

If the Firebase HTTP p95 and the custom `/admin/metrics` Client tab
**Network** p95 disagree by more than ±20% for the same 24 h window:

1. Check the sampling rate on both sides. Firebase samples at ~1-25%
   by default; our pipeline ships every request when
   `PerfFlagsService.samplingRate == 1.0`.
2. Confirm Firebase's URL grouping — it groups by domain + path
   template; our `endpoint` column is the un-templated literal URL.
   For parameterized paths the two may diverge.
3. Check `_perf_skip` — our client-latency POSTs bypass both
   interceptors, so they don't appear in either source.
4. Widen the window. Below ~2 h, Firebase's sampling noise dominates.

Never make an incident-response decision from Firebase alone. Open the
custom dashboard first; if the number there confirms a regression,
Firebase is there to confirm it wasn't a measurement artifact in our
client code — not the other way around.

### Disabling at runtime (no deploy)

Firebase Performance can be toggled off from the Firebase console:
Project settings → Integrations → Performance → Data collection →
Off. Takes effect on each device's next app-start. Our custom pipeline
has its own kill-switch (see `cla-1c` above) — use that if you need
to shed server-side load; the Firebase toggle only affects the
secondary source.

### Backout / downgrade

- To remove entirely: delete the `firebase_performance` dep from
  `app/pubspec.yaml`, remove the `FirebaseHttpMetricInterceptor`
  install block in `main.dart`, revert the `Info.plist` /
  `AndroidManifest.xml` scope flags (cla-12).
- To downgrade version: the `^0.10.0+11` pin is the last 0.10.x line
  compatible with `firebase_core ^3.x`. Moving up to 0.11.x requires
  `firebase_core ^4.7.0` which is a multi-dep bump.

---

## Synthetic ingest load test (cla-14)

`services/api/scripts/load_test_client_latencies.py` hammers
`POST /v1/client-latencies` with N concurrent async workers for T
seconds and reports per-request p50/p95/p99 latency + success rate.

The default profile — **50 workers × 100 events × 5 minutes** — matches
the epic AC and the expected steady-state fleet (50 active users × ~500
events/day × ~5 sessions/day ≈ 125 k events/day, well inside the default
profile's throughput).

### Rate-limit note

The anonymous ingest path caps at 10 events/IP/rolling-minute (see
`services/api/src/api/v1/client_latency/ingest.py`). Running 50 × 100
batches from one IP is ~500× that, so the load test requires an
authenticated JWT. For a local docker-compose smoke run, you can
temporarily bump `_ANON_RATE_LIMIT_MAX_EVENTS` to a very large number
in the ingest module and skip the JWT; remember to revert.

### Running it

```bash
# Against local docker-compose (with anon rate-limit loosened, or
# --jwt passed).
python services/api/scripts/load_test_client_latencies.py \
    --jwt "$YOUR_TEST_TOKEN"

# Quick smoke (30 s, 10 workers).
python services/api/scripts/load_test_client_latencies.py \
    --concurrency 10 --duration-s 30 --jwt "$JWT"
```

While it's running, also run the following in a second terminal to
spot-check DB-side contention:

```sql
-- Active connections and what they're doing.
SELECT pid, state, wait_event_type, wait_event, query_start, substring(query for 80)
FROM pg_stat_activity
WHERE state = 'active' AND datname = 'palateful'
ORDER BY query_start;

-- Cache-hit ratio on the client_latencies table specifically.
SELECT relname,
       heap_blks_read,
       heap_blks_hit,
       round(100.0 * heap_blks_hit / nullif(heap_blks_hit + heap_blks_read, 0), 2)
         AS hit_ratio_pct
FROM pg_statio_user_tables
WHERE relname = 'client_latencies';
```

### Signed-off baseline

Re-capture after any change that touches the ingest path. Paste the
script's report block below verbatim.

**Last run:** _TBD — operator captures after the next production-config
ingest load test. Leave the placeholder until then; the AC validates
against a real run, not a reproduced template. See the cla-14 qa
walkthrough for the intended capture format._

```
Wall time:        300.0 s
Workers:          50
Total requests:   <fill in>
Successful (2xx): <fill in>
Events / sec:     <fill in>

Per-request latency (ms):
  p50:   <fill in>
  p95:   <fill in>
  p99:   <fill in>

AC check:
  p95 < 100 ms:          <PASS / FAIL>
  success rate == 100 %: <PASS / FAIL>
```

DB-side during the run:
- `pg_stat_activity` active queries: stay under ~N_workers
- `client_latencies` cache hit ratio: stay > 98 %
- No slow-query log entries (PostgreSQL
  `log_min_duration_statement=1000ms` default).

---

## Debug perf overlay (ptd-1)

Floating in-app widget that lists the last 100 HTTP requests with
durations + status codes. `kDebugMode`-gated — zero cost in release
builds (the `PerfOverlay` widget returns its child unwrapped).

### How to use

1. `cd app && flutter run -d <simulator>` (debug build).
2. Long-press the top-right 64×64 corner of any screen. The overlay
   panel slides down, showing the most recent requests newest-first
   (`GET /v1/recipe-books 142ms 200`, etc.).
3. Status codes are colour-coded: green 2xx, orange 4xx, red 5xx /
   network error.
4. Long-press again — or tap the `×` in the panel — to toggle off.

### Files

- `app/lib/core/debug/perf_overlay.dart`
- `app/lib/core/debug/perf_request_log.dart`
- `app/lib/core/debug/perf_dio_interceptor.dart`
- Installed in `app/lib/main.dart` under `if (kDebugMode)`.

### Why top-right corner?

Palateful has no avatar widget and the bottom `NavigationBar` would
eat the long-press. Top-right via `MaterialApp.builder` works across
every top-level screen regardless of nav layout (mobile / tablet /
web). See the ptd-1 story scope-divergence notes.

---

## Perf audit harness (ptd-2.5 / ptd-2 / ptd-3)

Per-screen integration tests that count attempted GETs on cold start.
Each screen has a canonical `integration_test/perf_audit/<NN>_perf_audit_<screen>_test.dart`
that reads the screen's top-level Riverpod provider and asserts the
exact number of GETs against `tools/perf-budgets.yaml`.

### Running locally

```bash
# One file at a time — flutter-tester has a log-reader race when
# multiple integration test files load back-to-back in a single run.
cd app
flutter test integration_test/perf_audit/08_perf_audit_home_test.dart -d flutter-tester
```

The full suite runs via `bin/perf-audit` (below).

### Why provider-level instead of widget-tree pumps?

`app.main()` boots Firebase / Auth0 / dotenv which are wrong-shape for
`flutter-tester`. Reading the provider directly exercises the actual
data-layer budget — the thing the CI guard contracts on — without the
fragile boot path. Each test runs in ~10s on a warm pub cache.

### Fixtures

`tools/perf-audit-fixtures/` holds committed JSON responses served by
`PerfAuditMockAdapter`. Fixture files are slug-keyed:
`METHOD_path.json` → `GET_v1_users_me.json`. See
[`tools/perf-audit-fixtures/README.md`](../tools/perf-audit-fixtures/README.md)
for format + refresh process.

### Refreshing a fixture

When backend shape drifts (field renamed, payload split):

```bash
docker compose up api       # or point at your dev deploy
TOKEN=$(cat ~/.palateful-dev-token)
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/users/me \
  | jq '{status: 200, body: .}' \
  > tools/perf-audit-fixtures/GET_v1_users_me.json
```

Commit the refreshed fixture with a one-line PR note naming the
backend change that caused the drift.

---

## `bin/perf-audit` (ptd-4)

Capture-or-assert driver. Runs every per-screen integration test,
collects `PERF_AUDIT_CSV` sentinels, pipes to
`tools/perf-audit-diff.py`.

```bash
# Regenerate the baseline yaml (use when ffm / perf work lands an
# intentional new fetch that should shift the budget).
bin/perf-audit --capture

# Verify observed counts against the committed yaml. Default warn-mode
# (exits 0 even on violations). Strict-mode via env var:
bin/perf-audit --assert
PERF_AUDIT_STRICT=1 bin/perf-audit --assert
```

### Custom budget file

```bash
PERF_AUDIT_BUDGET_FILE=tools/perf-audit-test-fixtures/regression.yaml \
  bin/perf-audit --assert
```

Used by ptd-8's self-test to feed a known-bad budget.

### Exit codes

- `0` — capture success, or assert within budget, or assert violation
  in warn-mode.
- `1` — strict-mode violation, or zero CSV sentinels collected
  (tests failing?), or diff helper error.
- `2` — usage / tooling error (missing fixtures dir, diff helper,
  etc.).

### CI time cost

~2 min wall-clock on GitHub Actions (9 × ~12s flutter-tester cold
boot + ~30s pub cache hit). Safe in the `flutter-test` job; well
under the <5 min epic budget.

---

## Raising a perf budget (ptd-4.5)

When a feature legitimately needs a new fetch:

1. Re-capture the baseline to see the effect:
   `bin/perf-audit --capture`. Inspect the diff to
   `tools/perf-budgets.yaml`.
2. If an endpoint's count jumped past 1, add a matching waiver line
   to `tools/perf-budget-waivers.txt`:
   ```
   home:GET /v1/recipe-books:new share-sheet preview needs a second fetch
   ```
3. Add a one-sentence rationale to the PR description.
4. Push. CI runs `tools/no-perf-budget-waiver-check.sh` (waiver
   matches budget) and `actions/labeler` auto-applies the
   `perf-budget-change` label. Reviewer now has **four independent
   cues** in the diff (yaml bump, waiver line, PR description, label).

Totals (`total:`) track the sum of endpoints per screen and are
asserted alongside per-endpoint counts.

### When a waiver expires / becomes wrong

Waivers are flat text with no expiry. Remove stale lines when the
paired endpoint drops back to 1 and the yaml is updated to match.
The grep guard cross-checks only the yaml → waiver direction; a
leftover waiver is harmless until the corresponding budget entry
gets bumped again.

---

## Self-test (ptd-8)

```bash
tools/perf-audit-self-test.sh
# → "perf-audit-self-test: OK (regression detected, baseline clean)"
```

Pipes a canned observed CSV into `perf-audit-diff.py` twice:

1. Against `tools/perf-audit-test-fixtures/regression.yaml` (home
   pinned at total=3) — expects exit 1.
2. Against `tools/perf-audit-test-fixtures/baseline.yaml` (sized to
   match observed) — expects exit 0.

If either branch returns the wrong exit code, the comparator has
regressed and CI fails with a clear diagnostic. Runs in <100ms.

---

## CI regression guard (ptd-5)

Three new steps appended to `.github/workflows/ci.yml`'s
`flutter-test` job (ordered cheapest first):

1. `No perf-budget waivers missing` — runs `no-perf-budget-waiver-check.sh`.
2. `Perf audit self-test` — runs `perf-audit-self-test.sh`.
3. `Perf audit — assert per-screen budgets` — runs
   `bin/perf-audit --assert` with a retry-once wrapper; tees the
   per-screen diff table into `$GITHUB_STEP_SUMMARY`.

Plus a new `perf-budget-label` job: `actions/labeler@v5` + `.github/labeler.yml`
auto-applies `perf-budget-change` on PRs that touch the budget yaml
or waiver file.

### Warn-mode → strict flip

Grace window ends **2026-05-07**. On or after that date, open a
one-line PR that:

1. Adds `PERF_AUDIT_STRICT: '1'` to the `env:` of the
   "Perf audit — assert per-screen budgets" step.
2. Drops the block comment naming the grace window.

Before flipping, skim a week of warn-mode CI summaries to confirm the
baseline is stable across real PR traffic. If anyone raised the budget
intentionally during the window and forgot the waiver, that's what the
strict flip catches.

### Harness flake / quarantine

Retry-once is automatic. If a specific test proves persistently flaky,
add its filename (one per line) to a new file
`tools/perf-audit-quarantine.txt` (not yet auto-implemented) — or
directly exclude it from the `bin/perf-audit` loop via a skip match.
Revisit automation if this becomes a real pattern; one story of MVP
plumbing doesn't justify a persistent flake-count store.
