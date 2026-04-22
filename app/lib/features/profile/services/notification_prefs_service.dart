import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';

/// rp-2 — notification preferences mutations. Every mutation method
/// emits [NotificationPrefsUpdated] with the **full server response
/// body** on the success branch, so subscribers (`notificationPrefsProvider`,
/// future admin dashboards) patch in place without a second fetch.
///
/// The endpoint (`PUT /v1/users/me/notification-preferences`) already
/// returns the complete prefs blob — zero backend change required.
class NotificationPrefsService {
  NotificationPrefsService(this._api);

  final ApiClient _api;

  Future<Map<String, dynamic>> getNotificationPreferences() async {
    final response = await _api.getNotificationPreferences();
    return _asMap(response.data);
  }

  /// Update one or more scalar prefs (push enabled, quiet hours,
  /// timezone, partner_activity toggle, etc.). Emits on success.
  Future<Map<String, dynamic>> updateNotificationPreferences({
    bool? pushEnabled,
    String? emailDigest,
    String? quietHoursStart,
    String? quietHoursEnd,
    String? timezone,
    bool? partnerActivity,
    bool? autoApproveImports,
  }) async {
    final response = await _api.updateNotificationPreferences(
      pushEnabled: pushEnabled,
      emailDigest: emailDigest,
      quietHoursStart: quietHoursStart,
      quietHoursEnd: quietHoursEnd,
      timezone: timezone,
      partnerActivity: partnerActivity,
      autoApproveImports: autoApproveImports,
    );
    final prefs = _asMap(response.data);
    emitMutation(NotificationPrefsUpdated(prefs: prefs));
    return prefs;
  }

  /// Single-category toggle — `categories: {key: value}`. Used by the
  /// optimistic toggle path in `notification_preferences_screen.dart`.
  Future<Map<String, dynamic>> updateCategoryPref({
    required String category,
    required bool enabled,
  }) async {
    final response = await _api.updateNotificationPreferences(
      categories: {category: enabled},
    );
    final prefs = _asMap(response.data);
    emitMutation(NotificationPrefsUpdated(prefs: prefs));
    return prefs;
  }

  static Map<String, dynamic> _asMap(Object? data) {
    if (data is Map) return Map<String, dynamic>.from(data);
    return const <String, dynamic>{};
  }
}
