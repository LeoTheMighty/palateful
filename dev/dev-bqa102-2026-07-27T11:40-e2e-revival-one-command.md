---
hash: bqa102
type: dev
created: 2026-07-27T11:40:00-06:00
title: E2E revival — one-command green with lifecycle wrapper
from: plan/plan-41ee13-2026-07-27T10:36-browser-qa-agent.md
status: in-progress
owner: /devx-2026-07-27T1648-73151
branch: feat/dev-bqa102
---

## Goal
Make `npx nx run e2e:test` the full lifecycle (stack up → wait-healthy → all flows → teardown-in-trap → exit 0 iff all pass) and fix the three latent stack defects that keep the gen-2 harness dormant or dangerous: the dormant auth bypass (`ENVIRONMENT` unset), the migrator/api DB mismatch (`test` vs `palateful`), and the prod-API default (`API_BASE_URL` → https://api.palateful.app with the fixed e2e token). Bring the hmp-5 flow into the numbered population (8 flows). Turns E-2 green.

## Acceptance criteria
- [ ] `docker-compose.e2e.yml` api overlay sets `ENVIRONMENT: development` (arms the bypass gate at `services/api/src/dependencies.py:109`) and `DATABASE_URL: postgresql://postgres:postgres@db:5432/test` (matches `migrator-test`, isolates e2e writes; bypass lazy-seeds via `find_or_create_by` — no SQL seed needed).
- [ ] `services/e2e/scripts/run_all.sh`: (a) drive invocation gains `--dart-define=API_BASE_URL=http://localhost:8000`; (b) fail-fast chromedriver presence check with `brew install chromedriver` hint; (c) exactly one retry per test on the `AppConnectionException` signature — output captured via `tee` to a temp log (exit code via `PIPESTATUS` under the existing `set -uo pipefail`) while still streaming; the retry repeats the `pkill -f flutter_tools_chrome_device` + sleep reset first.
- [ ] `app/integration_test/meals_home_promotion_flow_test.dart` renamed to `app/integration_test/08_meals_home_promotion_test.dart` (git mv, no content change) — joins the `0*` glob; population becomes 8.
- [ ] New `services/e2e/scripts/e2e_lifecycle.sh`: up → poll `localhost:8000` healthy → `run_all.sh` → down in a `trap` (teardown survives failure); exits nonzero iff any flow failed. `services/e2e/project.json` `test` target points at it; `test-single`/`test-headless` gain the `API_BASE_URL=http://localhost:8000` define; `stack-up`/`stack-down` retained.
- [ ] Gen-1 Maestro (`services/e2e/flows/`, `services/e2e/config.yaml`) moved verbatim to `archive/e2e-maestro/`; `services/e2e/NEXT_STEPS.md` retired (still-true content folded into README, rest archived); `services/e2e/README.md` rewritten — live path only (stack, one-command run, single-test drive, flake note, chromedriver prereq, the `API_BASE_URL` gotcha), no Maestro / `--flow=` mentions.
- [ ] `bash run-eval.sh browser-qa-agent/evals/e2_e2e_one_command.sh` (cwd `_devx/workstreams`) exits 0 — two consecutive one-command runs, 8/8 flows each. Eval NOT re-authored (authored at RED).
- [ ] Manual trap spot-check evidence pasted: start a run, `docker kill palateful-api` mid-suite, wrapper exits nonzero and `docker compose -f docker-compose.yml -f docker-compose.e2e.yml ps -q` prints nothing.

## Technical notes
- Retry is targeted, not blanket: blanket retries mask real regressions; zero retries fails the two-consecutive-runs bar on known infra flake.
- `run_all.sh`'s own EXIT trap (chromedriver kill, `run_all.sh:26`) is process-local — composes with the wrapper's compose-down trap; both fire.
- Compose-merge lets the e2e overlay's `DATABASE_URL` win over `docker-compose.yml:87`.
- The flow population is `run_all.sh`'s glob (`integration_test/0*_test.dart`); `perf_audit/` stays excluded by construction (subdirectory). The eval asserts pass count == glob count, so silent drops/adds fail loudly.
- Parallel-safe with bqa101 and bqa103 (disjoint files/repos).
- Full context: plan `_devx/workstreams/browser-qa-agent/plan.md` §Phase 2 + §Current state (three latent defects).

## Status log
- 2026-07-27T11:40 — emitted from plan 41ee13 at RED-gate PASS (tests-first phase; RED artifact `evals/e2_e2e_one_command.sh` observed failing right-reason, see `evals/RED-report.md`).
- 2026-07-27T16:48:59-06:00 — claimed by /devx in session /devx-2026-07-27T1648-73151
