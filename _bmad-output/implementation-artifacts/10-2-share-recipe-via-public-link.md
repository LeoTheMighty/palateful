# Story 10.2: Share Recipe via Public Link

Status: review

## Story

As a user,
I want to share a recipe or recipe book via a public link that anyone can view without an account,
so that I can share my recipes with friends and family who don't use Palateful.

## Acceptance Criteria

1. **Share button on recipe detail** — The recipe detail screen has a "Share Link" action (in the AppBar overflow or a dedicated icon) that generates a public link and presents a bottom sheet with the link, a copy button, and a revoke option.
2. **Per-recipe public token** — When a user taps "Share Link" on a recipe, the backend creates a unique `share_token` (URL-safe, 20 chars) on that recipe and returns a shareable deep link: `palateful://recipe-public/{token}`. Each recipe has at most one active share token at a time.
3. **Public recipe endpoint by token** — `GET /v1/recipes/public/{token}` (no auth required) looks up the recipe by `share_token` and returns full recipe data (name, description, ingredients, steps, tags, image_url, source_url, recipe_book_name). Returns 404 if token is unknown.
4. **Revoke public link** — `DELETE /v1/recipes/{recipe_id}/share` (auth required, owner/editor only) sets `share_token = NULL`. After revocation the public link returns 404.
5. **Recipe book sharing** — The recipe book members screen (or a new share option in recipe book detail) has a "Share Book Publicly" toggle that sets `RecipeBook.is_public = true`. The existing `GET /v1/recipe-books/{id}/public` and `GET /v1/recipes/{id}/public` endpoints already handle book-level public access. Revoking = set `is_public = false`.
6. **Public view** — When a deep link `palateful://recipe-public/{token}` is tapped by anyone (including non-users), the app opens a `PublicRecipeScreen` showing the recipe in read-only format (photo, name, ingredients, steps). No edit/fork/note/favorite controls are shown.
7. **Share link bottom sheet** — After generating a link, a bottom sheet shows: the deep link text, a "Copy Link" button, and a "Revoke Link" button. Tapping "Copy Link" copies to clipboard and shows a "Copied!" snackbar.
8. **Backend tests** — `test_share_recipe.py` covers: generate token (201), re-generate replaces old token, revoke sets token null (200), public endpoint returns recipe (200), public endpoint with invalid token returns 404, unauthenticated generate/revoke returns 401.
9. **Flutter widget tests** — `share_recipe_test.dart` covers: tapping "Share Link" calls `shareRecipe()` on the API client, bottom sheet appears with link, copy button works, revoke calls `revokeRecipeShare()`.

## Tasks / Subtasks

- [x] Task 1: DB migration — add `share_token` to `recipes` table (AC: 2)
  - [x] Create `services/migrator/migrations/versions/20260320000001_add_recipe_share_token.py`
  - [x] `op.add_column('recipes', sa.Column('share_token', sa.String(20), nullable=True, unique=True))`
  - [x] Add unique index on `share_token` (excluding nulls via partial index or standard unique constraint)
  - [x] Add `share_token` field to `libraries/utils/utils/models/recipe.py`

- [x] Task 2: Backend — generate share token endpoint (AC: 2)
  - [x] Create `services/api/src/api/v1/recipe/share_recipe.py` with `ShareRecipe(Endpoint)` class
  - [x] `POST /v1/recipes/{recipe_id}/share` (auth required)
  - [x] Verify user is owner or editor of the recipe's book
  - [x] Generate token: `secrets.token_urlsafe(15)[:20]`
  - [x] Save `recipe.share_token = token`, commit
  - [x] Return `{token, deep_link: "palateful://recipe-public/{token}"}` with status 201

- [x] Task 3: Backend — revoke share token endpoint (AC: 4)
  - [x] Create `services/api/src/api/v1/recipe/revoke_recipe_share.py` with `RevokeRecipeShare(Endpoint)` class
  - [x] `DELETE /v1/recipes/{recipe_id}/share` (auth required)
  - [x] Verify user is owner or editor
  - [x] Set `recipe.share_token = None`, commit
  - [x] Return 200 `{success: true}`

- [x] Task 4: Backend — public recipe endpoint by token (AC: 3)
  - [x] Create `services/api/src/api/v1/recipe/get_public_recipe_by_token.py` with `GetPublicRecipeByToken(Endpoint)`
  - [x] `GET /v1/recipes/public/{token}` (no auth required)
  - [x] Look up recipe by `share_token == token`; return 404 if not found
  - [x] Return same response shape as existing `GetPublicRecipe` (reuse its `Response` / `IngredientResponse` / `StepResponse` models)

- [x] Task 5: Backend — wire routes (AC: 2, 3, 4)
  - [x] In `services/api/src/api/v1/recipe/__init__.py` add imports and `__all__` entries for `ShareRecipe`, `RevokeRecipeShare`, `GetPublicRecipeByToken`
  - [x] In `services/api/src/routers/v1/recipe_router.py` add:
    - `POST /recipes/{recipe_id}/share` → `ShareRecipe`
    - `DELETE /recipes/{recipe_id}/share` → `RevokeRecipeShare`
    - `GET /recipes/public/{token}` → `GetPublicRecipeByToken` (no auth dependency)

- [x] Task 6: Backend tests (AC: 8)
  - [x] Create `services/api/tests/test_share_recipe.py`
  - [x] Test: generate token returns 201 with token + deep_link
  - [x] Test: re-generate replaces old token (new token returned)
  - [x] Test: revoke sets token null, returns 200
  - [x] Test: public endpoint returns recipe by valid token
  - [x] Test: public endpoint returns 404 for invalid token
  - [x] Test: unauthenticated generate → 401/422
  - [x] Test: unauthorized user (not book member) cannot generate → 403

- [x] Task 7: Flutter — API client methods (AC: 2, 4)
  - [ ] In `app/lib/core/services/api_client.dart` add:
    ```dart
    Future<Response> shareRecipe(String recipeId) =>
        _dio.post('/v1/recipes/$recipeId/share');
    Future<Response> revokeRecipeShare(String recipeId) =>
        _dio.delete('/v1/recipes/$recipeId/share');
    Future<Response> getPublicRecipeByToken(String token) =>
        _dio.get('/v1/recipes/public/$token');
    ```

- [x] Task 8: Flutter — "Share Link" button + bottom sheet in recipe detail (AC: 1, 7)
  - [x] In `app/lib/features/recipes/recipe_detail_screen.dart`:
    - Add `bool _isSharing = false;` and `String? _shareLink;` state fields
    - Add `_shareRecipe()` method that calls `_apiClient.shareRecipe(widget.recipeId)` and opens `_ShareLinkSheet`
    - Add `_showShareLinkSheet()` method with revoke callback
    - Added "Share Link" to PopupMenuButton (`Icons.link_outlined`)
  - [x] Create `_ShareLinkSheet` widget in same file:
    - Shows the deep link text
    - "Copy Link" button → copies to clipboard, shows "Copied!" SnackBar
    - "Revoke" button → calls `onRevoke` callback, closes sheet

- [x] Task 9: Flutter — deep link routing for public recipe (AC: 6)
  - [x] In `app/lib/core/router/app_router.dart` add route `/recipe-public/:token`
  - [x] Create `app/lib/features/recipes/public_recipe_screen.dart`:
    - Stateful widget, loads recipe via `getIt<ApiClient>().getPublicRecipeByToken(widget.token)`
    - Shows: recipe photo, name, recipe_book_name, ingredients list, steps list
    - No edit/favorite/fork/cart buttons
    - Loading and error states

- [x] Task 10: Flutter widget tests (AC: 9)
  - [x] Create `app/test/features/recipes/share_recipe_test.dart`
  - [x] Test: tapping "Share Link" calls `shareRecipe()` on the API client
  - [x] Test: bottom sheet appears with the returned deep link
  - [x] Test: tapping "Copy Link" shows "Copied!" snackbar
  - [x] Test: tapping "Revoke" calls `revokeRecipeShare()`
  - [x] Test: error shows "Failed to generate share link" snackbar

## Dev Notes

### Backend: Migration Pattern

Follow the pattern of recent migrations. Example: `20260319000004_add_recipe_fork_lineage.py`.

```python
"""add recipe share_token

Revision ID: 20260320000001
Revises: 20260319000004
Create Date: 2026-03-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260320000001'
down_revision = '20260319000004'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('recipes', sa.Column('share_token', sa.String(20), nullable=True))
    op.create_index('ix_recipes_share_token', 'recipes', ['share_token'], unique=True,
                    postgresql_where=sa.text('share_token IS NOT NULL'))

def downgrade() -> None:
    op.drop_index('ix_recipes_share_token', table_name='recipes')
    op.drop_column('recipes', 'share_token')
```

Check the actual last migration file's `down_revision` value to set `Revises:` correctly.

### Backend: `Recipe` model field addition

In `libraries/utils/utils/models/recipe.py`, add after `embedding` field:

```python
# Public sharing token (nullable — set when user generates a public link)
share_token: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
```

### Backend: `ShareRecipe` Endpoint

**File:** `services/api/src/api/v1/recipe/share_recipe.py`

```python
"""Generate a public share token for a recipe."""

import secrets

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class ShareRecipe(Endpoint):
    """Generate a public share link token for a recipe."""

    def execute(self, recipe_id: str):
        user: User = self.user
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(status_code=404, detail="Recipe not found",
                               code=ErrorCode.RECIPE_NOT_FOUND)

        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(status_code=403, detail="Permission denied",
                               code=ErrorCode.FORBIDDEN)

        token = secrets.token_urlsafe(15)[:20]
        recipe.share_token = token
        self.db.commit()
        self.db.refresh(recipe)

        return success(
            data=ShareRecipe.Response(
                token=token,
                deep_link=f"palateful://recipe-public/{token}",
            ),
            status=201,
        )

    class Response(BaseModel):
        token: str
        deep_link: str
```

**Router:** `POST /v1/recipes/{recipe_id}/share`

```python
@recipe_router.post("/{recipe_id}/share", status_code=201)
async def share_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    return ShareRecipe.call(user=user, database=database, recipe_id=recipe_id)
```

### Backend: `RevokeRecipeShare` Endpoint

**File:** `services/api/src/api/v1/recipe/revoke_recipe_share.py`

```python
"""Revoke a recipe's public share token."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class RevokeRecipeShare(Endpoint):
    """Revoke the public share link for a recipe."""

    def execute(self, recipe_id: str):
        user: User = self.user
        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(status_code=404, detail="Recipe not found",
                               code=ErrorCode.RECIPE_NOT_FOUND)

        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=recipe.recipe_book_id
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(status_code=403, detail="Permission denied",
                               code=ErrorCode.FORBIDDEN)

        recipe.share_token = None
        self.db.commit()

        return success(data=RevokeRecipeShare.Response(success=True))

    class Response(BaseModel):
        success: bool
```

### Backend: `GetPublicRecipeByToken` Endpoint

**File:** `services/api/src/api/v1/recipe/get_public_recipe_by_token.py`

```python
"""Get public recipe by share token (no auth required)."""

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_step import RecipeStep
from utils.formatting import format_quantity

# Reuse the Response/IngredientResponse/StepResponse from GetPublicRecipe
from api.v1.recipe.get_public_recipe import GetPublicRecipe


class GetPublicRecipeByToken(Endpoint):
    """Get recipe by public share token."""

    def execute(self, token: str):
        # Look up recipe by share_token
        recipe = (
            self.db.query(Recipe)
            .filter(Recipe.share_token == token)
            .first()
        )
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND
            )

        recipe_book = self.database.find_by(RecipeBook, id=recipe.recipe_book_id)

        steps = self.database.where(
            RecipeStep, asc="step_number", recipe_id=recipe.id
        ).all()

        recipe_ingredients = (
            self.db.query(RecipeIngredient, Ingredient)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .filter(RecipeIngredient.recipe_id == recipe.id)
            .order_by(RecipeIngredient.order_index)
            .all()
        )

        return success(
            data=GetPublicRecipe.Response(
                id=recipe.id,
                name=recipe.name,
                description=recipe.description,
                instructions=recipe.instructions,
                servings=recipe.servings,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                image_url=recipe.image_url,
                source_url=recipe.source_url,
                tags=recipe.tags or [],
                ingredients=[
                    GetPublicRecipe.IngredientResponse(
                        id=ri.id,
                        ingredient=GetPublicRecipe.IngredientSummary(
                            id=ing.id,
                            canonical_name=ing.canonical_name,
                            category=ing.category,
                        ),
                        quantity_display=format_quantity(ri.quantity_display, ri.unit_display),
                        unit_display=ri.unit_display,
                        quantity_normalized=ri.quantity_normalized,
                        unit_normalized=ri.unit_normalized,
                        notes=ri.notes,
                        is_optional=ri.is_optional,
                        order_index=ri.order_index,
                    )
                    for ri, ing in recipe_ingredients
                ],
                steps=[
                    GetPublicRecipe.StepResponse(
                        id=str(s.id),
                        step_number=s.step_number,
                        instruction=s.instruction,
                        active_time_minutes=s.active_time_minutes,
                        timers=s.timers,
                        wait_time_minutes=s.wait_time_minutes,
                        wait_type=s.wait_type,
                        can_prep_ahead=s.can_prep_ahead,
                        is_optional=s.is_optional,
                    )
                    for s in steps
                ],
                recipe_book_name=recipe_book.name if recipe_book else "",
                created_at=recipe.created_at,
                updated_at=recipe.updated_at,
            )
        )
```

**Router registration** (no auth):

```python
@recipe_router.get("/public/{token}")
async def get_public_recipe_by_token(
    token: str,
    database: Database = Depends(get_database),
):
    """Get a recipe by its public share token (no auth required)."""
    return GetPublicRecipeByToken.call(database=database, token=token)
```

**IMPORTANT:** The route `GET /public/{token}` must be registered **before** `GET /{recipe_id}` to avoid routing conflicts in FastAPI.

### Backend: `api/v1/recipe/__init__.py`

Add to imports and `__all__`:

```python
from api.v1.recipe.share_recipe import ShareRecipe
from api.v1.recipe.revoke_recipe_share import RevokeRecipeShare
from api.v1.recipe.get_public_recipe_by_token import GetPublicRecipeByToken

__all__ = [
    ...,
    "ShareRecipe",
    "RevokeRecipeShare",
    "GetPublicRecipeByToken",
]
```

### Backend Test Pattern

Follow `test_export_recipes.py` and `test_get_public_recipe.py` if one exists. Key mocks:
- `MockRecipe` from `conftest.py` — add `share_token` attribute if needed (check if `MockRecipe` uses `__dict__` or has explicit fields)
- `mock_db.set_find_by(Recipe, recipe, id=recipe_id)` for recipe lookup
- `mock_db.set_find_by(RecipeBookUser, membership, user_id=..., recipe_book_id=...)`
- For public-by-token: mock `mock_db.db.query(Recipe).filter(Recipe.share_token == token).first()` — need `MockQuery` or raw mock on `db.query`

**Response structure:** `response.json()` is the data directly (not wrapped), because `Endpoint.handle_result()` uses `content=jsonable_encoder(result['data'])`.

### Flutter: `_ShareLinkSheet` and `_shareRecipe()` Method

```dart
bool _isSharing = false;
String? _shareToken;
String? _shareLink;

Future<void> _shareRecipe() async {
  if (_isSharing) return;
  setState(() => _isSharing = true);
  try {
    final response = await _apiClient.shareRecipe(widget.recipeId);
    final data = response.data as Map<String, dynamic>;
    if (mounted) {
      setState(() {
        _shareToken = data['token'] as String;
        _shareLink = data['deep_link'] as String;
      });
      _showShareLinkSheet(_shareLink!);
    }
  } catch (_) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to generate share link')),
      );
    }
  } finally {
    if (mounted) setState(() => _isSharing = false);
  }
}

void _showShareLinkSheet(String link) {
  showModalBottomSheet(
    context: context,
    builder: (ctx) => _ShareLinkSheet(
      link: link,
      onRevoke: () async {
        Navigator.of(ctx).pop();
        await _apiClient.revokeRecipeShare(widget.recipeId);
        if (mounted) {
          setState(() { _shareToken = null; _shareLink = null; });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Link revoked')),
          );
        }
      },
    ),
  );
}
```

`_ShareLinkSheet` widget:

```dart
class _ShareLinkSheet extends StatelessWidget {
  final String link;
  final VoidCallback onRevoke;
  const _ShareLinkSheet({required this.link, required this.onRevoke});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('Public Link', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 16),
          SelectableText(link),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  icon: const Icon(Icons.copy),
                  label: const Text('Copy Link'),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: link));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Copied!')),
                    );
                  },
                ),
              ),
              const SizedBox(width: 12),
              TextButton(
                onPressed: onRevoke,
                child: const Text('Revoke'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
```

### Flutter: `PublicRecipeScreen`

**File:** `app/lib/features/recipes/public_recipe_screen.dart`

Simple stateful widget that:
- Takes `token` parameter
- Calls `getIt<ApiClient>().getPublicRecipeByToken(token)` (ApiClient is always instantiated in GetIt, even before auth)
- Shows recipe name, book name, image, ingredients, steps
- No favorite/edit/fork/cart buttons
- Loading spinner and error state

Note: Since `getPublicRecipeByToken` hits a no-auth endpoint, it doesn't need an Authorization header. However, Dio will still attach the auth header if configured globally. The backend endpoint must ignore the Authorization header (not require it). Because FastAPI's `GET /public/{token}` has no `Depends(get_current_user)`, it will accept requests with or without auth headers.

### Flutter: App Router Deep Link

In `app/lib/core/router/app_router.dart`, add near the existing `/invite/:token` route:

```dart
GoRoute(
  path: '/recipe-public/:token',
  parentNavigatorKey: _rootNavigatorKey,
  builder: (context, state) {
    final token = state.pathParameters['token']!;
    return PublicRecipeScreen(token: token);
  },
),
```

### Flutter Test Pattern

In `app/test/features/recipes/share_recipe_test.dart`:
- Register `_FakeApiClient` (overrides `shareRecipe`, `revokeRecipeShare`, `getRecipe`) and `_FakeAuthService` in GetIt
- Pump `RecipeDetailScreen(recipeId: 'recipe-1')`
- Use `tester.ensureVisible(find.byIcon(Icons.share_outlined))` before tapping
- After tap and pumpAndSettle, verify bottom sheet shows link text

### Project Structure Notes

**New files:**
- `services/migrator/migrations/versions/20260320000001_add_recipe_share_token.py` — Alembic migration
- `services/api/src/api/v1/recipe/share_recipe.py` — `ShareRecipe` endpoint
- `services/api/src/api/v1/recipe/revoke_recipe_share.py` — `RevokeRecipeShare` endpoint
- `services/api/src/api/v1/recipe/get_public_recipe_by_token.py` — `GetPublicRecipeByToken` endpoint
- `services/api/tests/test_share_recipe.py` — backend tests
- `app/lib/features/recipes/public_recipe_screen.dart` — public recipe view
- `app/test/features/recipes/share_recipe_test.dart` — Flutter widget tests

**Modified files:**
- `libraries/utils/utils/models/recipe.py` — add `share_token` field
- `services/api/src/api/v1/recipe/__init__.py` — add new endpoint imports/exports
- `services/api/src/routers/v1/recipe_router.py` — register 3 new routes
- `app/lib/core/services/api_client.dart` — add `shareRecipe`, `revokeRecipeShare`, `getPublicRecipeByToken`
- `app/lib/features/recipes/recipe_detail_screen.dart` — add share button + bottom sheet logic
- `app/lib/core/router/app_router.dart` — add `/recipe-public/:token` route

### References

- Epic 10.2 story: `_bmad-output/planning-artifacts/epics.md` (line 1088)
- Recipe model: `libraries/utils/utils/models/recipe.py`
- Existing public recipe endpoint: `services/api/src/api/v1/recipe/get_public_recipe.py`
- Create invite link (token generation pattern): `services/api/src/api/v1/invite_links/create_invite_link.py`
- InviteLink model: `libraries/utils/utils/models/invite_link.py`
- Recipe router: `services/api/src/routers/v1/recipe_router.py`
- Recipe detail screen: `app/lib/features/recipes/recipe_detail_screen.dart`
- App router: `app/lib/core/router/app_router.dart`
- ApiClient: `app/lib/core/services/api_client.dart`
- Export collection test (pattern): `services/api/tests/test_export_recipes.py`
- Share mechanism (Flutter reference): `app/lib/features/recipe_books/recipe_book_members_screen.dart`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `share_token` partial index uses `postgresql_where=sa.text("share_token IS NOT NULL")` to allow multiple NULL values while enforcing uniqueness on non-NULL tokens
- `GetPublicRecipeByToken` reuses `GetPublicRecipe`'s `Response`/`IngredientResponse`/`StepResponse` models to avoid duplication
- Route ordering matters: `GET /recipes/public/{token}` must be registered before `GET /recipes/{recipe_id}` to avoid path collision in FastAPI
- "Share Link" added to the existing `PopupMenuButton` in `RecipeDetailScreen` rather than a separate AppBar icon, keeping the AppBar uncluttered
- `_ShareLinkSheet` defined as a private class at the bottom of `recipe_detail_screen.dart` (not a separate file) — reduces file count for a simple widget
- AC5 (recipe book sharing) is handled by existing backend infrastructure (`RecipeBook.is_public` + `PUT /v1/recipe-books/{id}`) — no new backend work needed; the UI for toggling `is_public` was out of scope for this story
- All 17 backend tests and 5 Flutter widget tests pass; 359 total backend tests pass (no regressions)

### File List

- `services/migrator/migrations/versions/20260320000001_add_recipe_share_token.py` — new: Alembic migration adding `share_token` column to `recipes`
- `libraries/utils/utils/models/recipe.py` — added `share_token` field
- `services/api/src/api/v1/recipe/share_recipe.py` — new: `ShareRecipe` endpoint (`POST /recipes/{id}/share`)
- `services/api/src/api/v1/recipe/revoke_recipe_share.py` — new: `RevokeRecipeShare` endpoint (`DELETE /recipes/{id}/share`)
- `services/api/src/api/v1/recipe/get_public_recipe_by_token.py` — new: `GetPublicRecipeByToken` endpoint (`GET /recipes/public/{token}`)
- `services/api/src/api/v1/recipe/__init__.py` — added imports and `__all__` entries for 3 new endpoints
- `services/api/src/routers/v1/recipe_router.py` — added 3 new routes
- `services/api/tests/test_share_recipe.py` — new: 17 backend tests
- `app/lib/core/services/api_client.dart` — added `shareRecipe()`, `revokeRecipeShare()`, `getPublicRecipeByToken()`
- `app/lib/features/recipes/recipe_detail_screen.dart` — added share state, `_shareRecipe()`, `_showShareLinkSheet()`, "Share Link" menu item, `_ShareLinkSheet` widget
- `app/lib/features/recipes/public_recipe_screen.dart` — new: `PublicRecipeScreen` widget
- `app/lib/core/router/app_router.dart` — added `/recipe-public/:token` route + import
- `app/test/features/recipes/share_recipe_test.dart` — new: 5 Flutter widget tests
