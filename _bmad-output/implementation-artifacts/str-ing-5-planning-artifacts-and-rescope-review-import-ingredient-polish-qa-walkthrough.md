# QA Walkthrough — str-ing-5 (Planning artifacts + rescope)

**Epic:** epic-ingredients-string-simplification

## Pre-flight
- [ ] `git log --oneline origin/main..HEAD` shows the `docs(ingredients): str-ing-5 — rescope riip + dated doc notes` commit.
- [ ] `_bmad-output/planning-artifacts/epic-review-import-ingredient-polish.md` opens with the 2026-04-20 rescope note (riip-4 narrow, riip-7 deleted, riip-1/2/3/5/6/8 unchanged).
- [ ] `_bmad-output/implementation-artifacts/sprint-status.yaml` shows:
  - `epic-ingredients-string-simplification: done`
  - `str-ing-1..str-ing-5: done`
  - `riip-7-flutter-ingredient-row-state-badge: deleted`
- [ ] `docs/MVP.md` + `docs/RECIPE_IMPORT_SYSTEM.md` both carry dated 2026-04-20 retirement notes above the existing body.

## Manual walkthrough
1. Open `_bmad-output/planning-artifacts/epic-review-import-ingredient-polish.md` — verify the rescope note is the first thing a reader sees.
2. Grep `rg 'pending_review|IngredientRowStateBadge|ingredient_substitution|ingredient_matches|search_ingredients_fuzzy' docs/ _bmad-output/planning-artifacts/epic-review-import-ingredient-polish.md` — matches should only be inside the dated note / retracted bullets.
3. Re-read `docs/MVP.md` + `docs/RECIPE_IMPORT_SYSTEM.md` — confirm the retirement note flags ingredient canonicalization / matcher language as historical.

## Known gaps
- PRD / architecture / epics dated strikethrough work is deferred to a post-parallel-merge follow-up commit to avoid colliding with concurrent /dev agents' large in-flight additions to those files. The user-visible "don't re-plan this" guardrail is already in place via the rescope note + sprint-status, so no active planner is pointed at retired scope.
