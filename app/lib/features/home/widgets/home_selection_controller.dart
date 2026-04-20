import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Immutable state for the home multi-select experience.
///
/// Selection sets are separated by kind (recipe vs meal) so the bulk
/// bar can pattern-match the primary action without dragging around
/// the whole `Map<String, dynamic>` payloads.
class HomeSelectionState {
  final bool isActive;
  final Set<String> selectedRecipeIds;
  final Set<String> selectedMealIds;

  const HomeSelectionState({
    required this.isActive,
    required this.selectedRecipeIds,
    required this.selectedMealIds,
  });

  static const empty = HomeSelectionState(
    isActive: false,
    selectedRecipeIds: <String>{},
    selectedMealIds: <String>{},
  );

  int get totalSelected => selectedRecipeIds.length + selectedMealIds.length;

  bool isRecipeSelected(String id) => selectedRecipeIds.contains(id);
  bool isMealSelected(String id) => selectedMealIds.contains(id);

  HomeSelectionState copyWith({
    bool? isActive,
    Set<String>? selectedRecipeIds,
    Set<String>? selectedMealIds,
  }) =>
      HomeSelectionState(
        isActive: isActive ?? this.isActive,
        selectedRecipeIds: selectedRecipeIds ?? this.selectedRecipeIds,
        selectedMealIds: selectedMealIds ?? this.selectedMealIds,
      );

  /// Enumeration of selection shapes the bulk bar consumes. Keeps the
  /// primary-action resolver table-driven so hmp-3 can extend without
  /// adding ad-hoc bool checks.
  SelectionShape get shape {
    final r = selectedRecipeIds.length;
    final m = selectedMealIds.length;
    if (r == 0 && m == 0) return SelectionShape.empty;
    if (m == 0 && r == 1) return SelectionShape.singleRecipe;
    if (m == 0 && r >= 2) return SelectionShape.multipleRecipesOnly;
    if (m == 1 && r == 0) return SelectionShape.singleMealNoRecipes;
    if (m == 1 && r >= 1) return SelectionShape.singleMealWithRecipes;
    return SelectionShape.multipleMeals; // m >= 2
  }
}

enum SelectionShape {
  empty,
  singleRecipe,
  multipleRecipesOnly,
  singleMealNoRecipes,
  singleMealWithRecipes,
  multipleMeals,
}

/// Primary-action slot on the bulk bar. Sealed so the bar can
/// pattern-match on construction instead of probing booleans.
sealed class BulkPrimaryAction {
  const BulkPrimaryAction();
}

class CreateMealAction extends BulkPrimaryAction {
  const CreateMealAction();
}

class AddToMealAction extends BulkPrimaryAction {
  /// Resolved at the UI layer — controller has no Meal registry, so
  /// the home screen supplies the name via [HomeBulkActionBar].
  const AddToMealAction();
}

class DisabledAction extends BulkPrimaryAction {
  final String reason;
  const DisabledAction(this.reason);
}

class EmptyAction extends BulkPrimaryAction {
  const EmptyAction();
}

/// Pure resolver — given a shape, produce the primary-action slot.
/// Kept out of the Notifier so unit tests can assert the table
/// directly without a ProviderContainer.
BulkPrimaryAction resolvePrimaryAction(SelectionShape shape) {
  switch (shape) {
    case SelectionShape.empty:
      return const EmptyAction();
    case SelectionShape.singleRecipe:
      return const DisabledAction(
        'Select 1 more recipe to create a Meal, or select a Meal to add to',
      );
    case SelectionShape.multipleRecipesOnly:
      return const CreateMealAction();
    case SelectionShape.singleMealNoRecipes:
      return const DisabledAction('Select recipes to add to this Meal');
    case SelectionShape.singleMealWithRecipes:
      return const AddToMealAction();
    case SelectionShape.multipleMeals:
      return const DisabledAction('Select only one Meal at a time');
  }
}

/// Home-screen multi-select state machine. Backs the `SelectionAppBar`
/// and `HomeBulkActionBar`. Uses Riverpod 3's `Notifier` idiom — the
/// epic calls for a `StateNotifier`, but Riverpod 3 removed the class;
/// the semantics are equivalent.
class HomeSelectionController extends Notifier<HomeSelectionState> {
  @override
  HomeSelectionState build() => HomeSelectionState.empty;

  /// Enter selection mode with the given seed item already selected.
  /// If already active this is equivalent to a `toggle` on the seed id.
  void enterWith({required String kind, required String id}) {
    if (state.isActive) {
      if (kind == 'meal') {
        toggleMeal(id);
      } else {
        toggleRecipe(id);
      }
      return;
    }
    state = HomeSelectionState(
      isActive: true,
      selectedRecipeIds: kind == 'meal' ? <String>{} : {id},
      selectedMealIds: kind == 'meal' ? {id} : <String>{},
    );
  }

  void toggleRecipe(String id) {
    final next = Set<String>.from(state.selectedRecipeIds);
    if (next.contains(id)) {
      next.remove(id);
    } else {
      next.add(id);
    }
    _applySelection(
      recipes: next,
      meals: state.selectedMealIds,
    );
  }

  void toggleMeal(String id) {
    final next = Set<String>.from(state.selectedMealIds);
    if (next.contains(id)) {
      next.remove(id);
    } else {
      next.add(id);
    }
    _applySelection(
      recipes: state.selectedRecipeIds,
      meals: next,
    );
  }

  /// Remove ids that vanished from a background refresh. If both sets
  /// are empty afterwards, selection mode exits automatically — the
  /// caller decides whether to surface the "Selection cleared" toast.
  bool reconcile({
    required Set<String> knownRecipeIds,
    required Set<String> knownMealIds,
  }) {
    if (!state.isActive) return false;
    final nextRecipes = state.selectedRecipeIds
        .where(knownRecipeIds.contains)
        .toSet();
    final nextMeals = state.selectedMealIds
        .where(knownMealIds.contains)
        .toSet();
    if (nextRecipes.length == state.selectedRecipeIds.length &&
        nextMeals.length == state.selectedMealIds.length) {
      return false;
    }
    _applySelection(recipes: nextRecipes, meals: nextMeals);
    return nextRecipes.isEmpty && nextMeals.isEmpty;
  }

  void exit() {
    state = HomeSelectionState.empty;
  }

  void _applySelection({
    required Set<String> recipes,
    required Set<String> meals,
  }) {
    final hasAny = recipes.isNotEmpty || meals.isNotEmpty;
    state = HomeSelectionState(
      isActive: hasAny,
      selectedRecipeIds: recipes,
      selectedMealIds: meals,
    );
  }
}

final homeSelectionProvider =
    NotifierProvider.autoDispose<HomeSelectionController, HomeSelectionState>(
  HomeSelectionController.new,
);
