# nfn-1 — QA walkthrough

Backend-only story; no UI to click. Walk these in production after deploy
(or against a local stack with the migrations applied).

## Smoke: GET prefs returns categories block

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.palateful.app/v1/users/me/notification-preferences | jq .
```

Expect (for a user who has never set categories):
- `categories.meals == true`
- `categories.timers == true`
- `categories.shopping == true`
- `categories.partner_activity == true`
- `categories.imports == true`
- `categories.friends_invitations == true`

## Smoke: PUT a category opt-out, GET reflects it

```bash
curl -s -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "content-type: application/json" \
  -d '{"categories": {"imports": false}}' \
  https://api.palateful.app/v1/users/me/notification-preferences | jq .categories
```

Expect: `imports == false`, all others still `true`.

## Smoke: PUT with unknown key → 400

```bash
curl -i -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "content-type: application/json" \
  -d '{"categories": {"bogus": true}}' \
  https://api.palateful.app/v1/users/me/notification-preferences
```

Expect: `HTTP/1.1 400`. Body `error_message` contains `bogus` + valid key list.

## End-to-end suppression: opt out of imports, trigger an import

1. Set `categories.imports = false` (above).
2. Trigger an import that lands in awaiting-review (any URL import).
3. Watch API logs (`bin/prod-logs api` or `docker compose logs -f api`).
   Expect a line:
   ```
   push_notifications: suppressed (category=imports) user=<your-id> type=import_needs_review
   ```
4. No push lands on your device.
5. Set `categories.imports = true`. Trigger another import. Push lands.

## Legacy compatibility: pre-categories client

1. As a user who has the **legacy** prefs shape (no `categories` key,
   only `partner_activity: false`), send yourself a `RECIPE_ADDED`
   notification (have someone add a recipe to a shared book).
2. Expect the suppression line:
   ```
   push_notifications: suppressed (category=partner_activity) user=<your-id> type=recipe_added
   ```

## Master switch + categories: master wins

1. Set `push_enabled = false` AND `categories.imports = true`.
2. Trigger an import.
3. Expect `suppressed (user prefs disabled)` log line — never reaches
   the category check.

## TEST push bypasses categories

1. Set every category to `false`.
2. Hit the admin test-push button on yourself.
3. Push lands; logs show no suppression.
