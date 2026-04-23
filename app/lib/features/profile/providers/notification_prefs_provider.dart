import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../../../core/state/provider_ttl.dart';
import '../services/notification_prefs_service.dart';

/// Notification preferences blob for the signed-in user.
/// Invalidates on `NotificationPrefsUpdated`.
final notificationPrefsProvider =
    FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  // ffm-6: 10-minute TTL backstop.
  keepAliveWithTtl(
    ref,
    maxAge: const Duration(minutes: 10),
    revalidate: () async => ref.invalidateSelf(),
  );
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (event is NotificationPrefsUpdated) {
      ref.invalidateSelf();
    }
  });
  ref.onDispose(sub.cancel);

  return getIt<NotificationPrefsService>().getNotificationPreferences();
});
