import 'package:flutter/material.dart';

/// recipe-bulk-org-4 — collapsed-by-default book picker for the recipe
/// detail screen.
///
/// In its collapsed state the row renders a single 📒 pill with the
/// current book name. Tapping the pill expands a horizontal scroll of
/// every writable book + a trailing "+ New book" pill. Tapping any
/// pill calls [onSelect] (a `bookId`-or-null sentinel) — null means
/// "+ New book"; the parent owns the inline-create flow.
///
/// Tapping the current pill collapses the row without firing any
/// callback. Tapping outside the row also collapses it (the parent
/// listens for taps via a GestureDetector wrapped around this widget
/// when needed — by default, the row stays expanded until another pill
/// is tapped or the user taps the active pill).
class RecipeBookPillRow extends StatefulWidget {
  /// All books the user can move *this* recipe to + the recipe's
  /// current book. Caller has already filtered out non-writable books.
  /// `is_system` rows pin to the front of the expanded row.
  final List<Map<String, dynamic>> books;

  /// The recipe's current `recipe_book_id`. Highlighted in expanded
  /// state.
  final String currentBookId;

  /// Disabled while a move is in flight — taps are ignored.
  final bool isWorking;

  /// Fires with `bookId` for an existing book, or null for the
  /// "+ New book" pill. Parent does the work.
  final void Function(String? bookId) onSelect;

  const RecipeBookPillRow({
    super.key,
    required this.books,
    required this.currentBookId,
    required this.onSelect,
    this.isWorking = false,
  });

  @override
  State<RecipeBookPillRow> createState() => RecipeBookPillRowState();
}

class RecipeBookPillRowState extends State<RecipeBookPillRow> {
  bool _expanded = false;

  /// Public for parent-state callers (e.g. an outside-tap listener)
  /// that need to collapse the row imperatively.
  void collapse() {
    if (!_expanded) return;
    setState(() => _expanded = false);
  }

  Map<String, dynamic>? get _currentBook {
    for (final b in widget.books) {
      if (b['id']?.toString() == widget.currentBookId) return b;
    }
    return null;
  }

  /// Sort: system books first, then everything else preserving the
  /// upstream order. Pure helper so tests can pin the rule.
  List<Map<String, dynamic>> get _sortedBooks =>
      sortBooksForPillRow(widget.books);

  @override
  Widget build(BuildContext context) {
    if (_expanded) {
      return _buildExpanded(context);
    }
    return _buildCollapsed(context);
  }

  Widget _buildCollapsed(BuildContext context) {
    final theme = Theme.of(context);
    final current = _currentBook;
    final name = current?['name']?.toString() ?? 'Untitled';
    return Align(
      alignment: Alignment.centerLeft,
      child: ActionChip(
        avatar: Icon(
          Icons.menu_book_outlined,
          size: 18,
          color: theme.colorScheme.onSecondaryContainer,
        ),
        label: Text(name),
        onPressed:
            widget.isWorking ? null : () => setState(() => _expanded = true),
      ),
    );
  }

  Widget _buildExpanded(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        children: [
          for (final book in _sortedBooks) ...[
            _BookPillChip(
              book: book,
              isCurrent: book['id']?.toString() == widget.currentBookId,
              isWorking: widget.isWorking,
              onTap: () {
                final id = book['id']?.toString();
                if (id == widget.currentBookId) {
                  // Tapping the current pill collapses without firing.
                  setState(() => _expanded = false);
                  return;
                }
                widget.onSelect(id);
              },
            ),
            const SizedBox(width: 8),
          ],
          _NewBookPill(
            isWorking: widget.isWorking,
            onTap: () => widget.onSelect(null),
          ),
        ],
      ),
    );
  }
}

/// Pure helper — extracted so widget tests can assert ordering without
/// pumping the whole row.
List<Map<String, dynamic>> sortBooksForPillRow(
  List<Map<String, dynamic>> books,
) {
  final system = books.where((b) => b['is_system'] == true).toList();
  final user = books.where((b) => b['is_system'] != true).toList();
  return [...system, ...user];
}

class _BookPillChip extends StatelessWidget {
  final Map<String, dynamic> book;
  final bool isCurrent;
  final bool isWorking;
  final VoidCallback onTap;

  const _BookPillChip({
    required this.book,
    required this.isCurrent,
    required this.isWorking,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isSystem = book['is_system'] == true;
    return ChoiceChip(
      avatar: isSystem
          ? Icon(
              Icons.auto_awesome_outlined,
              size: 18,
              color: isCurrent
                  ? theme.colorScheme.primary
                  : theme.colorScheme.onSurfaceVariant,
            )
          : null,
      selected: isCurrent,
      label: Text(book['name']?.toString() ?? 'Untitled'),
      onSelected: isWorking ? null : (_) => onTap(),
    );
  }
}

class _NewBookPill extends StatelessWidget {
  final bool isWorking;
  final VoidCallback onTap;

  const _NewBookPill({required this.isWorking, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ActionChip(
      avatar: Icon(Icons.add, color: theme.colorScheme.primary),
      label: Text(
        'New book',
        style: TextStyle(color: theme.colorScheme.primary),
      ),
      onPressed: isWorking ? null : onTap,
    );
  }
}
