/// Enum of mutation types that surface a failure Snackbar. Keyed copy lives
/// in [mutationFailureCopy] so UI handlers call
/// `showMutationFailureSnackbar(context, type, retry: ...)` without having
/// to pass raw strings.
///
/// The migration epics (`reactive-migration-meals-calendar`,
/// `reactive-migration-books-profile-pantry-and-polish`) added every
/// remaining case. A unit test in `mutation_failure_copy_test.dart`
/// enumerates `MutationType.values` and asserts every enum value has a
/// `mutationFailureCopy` entry — the build fails the moment a new case
/// lands without copy.
enum MutationType {
  // Recipe
  createRecipe,
  updateRecipe,
  archiveRecipe,
  unarchiveRecipe,
  favoriteRecipe,
  unfavoriteRecipe,
  forkRecipe,
  moveRecipe,
  copyRecipe,
  addRecipeNote,
  deleteRecipeNote,
  bulkArchiveRecipes,
  bulkMoveRecipes,
  bulkUpdateTags,

  // Imports
  dismissImportItem,
  dismissAllFailed,
  retryImportItem,

  // Meals (rmc-1)
  createMeal,
  updateMeal,
  archiveMeal,
  unarchiveMeal,
  favoriteMeal,
  unfavoriteMeal,
  addComponent,
  removeComponent,
  reorderComponents,
  shareMeal,

  // Recipe books (rp-1)
  createRecipeBook,
  updateRecipeBook,
  archiveRecipeBook,
  restoreRecipeBook,
  deleteRecipeBook,
  addBookMember,
  updateBookMemberRole,
  removeBookMember,

  // Profile + notification prefs (rp-2)
  updateProfile,
  setUsername,
  submitFeedback,
  exportRecipes,
  updateNotificationPrefs,

  // Pantry (rp-3)
  addPantryItem,
  updatePantryItem,
  deletePantryItem,

  // Cooking log (rp-3)
  createCookingLog,

  // Shopping list items (rp-4)
  addShoppingListItem,
  updateShoppingListItem,
  deleteShoppingListItem,

  // Calendars (rmc-3)
  createCalendar,
  updateCalendar,
  deleteCalendar,

  // Meal events (rmc-3)
  createMealEvent,
  updateMealEvent,
  rescheduleMealEvent,
  moveMealEvent,
  deleteMealEvent,
  markMealCompleted,
  planMealEvent,
  loadShoppingLists,
  addEventIngredients,

  // Recurrence rules (rmc-3)
  createRecurrenceRule,
  updateRecurrenceRule,
  deleteRecurrenceRule,
  moveRecurrenceRule,
}

/// (verb, noun) pair used to render `"Couldn't <verb> <noun>"` in the
/// Snackbar. Copy is intentionally short — at iPhone SE 3rd-gen 320px width
/// the title line must fit on two lines, and the Retry button label (5
/// chars) must never wrap.
///
/// See rf-1 / epic Risks — "Snackbar width at 320px".
class MutationFailureCopy {
  const MutationFailureCopy({required this.verb, required this.noun});

  final String verb;
  final String noun;

  String get title => "Couldn't $verb $noun";
}

const Map<MutationType, MutationFailureCopy> mutationFailureCopy = {
  MutationType.createRecipe:
      MutationFailureCopy(verb: 'save', noun: 'recipe'),
  MutationType.updateRecipe:
      MutationFailureCopy(verb: 'update', noun: 'recipe'),
  MutationType.archiveRecipe:
      MutationFailureCopy(verb: 'archive', noun: 'recipe'),
  MutationType.unarchiveRecipe:
      MutationFailureCopy(verb: 'restore', noun: 'recipe'),
  MutationType.favoriteRecipe:
      MutationFailureCopy(verb: 'favorite', noun: 'recipe'),
  MutationType.unfavoriteRecipe:
      MutationFailureCopy(verb: 'unfavorite', noun: 'recipe'),
  MutationType.forkRecipe:
      MutationFailureCopy(verb: 'fork', noun: 'recipe'),
  MutationType.moveRecipe:
      MutationFailureCopy(verb: 'move', noun: 'recipe'),
  MutationType.copyRecipe:
      MutationFailureCopy(verb: 'copy', noun: 'recipe'),
  MutationType.addRecipeNote:
      MutationFailureCopy(verb: 'add', noun: 'note'),
  MutationType.deleteRecipeNote:
      MutationFailureCopy(verb: 'delete', noun: 'note'),
  MutationType.bulkArchiveRecipes:
      MutationFailureCopy(verb: 'archive', noun: 'recipes'),
  MutationType.bulkMoveRecipes:
      MutationFailureCopy(verb: 'move', noun: 'recipes'),
  MutationType.bulkUpdateTags:
      MutationFailureCopy(verb: 'update', noun: 'tags'),
  MutationType.dismissImportItem:
      MutationFailureCopy(verb: 'dismiss', noun: 'import'),
  MutationType.dismissAllFailed:
      MutationFailureCopy(verb: 'dismiss', noun: 'imports'),
  MutationType.retryImportItem:
      MutationFailureCopy(verb: 'retry', noun: 'import'),
  MutationType.createMeal:
      MutationFailureCopy(verb: 'save', noun: 'meal'),
  MutationType.updateMeal:
      MutationFailureCopy(verb: 'update', noun: 'meal'),
  MutationType.archiveMeal:
      MutationFailureCopy(verb: 'archive', noun: 'meal'),
  MutationType.unarchiveMeal:
      MutationFailureCopy(verb: 'restore', noun: 'meal'),
  MutationType.favoriteMeal:
      MutationFailureCopy(verb: 'favorite', noun: 'meal'),
  MutationType.unfavoriteMeal:
      MutationFailureCopy(verb: 'unfavorite', noun: 'meal'),
  MutationType.addComponent:
      MutationFailureCopy(verb: 'add', noun: 'recipe'),
  MutationType.removeComponent:
      MutationFailureCopy(verb: 'remove', noun: 'recipe'),
  MutationType.reorderComponents:
      MutationFailureCopy(verb: 'reorder', noun: 'recipes'),
  MutationType.shareMeal:
      MutationFailureCopy(verb: 'share', noun: 'meal'),
  MutationType.createRecipeBook:
      MutationFailureCopy(verb: 'create', noun: 'recipe book'),
  MutationType.updateRecipeBook:
      MutationFailureCopy(verb: 'update', noun: 'recipe book'),
  MutationType.archiveRecipeBook:
      MutationFailureCopy(verb: 'archive', noun: 'recipe book'),
  MutationType.restoreRecipeBook:
      MutationFailureCopy(verb: 'restore', noun: 'recipe book'),
  MutationType.deleteRecipeBook:
      MutationFailureCopy(verb: 'delete', noun: 'recipe book'),
  MutationType.addBookMember:
      MutationFailureCopy(verb: 'add', noun: 'member'),
  MutationType.updateBookMemberRole:
      MutationFailureCopy(verb: 'update', noun: 'member role'),
  MutationType.removeBookMember:
      MutationFailureCopy(verb: 'remove', noun: 'member'),
  MutationType.updateProfile:
      MutationFailureCopy(verb: 'update', noun: 'profile'),
  MutationType.setUsername:
      MutationFailureCopy(verb: 'set', noun: 'username'),
  MutationType.submitFeedback:
      MutationFailureCopy(verb: 'send', noun: 'feedback'),
  MutationType.exportRecipes:
      MutationFailureCopy(verb: 'export', noun: 'recipes'),
  MutationType.updateNotificationPrefs:
      MutationFailureCopy(verb: 'update', noun: 'notifications'),
  MutationType.addPantryItem:
      MutationFailureCopy(verb: 'add', noun: 'pantry item'),
  MutationType.updatePantryItem:
      MutationFailureCopy(verb: 'update', noun: 'pantry item'),
  MutationType.deletePantryItem:
      MutationFailureCopy(verb: 'remove', noun: 'pantry item'),
  MutationType.createCookingLog:
      MutationFailureCopy(verb: 'save', noun: 'cook note'),
  MutationType.addShoppingListItem:
      MutationFailureCopy(verb: 'add', noun: 'shopping item'),
  MutationType.updateShoppingListItem:
      MutationFailureCopy(verb: 'update', noun: 'shopping item'),
  MutationType.deleteShoppingListItem:
      MutationFailureCopy(verb: 'remove', noun: 'shopping item'),
  MutationType.createCalendar:
      MutationFailureCopy(verb: 'create', noun: 'calendar'),
  MutationType.updateCalendar:
      MutationFailureCopy(verb: 'update', noun: 'calendar'),
  MutationType.deleteCalendar:
      MutationFailureCopy(verb: 'delete', noun: 'calendar'),
  MutationType.createMealEvent:
      MutationFailureCopy(verb: 'plan', noun: 'meal'),
  MutationType.updateMealEvent:
      MutationFailureCopy(verb: 'update', noun: 'meal'),
  MutationType.rescheduleMealEvent:
      MutationFailureCopy(verb: 'reschedule', noun: 'meal'),
  MutationType.moveMealEvent:
      MutationFailureCopy(verb: 'move', noun: 'meal'),
  MutationType.deleteMealEvent:
      MutationFailureCopy(verb: 'remove', noun: 'meal'),
  MutationType.markMealCompleted:
      MutationFailureCopy(verb: 'mark', noun: 'cooked'),
  MutationType.planMealEvent:
      MutationFailureCopy(verb: 'plan', noun: 'meal'),
  MutationType.loadShoppingLists:
      MutationFailureCopy(verb: 'load', noun: 'shopping lists'),
  MutationType.addEventIngredients:
      MutationFailureCopy(verb: 'add', noun: 'ingredients'),
  MutationType.createRecurrenceRule:
      MutationFailureCopy(verb: 'save', noun: 'repeating meal'),
  MutationType.updateRecurrenceRule:
      MutationFailureCopy(verb: 'update', noun: 'repeating meal'),
  MutationType.deleteRecurrenceRule:
      MutationFailureCopy(verb: 'remove', noun: 'repeating meal'),
  MutationType.moveRecurrenceRule:
      MutationFailureCopy(verb: 'move', noun: 'repeating meal'),
};
