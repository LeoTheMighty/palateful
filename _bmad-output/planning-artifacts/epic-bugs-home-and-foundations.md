<!-- refined via party-mode 2026-04-16 -->
# Epic: Home Screen Declutter & Foundation Gaps

## Overview

A grab-bag of high-leverage, low-effort fixes that don't individually justify an epic but collectively move the app from "works" to "trustworthy to dogfood." Two cleanups on the home screen (remove AI chat entry, consolidate sort+filter), one onboarding gap (every user needs a default shopping list), and one ops gap (Leo still can't promote himself to admin because no script exists).

**Goal:** After this epic, the home screen feels intentional instead of busy, every new user lands with a shopping list ready to use, and Leo can run a one-line command to promote himself in prod.

## Design Principles (refined via party-mode 2026-04-16)

1. **Delete is the best cleanup** — remove the AI chat button and the separate sort row. Don't restyle.
2. **Defaults are invisible when right** — a new user never knows the system auto-created a shopping list for them; they just find it already there.
3. **Idempotent post-commit beats widened transactions** (Winston) — onboarding doesn't expand its critical path to cover shopping-list creation. If the post-commit write fails, a one-shot migration sweep mops it up.
4. **Admin-only surfaces gate on `is_admin`** (Sally+John) — the re-homed AI chat entry is hidden from non-admins. Don't advertise an experimental feature to accounts that'll never use it.
5. **Sort and filter have different affordances in the same sheet** (Sally) — sort is a radio list (monoexclusive), filter is chip multiselect. One Clear-All with snackbar-undo, not two scoped clears.
6. **Audit-log every admin-invoked mutation** (Murat) — the promote-admin script writes an audit row on every role change with actor, target, timestamp.
7. **One script, both directions** (Murat) — promote and demote live in the same script behind a flag; Leo can undo his own mistake without a second file.

## Locked Decisions (carry forward to activity-hub and calendar-ux workshops)

- No feature flags, no backwards-compat shims.
- Admin-only gates live on `is_admin`. No route-level flags or env vars.
- Destructive user actions use snackbar-undo (3s). No modal confirms for reversible ops.
- Audit-log all admin-invoked mutations via the existing ErrorLog / audit path.
- Idempotent writes over wider transactions (post-commit hooks > transaction widening).
- Directories: ops scripts → `services/api/scripts/`; migrations → `services/migrator/migrations/`; Flutter feature subdirs → `app/lib/features/<area>/widgets/`.
- No stories for capabilities without a named user ask.

## File Structure (expected)

```
app/lib/features/home/
├── home_screen.dart                    # MODIFIED — remove AI chat header button, remove sort chip row
└── widgets/
    ├── sort_chips.dart                 # DELETED (logic folds into filter_sort_sheet)
    ├── filter_pill.dart                # MODIFIED — icon-only, opens combined sheet
    └── filter_sort_sheet.dart          # NEW — radio sort section + chip filter section

app/lib/features/profile/
└── profile_screen.dart                 # MODIFIED — admin-only AI Assistant entry

services/api/src/api/v1/user/
└── complete_onboarding.py              # MODIFIED — post-commit hook creates default shopping list
services/api/src/core/
└── shopping_list_bootstrap.py          # NEW — single idempotent function reused by onboarding + CreateShoppingList + backfill

services/migrator/migrations/
└── 2026XXXX_backfill_default_shopping_list.py  # NEW — one-shot, gated on onboarding_completed_at IS NOT NULL

services/api/scripts/
└── promote_admin.py                    # NEW — promote/demote by email; dry-run default; audit-logs
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| bugs-home-1 | Remove AI chat from home header; admin-only Profile entry | 🟡 P1 | 0.25 d | None |
| bugs-home-2 | Consolidate sort + filter into single icon + sheet | 🟡 P1 | 0.5–1 d | bugs-home-1 (header edits) |
| bugs-onb-1 | Onboarding default shopping list + one-shot backfill | 🔴 P0 | 0.5–1 d | None (parallel) |
| bugs-adm-1 | Admin promotion/demotion script with audit logging | 🔴 P0 | 0.25 d | None (parallel) |

**Total estimated effort: 1.5–2.5 days**

---

## Story bugs-home-1: Remove AI chat from home header; admin-only Profile entry

As Leo,
I want the AI assistant chat entry removed from the home screen header and re-homed behind an admin-only Profile entry,
so that the main surface stops advertising a feature that's redundant with MCP for the only user who'd use it, while the route stays reachable for my own testing.

### Acceptance Criteria

1. The "AI Assistant" chat button at `home_screen.dart:552-557` is removed.
2. The Profile tab gains an "AI Assistant (internal)" row that is **only rendered when `user.is_admin == true`**. Non-admin users never see it.
3. The chat route, screens, and providers are not deleted — the Profile entry navigates to the existing chat screen unmodified.
4. Home header vertical rhythm stays clean after removal — recipe grid moves up by the height of the removed button, with no empty gap filling.
5. No analytics cleanup code is added. Stale "chat_opened_from_home" events decay naturally.
6. No new feature flags.

### Key Files
- Modify: `app/lib/features/home/home_screen.dart`
- Modify: `app/lib/features/profile/profile_screen.dart`
- Preserve: `app/lib/features/chat/`

---

## Story bugs-home-2: Consolidate sort + filter into single icon + sheet

As Leo,
I want sort and filter in one bottom sheet behind one funnel icon,
so that my home header stops competing with itself for attention.

### Acceptance Criteria

1. The separate sort chip row is removed. The filter pill becomes a funnel icon in the top row next to the search bar.
2. Tapping the icon opens a bottom sheet with two sections:
   - **Sort by** — radio list (monoexclusive): best, newest, popular, quickest, random. One selected at all times.
   - **Filters** — chip multiselect: book, tags, vibes, and whatever else currently exists.
3. The icon shows a dot badge when any non-default sort OR any filter is active.
4. A single **Clear all** action at the bottom resets both sort (to "best") and filters. A 3s snackbar with **Undo** appears after clearing.
5. Existing state providers for sort and filter are reused, not rebuilt. Sheet dismiss triggers grid refresh via existing hooks.
6. No deep-link preservation requirement — Palateful has no external deep links that reference sort chips.
7. Visual regression check: the recipe grid starts one chip-row higher than before, with no gap.

### Key Files
- Modify: `app/lib/features/home/home_screen.dart`
- Delete: `app/lib/features/home/widgets/sort_chips.dart`
- Modify: `app/lib/features/home/widgets/filter_pill.dart` (icon-only)
- Create: `app/lib/features/home/widgets/filter_sort_sheet.dart`

---

## Story bugs-onb-1: Onboarding default shopping list + one-shot backfill

As a brand-new user,
I want a default shopping list to already exist the first time I open the Cart tab,
so that "Add to Cart" works from my first recipe with zero setup.

### Acceptance Criteria

1. `complete_onboarding` writes the recipe book as it does today, commits, and then calls a **post-commit** hook that invokes a shared idempotent helper `shopping_list_bootstrap.ensure_default(user)`. The helper:
   - returns early if the user already has a `default_shopping_list_id`
   - otherwise creates a shopping list named "Shopping List" and sets the default
2. The onboarding transaction is **not widened** to include the shopping list write. A failure in the post-commit hook is logged and leaves the user with a successfully completed onboarding + no default list. The backfill sweep recovers them.
3. A one-shot migration at `services/migrator/migrations/` runs **once** and sets a default for every user matching:
   ```
   default_shopping_list_id IS NULL
   AND onboarding_completed_at IS NOT NULL
   ```
   This gating prevents resurrecting lists for users who deliberately cleaned up after onboarding. The migration is chunked (500 users/batch) and idempotent on re-run.
4. The existing "auto-set first created list as default" behavior in `CreateShoppingList` is refactored to call the same `shopping_list_bootstrap.ensure_default` helper — one source of truth for default-creation logic across all three entry points (onboarding, manual create, backfill).
5. Flutter: the Cart tab empty-state copy is updated. "Create your first shopping list" is shown only when the user has **no** lists at all (not when they have none as default) — the default-creation flow means new users never see this.
6. Integration test: complete onboarding → assert `default_shopping_list_id` populated within 1s via post-commit hook polling.
7. Regression test: user deletes all their lists → backfill does not recreate one on next login (migration is one-shot, not per-session).

### Key Files
- Modify: `services/api/src/api/v1/user/complete_onboarding.py`
- Create: `services/api/src/core/shopping_list_bootstrap.py` (or equivalent location; single helper)
- Modify: `services/api/src/api/v1/shopping_list/create_shopping_list.py` (use helper)
- Create: `services/migrator/migrations/2026XXXX_backfill_default_shopping_list.py`
- Modify: `app/lib/features/cart/` empty-state copy
- Tests: `services/api/tests/api/v1/user/test_complete_onboarding.py`, `services/api/tests/core/test_shopping_list_bootstrap.py`

---

## Story bugs-adm-1: Admin promotion/demotion script with audit logging

As Leo,
I want a script I can run against prod to promote or demote a user by email, with dry-run as default and a durable audit trail,
so that I can finally use my admin dashboard and safely reverse mistakes.

### Acceptance Criteria

1. `services/api/scripts/promote_admin.py` accepts `--email` (required) and one of `--promote` (default) or `--demote`.
2. Default behavior is **dry-run**: prints full target user record (id, email, display name, created_at, current `is_admin`) and the would-be change. Exits without writing.
3. `--yes` enables the write. Without `--yes`, exits with code 0 after dry-run output.
4. Refuses to run if:
   - `--email` missing
   - no user matches (exits with code 2 and a clear error)
   - multiple users match (exits with code 2 — defensive; shouldn't happen given unique constraint)
   - email match uses exact equality, no `LIKE` / `ILIKE`
5. If the target user is already in the requested state, prints "already {admin|not admin}, no-op" and exits code 0 — idempotent.
6. On successful write, emits an audit row using the existing ErrorLog / audit mechanism with:
   - actor: `"script:promote_admin"`
   - target_user_id, target_email
   - before/after `is_admin` state
   - timestamp (UTC)
7. Logs the change to stdout in a grep-able format: `PROMOTE_ADMIN user_id=<uuid> email=<email> before=<bool> after=<bool> actor=script:promote_admin`
8. Connects via `DATABASE_URL` env var, same pattern as migrator. No running services required.
9. Documentation: one-line invocation added to `CLAUDE.md` under a new "Ops scripts" heading, including the prod-run procedure and an example for demoting (mistake recovery).
10. First prod run promotes `leonid@ac93.org`. Verify via admin dashboard that the role takes effect.

### Key Files
- Create: `services/api/scripts/promote_admin.py`
- Audit: existing ErrorLog / audit model path to confirm audit-write shape
- Modify: `CLAUDE.md`

## Definition of Done (Epic Level)

- Home header has no AI chat button; admin-only Profile entry replaces it.
- Home header has one funnel icon; sort+filter live in one sheet.
- A newly onboarded user's Cart tab has a default shopping list with zero setup.
- Every historically-onboarded user has `default_shopping_list_id` populated after the migration sweep (gated on `onboarding_completed_at IS NOT NULL`).
- Leo promotes himself in prod via `python services/api/scripts/promote_admin.py --email leonid@ac93.org --yes` and sees the admin dashboard unlock.
- An audit row exists for every admin role change made via the script.
