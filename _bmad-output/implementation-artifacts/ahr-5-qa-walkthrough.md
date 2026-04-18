# QA Walkthrough — ahr-5 See-all Footer

**Status:** complete
**Epic:** epic-activity-hub-redesign
**Depends on:** ahr-4 (Imports tab shell)

## What to verify

### A. Footer visibility

- [ ] With zero archived imports AND zero >30d-completed items →
      footer is not rendered at all (no caret row).
- [ ] With ≥1 archived OR ≥1 >30d-completed → footer shows
      collapsed row "See all (N) ›".
- [ ] N is the sum of both counts.

### B. Expand + muted rendering

- [ ] Tap "See all (N)" → rows load lazily (single spinner).
- [ ] Rows render in muted type (`onSurface` alpha 0.65).
- [ ] Rows are sorted by archived_at DESC, falling back to
      created_at DESC.
- [ ] Tap again → list collapses; no network refetch on re-expand.

### C. Swipe-right to unarchive

- [ ] Swipe-right on any See-all row → row animates out, 3s
      snackbar "Unarchived · Undo".
- [ ] `POST /v1/import-items/{id}/unarchive` fires.
- [ ] The row comes back into its live section on the next 30s
      poll (e.g., yellow row → Needs Review).

### D. Undo

- [ ] Swipe-right a row, tap Undo within 3s.
- [ ] Row returns to the See-all list.
- [ ] `POST /v1/import-items/{id}/archive` fires to put it back.

### E. "All clear" + see-all

- [ ] Seed zero live items but ≥1 archived.
- [ ] Imports tab shows "All clear — no imports yet" centered AND
      the See-all footer below it.
- [ ] Footer is fully functional (expand/swipe).

### F. Dark mode legibility

- [ ] Switch to dark theme.
- [ ] See-all rows render muted but legible. Chip/text contrast
      remains acceptable.
