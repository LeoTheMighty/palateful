# Plan critique — 2026-07-27 (lenses: pm, architect, dev, qa)

Four parallel lens subagents critiqued the drafted plan.md; every accepted
finding was grep-verified in the main session before application (grounding
rule). Findings and dispositions:

## Accepted — structural (plan rewritten around these)

1. **RED-gate bootstrap circularity** (architect HIGH, qa HIGH): dev specs
   emit only on `devx gate evals` PASS, but the `projects:` block that
   makes the gate resolvable was scheduled inside Phase 1. → New
   "RED-stage prerequisites" section: the `projects:` block +
   `run-eval.sh` dispatcher commit at RED, before the gate run; the `qa:`
   block keeps lying until Phase 1 so `e1` stays right-reason RED.
2. **Eval artifacts scheduled inside their own phases** (architect HIGH,
   qa HIGH — violates the RED contract "author at Verified-by path at RED;
   phases re-run, never author/re-author"). → All authoring tasks removed
   from phases 1/2/5/6; phases now only re-run and watch green.
3. **Prod-API default in every drive invocation** (dev HIGH; verified:
   `app/lib/core/config/environment.dart:9-12` defaults
   `https://api.palateful.app`; `run_all.sh` and `project.json` pass no
   `API_BASE_URL`): a "local" e2e run or attended pass would drive
   production with the fixed e2e token. →
   `--dart-define=API_BASE_URL=http://localhost:8000`
   (convention: `bin/prod-web-deploy:17`) added to `run_all.sh`,
   `test-single`/`test-headless`, the `/devx-test` launch command, and the
   eval-convention recipe.
4. **E-1's grep target never appears in dry-run output** (qa HIGH,
   architect MEDIUM; verified `gate.ts:437-452`: dry-run emits JSON
   `planned[{eId,artifact,command}]`/`deferred[]`, no verdict prose). →
   e1 asserts on parsed JSON: every planned command non-null,
   planned+deferred == 6, plus the playwright grep.
5. **Exit 2 indistinguishable from exit 1 at the gate** (architect MEDIUM,
   qa HIGH; `gate-evals.ts:408-414` has no exit-2 branch — an
   infra-broken P0 reads as right-reason). → `INFRA:` sentinel convention
   + RED-stage discipline: reject the gate if any RED-report quote
   contains `INFRA:`.
6. **`projects:` blast radius into `/devx` local CI** (architect MEDIUM;
   `skills/devx.md` Phase 5 runs each touched project's `test` bare):
   `test: bash` would read stdin; `test: bash scripts/run_all.sh` would
   run the suite without lifecycle. → `workstream-evals` gets a
   `run-eval.sh` dispatcher (no args → exit 0); `e2e` points at the
   lifecycle wrapper.
7. **E-5 permanently-red / unasserted second clause** (qa MEDIUM): the
   Verified-by becomes a wrapper (asserts README documents the convention
   + `demo_browser_flow.sh` is right-reason-shaped); the demo flow is a
   separate, deliberately-forever-red reference implementation, not a
   Verified-by artifact.
8. **E-2 population** (pm HIGH, qa MEDIUM): PRD/E-2 say "every
   `*_test.dart` flow"; the glob runs `0*` only, silently excluding the
   legit hmp-5 flow. Rather than a `devx revise` cascade (expectations
   touch resets 4 gate flags), the plan makes the wording true: rename
   `meals_home_promotion_flow_test.dart` →
   `08_meals_home_promotion_test.dart` (population 8); eval asserts pass
   count == glob count. `perf_audit/` added to the scope fence.

## Accepted — corrections and tightenings

9. **Vacuous `devx config` validation criteria** (architect HIGH:
   `loadValidatedConfig` has zero callers; consumers lack
   `config-schema.json`; cfg203 documented-only). → Criteria replaced
   with `devx config get` value checks; two-step `qa:` flip kept
   deliberately (documented driver contract; costs nothing); Current
   state notes validation is unenforced.
10. **Retry mechanics underspecified** (qa MEDIUM): T2.2 now requires
    output capture (tee + PIPESTATUS under `set -uo pipefail`) and
    repeating the pkill+sleep reset before the retry.
11. **Trap-proof criterion not runnable** (qa MEDIUM): downgraded to a
    manual spot-check with the exact commands written out.
12. **`NEXT_STEPS.md` stale after repoint** (architect LOW): added to
    Phase 2 retirement task.
13. **Scope fence contradictions** (pm MEDIUM): `decide.ts` row carved
    out of the "no engine code" fence (it is FR-5 scope); G-4's
    "real expectation in a subsequent workstream" recorded as a
    deliberate handoff in the fence; E-3 one-story proof boundary fenced.
14. **No dates on phases** (pm MEDIUM): phase checklist now carries the
    G-id + deadline each phase discharges; Phase 6 flagged as
    needs-Leo-attended with G-3's date riding on it.
15. **$1 cap reported, never enforced; G-5 is per-day** (pm MEDIUM):
    T4.1 skill body now enforces the daily budget (same-day recheck,
    confirm-before-second-pass, cumulative reporting); Phase 6 criterion
    is cumulative same-day spend.
16. **FR-4 "Phase 6 emits" vs author-at-Phase-5** (pm LOW): superseding
    note added in Phase 3 (design is the authority).
17. **Template write-if-absent forever** (dev note): later upstream
    template revisions never auto-propagate — recorded as a Phase 3
    context caveat.

## Rejected / no action

- Editing `expectations.md` (E-1 threshold wording, E-2 EARS) via
  `devx revise`: the cascade resets 4 gate flags (prd/design/plan/evals)
  and forces three gate re-runs; instead the plan satisfies each
  threshold's letter a fortiori (see 4, 8). If a future revision touches
  expectations anyway, fold the wording fixes in then.
- Registering `archive/` in .gitignore: verified tracked-by-default is
  correct (managed block covers only `.worktrees/`/`.devx-cache/`).
- dev lens confirmations needing no change: lifecycle trap composes with
  `run_all.sh`'s process-local EXIT trap; `devx` is a global bin;
  `devx init` upgrade round-trips config comment-preservingly
  (`init-upgrade.ts:245,349`); design's three stack-defect claims all
  check out.
