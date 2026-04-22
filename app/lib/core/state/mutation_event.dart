/// Sealed class hierarchy of mutation events broadcast over the app-wide
/// [MutationBus][mutation_bus.dart].
///
/// Every mutation — local service call, WS inbound, whatever — lowers into
/// one of these types. Subscribers filter by runtime type (`is RecipeCreated`,
/// `is ImportItemDismissed`, etc.) and refetch the data they own.
///
/// Payload shapes carry the full resource when the API already returns one
/// (create, update, favorite — see rf-2 backend expansion). Archive / delete
/// events carry only ids. Bulk events carry a list of ids.
///
/// Meal*/Calendar*/Book*/Pantry*/Profile* cases ship here as **stubs** so the
/// two migration epics (`reactive-migration-meals-calendar` and
/// `reactive-migration-books-profile-pantry`) only add emit/subscribe call
/// sites — never new type declarations. Adding a case here is a type-level
/// change that ripples to every exhaustive subscriber; keeping the shape
/// stable now saves churn later.
library;

/// Categorisation for filter helpers. Handy when a subscriber wants to
/// react to "any recipe event", "any import event", etc., without
/// enumerating every subclass.
enum MutationCategory {
  recipe,
  meal,
  calendar,
  mealEvent,
  recipeBook,
  importJob,
  importItem,
  pantryItem,
  profile,
  notificationPrefs,
}

/// Base class for everything on the bus.
sealed class MutationEvent {
  const MutationEvent();

  MutationCategory get category;
}

// ---------------------------------------------------------------------------
// Recipe events — live in rf-1; emits land in rf-4.
// ---------------------------------------------------------------------------

class RecipeCreated extends MutationEvent {
  const RecipeCreated({
    required this.recipeId,
    required this.recipe,
    required this.bookId,
  });

  final String recipeId;
  final Map<String, dynamic> recipe;
  final String bookId;

  @override
  MutationCategory get category => MutationCategory.recipe;
}

class RecipeUpdated extends MutationEvent {
  const RecipeUpdated({
    required this.recipeId,
    required this.recipe,
  });

  final String recipeId;
  final Map<String, dynamic> recipe;

  @override
  MutationCategory get category => MutationCategory.recipe;
}

class RecipeArchived extends MutationEvent {
  const RecipeArchived({
    required this.recipeId,
    required this.bookId,
  });

  final String recipeId;
  final String bookId;

  @override
  MutationCategory get category => MutationCategory.recipe;
}

class RecipeUnarchived extends MutationEvent {
  const RecipeUnarchived({
    required this.recipeId,
    required this.recipe,
  });

  final String recipeId;
  final Map<String, dynamic> recipe;

  @override
  MutationCategory get category => MutationCategory.recipe;
}

class RecipeFavorited extends MutationEvent {
  const RecipeFavorited({
    required this.recipeId,
    required this.recipe,
    required this.isFavorited,
  });

  final String recipeId;
  final Map<String, dynamic> recipe;
  final bool isFavorited;

  @override
  MutationCategory get category => MutationCategory.recipe;
}

class RecipeForked extends MutationEvent {
  const RecipeForked({
    required this.recipeId,
    required this.recipe,
    required this.parentRecipeId,
  });

  final String recipeId;
  final Map<String, dynamic> recipe;
  final String parentRecipeId;

  @override
  MutationCategory get category => MutationCategory.recipe;
}

class RecipeMoved extends MutationEvent {
  const RecipeMoved({
    required this.recipeId,
    required this.recipe,
    required this.oldBookId,
    required this.newBookId,
  });

  final String recipeId;
  final Map<String, dynamic> recipe;
  final String oldBookId;
  final String newBookId;

  @override
  MutationCategory get category => MutationCategory.recipe;
}

/// Single bulk event for bulk-archive flows. Subscribers that care about
/// single-item archive should handle both this and [RecipeArchived].
/// See epic Locked Decision #3 — no 100ms coalescer for bulk paths.
class RecipeBulkArchived extends MutationEvent {
  const RecipeBulkArchived({
    required this.recipeIds,
    required this.bookId,
  });

  final List<String> recipeIds;
  final String bookId;

  @override
  MutationCategory get category => MutationCategory.recipe;
}

// ---------------------------------------------------------------------------
// Import events — live in rf-1; emits land in rf-5.
// ---------------------------------------------------------------------------

class ImportItemDismissed extends MutationEvent {
  const ImportItemDismissed({
    required this.itemId,
    required this.item,
    required this.jobDismissed,
    this.jobId,
  });

  final String itemId;

  /// Full updated `ImportItem.Response` when available (rf-2 backend change).
  /// `null` when the server is still on the pre-rf-2 shape — subscribers
  /// fall back to invalidate-and-refetch.
  final Map<String, dynamic>? item;
  final bool jobDismissed;

  /// Job id this item belonged to, when known. Lets subscribers scope an
  /// invalidation without digging into [item].
  final String? jobId;

  @override
  MutationCategory get category => MutationCategory.importItem;
}

class ImportItemRetried extends MutationEvent {
  const ImportItemRetried({
    required this.itemId,
    required this.item,
    this.jobId,
  });

  final String itemId;
  final Map<String, dynamic>? item;
  final String? jobId;

  @override
  MutationCategory get category => MutationCategory.importItem;
}

class ImportJobDismissed extends MutationEvent {
  const ImportJobDismissed({required this.jobId});

  final String jobId;

  @override
  MutationCategory get category => MutationCategory.importJob;
}

// ---------------------------------------------------------------------------
// Meal / Calendar / MealEvent — STUBS only in this epic. Emits land in
// `epic-reactive-migration-meals-calendar`. Subtypes exist now so downstream
// epics only add call sites.
// ---------------------------------------------------------------------------

class MealCreated extends MutationEvent {
  const MealCreated({required this.mealId, required this.meal});

  final String mealId;
  final Map<String, dynamic> meal;

  @override
  MutationCategory get category => MutationCategory.meal;
}

class MealUpdated extends MutationEvent {
  const MealUpdated({required this.mealId, required this.meal});

  final String mealId;
  final Map<String, dynamic> meal;

  @override
  MutationCategory get category => MutationCategory.meal;
}

class MealArchived extends MutationEvent {
  const MealArchived({required this.mealId});

  final String mealId;

  @override
  MutationCategory get category => MutationCategory.meal;
}

class MealFavorited extends MutationEvent {
  const MealFavorited({
    required this.mealId,
    required this.meal,
    required this.isFavorited,
  });

  final String mealId;
  final Map<String, dynamic> meal;
  final bool isFavorited;

  @override
  MutationCategory get category => MutationCategory.meal;
}

class CalendarCreated extends MutationEvent {
  const CalendarCreated({required this.calendarId, required this.calendar});

  final String calendarId;
  final Map<String, dynamic> calendar;

  @override
  MutationCategory get category => MutationCategory.calendar;
}

class CalendarUpdated extends MutationEvent {
  const CalendarUpdated({required this.calendarId, required this.calendar});

  final String calendarId;
  final Map<String, dynamic> calendar;

  @override
  MutationCategory get category => MutationCategory.calendar;
}

class CalendarArchived extends MutationEvent {
  const CalendarArchived({required this.calendarId});

  final String calendarId;

  @override
  MutationCategory get category => MutationCategory.calendar;
}

class MealEventCreated extends MutationEvent {
  const MealEventCreated({required this.eventId, required this.event});

  final String eventId;
  final Map<String, dynamic> event;

  @override
  MutationCategory get category => MutationCategory.mealEvent;
}

class MealEventUpdated extends MutationEvent {
  const MealEventUpdated({required this.eventId, required this.event});

  final String eventId;
  final Map<String, dynamic> event;

  @override
  MutationCategory get category => MutationCategory.mealEvent;
}

class MealEventArchived extends MutationEvent {
  const MealEventArchived({required this.eventId});

  final String eventId;

  @override
  MutationCategory get category => MutationCategory.mealEvent;
}

// ---------------------------------------------------------------------------
// Recipe-book / Pantry / Profile — STUBS only in this epic. Emits land in
// `epic-reactive-migration-books-profile-pantry-and-polish`.
// ---------------------------------------------------------------------------

class RecipeBookCreated extends MutationEvent {
  const RecipeBookCreated({required this.bookId, required this.book});

  final String bookId;
  final Map<String, dynamic> book;

  @override
  MutationCategory get category => MutationCategory.recipeBook;
}

class RecipeBookUpdated extends MutationEvent {
  const RecipeBookUpdated({required this.bookId, required this.book});

  final String bookId;
  final Map<String, dynamic> book;

  @override
  MutationCategory get category => MutationCategory.recipeBook;
}

class RecipeBookArchived extends MutationEvent {
  const RecipeBookArchived({required this.bookId});

  final String bookId;

  @override
  MutationCategory get category => MutationCategory.recipeBook;
}

class PantryItemCreated extends MutationEvent {
  const PantryItemCreated({required this.itemId, required this.item});

  final String itemId;
  final Map<String, dynamic> item;

  @override
  MutationCategory get category => MutationCategory.pantryItem;
}

class PantryItemUpdated extends MutationEvent {
  const PantryItemUpdated({required this.itemId, required this.item});

  final String itemId;
  final Map<String, dynamic> item;

  @override
  MutationCategory get category => MutationCategory.pantryItem;
}

class PantryItemArchived extends MutationEvent {
  const PantryItemArchived({required this.itemId});

  final String itemId;

  @override
  MutationCategory get category => MutationCategory.pantryItem;
}

class ProfileUpdated extends MutationEvent {
  const ProfileUpdated({required this.profile});

  final Map<String, dynamic> profile;

  @override
  MutationCategory get category => MutationCategory.profile;
}

class NotificationPrefsUpdated extends MutationEvent {
  const NotificationPrefsUpdated({required this.prefs});

  final Map<String, dynamic> prefs;

  @override
  MutationCategory get category => MutationCategory.notificationPrefs;
}
