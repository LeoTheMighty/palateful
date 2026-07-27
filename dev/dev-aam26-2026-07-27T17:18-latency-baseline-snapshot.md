---
hash: aam26
type: dev
created: 2026-07-27T17:18:00-06:00
title: Latency baseline snapshot — tabulate pre-vs-post-migration p95 deltas and gate the epic's win
from: _bmad-output/planning-artifacts/epic-api-async-migration.md
status: ready
blocked-by: [aam24]
branch: feat/dev-aam26
---

## Goal
Prove the migration's win with numbers: capture a 7-day post-cutover `analyze_latency.py` snapshot, diff it against the pre-migration baseline, and gate on the epic's two headline targets (meals-detail client p95 < 500ms, client-errors server p95 < 200ms). Tabulate every endpoint's delta with sample counts so low-traffic noise is visible.

## Acceptance criteria
- [ ] Post-cutover capture: `bin/prod-script services/api/scripts/analyze_latency.py --window 7d` (endpoints + tasks) taken 7 days after aam-24 lands; output saved as `_bmad-output/implementation-artifacts/aam-26-post.csv`.
- [ ] Pre-migration baseline reconstructed and saved as `_bmad-output/implementation-artifacts/aam-26-baseline.csv` (see notes — the "day aam-1 opens" capture was never saved; use historical `request_latencies` / `client_latencies` windows or the 2026-04-23 figures recorded in the epic Overview: meals-detail client p95 5192ms, client-errors server p95 5931ms).
- [ ] Target 1 (hard gate): `GET /v1/meals/{meal_id}` client-side p95 < 500ms (baseline 5192ms).
- [ ] Target 2 (hard gate): `POST /v1/users/me/client-errors` server-side p95 < 200ms (baseline 5931ms).
- [ ] Target 3: no other endpoint's p95 regressed > 20%; any regression files a blocking follow-up (aam-28+ namespace) and this story does not close.
- [ ] Target 4: `POST /v1/client-latencies` ingest p95 unchanged or improved.
- [ ] All endpoint p95 deltas tabulated in `_bmad-output/implementation-artifacts/aam-26-qa-walkthrough.md` with sample counts alongside p95.
- [ ] If targets 1 or 2 miss: story blocks on investigation; rollback to last-good pre-aam-24 commit (documented in aam-24's QA walkthrough) is explicitly on the table.

## Technical notes
- Epic Phase 6 story `aam-26-latency-baseline-snapshot`. Snippets: CHUNK-C7 in `aam-phase1-dev-snippets.md` (suggests a `tools/` diff script — optional; a saved CSV pair + tabulated diff satisfies the epic ACs).
- Verification against main (2026-07-27): NOT landed — no `aam-26-baseline.csv` or any aam-26 artifact exists under `_bmad-output/implementation-artifacts/`. The AC "captured pre-aam-1 the day aam-1 opens" was missed at the time, so this story must reconstruct the baseline: `analyze_latency.py` supports `--window all` and `--regression-hunt` (recent vs 7-to-30d baseline); the epic Overview pins the two headline numbers from 2026-04-23 debug tooling. See `docs/PERFORMANCE_OPS.md` for baseline-capture / diff recipes (referenced from CLAUDE.md).
- Mostly an ops/measurement story: read-only prod queries via `bin/prod-script`, artifact files, and a QA walkthrough — little or no application code. If a diff script is added under `tools/`, keep it out of the api coverage gate's scope.
- Requires aam-24 landed plus a 7-day soak — schedule accordingly; can be the last story to close even though aam-27 may merge earlier.
- Original BMAD story key: aam-26-latency-baseline-snapshot.

## Status log
- 2026-07-27T17:18 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; scope re-verified against main (see Technical notes)
