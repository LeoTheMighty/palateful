# Story 12.1: Admin Role System & Auth0 Prod Config

Status: in-progress

## Story

As a developer,
I want an `is_admin` flag on users, a `require_admin` FastAPI dependency, and Auth0 configured for the production domain,
so that admin-only features can be gated behind proper authorization and the app works on `palateful.app`.

## Acceptance Criteria

1. `users` table has `is_admin BOOLEAN DEFAULT FALSE` column
2. All existing users default to `is_admin = false`
3. `require_admin` dependency chains on `get_current_user` and raises 403 for non-admins
4. `GET /v1/users/me` response includes `is_admin: bool` field
5. Auth0 tenant has `https://palateful.app` in allowed callback URLs, web origins, and logout URLs
6. Non-admin users cannot access any endpoint that uses `require_admin`

## Tasks / Subtasks

- [ ] Task 1: Database migration — add `is_admin` boolean column to `users` table
- [ ] Task 2: Update User model — add `is_admin` field
- [ ] Task 3: Create `require_admin` dependency in `services/api/src/dependencies.py`
- [ ] Task 4: Update `GetMe` response to include `is_admin`
- [ ] Task 5: Manual — update Auth0 callback URLs for `palateful.app` (documented, not code)

## Dev Notes

- Migration down_revision: `v1b3s5d7f9h1` (add_recipe_vibes)
- `require_admin` pattern: `user: User = Depends(require_admin)` on admin endpoints
- First admin will be seeded via prod console (Story 12.5) or data migration
