import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';

/// View model for a See-all row in the Imports tab.
///
/// The Imports See-all aggregates items from multiple jobs. We page at
/// the JOB level (`listImportJobs(archivedOnly=true, cursor=...)`) and
/// fetch items per-job, because the backend only offers per-job item
/// listing. Each "page" of this provider is `limit=50` archived jobs
/// plus all their items, flattened into this view-model list.
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

  /// Opaque cursor for the NEXT page of archived jobs. `null` means
  /// "no more jobs to scan".
  final String? nextJobCursor;

  final bool hasLoadedFirstPage;
  final bool isLoading;
  final bool hasError;

  const ImportsSeeAllState({
    required this.items,
    required this.nextJobCursor,
    required this.hasLoadedFirstPage,
    required this.isLoading,
    required this.hasError,
  });

  static const empty = ImportsSeeAllState(
    items: [],
    nextJobCursor: null,
    hasLoadedFirstPage: false,
    isLoading: false,
    hasError: false,
  );

  bool get isEnded =>
      hasLoadedFirstPage && nextJobCursor == null && !hasError;

  ImportsSeeAllState copyWith({
    List<SeeAllImportItemView>? items,
    String? nextJobCursor,
    bool? nextJobCursorSet,
    bool? hasLoadedFirstPage,
    bool? isLoading,
    bool? hasError,
  }) =>
      ImportsSeeAllState(
        items: items ?? this.items,
        nextJobCursor:
            (nextJobCursorSet ?? false) ? nextJobCursor : this.nextJobCursor,
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
        state.nextJobCursor == null &&
        !state.hasError) {
      return;
    }

    state = state.copyWith(isLoading: true, hasError: false);

    try {
      final client = getIt<ApiClient>();
      final jobsResponse = await client.listImportJobs(
        archivedOnly: true,
        includeArchived: true,
        cursor: state.nextJobCursor,
        limit: 50,
      );
      final rawJobs =
          List<dynamic>.from(jobsResponse.data['jobs'] ?? []);
      final nextCursor = jobsResponse.data['next_cursor'] as String?;

      // ffm-2: one batched fetch for all archived jobs on this page
      // with `include_archived=true` — that's the whole point of
      // See-all. Backend caps at 50 job_ids; `listImportJobs` limit
      // above is 50, so one call per page is safe. A chunk loop is
      // kept for defensive sanity.
      final jobsById = <String, dynamic>{
        for (final j in rawJobs) j['id'].toString(): j,
      };
      final newRows = <SeeAllImportItemView>[];
      if (jobsById.isNotEmpty) {
        final jobIds = jobsById.keys.toList();
        for (var start = 0; start < jobIds.length; start += 50) {
          final chunk =
              jobIds.sublist(start, (start + 50).clamp(0, jobIds.length));
          final batchResponse = await client.listImportItemsBatch(
            chunk,
            includeArchived: true,
          );
          final rawItems =
              List<dynamic>.from(batchResponse.data['items'] ?? []);
          for (final item in rawItems) {
            final jobId = item['job_id']?.toString();
            if (jobId == null) continue;
            final parentJob = jobsById[jobId];
            if (parentJob == null) continue;
            newRows.add(_fromRaw(item, parentJob));
          }
        }
      }

      state = state.copyWith(
        items: [...state.items, ...newRows],
        nextJobCursor: nextCursor,
        nextJobCursorSet: true,
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

  static SeeAllImportItemView _fromRaw(dynamic item, dynamic parentJob) {
    final parent = parentJob is Map ? parentJob : const {};
    return SeeAllImportItemView(
      id: item['id'].toString(),
      title: (item['recipe_name']?.toString().isNotEmpty ?? false)
          ? item['recipe_name'].toString()
          : 'Untitled',
      sourceType: (item['source_type'] ?? parent['source_type']) as String?,
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
