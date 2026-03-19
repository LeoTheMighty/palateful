# Story 7.1: Shared Recipe Books with Role-Based Access

Status: done

## Story

As a user,
I want to create shared recipe books and control who can view, edit, or manage them,
So that my partner and I can collaborate on recipe collections with clear permissions.

## Acceptance Criteria

1. **Given** I create a recipe book **When** I set it as shared **Then** I am the owner and the book is visually distinguishable from personal books in the UI.
2. **Given** I own a shared book **When** I view it **Then** I can add members by user ID with a role (editor or viewer) and remove existing members.
3. **Given** I am an editor in a shared book **When** I try to add/edit recipes **Then** I can do so; when I try to delete the book or manage members **Then** I am denied with 403.
4. **Given** I am a viewer in a shared book **When** I try to add, edit, or delete recipes **Then** I am denied with 403; I can still browse and cook from all recipes.
5. **Given** I list my recipe books **When** the response arrives **Then** each book includes my role in it (owner/editor/viewer) and whether the book is shared.
6. **Given** I open a recipe book **When** the detail loads **Then** I see the member list with each member's role, and role-appropriate action buttons (edit/add hidden for viewers).
7. **Given** I own a shared book **When** I view the members screen **Then** I can update a member's role or remove them.

## Tasks / Subtasks

- [x] Task 1: Database migration — add `is_shared` to `recipe_books` (AC: #1, #5)
  - [x] Create `services/migrator/migrations/versions/20260319000003_add_is_shared_to_recipe_books.py` with revision ID `j0k1l2m3n4o5`, down_revision `i9j0k1l2m3n4`
  - [x] `upgrade()`: `op.add_column('recipe_books', sa.Column('is_shared', sa.Boolean(), server_default='false', nullable=False))`
  - [x] `downgrade()`: `op.drop_column('recipe_books', 'is_shared')`

- [x] Task 2: Update `RecipeBook` model (AC: #1, #5)
  - [x] In `libraries/utils/utils/models/recipe_book.py`, add `is_shared: Mapped[bool] = mapped_column(Boolean, default=False)` after `is_public`

- [x] Task 3: Update `CreateRecipeBook` to accept `is_shared` (AC: #1)
  - [x] In `CreateRecipeBook.Params`, add `is_shared: bool = False`
  - [x] In `execute()`, pass `is_shared=params.is_shared` to `RecipeBook(...)` constructor
  - [x] Include `is_shared` in `CreateRecipeBook.Response`

- [x] Task 4: Update `ListRecipeBooks` response to include role and sharing info (AC: #5)
  - [x] In the query, add `.add_columns(RecipeBookUser.role, func.count(RecipeBookUser.user_id.distinct()).label('member_count'))` — join members for count; current user's role comes from the existing `RecipeBookUser` join
  - [x] Update `RecipeBookItem` to add `user_role: str`, `is_shared: bool`, `member_count: int = 0`
  - [x] Pass the values when constructing items: `user_role=membership.role`, `is_shared=recipe_book.is_shared`, `member_count=member_count`
  - [x] **Implementation note**: The current query already joins `RecipeBookUser` on `user_id == user.id` so each row has one membership row — `user_role` = `membership.role`. For `member_count`, add a subquery or second join with count of all members for that book.

- [x] Task 5: Update `GetRecipeBook` response to include user role and members (AC: #6)
  - [x] Add inner class `MemberItem(BaseModel)`: `user_id: str`, `name: str | None`, `role: str`
  - [x] In `execute()`: look up `membership.role` for current user and include as `user_role` in response
  - [x] In `execute()`: query all `RecipeBookUser` rows for this book joined with `User` for name; build `members` list
  - [x] Update `GetRecipeBook.Response` to add `user_role: str`, `is_shared: bool`, `members: list[MemberItem] = []`

- [x] Task 6: Create member management endpoints (AC: #2, #3, #7)
  - [x] Create `services/api/src/api/v1/recipe_book/add_recipe_book_member.py` with class `AddRecipeBookMember(Endpoint)`
    - `Params(BaseModel)`: `user_id: str`, `role: str` (must be "editor" or "viewer" — validate with `model_validator`)
    - `execute()`: verify caller is owner (403 if not); look up target user by ID (404 if not found); check no existing membership (409 if exists); create `RecipeBookUser(user_id=..., recipe_book_id=..., role=..., invited_by_id=caller.id)`; return `Response(user_id, name, role)`
  - [x] Create `services/api/src/api/v1/recipe_book/remove_recipe_book_member.py` with class `RemoveRecipeBookMember(Endpoint)`
    - `execute(recipe_book_id, target_user_id)`: verify caller is owner; prevent self-removal (owner cannot remove themselves); find membership (404 if not found); delete it; return `Response(success=True)`
  - [x] Create `services/api/src/api/v1/recipe_book/update_recipe_book_member_role.py` with class `UpdateRecipeBookMemberRole(Endpoint)`
    - `Params(BaseModel)`: `role: str` (must be "editor" or "viewer")
    - `execute(recipe_book_id, target_user_id, params)`: verify caller is owner; prevent changing own role; find target membership (404 if not); update role; return updated `Response`
  - [x] Update `services/api/src/api/v1/recipe_book/__init__.py` to export all three new classes
  - [x] Add routes to `services/api/src/routers/v1/recipe_book_router.py`:
    - `POST /{recipe_book_id}/members` → `AddRecipeBookMember.call(recipe_book_id=..., params=..., user=user, database=database)`
    - `DELETE /{recipe_book_id}/members/{target_user_id}` → `RemoveRecipeBookMember.call(recipe_book_id=..., target_user_id=..., user=user, database=database)`
    - `PATCH /{recipe_book_id}/members/{target_user_id}` → `UpdateRecipeBookMemberRole.call(recipe_book_id=..., target_user_id=..., params=..., user=user, database=database)`

- [x] Task 7: Backend tests (AC: all)
  - [x] Create `services/api/tests/test_recipe_book_members.py`
  - [x] `TestAddRecipeBookMember`: 6 tests pass (owner adds editor/viewer, editor denied, viewer denied, invalid role, no access)
  - [x] `TestRemoveRecipeBookMember`: 3 tests pass (owner removes, editor denied, owner can't remove self)
  - [x] `TestUpdateRecipeBookMemberRole`: 3 tests pass (owner updates, editor denied, invalid role)
  - [x] `TestListRecipeBooksRoleInfo`: 2 tests pass (shape check, shared book)
  - [x] `TestGetRecipeBookRoleInfo`: 2 tests pass (user_role+members in response, 403 no access)
  - [x] Run `npx nx run api:test` — 243 tests pass

- [x] Task 8: Flutter — ApiClient additions (AC: #2, #6, #7)
  - [x] In `app/lib/core/services/api_client.dart`, add `addRecipeBookMember`, `removeRecipeBookMember`, `updateRecipeBookMemberRole`

- [x] Task 9: Flutter — `RecipeBooksScreen` shared book indicator (AC: #1, #5)
  - [x] Shared books show `Icons.book_outlined` in `secondaryContainer`; personal use `Icons.book` in `primaryContainer`
  - [x] Role chip shown only for shared books, with role-specific colors

- [x] Task 10: Flutter — `RecipeBookDetailScreen` role-aware UI and members panel (AC: #3, #4, #6)
  - [x] `_userRole` and `_isShared` state variables populated from API response
  - [x] FAB hidden for viewers; archive/delete only for owners; members button for shared book owners

- [x] Task 11: Flutter — Create `RecipeBookMembersScreen` (AC: #7)
  - [x] Created `app/lib/features/recipe_books/recipe_book_members_screen.dart`
  - [x] Full CRUD UI: list members, change role, remove member, add member dialog

- [x] Task 12: Flutter — Route registration and navigation (AC: #7)
  - [x] Route `/recipe-books/:id/members` registered in `app_router.dart`
  - [x] Navigation from detail screen with `?role=$_userRole` query param

- [x] Task 13: Flutter tests (AC: all)
  - [x] Created `app/test/recipe_book_members_test.dart` — 4/4 tests pass
  - [x] Full Flutter test suite: 156 tests pass

## Dev Notes

### What Already Exists — Do NOT Re-implement

**RBAC enforcement (already fully implemented — no changes needed):**
- `CreateRecipe`: checks `membership.role not in ("owner", "editor")` → 403
- `UpdateRecipe`, `DeleteRecipe`, `ArchiveRecipe`, `RestoreRecipe`: similarly check owner/editor
- `UpdateRecipeBook`: checks owner/editor for edits, owner-only for `is_public` changes
- `DeleteRecipeBook`: checks owner-only
- `ArchiveRecipeBook`, `RestoreRecipeBook`: check owner-only
- `invitations/helpers.py`: checks owner/editor for sending invitations

**RecipeBookUser model (already has all needed fields):**
```python
class RecipeBookUser(JoinsBase):
    __tablename__ = "recipe_book_users"
    role: Mapped[str] = mapped_column(String, default="member")  # owner, editor, viewer
    user_id: Mapped[uuid.UUID]
    recipe_book_id: Mapped[uuid.UUID]
    invited_by_id: Mapped[uuid.UUID | None]
    user: Mapped["User"] = relationship(foreign_keys=[user_id], ...)
    recipe_book: Mapped["RecipeBook"] = relationship(...)
```
Note: the `default="member"` is the DB default but should be overridden explicitly on creation — always pass `role="owner"`, `role="editor"`, or `role="viewer"` explicitly.

**What does NOT exist yet:**
- `is_shared` column on `recipe_books`
- `user_role` / `is_shared` / `member_count` in ListRecipeBooks response
- `user_role` / `members` / `is_shared` in GetRecipeBook response
- `AddRecipeBookMember`, `RemoveRecipeBookMember`, `UpdateRecipeBookMemberRole` endpoints
- Flutter: role-aware UI, shared book indicators, `RecipeBookMembersScreen`

### Backend: ListRecipeBooks query update

Current query:
```python
query = (
    self.db.query(RecipeBook, func.count(Recipe.id).label('recipe_count'))
    .join(RecipeBookUser, RecipeBook.id == RecipeBookUser.recipe_book_id)
    .outerjoin(Recipe, (RecipeBook.id == Recipe.recipe_book_id) & (Recipe.archived_at.is_(None)))
    .filter(RecipeBookUser.user_id == user.id, RecipeBook.archived_at.is_(None))
    .group_by(RecipeBook.id)
    .order_by(RecipeBook.updated_at.desc())
)
```

Updated query to include user role and member count:
```python
# Subquery for member count per book
member_count_subq = (
    self.db.query(
        RecipeBookUser.recipe_book_id,
        func.count(RecipeBookUser.user_id).label('member_count')
    )
    .filter(RecipeBookUser.archived_at.is_(None))
    .group_by(RecipeBookUser.recipe_book_id)
    .subquery()
)

query = (
    self.db.query(
        RecipeBook,
        func.count(Recipe.id).label('recipe_count'),
        RecipeBookUser.role.label('user_role'),
        func.coalesce(member_count_subq.c.member_count, 1).label('member_count'),
    )
    .join(RecipeBookUser, (RecipeBook.id == RecipeBookUser.recipe_book_id) & (RecipeBookUser.user_id == user.id))
    .outerjoin(Recipe, (RecipeBook.id == Recipe.recipe_book_id) & (Recipe.archived_at.is_(None)))
    .outerjoin(member_count_subq, RecipeBook.id == member_count_subq.c.recipe_book_id)
    .filter(RecipeBook.archived_at.is_(None))
    .group_by(RecipeBook.id, RecipeBookUser.role, member_count_subq.c.member_count)
    .order_by(RecipeBook.updated_at.desc())
)
results = query.offset(offset).limit(limit).all()
items = [
    ListRecipeBooks.RecipeBookItem(
        id=str(recipe_book.id),
        name=recipe_book.name,
        description=recipe_book.description,
        is_public=recipe_book.is_public,
        is_shared=recipe_book.is_shared,
        user_role=user_role,
        recipe_count=recipe_count,
        member_count=member_count,
        created_at=recipe_book.created_at,
        updated_at=recipe_book.updated_at
    )
    for recipe_book, recipe_count, user_role, member_count in results
]
```

Note: `count()` requires all non-aggregate columns in `group_by()` when using SQLAlchemy — group by `RecipeBook.id` alone won't work if you select `RecipeBookUser.role` separately. The pattern above groups by both.

### Backend: GetRecipeBook update

After checking current user membership, also query all members:
```python
all_memberships = (
    self.db.query(RecipeBookUser, User)
    .join(User, RecipeBookUser.user_id == User.id)
    .filter(
        RecipeBookUser.recipe_book_id == recipe_book_id,
        RecipeBookUser.archived_at.is_(None),
    )
    .all()
)
members = [
    GetRecipeBook.MemberItem(
        user_id=str(rbu.user_id),
        name=u.name,
        role=rbu.role,
    )
    for rbu, u in all_memberships
]
```

### Backend: AddRecipeBookMember — look up user

```python
from utils.models.user import User

target_user = self.database.find_by(User, id=params.user_id)
if not target_user:
    raise APIException(status_code=404, detail="User not found", code=ErrorCode.USER_NOT_FOUND)

existing = self.database.find_by(RecipeBookUser, user_id=params.user_id, recipe_book_id=recipe_book_id)
if existing:
    raise APIException(status_code=409, detail="User is already a member", code=ErrorCode.CONFLICT)

membership = RecipeBookUser(
    user_id=target_user.id,
    recipe_book_id=recipe_book_id,
    role=params.role,
    invited_by_id=user.id
)
self.database.create(membership)
```

### Backend: Endpoint.call() pattern

All new endpoints must use the `Endpoint.call()` pattern — **never** call `.execute()` directly from routers:
```python
# Router:
return AddRecipeBookMember.call(
    recipe_book_id=recipe_book_id,
    params=params,
    user=user,
    database=database
)

# Endpoint:
class AddRecipeBookMember(Endpoint):
    def execute(self, recipe_book_id: str, params: "AddRecipeBookMember.Params"):
        user: User = self.user
        # ...
        return success(data=AddRecipeBookMember.Response(...))
```

### Flutter: Role-aware pattern

Pattern for conditionally showing actions:
```dart
// In state after _loadRecipeBook():
_userRole = _recipeBook?['user_role'] as String? ?? 'owner';
_isShared = _recipeBook?['is_shared'] as bool? ?? false;
_members = _recipeBook?['members'] as List<dynamic>? ?? [];

// Conditional FAB:
floatingActionButton: _userRole != 'viewer'
    ? FloatingActionButton(...)
    : null,

// Conditional AppBar actions:
actions: [
  if (_userRole == 'owner') ...[IconButton(delete), IconButton(archive)],
  if (_userRole != 'viewer') IconButton(edit),
  if (_isShared && _userRole == 'owner')
    IconButton(
      icon: const Icon(Icons.group),
      tooltip: 'Members',
      onPressed: () => context.push('/recipe-books/${widget.recipeBookId}/members?role=$_userRole'),
    ),
]
```

### Flutter: RecipeBookMembersScreen test pattern

Follow isolated widget pattern (no getIt/ApiClient):
```dart
testWidgets('members screen shows member name and role chip', (tester) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: ListTile(
        leading: const CircleAvatar(child: Icon(Icons.person)),
        title: const Text('Jane Smith'),
        subtitle: const Text('editor'),
        trailing: null,
      ),
    ),
  ));
  expect(find.text('Jane Smith'), findsOneWidget);
  expect(find.text('editor'), findsOneWidget);
});
```

### Project Structure Notes

**New files:**
- `services/migrator/migrations/versions/20260319000003_add_is_shared_to_recipe_books.py`
- `services/api/src/api/v1/recipe_book/add_recipe_book_member.py`
- `services/api/src/api/v1/recipe_book/remove_recipe_book_member.py`
- `services/api/src/api/v1/recipe_book/update_recipe_book_member_role.py`
- `services/api/tests/test_recipe_book_members.py`
- `app/lib/features/recipe_books/recipe_book_members_screen.dart`
- `app/test/recipe_book_members_test.dart`

**Modified files:**
- `libraries/utils/utils/models/recipe_book.py` — add `is_shared`
- `services/api/src/api/v1/recipe_book/create_recipe_book.py` — accept `is_shared`
- `services/api/src/api/v1/recipe_book/list_recipe_books.py` — include role and sharing info
- `services/api/src/api/v1/recipe_book/get_recipe_book.py` — include user_role and members
- `services/api/src/api/v1/recipe_book/__init__.py` — export new classes
- `services/api/src/routers/v1/recipe_book_router.py` — add member routes
- `app/lib/core/services/api_client.dart` — add member management methods
- `app/lib/features/recipe_books/recipe_books_screen.dart` — shared indicator and role chip
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` — role-aware UI
- `app/lib/core/router/app_router.dart` — add members route

### References

- [Source: libraries/utils/utils/models/recipe_book.py] — RecipeBook model
- [Source: libraries/utils/utils/models/recipe_book_user.py] — RecipeBookUser model (owner/editor/viewer roles)
- [Source: services/api/src/api/v1/recipe_book/create_recipe_book.py] — existing create pattern
- [Source: services/api/src/api/v1/recipe_book/list_recipe_books.py] — existing list query
- [Source: services/api/src/api/v1/recipe_book/get_recipe_book.py] — existing get pattern
- [Source: services/api/src/api/v1/recipe_book/delete_recipe_book.py] — owner-only enforcement pattern
- [Source: services/api/src/routers/v1/recipe_book_router.py] — router pattern
- [Source: services/api/src/api/v1/recipe/create_recipe.py] — owner/editor check pattern
- [Source: services/api/tests/conftest.py] — MockModel, MockQuery, MockRecipeBook, MockRecipeBookUser
- [Source: app/lib/features/recipe_books/recipe_books_screen.dart] — existing screen
- [Source: app/lib/features/recipe_books/recipe_book_detail_screen.dart] — existing detail screen
- [Source: app/lib/core/services/api_client.dart] — existing API client methods
- [Source: app/lib/core/router/app_router.dart] — route registration pattern
- [Source: _bmad-output/planning-artifacts/epics.md#7.1] — AC, user story

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Fixed `test_list_recipe_books_success`: updated MockQuery from 2-tuple to 4-tuple `(book, 3, "owner", 1)` after query now returns 4 columns
- Fixed `test_get_recipe_book_*`: switched from `set_where(Recipe, [...])` to `mock_db.db.query.side_effect = [MockQuery([...]), MockQuery([])]` after GetRecipeBook now makes 2 sequential db.query calls (recipes + members)
- Fixed `MockRecipeBook` missing `is_shared`: added `"is_shared": False` to conftest.py defaults
- Fixed Flutter lint: `DropdownButtonFormField(value:)` → `(initialValue:)`, removed leading underscores from local functions, `(_, __)` → `(context, index)` in separatorBuilder

### Completion Notes List

- All 13 tasks implemented and verified
- Backend: 243 API tests pass
- Flutter: 156 widget tests pass, flutter analyze clean
- Code review fixes applied:
  - H1: Added `onChanged: (_) => setDialogState(() {})` to TextField in `_showAddMemberDialog` so Add button re-evaluates when user types
  - H2: Gated `onLongPress` on recipe cards with `_userRole == 'viewer'` check so viewers cannot enter bulk select mode
  - M1: Replaced meaningless `test_list_with_shared_book` with proper assertion verifying `is_shared=True`, `user_role`, and `member_count`
  - M2: Changed `ErrorCode.RECIPE_BOOK_ACCESS_DENIED` → `ErrorCode.INVALID_REQUEST` for self-removal 400 error
  - M3: Added `conftest.py` and `test_recipe_book.py` to File List

### File List

**New files:**
- `services/migrator/migrations/versions/20260319000003_add_is_shared_to_recipe_books.py`
- `services/api/src/api/v1/recipe_book/add_recipe_book_member.py`
- `services/api/src/api/v1/recipe_book/remove_recipe_book_member.py`
- `services/api/src/api/v1/recipe_book/update_recipe_book_member_role.py`
- `services/api/tests/test_recipe_book_members.py`
- `app/lib/features/recipe_books/recipe_book_members_screen.dart`
- `app/test/recipe_book_members_test.dart`

**Modified files:**
- `libraries/utils/utils/models/recipe_book.py`
- `services/api/src/api/v1/recipe_book/create_recipe_book.py`
- `services/api/src/api/v1/recipe_book/list_recipe_books.py`
- `services/api/src/api/v1/recipe_book/get_recipe_book.py`
- `services/api/src/api/v1/recipe_book/__init__.py`
- `services/api/src/routers/v1/recipe_book_router.py`
- `services/api/tests/conftest.py` — added `is_shared: False` to MockRecipeBook defaults
- `services/api/tests/test_recipe_book.py` — updated mocks for new 4-column query signature
- `app/lib/core/services/api_client.dart`
- `app/lib/features/recipe_books/recipe_books_screen.dart`
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart`
- `app/lib/core/router/app_router.dart`
