import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Session-scoped set of expanded `import_item.id` / `import_job.id`
/// strings. Backs the caret toggle on every ImportRow in the Imports
/// tab — a row is expanded iff its id lives in the set.
///
/// Cleared on app restart per AC8 of irrd-4. Used via
/// `ref.watch(importRowExpansionProvider.select((s) => s.contains(id)))`
/// so expanding one row does NOT rebuild every sibling row in the list.
class ExpandedRowsNotifier extends Notifier<Set<String>> {
  @override
  Set<String> build() => <String>{};

  void toggle(String id) {
    if (state.contains(id)) {
      final next = {...state}..remove(id);
      state = next;
    } else {
      state = {...state, id};
    }
  }

  void expand(String id) {
    if (state.contains(id)) return;
    state = {...state, id};
  }

  void collapse(String id) {
    if (!state.contains(id)) return;
    final next = {...state}..remove(id);
    state = next;
  }

  bool isExpanded(String id) => state.contains(id);
}

final importRowExpansionProvider =
    NotifierProvider<ExpandedRowsNotifier, Set<String>>(
  ExpandedRowsNotifier.new,
);
