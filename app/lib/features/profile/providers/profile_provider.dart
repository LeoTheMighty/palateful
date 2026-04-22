import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../services/profile_service.dart';

/// The signed-in user's own profile blob (`GET /v1/users/me`).
/// Invalidates on `ProfileUpdated` and `UsernameUpdated`.
final profileProvider =
    FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (event is ProfileUpdated || event is UsernameUpdated) {
      ref.invalidateSelf();
    }
  });
  ref.onDispose(sub.cancel);

  return getIt<ProfileService>().getMe();
});
