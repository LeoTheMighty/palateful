import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Session-scoped set of locally-archived IDs so a just-swiped row stays
/// hidden even if the next 30s poll is mid-flight and returns it. The
/// set clears on app restart — the server is the source of truth across
/// sessions.
///
/// Two concrete instances exist ([activityArchiveProvider] for
/// `user_activity.id`, [importItemArchiveProvider] for `import_item.id`)
/// so the two surfaces can't cross-contaminate.
class ArchivedIdSet extends Notifier<Set<String>> {
  @override
  Set<String> build() => <String>{};

  void add(String id) {
    state = {...state, id};
  }

  void remove(String id) {
    if (!state.contains(id)) return;
    final next = {...state}..remove(id);
    state = next;
  }

  bool contains(String id) => state.contains(id);
}

/// Locally-archived `user_activity` IDs.
final activityArchiveProvider =
    NotifierProvider<ArchivedIdSet, Set<String>>(ArchivedIdSet.new);

/// Locally-archived `import_item` IDs. Used by the Imports tab (ahr-4)
/// and the See-all footer (ahr-5). Lives here so both tabs read a
/// shared source of truth.
final importItemArchiveProvider =
    NotifierProvider<ArchivedIdSet, Set<String>>(ArchivedIdSet.new);
