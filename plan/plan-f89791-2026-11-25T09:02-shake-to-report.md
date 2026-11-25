---
hash: f89791
type: plan
created: 2026-11-25T09:02:07-07:00
title: Shake To Report
status: in-progress
stage: executing
entered_at: prd
gate_status:
  prd_validated: true
  design_verified: true
  plan_verified: true
  evals_red: true
  evals_locked: true
  red_eval_ids:
    E-5: null
    E-6: null
    E-7: null
    E-8: null
    E-9: null
    E-10: null
    E-1: _devx/workstreams/shake-to-report/evals/E-1_user_path.sh
    E-2: _devx/workstreams/shake-to-report/evals/E-2_everyday_motion.sh
    E-3: _devx/workstreams/shake-to-report/evals/E-3_no_interruption.sh
    E-4: _devx/workstreams/shake-to-report/evals/E-4_role_and_ring.sh
  red_eval_shas:
    _devx/workstreams/shake-to-report/evals/E-1_user_path.sh: ba3d4345e19302eb99d3b63de45189d49c27d8828dc1eeb0d41168db09975b1d
    _devx/workstreams/shake-to-report/evals/E-2_everyday_motion.sh: 2701a3f5c7d641e0594fcbd763751ef2813c43f619af9d619b22fc303a2a68f5
    _devx/workstreams/shake-to-report/evals/E-3_no_interruption.sh: 83ebab7f32644c652932c5fff9802d6bb77f0409f66ae52710faf86a19af2855
    _devx/workstreams/shake-to-report/evals/E-4_role_and_ring.sh: b1a1af9f0f7dad8809712f53a39f5e2cbd13f652d507b8b4befb629ac4ca42b6
outcome:
  status: null
  measure_by: null
workstream: _devx/workstreams/shake-to-report
gate_verdicts:
  prd: PASS
  design: CONCERNS
  plan: PASS
  evals: PASS
---

## Goal

Shake-to-report for Palateful's iOS and Android app: a deliberate shake shows a small prompt; a tap opens the dev-request form for an admin (arq103's `/admin/dev-requests/new`, an external gate) and the existing feedback sheet for everyone else, recording the screen. Built so a false shake costs nothing, with a server-side rollout ring and a per-device switch. Artifacts live in `_devx/workstreams/shake-to-report/`.

## Status log

- 2026-11-25T09:02 — workstream scaffolded by `devx workstream new shake-to-report`.
- 2026-11-25T09:35 — prd stage: `devx gate prd f89791` → PASS (1 FAIL round: E-8 threshold had no numerals). Artifacts: `prd/agent.md`, `prd/human.md` (render lint 0 HARD), `expectations.md` (E-1…E-10; P0: E-1…E-4), `decisions/2026-11-25-separate-workstream.md`. Templates came from cherry-picking 87c0663e (admin-request-intake's template commit) so both branches add identical files; the first `devx workstream new` at c80d253 refused on the flat templates and still wrote a plan spec and three empty dirs, removed by hand. Critique skipped (thoroughness send-it). Outline not bootstrapped (dispatched run). Profile preflight: non-interactive, registry defaults, nothing recorded. Feasibility probe before pinning Verified-by: the real `PalatefulApp` boots signed-in in a widget test run from outside the `app/` package, and the sensors_plus channel can be faked.
- 2026-11-25T09:36 — revise: E-1, E-6, E-8 named the feedback endpoint as `POST /v1/user/feedback`, written from memory; the route is `POST /v1/users/me/feedback` (`services/api/src/routers/v1/user_router.py:214`, `app/lib/core/services/api_client.dart:877`). `devx revise f89791 --touched expectations.md` (4 flags reset), `devx gate prd f89791` → PASS.
- 2026-11-25T09:41 — design stage: `devx gate coverage f89791` (design) → CONCERNS, advanced: G-2 partial (FR-3's thresholds unproven until E-7 on hardware), G-4 partial (needs arq103's route on main). research.md answered by the authoring session, NOT blind (no subagent tool); every citation re-read at its line, 6 drifted line numbers corrected. Coverage table self-judged (`decisions/2026-11-25-design-coverage-table.json`); 2 extras flagged (web feedback gains platform `web`; route-exists check before the admin push). Own design bug caught before the gate: `defaultTargetPlatform` on web reports the browser's OS. Artifacts: `design/agent.md`, `design/human.md` (render lint 0 HARD), `design/research-questions.md`, `design/research.md`.
- 2026-11-25T09:45 — plan stage: 6 phases (shk101…shk106) and 2 external gates (X-1 arq103's route on main; X-2 a version-bumped release). Riskiest phase named: 3 (native dependency; no PR-time CI builds iOS or Android, and its pubspec edit fires Xcode Cloud). The P0 evals join CI's Flutter job in the phase that turns each green. Critique skipped (send-it; no subagent tool for lenses). `devx gate coverage f89791` (plan) → FAIL once (rows lacked the `artifact` field the P0 floor reads), then PASS; execution graph clean. Coverage table self-judged (`decisions/2026-11-25-plan-coverage-table.json`). Artifacts: `plan/agent.md`, `plan/human.md` (render lint 0 HARD).
- 2026-11-25T10:04 — revise: a throwaway spike (never committed) showed the prompt never faded: in Flutter 3.41 a SnackBar with an action persists by default and only `persist` gates its timeout (`material/snack_bar.dart:303`, `material/scaffold.dart:615-628`), so design § Host now passes `persist: MediaQuery.accessibleNavigationOf(context)` and RQ10 is corrected (its doc-comment quote is stale). `devx revise f89791 --touched design` (3 flags reset); Gate 2 → CONCERNS (same two partials), Gate 3 → PASS.
- 2026-11-25T10:04 — RED stage: `devx gate evals f89791` → PASS (4 P0 RED, 6 P1/P2 deferred legally); `--verify` PASS, 4 wrappers stamped. Each P0 boots the real `PalatefulApp` from a test file outside `app/` (so CI's `flutter test` never collects a RED file; no Flutter RED registry needed) and feeds sensors_plus's `user_accel` channel. Runner exits 1 only when every failure is a `TestFailure` carrying a `SHAKE-RED[...]` marker and every `control:` test passed, else 3. Today: E-1 RED `E-1:no-prompt` (motion listeners 0); E-2 RED only via its positive control (its 0-false-trigger claim is vacuous on unbuilt code, and the eval refuses to count it); E-3 RED via each busy state's closing positive control plus `timer:no-prompt`; E-4 RED in 7 tests incl. `x1-route-missing`. Runner negative controls (scratch copy, deleted): tamper, harness channel typo, exception, unmarked assertion, compile error → exit 3 each. The channel typo first PASSED — the motion control reused the harness's own constant — fixed by checking against an independent literal from the plugin's source. Green-reachability: a throwaway host in a scratch worktree (never committed, deleted) turned E-1 and E-2 GREEN and E-3's timer test GREEN; E-3's busy states and E-4's ring cases failed on it by their own markers; it also found the `persist` gap (revise above). Emitted shk101…shk106 + DEV.md section (inserted before rotation-self-heal, not at EOF, so it cannot collide with admin-request-intake's EOF append) + todo pointers; `devx plan-helper validate-emit shake-to-report` ok. NOT done: retro story (`emit-retro-story` refuses in a linked worktree; this session may not use the main checkout) and GRAPH.md. Not locked by `--verify`: the Dart files and harness — the wrappers pin them and exit 3 on any edit, so tampering shows at run time, not at `--verify`.
