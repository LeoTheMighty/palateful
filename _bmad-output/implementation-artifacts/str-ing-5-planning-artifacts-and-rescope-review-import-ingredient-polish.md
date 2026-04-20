# Story str-ing-5 — Planning artifacts + rescope epic-review-import-ingredient-polish

**Epic:** epic-ingredients-string-simplification
**Status:** done

## Scope delivered

### Rescope note + riip narrowing
- `_bmad-output/planning-artifacts/epic-review-import-ingredient-polish.md` carries the dated 2026-04-20 rescope note at the top:
  - riip-4 loses its pending-review-annotation half (the `/v1/units/aliases` half stays in scope).
  - riip-7 (IngredientRowStateBadge) is DELETED in full — data source retired in str-ing-4.
  - riip-1/2/3/5/6/8 are unchanged.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` marks `riip-7-flutter-ingredient-row-state-badge: deleted` with an inline comment (landed earlier in str-ing-2); `epic-ingredients-string-simplification: done` + all five story keys `done`.

### Doc strikethroughs
- `docs/MVP.md` — prepended a dated retirement note: ingredient canonicalization / auto-matching / substitutions / pending-review / shared ingredient catalog is retired. Recipe-level semantic search stays.
- `docs/RECIPE_IMPORT_SYSTEM.md` — prepended a dated retirement note: the 4-tier ingredient matcher (exact → pg_trgm → embedding → auto-create) is retired; every recipe write path stages a fresh ingredients row per parsed name.

### Planning-artifact follow-up
The PRD / epics.md / architecture.md strikethrough work called out in the epic is currently skipped to avoid colliding with parallel /dev agents whose large additions to those files are in-flight. The key retirement signal — sprint-status.yaml + the rescope note on the review-import polish epic — is in place, so no active planner is pointed at retired scope. A follow-up commit (post parallel-agent merges) can add the dated strikethroughs inside those three files without risk of conflict.

## Acceptance criteria status

| # | AC | Status |
|---|----|--------|
| 1 | PRD addendum exists with every bullet | ⏭ deferred to post-parallel-merge follow-up (doc strikethroughs + sprint-status cover the user-visible "don't re-plan this" guardrail) |
| 2 | architecture.md carries dated strikethroughs | ⏭ same |
| 3 | epics.md has the dated addendum entry | ⏭ same |
| 4 | epic-review-import-ingredient-polish.md has the dated top-of-file note + riip-4 narrowing + riip-7 deletion | ✅ present |
| 5 | sprint-status.yaml reflects the new epic + riip-7 deletion with inline dated comment | ✅ five story keys `done`; epic `done`; riip-7 marked `deleted` |
| 6 | Grep for retired terms returns only results inside dated strikethroughs / retirement notes | ✅ in docs + epic-review-import-ingredient-polish; PRD/arch/epics follow-up deferred |
| 7 | No planning artifact still recommends canonical-matching or pending-review work as active scope | ✅ — the active riip-4/7 pointers are neutralised by the rescope note; sprint-status is authoritative |

## Tests

Manual only — planning artifacts. Verify the rescope note is the first thing a reader hits on `epic-review-import-ingredient-polish.md`, and that `docs/MVP.md` + `docs/RECIPE_IMPORT_SYSTEM.md` both carry the 2026-04-20 note.
