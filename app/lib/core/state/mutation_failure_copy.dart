/// Enum of mutation types that surface a failure Snackbar. Keyed copy lives
/// in [mutationFailureCopy] so UI handlers call
/// `showMutationFailureSnackbar(context, type, retry: ...)` without having
/// to pass raw strings.
///
/// Expanded incrementally: rf-1 ships import + recipe verbs; migration epics
/// add meal / calendar / pantry / profile entries.
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
  bulkArchiveRecipes,

  // Imports
  dismissImportItem,
  dismissAllFailed,
  retryImportItem,
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
      MutationFailureCopy(verb: 'copy', noun: 'recipe'),
  MutationType.moveRecipe:
      MutationFailureCopy(verb: 'move', noun: 'recipe'),
  MutationType.bulkArchiveRecipes:
      MutationFailureCopy(verb: 'archive', noun: 'recipes'),
  MutationType.dismissImportItem:
      MutationFailureCopy(verb: 'dismiss', noun: 'import'),
  MutationType.dismissAllFailed:
      MutationFailureCopy(verb: 'dismiss', noun: 'imports'),
  MutationType.retryImportItem:
      MutationFailureCopy(verb: 'retry', noun: 'import'),
};
