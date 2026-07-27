<!-- todo.md — Browser Qa Agent working memory (harness-fold-in FR-1).

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
  - [x] Research fan-out: QA infra / browser-e2e / engine seams (3 Explore agents, 2026-07-27)
  - [x] Scoping interview: hybrid driver, both-repos palateful-first, all 4 QA depths
  - [x] prd.md drafted (G-1..5, UC-1..5, CAP-1..7, FR-1..8)
  - [x] expectations.md drafted (E-1..E-6; P0: E-1 runner resolution, E-2 e2e green)
  - [x] decisions/2026-07-27-hybrid-qa-driver.md (revises framework QA.md 2026-04-23; propagation = FR-7)
  - [x] Gate 1 run + pass (FAIL on E-4/E-6 Verified-by → fixed → PASS)
- [x] Gate: prd
- [x] Stage: Design
  - [x] User design answers folded in (claude-in-chrome OK; e2e local-only; FR-5 direct to devx main)
  - [x] Grounding fan-out: e2e harness / devx engine internals / runner idiom (3 Explore agents)
  - [x] design.md drafted (template-complete, cited paths grep-verified)
  - [x] Coverage-judge subagent → table JSON
  - [x] Gate 2 run (`devx gate coverage 41ee13 --table …`) + pass (CONCERNS → persona rows thickened → revise → PASS)
- [x] Gate: coverage(design)
- [x] Stage: Plan
  - [x] Deferred design question closed: `writeEngineTemplates` runs on init upgrade (init-upgrade.ts:688) — template installs; no fallback needed
  - [x] plan.md drafted (7 phases; 1∥2∥3, 4→5→6→7)
  - [x] Critique pass: 4 lens subagents (pm/architect/dev/qa); 17 findings applied incl. RED-prereq hoist, prod-API define, INFRA: sentinel, E-5 wrapper split → decisions/2026-07-27-plan-critique.md
  - [x] Coverage-judge subagent → table JSON (E-5 partial, rest covered)
  - [x] Gate 3 run (`devx gate coverage 41ee13 --table …`) → CONCERNS (E-5 substitution caveat recorded; P0 floor passed) → plan_verified, stage: red
  - [x] Commit + status log
- [x] Gate: coverage(plan)
- [ ] Stage: RED
- [ ] Gate: evals
- [ ] Stage: Execute
- [ ] Stage: Retro
- [ ] Stage: Outcome
