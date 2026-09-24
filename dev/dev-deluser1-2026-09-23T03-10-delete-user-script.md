---
hash: deluser1
type: dev
created: 2026-09-23T03:10:00-06:00
title: delete_user.py — make a prod test identity reversible
from: dev/dev-envspell1-2026-09-22T21:30-environment-spelling-divergence.md
status: ready
owner: null
branch: null
---

## Goal

A prod test user can be created in five minutes and **cannot be removed at
all**. There is no deletion path anywhere: `services/api/scripts/` has no
delete script, and nothing else offers one. Leo took that trade knowingly on
2026-09-23 to unblock testing against prod without using his own account;
this story is the other half of it.

Until this exists, every test run accretes rows in the prod database that
nobody can remove, and the test user shows up in `admin/list_users.py` and
skews `admin/get_stats.py`.

## The part that makes this harder than it looks

**The app re-provisions on every authed request.** `get_current_user` calls
`find_or_create_by(User, auth0_id=…)`, then `_ensure_default_calendar` and
`_ensure_system_trying_out` (`services/api/src/dependencies.py`). Deleting a
user while their Auth0 identity can still authenticate simply re-creates the
user, a default calendar and a starter recipe book on the next request.

So **deletion has an ordering requirement, not just a table list**: the Auth0
identity must be disabled or deleted *first*, then the rows purged. A script
that only does the second half will appear to work and silently undo itself.

## Measured shape of the problem (2026-09-23)

- **34 models reference a user** via `user_id` / `owner_id` / `created_by` /
  `invited_by`. 31 of those FKs declare an `ondelete`; **3 do not** and will
  raise on a plain `DELETE`.
- Repo-wide the mix is `CASCADE` ×56, `SET NULL` ×43, `RESTRICT` ×4. So a
  single `DELETE FROM users` neither fully cascades nor fully fails — it
  partially succeeds, which is the worst of the three outcomes.
- Membership tables (`calendar_user`, `pantry_user`, `recipe_book_user`,
  `shopping_list_user`, `meal_event_participant`) carry **two** user FKs
  (`user_id` and `invited_by`), so a row can survive as an orphan referencing
  a deleted inviter.

## Acceptance criteria

- [ ] `services/api/scripts/delete_user.py`, in the house style of the other
      ops scripts: `--id-or-email`, **dry-run by default**, `--yes` to
      commit, exit codes matching the existing convention (`0` success/no-op,
      `2` no match, `1` error).
- [ ] **Dry-run prints exactly what would be removed**, per table, with
      counts — not a summary. This is the output a human approves before a
      destructive prod action, so it must be readable and complete.
- [ ] Decide and document **hard delete vs anonymise**, rather than picking
      silently. Anonymising (null the auth0_id/email, mark archived) keeps FK
      graphs intact and preserves aggregate history; hard delete actually
      removes the data. The `SET NULL` FKs suggest the schema already expects
      the anonymise shape for some tables.
- [ ] Handles the three user-referencing FKs that declare no `ondelete`, and
      the double-FK membership tables, explicitly — by name, with a test.
- [ ] Refuses to run against a user that is not the designated test identity
      unless `--force` is passed, and names the guard in its docstring. A
      script that can delete Leo's account by typo is worse than no script.
- [ ] Documents the ordering requirement at the top: **disable the Auth0
      identity first**, or the deletion undoes itself on the next request.
- [ ] Writes an audit row (`service="audit"`) like the other mutating ops
      scripts, so the removal is itself queryable.
- [ ] `CLAUDE.md`'s Ops Scripts section gains an entry, as every other script
      there has.

## Technical notes

- Do not build this as an API endpoint. It is an ops action, run rarely, with
  a human reading a dry-run first — the same shape as `promote_admin.py`.
- `error_log.user_id` is `SET NULL`, so deleting a user does **not** destroy
  the error history — worth stating, because the instinct is to assume it
  does and to avoid deleting for that reason.
- Check whether any table's `RESTRICT` FK blocks deletion outright; if so the
  script must say which and why rather than failing with a raw
  `IntegrityError`.

## Status log
- 2026-09-23T03:10 — filed at 41's direction alongside Leo's decision to
  create a prod test user now, so the reversibility work is tracked rather
  than remembered. The FK counts above are measured from
  `libraries/utils/utils/models/`, not estimated.
