import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kRecipeListViewKey = 'recipe_list_view';

/// Density mode for the recipe list (home screen + recipe-book-detail).
/// Persisted globally per user (not per book) — see epic
/// `recipe-list-organization` Locked Decision: "A user is either a
/// 'table person' or a 'grid person' globally."
enum RecipeListView { grid, table }

/// Read the saved view from SharedPreferences. Called from `main.dart`
/// pre-app so the first frame respects the user's last choice instead
/// of flashing the default. Defensive: any read failure (broken plugin,
/// unrecognized value) falls back to [RecipeListView.grid].
Future<RecipeListView> loadSavedRecipeListView() async {
  try {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_kRecipeListViewKey);
    if (raw == null) return RecipeListView.grid;
    return RecipeListView.values.firstWhere(
      (v) => v.name == raw,
      orElse: () => RecipeListView.grid,
    );
  } catch (_) {
    return RecipeListView.grid;
  }
}

class RecipeListViewNotifier extends Notifier<RecipeListView> {
  final RecipeListView _initial;
  RecipeListViewNotifier([this._initial = RecipeListView.grid]);

  @override
  RecipeListView build() => _initial;

  Future<void> toggle() async {
    final next = state == RecipeListView.grid
        ? RecipeListView.table
        : RecipeListView.grid;
    await set(next);
  }

  Future<void> set(RecipeListView view) async {
    if (state == view) return;
    state = view;
    // Best-effort persistence — a write failure must NOT roll the
    // in-memory state back; the user's tap should still feel immediate.
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kRecipeListViewKey, view.name);
    } catch (_) {}
  }
}

/// Default-constructed notifier defaults to grid. `main.dart` overrides
/// this with the SharedPreferences-loaded value at boot so cold-starts
/// honor the last choice without a frame of grid-flash.
final recipeListViewProvider =
    NotifierProvider<RecipeListViewNotifier, RecipeListView>(
  RecipeListViewNotifier.new,
);
