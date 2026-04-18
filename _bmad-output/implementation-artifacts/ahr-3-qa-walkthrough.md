# QA Walkthrough — ahr-3 Notifications Tab + Swipe-to-Archive

**Status:** complete
**Epic:** epic-activity-hub-redesign
**Depends on:** ahr-1 (backend archive endpoints), ahr-2 (shell)

## What to verify

### A. Feed renders non-import activities

- [ ] Open `/activity` → Notifications tab is selected by default.
- [ ] Feed shows chronological list of `invitation` / `partner_action`
      / `meal_reminder` rows.
- [ ] `import_*` rows never appear on this tab.
- [ ] Empty state renders "You're all caught up" when there are zero
      non-import activities.

### B. Swipe archives with 3s undo

- [ ] Swipe any row left → row animates out.
- [ ] A 3s snackbar appears reading "Archived · Undo".
- [ ] Watch network: `POST /v1/activities/{id}/archive` fires once
      with the row's id.
- [ ] Wait 3s → snackbar dismisses; the row stays hidden.

### C. Undo restores in-place

- [ ] Swipe a row → snackbar appears.
- [ ] Tap "Undo" within 3s → the row returns to the list at its
      original position.
- [ ] Watch network: `POST /v1/activities/{id}/unarchive` fires.
- [ ] No error toasts appear.

### D. Error path restores the row

- [ ] Simulate a 5xx response from the archive endpoint (or kill
      connectivity briefly).
- [ ] Swipe a row → the row temporarily disappears.
- [ ] Within ~1 second: the row reappears AND an error snackbar reads
      "Couldn't archive, try again".
- [ ] No duplicate row inserted, list order preserved.

### E. Bugs-act-1 tab-open mark-all-read still works

- [ ] Seed one unread `partner_action` activity.
- [ ] Open Notifications tab → the row renders with unread styling.
- [ ] After initial load, inspect: PUT `/v1/activities/{id}/read` fires
      for every unread row.
- [ ] Bottom-nav badge count reflects the new read state.

### F. Polling preserved

- [ ] Stay on the Notifications tab for 35 seconds.
- [ ] Observe: `GET /v1/activities` fires again at ~30s.
- [ ] Any newly-server-archived rows disappear on the poll.

### G. Cross-session session-cache

- [ ] Swipe a row to archive.
- [ ] Without cold-restarting the app, navigate away and back — the
      row stays hidden (the session archive set is respected).
- [ ] Cold-restart the app. Reopen Notifications. The server's
      authoritative list is fetched — archived rows stay out per
      `?include_archived=false` default.

## Regression-safe

- Tab-open mark-all-read from bugs-act-1 still triggers on load.
- No import-typed rows leak into this feed.
- Pull-to-refresh still re-fetches.
