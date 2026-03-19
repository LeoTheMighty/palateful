# Story 4.3: Restore Previous Version

Status: ready-for-dev

## Story

As a user,
I want to restore any previous version of a recipe with one tap,
so that I can go back to what worked without losing any history.

## Acceptance Criteria

1. When I tap "Restore this version" on a version diff screen for a recipe I own, a confirmation dialog appears before proceeding
2. On confirmation, a new version is created with the content of the selected snapshot (never destroys history — append-only)
3. The version timeline shows the restore action clearly (e.g., a "Restored from v2" chip instead of field change chips)
4. All previous versions remain accessible in the timeline after a restore
5. After restore, the user is navigated back to the recipe detail screen which reflects the restored content immediately
6. If I am a viewer (not owner/editor) of a recipe book, the "Restore" button is hidden (or disabled) — restore is an owner/editor action
7. If the restore fails (network error), an error SnackBar is shown and the user remains on the diff screen

## Tasks / Subtasks

- [ ] Task 1: Create `RestoreRecipeVersion` backend endpoint `POST /recipes/:id/versions/:version_id/restore` (AC: #2, #3, #4, #6)
  - [ ] Create `services/api/src/api/v1/recipe/restore_recipe_version.py`
  - [ ] Access check: user must be owner or editor (403 for viewers)
  - [ ] Load recipe + version snapshot; 404 if not found
  - [ ] Call `_create_version_snapshot` to save current state with `changed_fields = [f"restore:{version.version_number}"]`
  - [ ] Delete current ingredients and recreate from snapshot (parse formatted qty string with `_parse_quantity_display`)
  - [ ] Delete current steps and recreate from snapshot
  - [ ] Update recipe name and instructions from snapshot
  - [ ] Return updated recipe (same `Response` shape as `UpdateRecipe.Response`)
  - [ ] Register in `services/api/src/api/v1/recipe/__init__.py`
  - [ ] Add route `POST /recipes/{recipe_id}/versions/{version_id}/restore` to `recipe_router.py`

- [ ] Task 2: Add `restoreRecipeVersion` to API client (AC: #5)
  - [ ] In `app/lib/core/services/api_client.dart`, add `restoreRecipeVersion(recipeId, versionId)`

- [ ] Task 3: Wire up restore button in `RecipeVersionDiffScreen` (AC: #1, #5, #6, #7)
  - [ ] Replace stub SnackBar with real logic
  - [ ] Read `can_edit` from `_currentRecipe['can_edit']`; hide or disable restore button when `can_edit == false`
  - [ ] On tap: show `AlertDialog` confirmation ("Restore to Version {N}?" + confirm/cancel)
  - [ ] On confirm: set `_isRestoring = true` (show loading spinner on button, disable taps)
  - [ ] Call `_apiClient.restoreRecipeVersion(widget.recipeId, widget.versionId)`
  - [ ] On success: show success SnackBar, then `context.go('/recipes/${widget.recipeId}')` to recipe detail
  - [ ] On error: set `_isRestoring = false`, show error SnackBar with message

- [ ] Task 4: Display "Restored from v{N}" label in `RecipeVersionHistoryScreen` (AC: #3)
  - [ ] In `itemBuilder`, detect `changed_fields` entries starting with `"restore:"`
  - [ ] Extract version number from `"restore:{N}"` → display chip as "Restored from v{N}" with `Icons.restore` icon
  - [ ] Style: use `colorScheme.tertiaryContainer` background to visually distinguish from normal change chips

- [ ] Task 5: Add API tests for `RestoreRecipeVersion` (AC: #2, #6)
  - [ ] `test_restore_recipe_version_success` — verifies 200, recipe updated, new version created
  - [ ] `test_restore_recipe_version_access_denied` — viewer gets 403
  - [ ] `test_restore_recipe_version_recipe_not_found` — 404 for unknown recipe
  - [ ] `test_restore_recipe_version_not_found` — 404 for unknown version id

## Dev Notes

### Backend: `RestoreRecipeVersion` Endpoint

```python
# services/api/src/api/v1/recipe/restore_recipe_version.py
from datetime import datetime
from decimal import Decimal
from fractions import Fraction

from pydantic import BaseModel
from sqlalchemy import func
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.formatting import format_quantity
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_step import RecipeStep
from utils.models.recipe_version import RecipeVersion
from utils.models.user import User
from utils.services.units.conversion import normalize_quantity


def _parse_quantity_display(s: str) -> Decimal:
    """Parse formatted quantity string back to Decimal.
    Handles '2', '0.5', '1/2', '1 1/4', etc.
    """
    try:
        s = s.strip()
        parts = s.split(' ')
        if len(parts) == 2:
            # "1 1/2" → whole + fraction
            whole = int(parts[0])
            frac = Fraction(parts[1])
            return Decimal(str(float(whole + frac)))
        else:
            # "1/2", "2", "0.5"
            return Decimal(str(float(Fraction(s))))
    except Exception:
        return Decimal(s)


class RestoreRecipeVersion(Endpoint):
    def execute(self, recipe_id: str, version_id: str):
        user: User = self.user

        recipe = self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(404, detail="Recipe not found", code=ErrorCode.RECIPE_NOT_FOUND)

        membership = self.database.find_by(
            RecipeBookUser, user_id=user.id, recipe_book_id=recipe.recipe_book_id
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(403, detail="You don't have permission to restore this recipe", code=ErrorCode.RECIPE_ACCESS_DENIED)

        version = self.database.find_by(RecipeVersion, id=version_id)
        if not version or str(version.recipe_id) != str(recipe_id):
            raise APIException(404, detail="Version not found", code=ErrorCode.NOT_FOUND)

        snapshot = version.snapshot

        # Save current state as a new version BEFORE applying restore
        self._create_restore_snapshot(recipe, recipe_id, version.version_number, user)

        # Apply snapshot: update recipe scalar fields
        updates = {}
        if 'name' in snapshot:
            updates['name'] = snapshot['name']
        if 'instructions' in snapshot:
            updates['instructions'] = snapshot['instructions']
        if updates:
            self.database.update(recipe, **updates)

        # Recreate ingredients from snapshot
        existing = self.database.where(RecipeIngredient, recipe_id=recipe_id).all()
        for ri in existing:
            self.database.delete(ri)

        for ing_data in snapshot.get('ingredients', []):
            qty_str = ing_data.get('quantity_display', '1')
            unit = ing_data.get('unit_display', '')
            try:
                qty_decimal = _parse_quantity_display(str(qty_str))
            except Exception:
                qty_decimal = Decimal('1')

            try:
                normalized = normalize_quantity(float(qty_decimal), unit)
                qty_normalized = Decimal(str(normalized.quantity_normalized))
                unit_normalized = normalized.unit_normalized
            except Exception:
                qty_normalized = qty_decimal
                unit_normalized = unit

            ri = RecipeIngredient(
                recipe_id=recipe_id,
                ingredient_id=ing_data['ingredient_id'],
                quantity_display=qty_decimal,
                unit_display=unit,
                quantity_normalized=qty_normalized,
                unit_normalized=unit_normalized,
                notes=ing_data.get('notes'),
                is_optional=ing_data.get('is_optional', False),
                order_index=ing_data.get('order_index', 0),
            )
            self.database.create(ri)

        # Recreate steps from snapshot
        existing_steps = self.database.where(RecipeStep, recipe_id=recipe_id).all()
        for step in existing_steps:
            self.database.delete(step)

        for step_data in snapshot.get('steps', []):
            new_step = RecipeStep(
                recipe_id=recipe_id,
                step_number=step_data['step_number'],
                instruction=step_data.get('instruction', ''),
                active_time_minutes=step_data.get('active_time_minutes'),
                timers=step_data.get('timers'),
                wait_time_minutes=step_data.get('wait_time_minutes'),
                wait_type=step_data.get('wait_type'),
                can_prep_ahead=step_data.get('can_prep_ahead', False),
                is_optional=step_data.get('is_optional', False),
            )
            self.database.create(new_step)

        # Return updated recipe (mirror UpdateRecipe.Response shape)
        # ... fetch updated ingredients, steps, version_count, then return success(data=Response(...))

    def _create_restore_snapshot(self, recipe, recipe_id, restored_from_version_number, user):
        """Snapshot the current state with changed_fields indicating a restore."""
        current_ingredients = self.database.where(RecipeIngredient, recipe_id=recipe_id).all()
        current_steps = self.database.where(RecipeStep, asc="step_number", recipe_id=recipe_id).all()

        snapshot = {
            "name": recipe.name,
            "instructions": recipe.instructions,
            "ingredients": [
                {
                    "ingredient_id": str(ri.ingredient_id),
                    "quantity_display": format_quantity(ri.quantity_display, ri.unit_display),
                    "unit_display": ri.unit_display,
                    "notes": ri.notes,
                    "is_optional": ri.is_optional,
                    "order_index": ri.order_index,
                }
                for ri in current_ingredients
            ],
            "steps": [
                {
                    "step_number": s.step_number,
                    "instruction": s.instruction,
                    "active_time_minutes": s.active_time_minutes,
                    "timers": s.timers,
                    "wait_time_minutes": s.wait_time_minutes,
                    "wait_type": s.wait_type,
                    "can_prep_ahead": s.can_prep_ahead,
                    "is_optional": s.is_optional,
                }
                for s in current_steps
            ],
        }

        max_version = (
            self.database.db.query(func.max(RecipeVersion.version_number))
            .filter(RecipeVersion.recipe_id == recipe_id)
            .scalar()
        ) or 0

        version = RecipeVersion(
            recipe_id=recipe_id,
            version_number=max_version + 1,
            snapshot=snapshot,
            changed_fields=[f"restore:{restored_from_version_number}"],
            created_by=user.id,
        )
        self.database.db.add(version)
```

**Response shape**: mirror `UpdateRecipe.Response` (same fields — reuse the Pydantic model or inline).

**Router registration** — add after `get_recipe_version` route:
```python
@recipe_router.post("/recipes/{recipe_id}/versions/{version_id}/restore")
async def restore_recipe_version(recipe_id: str, version_id: str, user=..., db=...):
    return RestoreRecipeVersion.call(recipe_id=recipe_id, version_id=version_id, user=user, database=db)
```

### Key Implementation Note: `_parse_quantity_display`

The snapshot stores `format_quantity()`-formatted strings (e.g., "1/2", "1 1/4", "2"). To recreate `RecipeIngredient` rows (which need a `Decimal` for `quantity_display`), parse them back via `Fraction`:

```python
>>> from fractions import Fraction
>>> Decimal(str(float(Fraction("1/2"))))  # → Decimal('0.5')
>>> Decimal(str(float(Fraction("2"))))     # → Decimal('2.0')
>>> # "1 1/4" → split on space, whole=1, frac=Fraction("1/4") → 1.25
```

### Flutter: `RestoreRecipeVersion` button

In `recipe_version_diff_screen.dart`, add `_isRestoring` state bool and `_canEdit` flag:

```dart
bool _isRestoring = false;

// In _loadData, after loading current recipe:
_canEdit = _currentRecipe?['can_edit'] as bool? ?? false;

// Replace stub button:
if (_canEdit)
  SizedBox(
    width: double.infinity,
    child: OutlinedButton.icon(
      icon: _isRestoring
          ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
          : const Icon(Icons.restore),
      label: Text(_isRestoring ? 'Restoring...' : 'Restore this version'),
      onPressed: _isRestoring ? null : _confirmRestore,
    ),
  ),

Future<void> _confirmRestore() async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Restore version?'),
      content: Text('This will restore Version ${widget.versionNumber} as a new version. Your current recipe will be saved in the history.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Restore')),
      ],
    ),
  );
  if (confirmed != true || !mounted) return;

  setState(() => _isRestoring = true);
  try {
    await _apiClient.restoreRecipeVersion(widget.recipeId, widget.versionId);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Restored to Version ${widget.versionNumber}')),
      );
      context.go('/recipes/${widget.recipeId}');
    }
  } catch (e) {
    if (mounted) {
      setState(() => _isRestoring = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Restore failed: $e'), backgroundColor: Theme.of(context).colorScheme.error),
      );
    }
  }
}
```

### Flutter: "Restored from v{N}" chip in history screen

In `recipe_version_history_screen.dart`, replace the generic chip mapping:

```dart
// In itemBuilder, replace changedFields chip builder:
if (changedFields.isNotEmpty) ...[
  const SizedBox(height: 6),
  Wrap(
    spacing: 4,
    runSpacing: 4,
    children: changedFields.map((field) {
      final f = field.toString();
      String label;
      if (f.startsWith('restore:')) {
        final fromNum = f.split(':')[1];
        label = 'Restored from v$fromNum';
      } else {
        label = _fieldLabels[f] ?? f;
      }
      final isRestore = f.startsWith('restore:');
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: isRestore
              ? colorScheme.tertiaryContainer.withValues(alpha: 0.5)
              : colorScheme.secondaryContainer.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isRestore) ...[
              Icon(Icons.restore, size: 12, color: colorScheme.onTertiaryContainer),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: textTheme.labelSmall?.copyWith(
                color: isRestore ? colorScheme.onTertiaryContainer : colorScheme.onSecondaryContainer,
              ),
            ),
          ],
        ),
      );
    }).toList(),
  ),
],
```

### Flutter: Route/Navigation

No new routes needed. After restore:
- `context.go('/recipes/${widget.recipeId}')` navigates to the recipe detail screen, replacing history stack
- The recipe detail screen will reload data in `initState`, reflecting restored content

### Tests

Follow pattern in `TestGetRecipeVersion`. Add `TestRestoreRecipeVersion` to `test_recipe.py`:

```python
class TestRestoreRecipeVersion:
    def test_restore_recipe_version_success(self, ...):
        # POST /recipes/{id}/versions/{vid}/restore
        # Verify 200, recipe name matches snapshot, new version created with changed_fields ["restore:1"]

    def test_restore_recipe_version_access_denied(self, ...):
        # Viewer role → 403

    def test_restore_recipe_version_recipe_not_found(self, ...):
        # Unknown recipe_id → 404

    def test_restore_recipe_version_not_found(self, ...):
        # Unknown version_id → 404
```

Use `MockRecipeVersion` (already in conftest.py) for mocking.

### Do Not:
- Re-implement the auto-versioning logic — reuse the same `_create_version_snapshot` pattern
- Use `database.create(version)` for the restore snapshot (use `database.db.add(version)` for atomicity)
- Expose a "Restore" button to viewers — check `can_edit` from the current recipe API response
- Navigate to the history screen after restore — go directly to the recipe detail screen (`context.go`)
- Add a migration — no schema changes needed; `changed_fields` is `ARRAY(String)` and supports `["restore:2"]`

### References

- [Source: services/api/src/api/v1/recipe/update_recipe.py] — `_create_version_snapshot` and ingredient/step recreate patterns to mirror
- [Source: services/api/src/api/v1/recipe/get_recipe_version.py] — Access check and version lookup pattern
- [Source: services/api/src/api/v1/recipe/__init__.py] — Registration pattern
- [Source: services/api/src/routers/v1/recipe_router.py] — Route registration pattern (add after `get_recipe_version`)
- [Source: app/lib/features/recipes/recipe_version_diff_screen.dart] — Stub restore button to replace (line ~493)
- [Source: app/lib/features/recipes/recipe_version_history_screen.dart] — Chip builder to update for `restore:N` display
- [Source: app/lib/core/services/api_client.dart] — API client pattern (`restoreRecipe` for reference)
- [Source: libraries/utils/utils/formatting.py] — `format_quantity` (needed for `_create_restore_snapshot`)
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.3] — Epic requirements (FR4, NFR16)

### Project Structure Notes

New files:
- `services/api/src/api/v1/recipe/restore_recipe_version.py`

Modified files:
- `services/api/src/api/v1/recipe/__init__.py` — register `RestoreRecipeVersion`
- `services/api/src/routers/v1/recipe_router.py` — add POST route
- `app/lib/core/services/api_client.dart` — add `restoreRecipeVersion(recipeId, versionId)`
- `app/lib/features/recipes/recipe_version_diff_screen.dart` — wire restore button, add `_isRestoring` + `_canEdit` state
- `app/lib/features/recipes/recipe_version_history_screen.dart` — display "Restored from v{N}" chips
- `services/api/tests/test_recipe.py` — add `TestRestoreRecipeVersion` (4 tests)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

### File List
