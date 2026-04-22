import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../services/recipe_book_service.dart';

/// rp-1 — single source of truth for the Books tab. All three list
/// surfaces (all, archived, shared) fetch via [RecipeBookService] and
/// invalidate when the MutationBus reports any book-level change.
///
/// Per epic Locked Decision #2, subscribers live inside the provider
/// body and call `ref.invalidateSelf()` on relevant events. The screen
/// never subscribes to the bus directly.

bool _shouldInvalidateBookList(MutationEvent event) => switch (event) {
      RecipeBookCreated() ||
      RecipeBookUpdated() ||
      RecipeBookArchived() ||
      RecipeBookUnarchived() ||
      RecipeBookDeleted() ||
      RecipeBookMemberAdded() ||
      RecipeBookMemberChanged() =>
        true,
      _ => false,
    };

bool _shouldInvalidateActiveBook(MutationEvent event, String bookId) {
  if (event is RecipeBookUpdated) return event.bookId == bookId;
  if (event is RecipeBookArchived) return event.bookId == bookId;
  if (event is RecipeBookUnarchived) return event.bookId == bookId;
  if (event is RecipeBookDeleted) return event.bookId == bookId;
  if (event is RecipeBookMemberAdded) return event.bookId == bookId;
  if (event is RecipeBookMemberChanged) return event.bookId == bookId;
  // Recipes added / moved / archived inside the book also update the
  // detail payload (recipe count / latest-activity banner).
  if (event is RecipeCreated) return event.bookId == bookId;
  if (event is RecipeArchived) return event.bookId == bookId;
  if (event is RecipeMoved) {
    return event.oldBookId == bookId || event.newBookId == bookId;
  }
  if (event is RecipeBulkArchived) return event.bookId == bookId;
  return false;
}

bool _shouldInvalidateBookMembers(MutationEvent event, String bookId) {
  if (event is RecipeBookMemberAdded) return event.bookId == bookId;
  if (event is RecipeBookMemberChanged) return event.bookId == bookId;
  return false;
}

/// All readable books for the signed-in user. Subscribers: Books tab list,
/// any picker that shows "move to another book".
final recipeBooksProvider =
    FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_shouldInvalidateBookList(event)) ref.invalidateSelf();
  });
  ref.onDispose(sub.cancel);

  return getIt<RecipeBookService>().listRecipeBooks();
});

/// Archived books screen. Separate provider so the active-books tab
/// doesn't pay for this fetch.
final archivedRecipeBooksProvider =
    FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (event is RecipeBookArchived ||
        event is RecipeBookUnarchived ||
        event is RecipeBookDeleted) {
      ref.invalidateSelf();
    }
  });
  ref.onDispose(sub.cancel);

  return getIt<RecipeBookService>().listArchivedRecipeBooks();
});

/// Single-book detail. Family-keyed so multiple detail screens (split
/// view on iPad, push-then-push on phone) cache independently.
final activeRecipeBookProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, String>(
        (ref, bookId) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_shouldInvalidateActiveBook(event, bookId)) ref.invalidateSelf();
  });
  ref.onDispose(sub.cancel);

  return getIt<RecipeBookService>().getRecipeBook(bookId);
});

/// Flat list of books the user is a member of but does not own.
/// Materialized by filtering `listRecipeBooks()` — the endpoint already
/// returns ownership metadata. Separate provider + filter keeps the
/// membership surface reactive without a second network round-trip.
final sharedRecipeBooksProvider =
    FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_shouldInvalidateBookList(event)) ref.invalidateSelf();
  });
  ref.onDispose(sub.cancel);

  final books = await getIt<RecipeBookService>().listRecipeBooks();
  return books
      .where((book) => book['is_owner'] == false || book['role'] != 'owner')
      .toList();
});

/// Members of a single book. Family-keyed by book id.
final recipeBookMembersProvider =
    FutureProvider.autoDispose.family<List<Map<String, dynamic>>, String>(
        (ref, bookId) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_shouldInvalidateBookMembers(event, bookId)) ref.invalidateSelf();
  });
  ref.onDispose(sub.cancel);

  final book = await getIt<RecipeBookService>().getRecipeBook(bookId);
  final members = book['members'];
  if (members is List) {
    return members
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();
  }
  return const <Map<String, dynamic>>[];
});
