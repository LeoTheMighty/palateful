import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../models/import_item_telemetry.dart';

/// Lazy, per-session telemetry fetch keyed on `import_item.id`.
///
/// irrd-4 — invoked the first time a row is caret-expanded. Subsequent
/// expansions within the same session read from cache. The parent
/// widget explicitly invalidates this provider via `ref.invalidate`
/// when the list payload's `(status, last_successful_stage)` tuple
/// changes, forcing a refetch so the expansion reflects reality.
final importItemTelemetryProvider = FutureProvider.autoDispose
    .family<ImportItemTelemetry, String>((ref, itemId) async {
  final apiClient = getIt<ApiClient>();
  final response = await apiClient.getImportItemTelemetry(itemId);
  final data = response.data as Map<String, dynamic>;
  return ImportItemTelemetry.fromJson(data);
});
