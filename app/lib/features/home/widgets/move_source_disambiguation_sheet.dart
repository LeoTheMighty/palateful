import 'package:flutter/material.dart';

/// Per-source-book group passed into [MoveSourceDisambiguationSheet] —
/// captures the source book id, its display name, and the recipe ids
/// the selection currently holds from that book.
class SourceBookGroup {
  final String bookId;
  final String bookName;
  final List<String> recipeIds;

  const SourceBookGroup({
    required this.bookId,
    required this.bookName,
    required this.recipeIds,
  });

  int get count => recipeIds.length;
}

/// Disambiguation sheet shown when `Move to…` fires from the global
/// "All recipes" view with a selection spanning multiple source books.
///
/// Default: every source book checked. Unchecking removes all recipes
/// from that group from the operation. Returns the (possibly trimmed)
/// list of `SourceBookGroup`s on Confirm, or `null` on dismiss.
class MoveSourceDisambiguationSheet extends StatefulWidget {
  final List<SourceBookGroup> groups;

  const MoveSourceDisambiguationSheet({super.key, required this.groups});

  static Future<List<SourceBookGroup>?> show(
    BuildContext context, {
    required List<SourceBookGroup> groups,
  }) {
    return showModalBottomSheet<List<SourceBookGroup>>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => MoveSourceDisambiguationSheet(groups: groups),
    );
  }

  @override
  State<MoveSourceDisambiguationSheet> createState() =>
      _MoveSourceDisambiguationSheetState();
}

class _MoveSourceDisambiguationSheetState
    extends State<MoveSourceDisambiguationSheet> {
  late final Set<String> _checked;

  @override
  void initState() {
    super.initState();
    _checked = {for (final g in widget.groups) g.bookId};
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ConstrainedBox(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.6,
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
              child: Text(
                'Move from which book?',
                style: theme.textTheme.titleMedium,
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text(
                'Uncheck a book to leave its recipes where they are.',
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                children: [
                  for (final g in widget.groups)
                    CheckboxListTile(
                      title: Text(g.bookName),
                      subtitle: Text(
                        '${g.count} ${g.count == 1 ? 'recipe' : 'recipes'}',
                      ),
                      value: _checked.contains(g.bookId),
                      onChanged: (v) => setState(() {
                        if (v == true) {
                          _checked.add(g.bookId);
                        } else {
                          _checked.remove(g.bookId);
                        }
                      }),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Cancel'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: _checked.isEmpty
                        ? null
                        : () => Navigator.pop(
                              context,
                              widget.groups
                                  .where((g) => _checked.contains(g.bookId))
                                  .toList(),
                            ),
                    child: const Text('Continue'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
