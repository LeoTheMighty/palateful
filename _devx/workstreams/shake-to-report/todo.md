<!-- todo.md — Shake To Report working memory (harness-fold-in FR-1).

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
  - [ ] Phase 1: Server accepts the trigger and serves the ring → shk101
  - [ ] Phase 2: One feedback launcher with an app-wide flush → shk102
  - [ ] Phase 3: Motion dependency and the shake recognizer → shk103
  - [ ] Phase 4: Shake host — prompt, suppression, feedback for every admitted user → shk104
  - [ ] Phase 5: Device switch and discoverability hint → shk105
  - [ ] Phase 6: Admins get the dev-request form → shk106
- [ ] Stage: Retro
- [ ] Stage: Outcome
