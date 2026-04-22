# Story nfn-2 — `notification_copy.py` module + rich import copy

**Status:** done
**Epic:** epic-notifications-foundation-prefs-copy
**Depends on:** nfn-1.

## Scope

New module `libraries/utils/utils/services/notification_copy.py`: one
pure function per `(NotificationType, variant)` returning a `(title,
body)` tuple. Initially populated with `import_needs_review` (3
variants: single+name, single-no-name, bulk) and `recipe_added`
(consumed by nfn-3). `notify_import_needs_review` refactored to load
the first awaiting-review `ImportItem` for the recipe name + image_url
when `pending_review_items == 1`; bulk variant skips the lookup.

## File list

- `libraries/utils/utils/services/notification_copy.py` [NEW] — emoji palette + 2 copy functions.
- `libraries/utils/utils/services/import_notifications.py` [REWRITE] — load item, pull name+image, call into copy module, pass image_url to PushNotification.
- `libraries/utils/test/test_notification_copy.py` [NEW] — pure-function tests for both copy functions.
- `libraries/utils/test/test_import_notifications.py` [NEW] — Tests A/B/C/D/E + bonus fallback/no-send paths.

## Acceptance criteria

- AC1 — `notification_copy.py` exports `import_needs_review` and `recipe_added`. Both pure, kw-only, return `(title, body)`. ✅
- AC2 — Single variant with `recipe_name="Sweet Potato Quiche"` → title contains `"Sweet Potato Quiche"` + 🍳. Body fixed string. ✅
- AC3 — Single variant with no name → fallback `"Your recipe is ready to review"`. ✅
- AC4 — Bulk variant (`count > 1`) → `"Your bulk import is ready"` + body `"{count} recipes need a quick review."`. Recipe name ignored. ✅
- AC5 — `notify_import_needs_review`: bulk path does NOT touch DB; single path does one query for the first awaiting-review item. ✅
- AC6 — `image_url` from `parsed_recipe.image_url` is passed to `PushNotification(image_url=...)` when present; else `None`. ✅
- AC7 — Defensive against missing/non-dict `parsed_recipe`, missing/empty `name`, missing `image_url`. ✅
- AC8 — All failure paths swallowed (try/except logs `.exception` and returns). ✅

## QA walkthrough

See `nfn-2-qa-walkthrough.md`.
