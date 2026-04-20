import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';

/// Triple that backs both Activity Hub See-all footer labels. The third
/// field holds the read-and-older bucket from either endpoint — the
/// Notifications payload calls it `read_and_older`, the Imports payload
/// calls it `read_and_old_completed`, but the client only cares about
/// the sum for its "See all (N)" label so they share this shape.
class SeeAllCountTriple {
  final int archived;
  final int other;
  final int total;

  const SeeAllCountTriple({
    required this.archived,
    required this.other,
    required this.total,
  });

  static const zero = SeeAllCountTriple(archived: 0, other: 0, total: 0);
}

/// Shared logic for both see-all-count flavours. Starts in
/// `AsyncValue.loading()`, refreshes on creation, exposes `refresh()`
/// so callers (tab poll, post-archive optimistic) can re-fetch.
abstract class _SeeAllCountBase
    extends Notifier<AsyncValue<SeeAllCountTriple>> {
  /// Endpoint-specific fetch — returns the JSON map.
  Future<Map<String, dynamic>> fetch(ApiClient client);

  /// Endpoint-specific "other" key name.
  String get otherKey;

  @override
  AsyncValue<SeeAllCountTriple> build() {
    refresh();
    return const AsyncValue.loading();
  }

  Future<void> refresh() async {
    try {
      final data = await fetch(getIt<ApiClient>());
      final archived = (data['archived'] as num?)?.toInt() ?? 0;
      final other = (data[otherKey] as num?)?.toInt() ?? 0;
      final total = (data['total'] as num?)?.toInt() ?? (archived + other);
      state = AsyncValue.data(SeeAllCountTriple(
        archived: archived,
        other: other,
        total: total,
      ));
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

class NotificationsSeeAllCountNotifier extends _SeeAllCountBase {
  @override
  String get otherKey => 'read_and_older';

  @override
  Future<Map<String, dynamic>> fetch(ApiClient client) async {
    final r = await client.getActivitiesSeeAllCount();
    return Map<String, dynamic>.from(r.data as Map);
  }
}

class ImportsSeeAllCountNotifier extends _SeeAllCountBase {
  @override
  String get otherKey => 'read_and_old_completed';

  @override
  Future<Map<String, dynamic>> fetch(ApiClient client) async {
    final r = await client.getImportItemsSeeAllCount();
    return Map<String, dynamic>.from(r.data as Map);
  }
}

final notificationsSeeAllCountProvider = NotifierProvider<
    NotificationsSeeAllCountNotifier, AsyncValue<SeeAllCountTriple>>(
  NotificationsSeeAllCountNotifier.new,
);

final importsSeeAllCountProvider = NotifierProvider<ImportsSeeAllCountNotifier,
    AsyncValue<SeeAllCountTriple>>(
  ImportsSeeAllCountNotifier.new,
);
