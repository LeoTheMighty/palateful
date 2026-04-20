import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

/// View model for a row in the Notifications See-all list. Shape is
/// intentionally lean — the footer widget renders a single muted
/// `ListTile`-style row and doesn't need the full activity envelope.
class SeeAllActivityView {
  final String id;
  final String type;
  final String title;
  final String? subtitle;
  final String? actionUrl;
  final DateTime? createdAt;
  final DateTime? archivedAt;

  const SeeAllActivityView({
    required this.id,
    required this.type,
    required this.title,
    required this.subtitle,
    required this.actionUrl,
    required this.createdAt,
    required this.archivedAt,
  });

  factory SeeAllActivityView.fromJson(Map<String, dynamic> json) =>
      SeeAllActivityView(
        id: json['id'].toString(),
        type: (json['type'] ?? '').toString(),
        title: (json['title'] ?? '').toString(),
        subtitle: json['subtitle'] as String?,
        actionUrl: json['action_url'] as String?,
        createdAt: json['created_at'] != null
            ? DateTime.tryParse(json['created_at'].toString())
            : null,
        archivedAt: json['archived_at'] != null
            ? DateTime.tryParse(json['archived_at'].toString())
            : null,
      );
}

/// Paginated list state for the Notifications See-all footer.
///
/// `items`          — accumulated rows across all loaded pages.
/// `nextCursor`     — opaque cursor for the next page (null = end-of-list
///                    OR nothing loaded yet).
/// `hasLoadedFirstPage` — true once the first fetch (success or error)
///                        has returned. Used to decide "empty → end-of-
///                        list row" vs. "still loading initial".
/// `isLoading`      — a fetch is in flight.
/// `hasError`       — last fetch failed; widget renders the retry row.
class NotificationsSeeAllState {
  final List<SeeAllActivityView> items;
  final String? nextCursor;
  final bool hasLoadedFirstPage;
  final bool isLoading;
  final bool hasError;

  const NotificationsSeeAllState({
    required this.items,
    required this.nextCursor,
    required this.hasLoadedFirstPage,
    required this.isLoading,
    required this.hasError,
  });

  static const empty = NotificationsSeeAllState(
    items: [],
    nextCursor: null,
    hasLoadedFirstPage: false,
    isLoading: false,
    hasError: false,
  );

  bool get isEnded => hasLoadedFirstPage && nextCursor == null && !hasError;

  NotificationsSeeAllState copyWith({
    List<SeeAllActivityView>? items,
    String? nextCursor,
    bool? nextCursorSet,
    bool? hasLoadedFirstPage,
    bool? isLoading,
    bool? hasError,
  }) {
    return NotificationsSeeAllState(
      items: items ?? this.items,
      // A nullable `nextCursor` can't use the normal copyWith idiom —
      // we need an explicit "set to null" signal separate from "leave
      // unchanged". `nextCursorSet=true` means "adopt the passed value,
      // even if it's null".
      nextCursor: (nextCursorSet ?? false) ? nextCursor : this.nextCursor,
      hasLoadedFirstPage: hasLoadedFirstPage ?? this.hasLoadedFirstPage,
      isLoading: isLoading ?? this.isLoading,
      hasError: hasError ?? this.hasError,
    );
  }
}

class NotificationsSeeAllNotifier extends Notifier<NotificationsSeeAllState> {
  @override
  NotificationsSeeAllState build() => NotificationsSeeAllState.empty;

  /// Load the next page. No-op while a fetch is in flight OR when the
  /// list has already ended.
  Future<void> loadNextPage() async {
    if (state.isLoading) return;
    if (state.hasLoadedFirstPage && state.nextCursor == null && !state.hasError) {
      return;
    }
    state = state.copyWith(isLoading: true, hasError: false);

    try {
      final response = await getIt<ApiClient>().listActivitiesSeeAll(
        cursor: state.nextCursor,
      );
      final rawItems = List<dynamic>.from(response.data['items'] ?? []);
      final rawNext = response.data['next_cursor'] as String?;
      final newRows = rawItems
          .whereType<Map>()
          .map((m) => SeeAllActivityView.fromJson(
                Map<String, dynamic>.from(m),
              ))
          .toList(growable: false);
      state = state.copyWith(
        items: [...state.items, ...newRows],
        nextCursor: rawNext,
        nextCursorSet: true,
        hasLoadedFirstPage: true,
        isLoading: false,
        hasError: false,
      );
    } catch (_) {
      // Preserve items already loaded; the retry row on the widget
      // re-fires the same cursor.
      state = state.copyWith(
        isLoading: false,
        hasLoadedFirstPage: true,
        hasError: true,
      );
    }
  }

  /// Drop a row by id (optimistic unarchive). The row can be re-inserted
  /// via `restoreRow()` if the API call fails.
  void removeRow(String id) {
    state = state.copyWith(
      items: state.items.where((r) => r.id != id).toList(growable: false),
    );
  }

  /// Re-insert a previously-removed row at the top (undo path). Kept
  /// minimal — no position reconstruction; pull-to-refresh is the
  /// authoritative re-sync.
  void restoreRow(SeeAllActivityView row) {
    state = state.copyWith(items: [row, ...state.items]);
  }

  /// Pull-to-refresh: drop accumulated pages and re-fetch page 1.
  Future<void> refreshFromTop() async {
    state = NotificationsSeeAllState.empty;
    await loadNextPage();
  }
}

/// Session-wide expansion bool for the Notifications See-all footer.
/// Survives tab switches (the notifier outlives the widget). The
/// expansion-bool-in-provider pattern is required by afh-3 AC10.a.
class NotificationsSeeAllExpanded extends Notifier<bool> {
  @override
  bool build() => false;

  void setExpanded(bool value) {
    if (state != value) state = value;
  }
}

final notificationsSeeAllProvider = NotifierProvider<
    NotificationsSeeAllNotifier, NotificationsSeeAllState>(
  NotificationsSeeAllNotifier.new,
);

final notificationsSeeAllExpandedProvider =
    NotifierProvider<NotificationsSeeAllExpanded, bool>(
  NotificationsSeeAllExpanded.new,
);
