# nfn-3 — QA walkthrough

## End-to-end: shared book partner-add → push lands

1. Have Sarah and Leo on a shared recipe book "Weeknight Dinners"
   (both with `categories.partner_activity = true`, default).
2. Sarah adds a new recipe "Banana Bread" to the book (with a hero
   image).
3. Leo's iPhone gets a push within ~5s:
   - Title: `🍳 New in Weeknight Dinners`
   - Body: `Sarah added Banana Bread`
   - Cover image attached.
4. Sarah does **NOT** get a push (she's the actor; excluded by
   `notify_recipe_book_members(exclude_user_id=...)`).
5. Tap the push → opens the new recipe (existing route, unchanged).

## Per-category opt-out works

1. Leo sets `categories.partner_activity = false` (via Profile →
   Notifications once nfn-4 lands; or via API directly):
   ```
   curl -X PUT -d '{"categories":{"partner_activity":false}}' ...
   ```
2. Sarah adds another recipe.
3. Leo gets no push. API logs:
   ```
   push_notifications: suppressed (category=partner_activity) user=<leo> type=recipe_added
   ```

## Legacy partner_activity flat field works

1. Leo's prefs JSONB has `{"push_enabled": true, "partner_activity": false}` (no `categories` key — pre-nfn-1 client).
2. Sarah adds a recipe.
3. Leo gets no push (legacy fallback path in `send_to_user`).

## No-image recipe still pushes

1. Sarah adds a recipe via the wizard with no image.
2. Leo gets the same push minus the image attachment. No errors.
