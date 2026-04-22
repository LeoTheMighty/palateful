// rp-2 — ProfileService + NotificationPrefsService + providers
// reactivity regression.
//
// Covers:
//   1. Each service mutation emits the expected event on the bus.
//   2. The two providers (profileProvider, notificationPrefsProvider)
//      subscribe and invalidate on their respective event types.
//   3. Failed mutation throws and emits NOTHING.
//   4. Optimistic toggle path — service emits AFTER server 2xx; the
//      screen-level optimistic setState is orthogonal (tested in the
//      dedicated optimistic_toggle widget test).

import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/state/mutation_bus.dart';
import 'package:palateful/features/profile/providers/notification_prefs_provider.dart';
import 'package:palateful/features/profile/providers/profile_provider.dart';
import 'package:palateful/features/profile/services/notification_prefs_service.dart';
import 'package:palateful/features/profile/services/profile_service.dart';

Response<dynamic> _ok(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _FakeApi extends ApiClient {
  Map<String, dynamic> me = {'id': 'u1', 'name': 'Leo', 'email': 'leo@example.com'};
  Map<String, dynamic> prefs = {
    'push_enabled': true,
    'categories': {'meals': true, 'timers': true},
    'quiet_hours_start': '22:00',
    'quiet_hours_end': '08:00',
  };
  bool throwNext = false;
  int getMeCalls = 0;
  int getPrefsCalls = 0;

  @override
  Future<Response> getMe() async {
    getMeCalls++;
    return _ok(me);
  }

  @override
  Future<Response> getNotificationPreferences() async {
    getPrefsCalls++;
    return _ok(prefs);
  }

  @override
  Future<Response> updateProfile({String? name}) async {
    _maybeThrow();
    me = {...me, if (name != null) 'name': name};
    return _ok(me);
  }

  @override
  Future<Response> setUsername(String username) async {
    _maybeThrow();
    return _ok({'username': username});
  }

  @override
  Future<Response> submitFeedback({
    required String body,
    String? category,
    Map<String, dynamic>? context,
  }) async {
    _maybeThrow();
    return _ok({'success': true});
  }

  @override
  Future<Response> exportRecipes() async {
    _maybeThrow();
    return _ok({'recipes': <Map<String, dynamic>>[]});
  }

  @override
  Future<Response> updateNotificationPreferences({
    bool? pushEnabled,
    String? emailDigest,
    String? quietHoursStart,
    String? quietHoursEnd,
    String? timezone,
    bool? partnerActivity,
    bool? autoApproveImports,
    Map<String, bool>? categories,
  }) async {
    _maybeThrow();
    final next = Map<String, dynamic>.from(prefs);
    if (pushEnabled != null) next['push_enabled'] = pushEnabled;
    if (quietHoursStart != null) next['quiet_hours_start'] = quietHoursStart;
    if (quietHoursEnd != null) next['quiet_hours_end'] = quietHoursEnd;
    if (timezone != null) next['timezone'] = timezone;
    if (partnerActivity != null) next['partner_activity'] = partnerActivity;
    if (categories != null) {
      final cur = Map<String, bool>.from(
          (next['categories'] as Map).cast<String, bool>());
      cur.addAll(categories);
      next['categories'] = cur;
    }
    prefs = next;
    return _ok(next);
  }

  void _maybeThrow() {
    if (throwNext) {
      throwNext = false;
      throw DioException(
        requestOptions: RequestOptions(path: ''),
        response: Response(
          requestOptions: RequestOptions(path: ''),
          statusCode: 500,
        ),
        type: DioExceptionType.badResponse,
      );
    }
  }
}

Future<List<MutationEvent>> _captureAllEvents(
  Future<void> Function() action,
) async {
  final events = <MutationEvent>[];
  final sub = mutationBusStream().listen(events.add);
  await action();
  await Future<void>.delayed(Duration.zero);
  await sub.cancel();
  return events;
}

void _register(_FakeApi api) {
  final gi = GetIt.instance;
  for (final t in [
    ApiClient,
    ProfileService,
    NotificationPrefsService,
  ]) {
    switch (t) {
      case ApiClient:
        if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
      case ProfileService:
        if (gi.isRegistered<ProfileService>()) {
          gi.unregister<ProfileService>();
        }
      case NotificationPrefsService:
        if (gi.isRegistered<NotificationPrefsService>()) {
          gi.unregister<NotificationPrefsService>();
        }
    }
  }
  gi.registerSingleton<ApiClient>(api);
  gi.registerLazySingleton<ProfileService>(
    () => ProfileService(gi<ApiClient>()),
  );
  gi.registerLazySingleton<NotificationPrefsService>(
    () => NotificationPrefsService(gi<ApiClient>()),
  );
}

void _unregister() {
  final gi = GetIt.instance;
  if (gi.isRegistered<NotificationPrefsService>()) {
    gi.unregister<NotificationPrefsService>();
  }
  if (gi.isRegistered<ProfileService>()) {
    gi.unregister<ProfileService>();
  }
  if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
}

void main() {
  setUpAll(() async {
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  group('ProfileService emits', () {
    late _FakeApi api;
    late ProfileService service;

    setUp(() {
      api = _FakeApi();
      _register(api);
      service = GetIt.instance<ProfileService>();
    });

    tearDown(_unregister);

    test('updateProfile emits ProfileUpdated with server payload', () async {
      final events = await _captureAllEvents(
          () async => service.updateProfile(name: 'Leo 2.0'));
      final profile = events.whereType<ProfileUpdated>().single;
      expect(profile.profile['name'], 'Leo 2.0');
    });

    test('setUsername emits UsernameUpdated', () async {
      final events = await _captureAllEvents(
          () async => service.setUsername('leo'));
      final uu = events.whereType<UsernameUpdated>().single;
      expect(uu.username, 'leo');
    });

    test('submitFeedback emits ProfileUpdated (minimal payload)', () async {
      final events = await _captureAllEvents(
          () async => service.submitFeedback(body: 'Nice app!'));
      expect(events.whereType<ProfileUpdated>(), hasLength(1));
    });

    test('exportRecipes does NOT emit (read-only)', () async {
      final events = await _captureAllEvents(
          () async => service.exportRecipes());
      expect(events, isEmpty);
    });

    test('failed updateProfile throws and emits NOTHING', () async {
      api.throwNext = true;
      final events = await _captureAllEvents(() async {
        try {
          await service.updateProfile(name: 'x');
        } on DioException {
          // swallowed
        }
      });
      expect(events, isEmpty);
    });
  });

  group('NotificationPrefsService emits', () {
    late _FakeApi api;
    late NotificationPrefsService service;

    setUp(() {
      api = _FakeApi();
      _register(api);
      service = GetIt.instance<NotificationPrefsService>();
    });

    tearDown(_unregister);

    test('updateCategoryPref emits with full prefs blob', () async {
      final events = await _captureAllEvents(
          () async => service.updateCategoryPref(
              category: 'meals', enabled: false));
      final ev = events.whereType<NotificationPrefsUpdated>().single;
      // Server returns the full prefs blob — subscribers patch in
      // place without another fetch.
      expect(ev.prefs['push_enabled'], true);
      expect(ev.prefs['categories']['meals'], false);
    });

    test('updateNotificationPreferences scalar emits full blob', () async {
      final events = await _captureAllEvents(() async {
        await service.updateNotificationPreferences(pushEnabled: false);
      });
      final ev = events.whereType<NotificationPrefsUpdated>().single;
      expect(ev.prefs['push_enabled'], false);
    });

    test('failed category toggle throws and emits NOTHING', () async {
      api.throwNext = true;
      final events = await _captureAllEvents(() async {
        try {
          await service.updateCategoryPref(
              category: 'timers', enabled: false);
        } on DioException {
          // swallowed
        }
      });
      expect(events, isEmpty);
    });
  });

  group('Providers invalidate on bus events', () {
    late _FakeApi api;
    late ProviderContainer container;

    setUp(() {
      api = _FakeApi();
      _register(api);
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
      _unregister();
    });

    test('profileProvider invalidates on ProfileUpdated', () async {
      await container.read(profileProvider.future);
      final baseline = api.getMeCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const ProfileUpdated(
        profile: {'name': 'Leo 2.0'},
      ));
      await Future<void>.delayed(Duration.zero);
      await container.read(profileProvider.future);
      expect(api.getMeCalls, greaterThan(baseline));
    });

    test('profileProvider invalidates on UsernameUpdated', () async {
      await container.read(profileProvider.future);
      final baseline = api.getMeCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const UsernameUpdated(username: 'leo'));
      await Future<void>.delayed(Duration.zero);
      await container.read(profileProvider.future);
      expect(api.getMeCalls, greaterThan(baseline));
    });

    test('profileProvider does NOT invalidate on NotificationPrefsUpdated',
        () async {
      await container.read(profileProvider.future);
      final baseline = api.getMeCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const NotificationPrefsUpdated(
        prefs: <String, dynamic>{'push_enabled': true},
      ));
      await Future<void>.delayed(Duration.zero);
      expect(api.getMeCalls, baseline);
    });

    test('notificationPrefsProvider invalidates on NotificationPrefsUpdated',
        () async {
      await container.read(notificationPrefsProvider.future);
      final baseline = api.getPrefsCalls;
      await Future<void>.delayed(Duration.zero);
      emitMutation(const NotificationPrefsUpdated(
        prefs: <String, dynamic>{'push_enabled': false},
      ));
      await Future<void>.delayed(Duration.zero);
      await container.read(notificationPrefsProvider.future);
      expect(api.getPrefsCalls, greaterThan(baseline));
    });
  });
}
