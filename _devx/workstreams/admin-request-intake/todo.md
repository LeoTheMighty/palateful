<!-- todo.md — Admin Request Intake working memory (harness-fold-in FR-1).

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
- [x] Gate: coverage(design)
- [x] Stage: Plan
- [x] Gate: coverage(plan)
- [x] Stage: RED
- [x] Gate: evals
- [ ] Stage: Execute
  - [ ] Phase 1: Request storage and the create endpoint → arq101
  - [ ] Phase 2: Operator channel — prod-script arguments, read and write scripts → arq102
  - [ ] Phase 3: Request-a-change form in the admin panel → arq103
  - [ ] Phase 4: List, detail and cancel endpoints → arq104
  - [ ] Phase 5: Panel list and detail screens → arq105
  - [ ] Phase 6: Pipeline progress fields in the write script → arq106
  - [ ] Phase 7: Fault signals — faults and fault-adopt modes → arq107
  - [ ] Phase 8: Adopted faults as rows, and routing moves → arq108
- [ ] Stage: Retro
- [ ] Stage: Outcome
