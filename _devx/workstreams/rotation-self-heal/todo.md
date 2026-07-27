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
  - [ ] **Carry into Plan:** the 5 partials (G-1..G-4, CAP-1) are all
        "unproven until CI actually runs / until a real rotation" — they
        need phases that produce evidence, not more design
- [x] Gate: coverage(design)
- [ ] Stage: Plan
- [ ] Gate: coverage(plan)
- [ ] Stage: RED
- [ ] Gate: evals
- [ ] Stage: Execute
- [ ] Stage: Retro
- [ ] Stage: Outcome
