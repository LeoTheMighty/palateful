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

> **Corrected 2026-09-24.** Three of the numbers first filed here were
> wrong; see the status log for how. The measured shape is:

- **44 FK columns across 33 tables reference `users.id`.** Exactly **one**
  lacks an `ondelete`: `ingredients.submitted_by_id` (NO ACTION). A plain
  `DELETE FROM users` therefore fails only if the target submitted
  ingredients — narrower than first filed, but still a partial success
  rather than a clean one. Keep the by-name handling: the script outlives
  any one identity.
- **No `RESTRICT` among the user FKs at all**, so the original open question
  about a blocking FK has a settled answer — it does not arise.
- **`error_logs.user_id` has no foreign key at all** — a bare `UUID` column
  (`error_log.py:24`). Error history survives a deletion, which was the
  original conclusion, but **not** by `SET NULL`: nothing nulls those rows,
  so they keep a `user_id` pointing at a user who no longer exists. The
  dry-run has to show them, or "deleted" claims something false.
- **Neither hard delete nor anonymise achieves "no test data left."**
  Measured on the QA identity: **768 referencing rows, 761 of them
  `client_latencies` on a `SET NULL` FK**, which survive a hard delete
  unattributed, plus 6 dangling `error_logs`.
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
- [x] **Decided: hard delete**, not anonymise (palateful-98, agreed by 41).
      With the caveat above — neither achieves "no test data left" — so the
      dry-run prints **"removed" and "kept, unattributed" as separate
      sections**. One number would assert a cleanliness that is not achieved.
- [ ] Handles `ingredients.submitted_by_id` (the one FK with no `ondelete`)
      and the double-FK membership tables explicitly — by name, with a test.
- [x] **Decided: the guard is `--confirm-email` plus refusing `is_admin`
      outright, with no override** (palateful-98) — not `--force`. A flag you
      can add is a flag you can add by reflex. A
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
- Deleting a user does **not** destroy error history — worth stating, since
  the instinct is to assume it does and avoid deleting for that reason. But
  those rows **dangle** rather than null out; see above.
- The ordering requirement cannot be enforced by the script: there is no
  Auth0 Management API client in the repo, only JWKS verification. It takes
  an explicit `--auth0-disabled` attestation and **re-queries after
  committing** — if the row has reappeared, the deletion undid itself and it
  says so loudly (palateful-98).

## Status log
- 2026-09-23T03:10 — filed at 41's direction alongside Leo's decision to
  create a prod test user now, so the reversibility work is tracked rather
  than remembered. The FK counts above are measured from
  `libraries/utils/utils/models/`, not estimated.
- 2026-09-24 — **three of this spec's measured claims were wrong.** Corrected
  above by palateful-98 from prod's `information_schema`, and reproduced
  independently here from the models, which agree with prod. 44 FK columns
  rather than 34 models; **one** missing `ondelete` rather than three; no
  `RESTRICT` among user FKs; and `error_logs.user_id` has no FK at all rather
  than `SET NULL`.

  **The method was at fault, not the care.** The original count came from a
  grep requiring `users.id` and `ondelete` **on the same line**, and
  SQLAlchemy conventionally splits `mapped_column(UUID,
  ForeignKey("users.id", ondelete="CASCADE"), …)` across lines — so every
  multi-line declaration read as "no `ondelete`". A regex over the whole
  `ForeignKey("users.id" …)` block returns 44 and 1, matching prod exactly.

  These numbers were measured, labelled measured, and wrong. That is the
  failure mode "I measured it" does not protect against, and the reason an
  evidence handle has to carry **the command**, not just the claim and the
  ref — a reader given the grep could have seen the same-line assumption in
  seconds. Filed against the entry this repo now carries on that subject.
