# Story nfn-1 — Backend per-category prefs check + categories defaults

**Status:** done
**Epic:** epic-notifications-foundation-prefs-copy
**Depends on:** none.

## Scope

Add a 6-category opt-out layer to push notification suppression. Every
non-diagnostic `NotificationType` maps to one of {meals, timers,
shopping, partner_activity, imports, friends_invitations}. `send_to_user`
checks the category preference between the master `push_enabled` check
and the quiet-hours check. PUT prefs accepts a new nested `categories`
dict with strict key validation; GET prefs always echoes a fully-defaulted
categories block (missing keys → True). Legacy `partner_activity` flat
field continues to work as a fallback for old clients.

## File list

- `libraries/utils/utils/services/push_notification.py` [MODIFY] — `NOTIFICATION_CATEGORIES`, `categories_default()`, `_CATEGORY_FOR_TYPE`, `_CATEGORY_BYPASS_TYPES`, `_resolve_category()`, exhaustiveness assertion, suppression check in `send_to_user`, new `suppressed_by_category` key in `base_result`.
- `services/api/src/api/v1/user/push_tokens.py` [MODIFY] — accept + validate `categories` in PUT; emit defaulted `categories` block in GET + PUT responses.
- `libraries/utils/test/test_push_notification.py` [MODIFY] — Tests A/B/C/C2/D + bonus force/TEST/SYSTEM bypass tests.
- `services/api/tests/test_user.py` [MODIFY] — GET defaulted categories, GET preserves user opt-outs, PUT partial merge, PUT unknown key → 400.

## Acceptance criteria

- AC1 — `notification_preferences.categories` JSONB sub-object with 6 keys, all defaulting to True via `categories_default()`. ✅
- AC2 — `_CATEGORY_FOR_TYPE` maps every non-diagnostic type to exactly one category. Module-level assert raises ImportError if a future type is added without a mapping. ✅
- AC3 — `send_to_user` checks category between push_enabled and quiet-hours. On suppression: INFO log `"suppressed (category=...)"` + `suppressed_by_category: True` in response. ✅
- AC4 — `TEST` (and `SYSTEM`/`NEW_FEEDBACK` admin types) bypass the category check. `force=True` bypasses too. ✅
- AC5 — Legacy `partner_activity` flat field works when `categories` is absent. ✅
- AC6 — `PUT /v1/user/me/notification-preferences` accepts `categories`. Unknown keys → 400 with descriptive error message including the bad key + list of valid keys. Persisted as a merge into the existing dict. ✅
- AC7 — All 5 tests (A imports-suppress, B no-categories-default-on, C legacy-suppress, C2 legacy-pass, D master-wins) pass; plus PUT unknown-key 400 + GET-default-shape tests. ✅

## QA walkthrough

See `nfn-1-qa-walkthrough.md`.
