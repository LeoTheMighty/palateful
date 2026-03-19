# Story 4.4: Recipe Notes

Status: done

## Story

As a user,
I want to annotate my recipes with notes that attach to the current version,
so that I can capture cooking observations and ideas within the recipe's timeline.

## Acceptance Criteria

1. When I add a note via text input on the recipe detail screen, the note is saved and persists — it is visible immediately without a page reload
2. Notes are visible on the recipe detail screen below the steps, each with a timestamp
3. Notes from previous versions are visible when viewing that version in the version history (diff screen shows snapshot notes)
4. I can add multiple notes to the same recipe (they accumulate as a list)
5. Notes include a timestamp (created_at)
6. I can delete my own notes (soft delete)

## Tasks / Subtasks

- [x] Task 1: Create `RecipeNote` model and migration (AC: #1, #4, #5)
  - [x] Create `libraries/utils/utils/models/recipe_note.py` with model extending `JoinsBase`
  - [x] Create migration `services/migrator/migrations/versions/20260319000001_add_recipe_notes.py`
  - [x] Revision: `h8i9j0k1l2m3`, down_revision: `g7h8i9j0k1l2`

- [x] Task 2: Backend endpoints for adding/deleting notes (AC: #1, #6)
  - [x] Create `services/api/src/api/v1/recipe/add_recipe_note.py` — `POST /recipes/{recipe_id}/notes`
  - [x] Create `services/api/src/api/v1/recipe/delete_recipe_note.py` — `DELETE /recipes/{recipe_id}/notes/{note_id}` (soft delete)
  - [x] Access check: recipe must be accessible (viewer can add notes to shared books, owner/editor only can delete others' notes)
  - [x] Register both in `services/api/src/api/v1/recipe/__init__.py`
  - [x] Add both routes to `services/api/src/routers/v1/recipe_router.py`

- [x] Task 3: Include notes in `GetRecipe` response (AC: #2)
  - [x] In `services/api/src/api/v1/recipe/get_recipe.py`, query `RecipeNote` for the recipe_id and include in response
  - [x] Add `NoteResponse` inner class and `notes: list[NoteResponse]` to `GetRecipe.Response`
  - [x] Import `RecipeNote` model

- [x] Task 4: Include notes in version snapshots (AC: #3)
  - [x] In `services/api/src/api/v1/recipe/update_recipe.py`, modify `_create_version_snapshot` to query `RecipeNote` and include `notes` key in snapshot dict
  - [x] In `services/api/src/api/v1/recipe/restore_recipe_version.py`, modify `_create_restore_snapshot` to include current notes in snapshot

- [x] Task 5: Flutter API client and recipe detail notes UI (AC: #1, #2, #4, #5, #6)
  - [x] In `app/lib/core/services/api_client.dart`, add `addRecipeNote(recipeId, body)` and `deleteRecipeNote(recipeId, noteId)`
  - [x] In `app/lib/features/recipes/recipe_detail_screen.dart`:
    - [x] Load `_recipe['notes']` into `List<dynamic> _notes` state
    - [x] Add notes section below steps/tags: list of note cards with body + formatted timestamp + delete button (own notes only)
    - [x] Add note input: `TextField` + submit `IconButton` below the notes list
    - [x] On submit: call `addRecipeNote`, insert new note into `_notes` list (optimistic update), clear input
    - [x] On delete: call `deleteRecipeNote`, remove from `_notes` list

- [x] Task 6: Show notes from snapshot in version diff screen (AC: #3)
  - [x] In `app/lib/features/recipes/recipe_version_diff_screen.dart`:
    - [x] Read `_snapshot?['notes'] as List?` and display a "Notes at this version" section at the bottom
    - [x] Show note body + timestamp (read-only, no delete)
    - [x] Only show section if snapshot has notes

- [x] Task 7: Tests (AC: #1, #6)
  - [x] `test_add_recipe_note_success` — 201, note body in response
  - [x] `test_add_recipe_note_access_denied` — recipe not found → 404
  - [x] `test_delete_recipe_note_success` — 200
  - [x] `test_delete_recipe_note_not_found` — 404

## Dev Notes

### Backend: `RecipeNote` Model

```python
# libraries/utils/utils/models/recipe_note.py
import uuid
from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.models.joins_base import JoinsBase

class RecipeNote(JoinsBase):
    __tablename__ = "recipe_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (Index("ix_recipe_notes_recipe_id", "recipe_id"),)
```

### Backend: Migration

```python
# revision: h8i9j0k1l2m3
# down_revision: g7h8i9j0k1l2
def upgrade():
    op.create_table(
        "recipe_notes",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("recipe_id", sa.UUID(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recipe_notes_recipe_id", "recipe_notes", ["recipe_id"])
```

### Backend: `AddRecipeNote` Endpoint

```python
# POST /recipes/{recipe_id}/notes
# Access: any user with read access to the recipe (viewer, editor, owner)
# Check: membership.role in ("owner", "editor", "viewer") — any member can add notes
# Body: { "body": "great with extra garlic" }
# Response: { "id": "...", "recipe_id": "...", "body": "...", "created_at": "..." }
```

Pattern to follow: `get_recipe.py` for access check, then `self.database.create(RecipeNote(...))`.

### Backend: `DeleteRecipeNote` Endpoint

```python
# DELETE /recipes/{recipe_id}/notes/{note_id}
# Access: note.created_by == user.id OR membership.role in ("owner")
# Soft delete: self.database.update(note, archived_at=datetime.now(timezone.utc))
# 404 if not found, 403 if not authorized
```

### Backend: Modify `GetRecipe` to Include Notes

In `get_recipe.py`, after loading steps, add:
```python
from utils.models.recipe_note import RecipeNote

notes = self.database.where(
    RecipeNote,
    recipe_id=recipe_id,
    asc="created_at",
).all()

note_responses = [
    GetRecipe.NoteResponse(
        id=str(n.id),
        body=n.body,
        created_by=str(n.created_by) if n.created_by else None,
        created_at=n.created_at,
    )
    for n in notes
]
```

Add to `GetRecipe.Response`: `notes: list["GetRecipe.NoteResponse"] = []`

### Backend: Notes in Version Snapshots

In `update_recipe.py` `_create_version_snapshot`, add after fetching current steps:
```python
from utils.models.recipe_note import RecipeNote

current_notes = self.database.where(RecipeNote, recipe_id=recipe_id).all()

# Add to snapshot dict:
"notes": [
    {
        "body": n.body,
        "created_by": str(n.created_by) if n.created_by else None,
        "created_at": n.created_at.isoformat(),
    }
    for n in current_notes
],
```

Do the same in `restore_recipe_version.py` `_create_restore_snapshot`.

**Important**: Do NOT restore notes when applying a snapshot. Notes are append-only observations, not recipe content. The restore operation only restores `name`, `instructions`, `ingredients`, `steps`.

### Flutter: `addRecipeNote` and `deleteRecipeNote` in ApiClient

```dart
Future<Response> addRecipeNote(String recipeId, String body) {
  return _dio.post('/v1/recipes/$recipeId/notes', data: {'body': body});
}

Future<Response> deleteRecipeNote(String recipeId, String noteId) {
  return _dio.delete('/v1/recipes/$recipeId/notes/$noteId');
}
```

### Flutter: Notes Section in `RecipeDetailScreen`

Add to state:
```dart
List<dynamic> _notes = [];
bool _isAddingNote = false;
final _noteController = TextEditingController();

@override
void dispose() {
  _noteController.dispose();
  super.dispose();
}
```

In `_loadRecipe()` setState:
```dart
_notes = (response.data['notes'] as List?) ?? [];
```

Notes section (insert after tags/source section, before the final SizedBox(height: 32)):
```dart
// Notes section
if (_notes.isNotEmpty || (_recipe?['can_edit'] == true)) ...[
  Text('Notes', style: textTheme.titleLarge),
  const SizedBox(height: 8),
  ..._notes.map((note) => _buildNoteCard(note)),
  const SizedBox(height: 12),
  _buildAddNoteInput(),
  const SizedBox(height: 24),
],
```

`_buildNoteCard(note)`:
- Container with `surfaceContainerHighest` background, rounded corners
- Body text + formatted timestamp (use `_formatDate` pattern from version history screen)
- Delete icon (trailing) only if `note['created_by'] == currentUserId` or `_recipe['can_edit'] == true`

`_buildAddNoteInput()`:
```dart
Row(
  children: [
    Expanded(
      child: TextField(
        controller: _noteController,
        decoration: const InputDecoration(hintText: 'Add a note...'),
        maxLines: null,
        textInputAction: TextInputAction.newline,
      ),
    ),
    IconButton(
      icon: _isAddingNote
          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
          : const Icon(Icons.send),
      onPressed: _isAddingNote ? null : _submitNote,
    ),
  ],
)
```

`_submitNote()`:
```dart
Future<void> _submitNote() async {
  final body = _noteController.text.trim();
  if (body.isEmpty) return;
  setState(() => _isAddingNote = true);
  try {
    final response = await _apiClient.addRecipeNote(widget.recipeId, body);
    if (mounted) {
      final newNote = response.data;
      setState(() {
        _notes = [..._notes, newNote];
        _isAddingNote = false;
      });
      _noteController.clear();
    }
  } catch (e) {
    if (mounted) {
      setState(() => _isAddingNote = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to add note: $e')),
      );
    }
  }
}
```

### Flutter: Notes in Version Diff Screen

In `recipe_version_diff_screen.dart`, after the existing diff sections (steps), add:

```dart
// Notes at this version (from snapshot)
final snapshotNotes = (_snapshot?['notes'] as List?) ?? [];
if (snapshotNotes.isNotEmpty)
  _buildSection(
    context,
    title: 'Notes at this version',
    children: snapshotNotes.map<Widget>((note) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(note['body'] as String, style: textTheme.bodyMedium),
              const SizedBox(height: 4),
              Text(
                _formatDate(note['created_at'] as String?),
                style: textTheme.labelSmall?.copyWith(color: colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      );
    }).toList(),
  ),
```

### Access Control for Notes

- **Add note**: any user with at least read access to the recipe (owner, editor, viewer)
  - Check: `self.database.find_by(RecipeBookUser, user_id=user.id, recipe_book_id=recipe.recipe_book_id)` → not None
- **Delete note**: owner of the note (note.created_by == user.id) OR book owner
  - This prevents random editors from deleting each other's notes
  - Soft delete: set `archived_at` — never hard delete

### Endpoint Registration Pattern

Follow existing pattern in `services/api/src/api/v1/recipe/__init__.py`:
```python
from api.v1.recipe.add_recipe_note import AddRecipeNote
from api.v1.recipe.delete_recipe_note import DeleteRecipeNote
```

Add to `__all__`.

Router (in `recipe_router.py`, after version routes):
```python
@recipe_router.post("/recipes/{recipe_id}/notes", status_code=201)
async def add_recipe_note(recipe_id: str, params: AddRecipeNote.Params, user=..., database=...):
    return AddRecipeNote.call(recipe_id=recipe_id, params=params, user=user, database=database)

@recipe_router.delete("/recipes/{recipe_id}/notes/{note_id}")
async def delete_recipe_note(recipe_id: str, note_id: str, user=..., database=...):
    return DeleteRecipeNote.call(recipe_id=recipe_id, note_id=note_id, user=user, database=database)
```

### Do Not:
- Create a versioned note system — notes are append-only annotations, not recipe content
- Include notes in `changed_fields` — notes don't trigger recipe version creation
- Restore notes when restoring a recipe version — only restore name/instructions/ingredients/steps
- Add notes editing (PUT) — out of scope for this story
- Add a separate GET /notes endpoint — notes come through GET /recipes/:id

### References

- [Source: libraries/utils/utils/models/recipe_version.py] — JoinsBase + column pattern
- [Source: services/migrator/migrations/versions/20260317000001_add_recipe_versions.py] — Migration chain reference (down_revision: `g7h8i9j0k1l2`, new revision: `h8i9j0k1l2m3`)
- [Source: services/api/src/api/v1/recipe/update_recipe.py] — `_create_version_snapshot` pattern to modify
- [Source: services/api/src/api/v1/recipe/restore_recipe_version.py] — `_create_restore_snapshot` pattern to modify
- [Source: services/api/src/api/v1/recipe/get_recipe.py] — access check + ingredient fetch pattern to mirror
- [Source: services/api/src/api/v1/recipe/__init__.py] — registration pattern
- [Source: services/api/src/routers/v1/recipe_router.py] — route pattern
- [Source: app/lib/features/recipes/recipe_detail_screen.dart] — notes section insert point (after tags, before final SizedBox at ~line 582)
- [Source: app/lib/features/recipes/recipe_version_diff_screen.dart] — diff sections pattern to follow for notes section
- [Source: app/lib/core/services/api_client.dart] — API client method pattern

### Project Structure Notes

New files:
- `libraries/utils/utils/models/recipe_note.py`
- `services/migrator/migrations/versions/20260319000001_add_recipe_notes.py`
- `services/api/src/api/v1/recipe/add_recipe_note.py`
- `services/api/src/api/v1/recipe/delete_recipe_note.py`

Modified files:
- `services/api/src/api/v1/recipe/__init__.py` — register AddRecipeNote, DeleteRecipeNote
- `services/api/src/api/v1/recipe/get_recipe.py` — include notes in response
- `services/api/src/api/v1/recipe/update_recipe.py` — include notes in `_create_version_snapshot`
- `services/api/src/api/v1/recipe/restore_recipe_version.py` — include notes in `_create_restore_snapshot`
- `services/api/src/routers/v1/recipe_router.py` — add 2 new routes
- `app/lib/core/services/api_client.dart` — add addRecipeNote, deleteRecipeNote
- `app/lib/features/recipes/recipe_detail_screen.dart` — notes section + add note input
- `app/lib/features/recipes/recipe_version_diff_screen.dart` — snapshot notes section

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Code Review Action Items

All issues found and auto-fixed:
- [x] H1: Notes section hidden from viewers with no notes — changed to always show
- [x] H2: Viewer couldn't delete own notes — always show delete button (backend enforces auth)
- [x] M1: Empty body accepted in AddRecipeNote — added `@field_validator` to reject empty/whitespace
- [x] M2: Missing 403 test for unauthorized delete — added `test_delete_recipe_note_unauthorized`
- [x] L1: `note` parameter type annotation improved — explicit cast in spread

### Completion Notes List

### File List

New files:
- `libraries/utils/utils/models/recipe_note.py`
- `services/migrator/migrations/versions/20260319000001_add_recipe_notes.py`
- `services/api/src/api/v1/recipe/add_recipe_note.py`
- `services/api/src/api/v1/recipe/delete_recipe_note.py`

Modified files:
- `services/api/src/api/v1/recipe/__init__.py`
- `services/api/src/api/v1/recipe/get_recipe.py`
- `services/api/src/api/v1/recipe/update_recipe.py`
- `services/api/src/api/v1/recipe/restore_recipe_version.py`
- `services/api/src/routers/v1/recipe_router.py`
- `app/lib/core/services/api_client.dart`
- `app/lib/features/recipes/recipe_detail_screen.dart`
- `app/lib/features/recipes/recipe_version_diff_screen.dart`
- `services/api/tests/test_recipe.py`
- `services/api/tests/conftest.py`
