# nfn-4 — QA walkthrough

Open the app on iPhone, log in as Leo, open Profile → Notifications.

## Layout

- Section order top-to-bottom:
  1. **Push Notifications** (master switch)
  2. **Notifications by category** (6 switches)
  3. **Import behavior** (auto-save toggle, NOT a notification opt-out)
  4. **Quiet Hours** (start/end picker)
  5. **Timezone**
- Section captions explain each block.

## Defaults (fresh user / never-set)

- All 6 category switches are ON.
- Body of each row shows the explanatory subtitle.

## Single category opt-out

1. Toggle "Imports" off.
2. Trigger an import that lands in awaiting-review.
3. No push lands. API logs:
   ```
   push_notifications: suppressed (category=imports) user=<leo> type=import_needs_review
   ```
4. Re-open the screen later — Imports stays off (server-roundtripped).

## Master OFF: disabled state, state preserved

1. With "Imports" off (from above), flip master "Push Notifications" off.
2. All 6 category switches go grey + un-tappable (Switch.onChanged is null).
3. Each switch keeps its prior value visually.
4. Flip master back on → category switches re-enable; Imports is still off.

## Auto-save imports row is visually separated

- "Import behavior" section sits below the categories block with a
  caption "Not a notification setting…".
- The row is enabled regardless of master notification toggle (it
  controls a backend behavior, not a push opt-out).

## Save failure path

- Disconnect from network → toggle a category → SnackBar "Failed to
  save preference." → switch reverts to its previous state.

## Logs

After each successful toggle, you should see a single PUT to
`/v1/users/me/notification-preferences` with body
`{"categories": {<key>: <value>}}`.
