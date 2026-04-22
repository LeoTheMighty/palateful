import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../services/cooking_log_service.dart';

/// rp-3 — family-keyed cooking history for one recipe. Invalidates on
/// `CookingLogCreated` filtered by `event.recipeId`.
final recipeCookingHistoryProvider = FutureProvider.autoDispose
    .family<List<Map<String, dynamic>>, String>((ref, recipeId) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (event is CookingLogCreated && event.recipeId == recipeId) {
      ref.invalidateSelf();
    }
  });
  ref.onDispose(sub.cancel);

  return getIt<CookingLogService>().listForRecipe(recipeId);
});
