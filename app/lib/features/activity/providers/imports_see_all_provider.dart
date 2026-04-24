import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';

/// View model for a See-all row in the Imports tab.
///
/// Backed directly by ``GET /v1/import-items/see-all`` — a single
/// cursor-paginated endpoint whose predicate matches the See-all count
/// exactly (archived items OR completed/skipped items older than
/// 30 days). The previous two-hop implementation filtered by parent
/// `ImportJob.archived_at`, which silently hid rows where the item was
/// archived but the job was not, and hid all old-terminal rows living
/// in active jobs — so the count was > 0 but the footer expanded to
/// empty.
class SeeAllImportItemView {
  final String id;
  final String title;
  final String? sourceType;
  final String? statusLabel;
  final DateTime? archivedAt;
  final DateTime? createdAt;

  const SeeAllImportItemView({
    required this.id,
    required this.title,
    required this.sourceType,
    required this.statusLabel,
    required this.archivedAt,
    required this.createdAt,
  });
}

class ImportsSeeAllState {
  final List<SeeAllImportItemView> items;

  /// Opaque cursor for the NEXT page of items. `null` after the first
  /// page means "no more items to scan".
  final String? nextCursor;

  final bool hasLoadedFirstPage;
  final bool isLoading;
  final bool hasError;

  const ImportsSeeAllState({
    required this.items,
    required this.nextCursor,
    required this.hasLoadedFirstPage,
    required this.isLoading,
    required this.hasError,
  });

  static const empty = ImportsSeeAllState(
    items: [],
    nextCursor: null,
    hasLoadedFirstPage: false,
    isLoading: false,
    hasError: false,
  );

  bool get isEnded =>
      hasLoadedFirstPage && nextCursor == null && !hasError;

  ImportsSeeAllState copyWith({
    List<SeeAllImportItemView>? items,
    String? nextCursor,
    bool? nextCursorSet,
    bool? hasLoadedFirstPage,
    bool? isLoading,
    bool? hasError,
  }) =>
      ImportsSeeAllState(
        items: items ?? this.items,
        nextCursor:
            (nextCursorSet ?? false) ? nextCursor : this.nextCursor,
        hasLoadedFirstPage: hasLoadedFirstPage ?? this.hasLoadedFirstPage,
        isLoading: isLoading ?? this.isLoading,
        hasError: hasError ?? this.hasError,
      );
}

class ImportsSeeAllNotifier extends Notifier<ImportsSeeAllState> {
  @override
  ImportsSeeAllState build() {
    // rf-5: refetch from top whenever an import-item event fires on
    // the MutationBus. Keeps the See-all footer fresh without waiting
    // on the 30s poll. Subscription torn down on provider dispose.
    final sub = ref.read(mutationBusProvider).listen((event) {
      if (event is ImportItemDismissed ||
          event is ImportItemRetried ||
          event is ImportJobDismissed) {
        // Only refetch if the user has already opened See-all.
        // `hasLoadedFirstPage=false` means the section is closed —
        // the next open triggers its own fetch anyway.
        if (state.hasLoadedFirstPage) refreshFromTop();
      }
    });
    ref.onDispose(sub.cancel);
    return ImportsSeeAllState.empty;
  }

  Future<void> loadNextPage() async {
    if (state.isLoading) return;
    if (state.hasLoadedFirstPage &&
        state.nextCursor == null &&
        !state.hasError) {
      return;
    }

    state = state.copyWith(isLoading: true, hasError: false);

    try {
      final client = getIt<ApiClient>();
      final response = await client.listSeeAllImportItems(
        cursor: state.nextCursor,
        limit: 50,
      );
      final rawItems = List<dynamic>.from(response.data['items'] ?? []);
      final nextCursor = response.data['next_cursor'] as String?;
      final newRows = [
        for (final item in rawItems) _fromRaw(item),
      ];

      state = state.copyWith(
        items: [...state.items, ...newRows],
        nextCursor: nextCursor,
        nextCursorSet: true,
        hasLoadedFirstPage: true,
        isLoading: false,
        hasError: false,
      );
    } catch (_) {
      state = state.copyWith(
        isLoading: false,
        hasLoadedFirstPage: true,
        hasError: true,
      );
    }
  }

  void removeRow(String id) {
    state = state.copyWith(
      items: state.items.where((r) => r.id != id).toList(growable: false),
    );
  }

  void restoreRow(SeeAllImportItemView row) {
    state = state.copyWith(items: [row, ...state.items]);
  }

  Future<void> refreshFromTop() async {
    state = ImportsSeeAllState.empty;
    await loadNextPage();
  }

  static SeeAllImportItemView _fromRaw(dynamic item) {
    return SeeAllImportItemView(
      id: item['id'].toString(),
      title: (item['recipe_name']?.toString().isNotEmpty ?? false)
          ? item['recipe_name'].toString()
          : 'Untitled',
      sourceType: item['source_type'] as String?,
      statusLabel: item['status']?.toString(),
      archivedAt: item['archived_at'] != null
          ? DateTime.tryParse(item['archived_at'].toString())
          : null,
      createdAt: item['created_at'] != null
          ? DateTime.tryParse(item['created_at'].toString())
          : null,
    );
  }
}

class ImportsSeeAllExpanded extends Notifier<bool> {
  @override
  bool build() => false;

  void setExpanded(bool value) {
    if (state != value) state = value;
  }
}

final importsSeeAllProvider =
    NotifierProvider<ImportsSeeAllNotifier, ImportsSeeAllState>(
  ImportsSeeAllNotifier.new,
);

final importsSeeAllExpandedProvider =
    NotifierProvider<ImportsSeeAllExpanded, bool>(
  ImportsSeeAllExpanded.new,
);
