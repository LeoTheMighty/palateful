<!-- todo.md — Rotation Self Heal working memory (harness-fold-in FR-1).

  Contract (design §"todo.md parse contract"):
  - Auto-maintained: `devx todo sync <hash>` trues the derived lines below.
    Derived = top-level lines matching `- [ ] Stage:|Gate:|Phase <n>: …`;
    their checkboxes mirror spec frontmatter + linked dev-spec state.
    Free-nested items (any deeper checkbox) belong to skills and humans —
    sync never touches them.
  - Never a gate input: no `devx gate` code path reads this file.
  - Pointers, not copies: phase lines point at emitted dev specs
    (`  - [ ] Phase <n>: <title> → <dev-hash>`); content lives in the spec.
  - Done = checked; abandoned = deleted. This file is NOT append-only.
  - Hand-edits are legal — the next writer reconciles.
-->

- [x] Stage: PRD
- [x] Gate: prd
- [x] Stage: Design
  - [x] Research: API db/health surfaces, terraform ECS/secrets, CI + failing tests
  - [x] User decision: FR-6 → scheduled GitHub Action (not CloudWatch alarm)
  - [x] User decision: pre-07-29 scope → FR-1 + FR-2 + FR-4; FR-3/5/6 after
  - [x] User decision: accept pending 90d rotation cadence from e74303f
  - [x] Write design.md (all template sections)
  - [x] Coverage judge pass 1 → fixed 6 citation errors + FR-6 lookup bug
  - [x] Coverage judge pass 2 → FR-1/FR-3/FR-6 upgraded to covered
  - [x] UC-5 folded into existing `bin/prod-status` (dropped net-new script)
  - [x] `devx gate coverage 462355` → **CONCERNS** (16 covered / 5 partial / 0 missing)
  - [x] `devx revise 462355 --touched prd.md` — rewrote the rotation-cadence
        non-goal to match the 90d decision; replayed `gate prd` (PASS) and
        `gate coverage` design mode (CONCERNS) back to prior state
  - [x] **Carry into Plan:** the 5 partials (G-1..G-4, CAP-1) are all
        "unproven until CI actually runs / until a real rotation" — they
        need phases that produce evidence, not more design
        → answered: G-1/CAP-1 by Phases 1–2, G-2/G-3/G-4 by Phase 9's drill
- [x] Gate: coverage(design)
- [x] Stage: Plan
  - [x] User decision: 8 phases (split FR-4 into handler/infra, FR-5 into
        provider/wiring) + a 9th rotation-drill phase for G-2/G-3 evidence
  - [x] Ground every cited path (found: CI validates `environments/dev`,
        which has no rds/ecs — a prod-only module gets fmt but no validate)
  - [x] Write plan.md (9 phases, expectation coverage table, deadline shape)
  - [x] Critique pass — 4 lenses (pm/architect/dev/qa), ran because the plan
        touches 5 surfaces (≥ engine.critique.min_surfaces)
  - [x] 7 HIGH accepted, incl. 3-lens concordance on two structural errors:
        Phase 1 could never reach `deploy-services` (nx-affected gating), and
        the first `terraform apply` lands at Phase 2, not Phase 4
  - [x] Coverage judge pass 1 → E-4 + E-6 partial; fixed both rather than
        arguing (single-flight cache + worker interval=60; T6.3b moves E-6's
        second clause into its named artifact)
  - [x] Coverage judge pass 2 → 8/8 covered
  - [x] `devx gate coverage 462355` (plan mode) → **PASS**
- [x] Gate: coverage(plan)
- [x] Stage: RED
  - [x] Add a `utils` runner to `devx.config.yaml` — E-5/E-6 are P0 but
        `libraries/utils` had no `projects:` entry, so both resolved
        `command: null` (a P0 floor breach)
  - [x] E-1: confirmed pre-existing RED (3 failures; fixtures frozen at
        2026-04-18 vs a 30-day `DateTime.now()` cutoff) — not re-authored
  - [x] E-2/E-3/E-4: authored `services/api/tests/test_health.py` at the
        **connect seam** (`db_probe._connect_once`), so `is_auth_error` runs
        for real inside the API test; includes the interleaved 30s/60s
        single-flight case that actually tests the design
  - [x] E-5: authored `libraries/utils/test/test_rotation_redeploy_handler.py`
        — both candidate event shapes (Secret Label Updated + CloudTrail
        `RotationSucceeded`), so T4.1's fallback needs no re-author
  - [x] E-6: authored `libraries/utils/test/test_db_credential_provider.py`
        — do_connect driven via `engine.pool._creator()` on a SQLite engine
        (driver-free; `engine.connect()` would fire `dialect.initialize()`)
  - [x] E-7/E-8: human stubs with full observation protocols
  - [x] **Found at RED:** T6.3b's stated mechanism is impossible — `agent` is
        not installed in the `libraries/utils` venv and its engines are built
        lazily, so importing `runner.py`/`tasks.py` inspects nothing.
        Recorded in rsh106; clause proven live for `database.py`'s 3 sites,
        source-level for the 2 agent sites
  - [x] **Found at RED:** the api suite needs `DATABASE_URL` in the env
        (`ci.yml:176`) or every test errors on a pydantic `Settings`
        validation; and `fail_under = 100` makes any single-file api run exit
        non-zero on coverage alone. Both recorded in rsh102
- [x] Gate: evals
- [ ] Stage: Execute
  - [ ] Phase 1: Unblock the deploy path on `main` (FR-1) → rsh101
    - [x] T1.1 Re-ran E-1's artifact and watched it fail NOW (3 failures,
          right-reason) before touching code — not re-authored
    - [x] T1.2 Four age-gated fixtures (`:277`, `:445`, `:518`, `:525`) →
          `_recent(Duration)`; widget untouched, `:510` left hardcoded
    - [x] T1.3 The masked `:543` + `:544` assertions now run and pass
    - [x] T1.4 Guard: `app/test/fixture_date_guard_test.dart` + a 29-file
          count baseline; lives inside `flutter-test` so it has real teeth.
          Demonstrated failing on a live reintroduction, then green.
    - [x] Local gates: `flutter test` 1536 passed / 0 failures (was 1524
          with 3 failures); analyze clean on both touched files
    - [x] PR #7 + review tour published
    - [ ] T1.5 Watch `flutter-test` → `deploy-web` → `detect-changes` on the
          `main` push (post-merge — `deploy-web` is main-push-gated)
    - [ ] T1.6 Record the 2026-05-03 `deploy-web` outcome (AC #6); if it
          reproduces, pin `flutter-version` + `wrangler@latest` and re-run
  - [ ] Phase 2: Credential-aware health probe (FR-2) → rsh102
  - [ ] Phase 3: Rotation-redeploy Lambda handler (FR-4a) → rsh103
  - [ ] Phase 4: EventBridge rule + Lambda infrastructure (FR-4b) → rsh104
  - [ ] Phase 5: Secrets Manager password provider (FR-5a) → rsh105
  - [ ] Phase 6: Engine-site registration + task-role IAM (FR-5b) → rsh106
  - [ ] Phase 7: Worker health check (FR-3) → rsh107
  - [ ] Phase 8: Deploy-freeze visibility (FR-6) → rsh108
  - [ ] Phase 9: Rotation drill — measure G-2, G-3, G-4 → rsh109
  - [ ] Retro → rshret
- [ ] Stage: Retro
- [ ] Stage: Outcome
