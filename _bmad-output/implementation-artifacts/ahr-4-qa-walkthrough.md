# QA Walkthrough — ahr-4 Imports Tab + Four Color Sections + Swipe Rules

**Status:** complete
**Epic:** epic-activity-hub-redesign
**Depends on:** ahr-1 (backend archive + 409), ahr-2 (shell)

## What to verify

### A. Four sections render in order

- [ ] Open `/activity?tab=imports`.
- [ ] Sections appear top-to-bottom: **In Progress** (blue) → **Needs
      Review** (yellow) → **Failed** (red) → **Auto-Imported** (green).
- [ ] Each section header chip reads "<Name> · <count>".
- [ ] Empty sections are hidden (not rendered with "0 items").

### B. Blue is read-only

- [ ] Seed one in-progress import (status=processing).
- [ ] Blue section shows the row with a small `CircularProgressIndicator`
      glyph at the trailing edge.
- [ ] Try to swipe the row left → nothing happens. No swipe
      affordance is revealed.
- [ ] `POST /v1/import-items/{id}/archive` does NOT fire.
- [ ] Tap the row → navigates to `/recipes/import/review-list/{job_id}`.

### C. Yellow / Red / Green swipe-to-archive

- [ ] Seed at least one row per non-blue section.
- [ ] Swipe any of them left → row animates out, 3s snackbar "Archived
      · Undo".
- [ ] Watch network: `POST /v1/import-items/{id}/archive` fires.
- [ ] Tap "Undo" → row reappears, `POST /v1/import-items/{id}/unarchive`
      fires.

### D. 409 mid-swipe restores with a specific message

- [ ] Seed an awaiting-review item. Have the backend force a 409 on
      the archive call (or race a status flip).
- [ ] Swipe it → optimistic hide + "Can't archive while importing"
      snackbar. Row reappears.
- [ ] No duplicate row inserted, list order preserved.

### E. Tap destinations per state

- [ ] Yellow row → `/recipes/import/review/{itemId}`.
- [ ] Red row → `/recipes/import/review/{itemId}`.
- [ ] Green row → `/recipes/{created_recipe_id}`.

### F. "All clear" empty state

- [ ] Seed zero imports (any status).
- [ ] Imports tab body shows "All clear — no imports yet" centered.
- [ ] Pull down → `GET /v1/import-jobs?status=...` re-fires per
      status.

### G. Polling

- [ ] Stay on Imports tab ~35s.
- [ ] Observe: four parallel `listImportJobs` calls + per-job
      `listImportItems` calls fire again around the 30s mark.

### H. Actionable badge

- [ ] Seed 2 processing + 3 awaiting_review + 1 failed + 4 completed
      items.
- [ ] `importsActionableBadgeProvider` surfaces `6` (= 2+3+1; green
      excluded).
- [ ] After archiving one yellow item, the badge drops to 5 on the
      next poll.

## Regression-safe

- Notifications tab unaffected (ahr-3 behavior preserved).
- `/activity/import-history` route still responds (ahr-7 retires it).
- Legacy `/activity?filter=imports` redirect (ahr-2) still lands on
  this tab.
