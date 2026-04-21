import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';

/// pfc-3: family-keyed cache for the recipe-detail payload.
///
/// Reopening the same recipe within ~5 minutes is zero-network —
/// `ref.keepAlive()` keeps the cache alive past the last observer
/// unmounting (so navigating to a linked meal and back is instant).
/// A 5-minute TTL drops the cache so users don't see stale data after
/// a long gap.
///
/// Mutations MUST invalidate this provider to force a refetch on the
/// next read — otherwise the user sees stale data after edits made
/// elsewhere (archive, rollback, rename, etc.). Use
/// [invalidateRecipe] below from any context (Ref, WidgetRef, or
/// BuildContext).
const recipeCacheTtl = Duration(minutes: 5);

final recipeProvider = FutureProvider.family
    .autoDispose<Map<String, dynamic>, String>((ref, recipeId) async {
  final link = ref.keepAlive();
  final timer = Timer(recipeCacheTtl, link.close);
  ref.onDispose(timer.cancel);

  final response = await getIt<ApiClient>().getRecipe(
    recipeId,
    debug: getIt<AuthService>().isAdmin,
  );
  return Map<String, dynamic>.from(response.data as Map);
});

/// Invalidate the recipe cache for [recipeId]. Accepts a [Ref],
/// [WidgetRef], or [BuildContext] so callers from any widget flavor
/// (Consumer, non-Consumer StatefulWidget) can drop the cache after
/// a mutation.
void invalidateRecipe(dynamic refOrContext, String recipeId) {
  if (refOrContext is BuildContext) {
    ProviderScope.containerOf(refOrContext)
        .invalidate(recipeProvider(recipeId));
    return;
  }
  refOrContext.invalidate(recipeProvider(recipeId));
}
