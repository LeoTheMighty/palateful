import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../recipe_books/providers/recipe_books_provider.dart';
import '../../recipe_books/services/recipe_book_service.dart';

/// Bottom sheet used by the home bulk bar (story 1) and the recipe-detail
/// pill-row picker (story 4) to let the user pick a destination book.
///
/// Books the user can write to (`user_role in {owner, editor}`) are
/// shown. System books (`is_system == true`) pin to the top — Trying Out
/// is the first option for users who have not curated their own books
/// yet. A trailing "+ New book" row lets the user create a new book
/// inline and target it in one motion.
///
/// Returns the selected book map, or `null` if the sheet was dismissed.
class BookPickerSheet extends ConsumerStatefulWidget {
  /// If non-null, the book id that should NOT appear in the list. Used
  /// when the picker is invoked in a "move to a different book" context
  /// (recipe detail pill row, single-source bulk move).
  final String? excludeBookId;

  /// Sheet title — defaults to "Choose a book". Bulk callers may pass
  /// "Move to…" or "Add to…" so the user sees the action they tapped.
  final String title;

  const BookPickerSheet({
    super.key,
    this.excludeBookId,
    this.title = 'Choose a book',
  });

  /// Convenience opener. Returns the picked book map (with at least
  /// `id` and `name`) or `null` when dismissed.
  static Future<Map<String, dynamic>?> show(
    BuildContext context, {
    String? excludeBookId,
    String title = 'Choose a book',
  }) {
    return showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => BookPickerSheet(
        excludeBookId: excludeBookId,
        title: title,
      ),
    );
  }

  @override
  ConsumerState<BookPickerSheet> createState() => _BookPickerSheetState();
}

class _BookPickerSheetState extends ConsumerState<BookPickerSheet> {
  bool _creating = false;

  @override
  Widget build(BuildContext context) {
    final asyncBooks = ref.watch(recipeBooksProvider);
    final theme = Theme.of(context);

    return ConstrainedBox(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.7,
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Text(widget.title, style: theme.textTheme.titleMedium),
            ),
            Flexible(
              child: asyncBooks.when(
                loading: () => const Padding(
                  padding: EdgeInsets.all(24),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) => Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    'Could not load books. Please try again.',
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                ),
                data: (allBooks) {
                  final books = sortBooksForPicker(
                    allBooks,
                    excludeBookId: widget.excludeBookId,
                  );
                  return ListView(
                    shrinkWrap: true,
                    children: [
                      for (final book in books) _BookRow(book: book),
                      _NewBookRow(
                        creating: _creating,
                        onCreate: _handleCreateNewBook,
                      ),
                    ],
                  );
                },
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Future<void> _handleCreateNewBook() async {
    if (_creating) return;
    final controller = TextEditingController();
    try {
      final name = await showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('New book'),
          content: TextField(
            controller: controller,
            autofocus: true,
            textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(
              hintText: 'e.g. Weeknight dinners',
            ),
            onSubmitted: (value) => Navigator.pop(ctx, value.trim()),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () =>
                  Navigator.pop(ctx, controller.text.trim()),
              child: const Text('Create'),
            ),
          ],
        ),
      );
      if (name == null || name.isEmpty) return;
      if (!mounted) return;

      setState(() => _creating = true);
      final created = await getIt<RecipeBookService>()
          .createRecipeBook({'name': name});
      if (!mounted) return;
      Navigator.pop(context, created);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not create book.')),
      );
    } finally {
      controller.dispose();
      if (mounted) setState(() => _creating = false);
    }
  }
}

/// Pure helper: filter+sort the picker's book list. Extracted so the
/// widget tests can pin the ordering rule without spinning a UI.
///
/// Rules:
/// - Drop the row whose id matches [excludeBookId].
/// - Drop rows where `user_role` isn't `owner` or `editor` — only books
///   the user can write to are valid move targets.
/// - System books (`is_system == true`) pin to the top, with Trying Out
///   first by name (alphabetical inside the system group is fine since
///   only one system book exists today).
/// - Within the user-book group, preserve the upstream order
///   (`recipeBooksProvider` returns `last_opened_at desc nulls last`).
List<Map<String, dynamic>> sortBooksForPicker(
  List<Map<String, dynamic>> books, {
  String? excludeBookId,
}) {
  final filtered = books.where((b) {
    final id = b['id']?.toString();
    if (id == null) return false;
    if (excludeBookId != null && id == excludeBookId) return false;
    final role = b['user_role']?.toString();
    return role == 'owner' || role == 'editor';
  }).toList();

  final system = filtered.where((b) => b['is_system'] == true).toList()
    ..sort((a, b) =>
        (a['name'] as String? ?? '').compareTo(b['name'] as String? ?? ''));
  final user = filtered.where((b) => b['is_system'] != true).toList();
  return [...system, ...user];
}

class _BookRow extends StatelessWidget {
  final Map<String, dynamic> book;
  const _BookRow({required this.book});

  @override
  Widget build(BuildContext context) {
    final isSystem = book['is_system'] == true;
    final theme = Theme.of(context);
    return ListTile(
      leading: Icon(
        isSystem ? Icons.auto_awesome_outlined : Icons.menu_book_outlined,
        color: isSystem ? theme.colorScheme.primary : null,
      ),
      title: Text(book['name']?.toString() ?? 'Untitled'),
      subtitle: Text('${book['recipe_count'] ?? 0} recipes'),
      onTap: () => Navigator.pop(context, book),
    );
  }
}

class _NewBookRow extends StatelessWidget {
  final bool creating;
  final VoidCallback onCreate;

  const _NewBookRow({required this.creating, required this.onCreate});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      leading: creating
          ? const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2))
          : Icon(Icons.add, color: theme.colorScheme.primary),
      title: Text(
        'New book',
        style: TextStyle(
          color: theme.colorScheme.primary,
          fontWeight: FontWeight.w500,
        ),
      ),
      onTap: creating ? null : onCreate,
    );
  }
}
