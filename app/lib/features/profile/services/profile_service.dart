import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';

/// rp-2 — mutations for the signed-in user's own profile.
///
/// Before rp-2 these calls lived inline inside `_ProfileScreenState`
/// closures. Now the service owns the API call and emits on the
/// [mutationBusProvider] on the success branch (Locked Decision #1).
class ProfileService {
  ProfileService(this._api);

  final ApiClient _api;

  Future<Map<String, dynamic>> getMe() async {
    final response = await _api.getMe();
    return _asMap(response.data);
  }

  Future<Map<String, dynamic>> updateProfile({String? name}) async {
    final response = await _api.updateProfile(name: name);
    final profile = _asMap(response.data);
    emitMutation(ProfileUpdated(profile: profile));
    return profile;
  }

  Future<void> setUsername(String username) async {
    await _api.setUsername(username);
    emitMutation(UsernameUpdated(username: username));
  }

  Future<bool> checkUsername(String username) async {
    final response = await _api.checkUsername(username);
    final data = _asMap(response.data);
    return data['available'] as bool? ?? false;
  }

  /// Feedback submission is a mutation in the "user's last-known state"
  /// sense even though it doesn't change their profile — we still emit
  /// a [ProfileUpdated] event with a minimal shape so any admin-inbox
  /// surface that subscribes can reconcile.
  Future<void> submitFeedback({
    required String body,
    String? category,
    Map<String, dynamic>? context,
  }) async {
    await _api.submitFeedback(body: body, category: category, context: context);
    emitMutation(const ProfileUpdated(
      profile: <String, dynamic>{'feedback_submitted': true},
    ));
  }

  Future<Map<String, dynamic>> exportRecipes() async {
    final response = await _api.exportRecipes();
    return _asMap(response.data);
  }

  static Map<String, dynamic> _asMap(Object? data) {
    if (data is Map) return Map<String, dynamic>.from(data);
    return const <String, dynamic>{};
  }
}
