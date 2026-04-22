import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../services/notification_prefs_service.dart';

/// Notification preferences blob for the signed-in user.
/// Invalidates on `NotificationPrefsUpdated`.
final notificationPrefsProvider =
    FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  ref.keepAlive();
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (event is NotificationPrefsUpdated) {
      ref.invalidateSelf();
    }
  });
  ref.onDispose(sub.cancel);

  return getIt<NotificationPrefsService>().getNotificationPreferences();
});
