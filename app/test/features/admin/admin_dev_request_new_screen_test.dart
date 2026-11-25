import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/di/injection.dart';
import 'package:palateful/core/router/app_router.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/core/services/auth_service.dart';
import 'package:palateful/features/admin/admin_dashboard_screen.dart';
import 'package:palateful/features/admin/admin_dev_request_new_screen.dart';

/// E-7 (admin-request-intake, PRD FR-14): an admin can file a request from
/// the panel.
///
/// Threshold: 1 create call per submit; id8 shown; 403/422/429 each
/// rendered as their message; 0 entries rendered for a non-admin.
///
/// The screen runs against the **real** `ApiClient` (its Dio and
/// interceptors), with only the HTTP adapter replaced. So these cases
/// cover what is sent on the wire (method, path, JSON keys) and how Dio
/// surfaces a 4xx, not just what a fake chose to return.
///
/// Every response body below was captured from the real endpoint,
/// `POST /v1/admin/dev-requests` on `feat/admin-request-slice` at
/// `cbe332d3`, through `services/api/tests/devreq_harness.py` (its own
/// throwaway database). Only the long `input` echoes and `created_at`
/// are rebuilt rather than pasted.

const _createPath = '/v1/admin/dev-requests';

final _created = {
  'id': '048298e4-2911-4828-8c97-fc4e35d63fbc',
  'id8': '048298e4',
  'status': 'submitted',
  'content_sha256':
      '763d086d8280510285f830518214fc5f589288b83579e07e2f315f8cc6ee16bd',
  // Captured as a literal; computed here so fixture_date_guard_test has
  // no dated fixture to object to. The screen never reads it.
  'created_at': DateTime.now().toUtc().toIso8601String(),
};

final _forbidden = {
  'error_code': 44,
  'error_message': 'Admin access required',
  'data': <String, dynamic>{},
};

final _rateLimited = {
  'error_code': 203,
  'error_message': 'Too many requests filed (max 5/hour). Retry in 3600s.',
  'data': {'error': 'rate_limited', 'retry_after_s': 3600},
};

Map<String, dynamic> _invalid(List<(String, String, String)> errors) => {
      'detail': [
        for (final (field, msg, input) in errors)
          {
            'type': 'value_error',
            'loc': ['body', field],
            'msg': msg,
            'input': input,
            'ctx': {'error': <String, dynamic>{}},
          },
      ],
    };

/// Three fields refused at once — the captured `422_two_fields` case.
final _invalidAll = _invalid([
  ('title', 'Value error, title is blank after normalization', ''),
  ('body', 'Value error, body is blank after normalization', ' '),
  (
    'done_when',
    'Value error, done_when is 1001 characters after normalization; '
        'the limit is 1000',
    'y' * 1001,
  ),
]);

/// A title of zero-width spaces: non-blank to Dart's `trim()`, blank to
/// the server's normalization. The captured `422_zwsp_title` case.
final _invalidZwspTitle = _invalid([
  ('title', 'Value error, title is blank after normalization', '​​'),
]);

final _invalidLongBody = _invalid([
  (
    'body',
    'Value error, body is 4001 characters after normalization; '
        'the limit is 4000',
    'x' * 4001,
  ),
]);

class _Sent {
  _Sent(this.method, this.path, this.json);
  final String method;
  final String path;
  final Object? json;
}

class _Reply {
  _Reply(this.status, this.body, {this.gate});
  final int status;
  final Object body;

  /// When set, the reply waits for it: holds a create in flight.
  final Future<void>? gate;
}

/// Answers `GET /v1/admin/stats` with `{}` and each create with the next
/// scripted reply; records every request as it went over the wire.
class _WireAdapter implements HttpClientAdapter {
  _WireAdapter([List<_Reply>? replies]) : replies = replies ?? [];

  final List<_Reply> replies;
  final List<_Sent> sent = [];

  List<_Sent> get creates =>
      sent.where((s) => s.method == 'POST' && s.path == _createPath).toList();

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    Object? json;
    if (requestStream != null) {
      final bytes = await requestStream.expand((c) => c).toList();
      if (bytes.isNotEmpty) json = jsonDecode(utf8.decode(bytes));
    }
    sent.add(_Sent(options.method, options.path, json));

    _Reply reply;
    if (options.method == 'POST' && options.path == _createPath) {
      reply = replies.removeAt(0);
    } else if (options.method == 'GET' && options.path == '/v1/admin/stats') {
      reply = _Reply(200, <String, dynamic>{});
    } else {
      reply = _Reply(404, {'detail': 'Not Found'});
    }
    if (reply.gate != null) await reply.gate;
    return ResponseBody.fromString(
      jsonEncode(reply.body),
      reply.status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }
}

class _AuthStub extends AuthService {
  _AuthStub({required this.admin});
  final bool admin;

  @override
  bool get isAuthenticated => true;

  @override
  bool get hasCompletedOnboarding => true;

  @override
  bool get isAdmin => admin;
}

ApiClient _clientOn(_WireAdapter adapter) {
  final client = ApiClient();
  client.dio.httpClientAdapter = adapter;
  return client;
}

Finder get _submit => find.byKey(const Key('dev_request_submit_button'));
Finder get _titleField => find.byKey(const Key('dev_request_title_field'));
Finder get _bodyField => find.byKey(const Key('dev_request_body_field'));
Finder get _doneWhenField =>
    find.byKey(const Key('dev_request_done_when_field'));

/// Scrolls Submit into view first: a long body pushes it off the 800×600
/// test surface, and a tap that misses sends nothing.
Future<void> _tapSubmit(WidgetTester tester) async {
  await tester.ensureVisible(_submit);
  await tester.tap(_submit);
}

bool _submitEnabled(WidgetTester tester) {
  // FilledButton.icon builds a private subclass, so match by key and read
  // the ButtonStyleButton it is.
  final button = tester.widget<ButtonStyleButton>(_submit);
  return button.onPressed != null;
}

String? _errorTextOf(WidgetTester tester, Finder field) =>
    tester.widget<TextField>(field).decoration?.errorText;

Future<void> _fill(
  WidgetTester tester, {
  String title = 'Pantry search misses plurals',
  String body = 'Searching "tomatoes" does not find "tomato".',
  String? doneWhen,
}) async {
  await tester.enterText(_titleField, title);
  await tester.enterText(_bodyField, body);
  if (doneWhen != null) await tester.enterText(_doneWhenField, doneWhen);
  await tester.pump();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('the form', () {
    late _WireAdapter adapter;

    // Awaited: reset is async, and an unawaited one finishes later and
    // clears whatever the test registered in between.
    setUp(() async => GetIt.I.reset());
    tearDown(() async => GetIt.I.reset());

    Future<void> pumpForm(WidgetTester tester, List<_Reply> replies) async {
      adapter = _WireAdapter(replies);
      GetIt.I.registerSingleton<ApiClient>(_clientOn(adapter));
      await tester.pumpWidget(
        const MaterialApp(home: AdminDevRequestNewScreen()),
      );
    }

    testWidgets('one submit sends one create, as typed, and shows the id8',
        (tester) async {
      await pumpForm(tester, [_Reply(201, _created)]);
      await _fill(tester, title: '  Title  ', doneWhen: 'Plural finds singular');

      await _tapSubmit(tester);
      await tester.pumpAndSettle();

      expect(adapter.creates, hasLength(1));
      final sent = adapter.creates.single.json as Map<String, dynamic>;
      expect(
        sent,
        {
          // Untrimmed: the server normalizes, the form does not.
          'title': '  Title  ',
          'body': 'Searching "tomatoes" does not find "tomato".',
          'done_when': 'Plural finds singular',
        },
        reason: 'the JSON keys are the endpoint\'s (extra="forbid" would '
            '422 any other key), and the text goes unnormalized',
      );
      final id8 = tester.widget<SelectableText>(
        find.byKey(const Key('dev_request_id8')),
      );
      expect(id8.data, '048298e4');
      expect(find.text(AdminDevRequestNewScreen.filedLine), findsOneWidget);
      expect(_titleField, findsNothing, reason: 'the form gives way to the result');
    });

    testWidgets('a second tap while the first is in flight sends nothing',
        (tester) async {
      final release = Completer<void>();
      await pumpForm(tester, [_Reply(201, _created, gate: release.future)]);
      await _fill(tester);

      await _tapSubmit(tester);
      await tester.pump();
      expect(_submitEnabled(tester), isFalse);
      await tester.tap(_submit, warnIfMissed: false);
      await tester.pump();

      release.complete();
      await tester.pumpAndSettle();

      expect(adapter.creates, hasLength(1));
      expect(find.byKey(const Key('dev_request_id8')), findsOneWidget);
    });

    testWidgets('a blank done-when is left out of the call', (tester) async {
      await pumpForm(tester, [_Reply(201, _created), _Reply(201, _created)]);

      await _fill(tester);
      await _tapSubmit(tester);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('dev_request_another_button')));
      await tester.pumpAndSettle();
      await _fill(tester, doneWhen: '   ');
      await _tapSubmit(tester);
      await tester.pumpAndSettle();

      expect(adapter.creates, hasLength(2));
      for (final c in adapter.creates) {
        expect((c.json as Map).containsKey('done_when'), isFalse,
            reason: 'optional means absent; "   " would be a 422');
      }
    });

    testWidgets('submit waits for a non-blank title and body', (tester) async {
      await pumpForm(tester, []);

      expect(_submitEnabled(tester), isFalse);
      await tester.enterText(_titleField, 'A title');
      await tester.pump();
      expect(_submitEnabled(tester), isFalse, reason: 'body still empty');
      await tester.enterText(_bodyField, ' \n\t ');
      await tester.pump();
      expect(_submitEnabled(tester), isFalse, reason: 'whitespace is blank');
      await tester.enterText(_bodyField, 'A body');
      await tester.pump();
      expect(_submitEnabled(tester), isTrue);

      // And the title on its own. Without this half, dropping the title
      // check left every case here green (negative control M19): the
      // title was never blank while the body was not.
      await tester.enterText(_titleField, '   ');
      await tester.pump();
      expect(_submitEnabled(tester), isFalse, reason: 'title is blank');
      await tester.enterText(_titleField, '');
      await tester.pump();
      expect(_submitEnabled(tester), isFalse, reason: 'title is empty');
    });

    testWidgets('403 renders the server message and keeps the text',
        (tester) async {
      await pumpForm(tester, [_Reply(403, _forbidden)]);
      await _fill(tester);

      await _tapSubmit(tester);
      await tester.pumpAndSettle();

      expect(
        find.descendant(
          of: find.byKey(const Key('dev_request_form_error')),
          matching: find.text('Admin access required'),
        ),
        findsOneWidget,
      );
      expect(find.byKey(const Key('dev_request_id8')), findsNothing);
      expect(tester.widget<TextField>(_titleField).controller!.text,
          'Pantry search misses plurals');
    });

    testWidgets('429 renders the server message', (tester) async {
      await pumpForm(tester, [_Reply(429, _rateLimited)]);
      await _fill(tester);

      await _tapSubmit(tester);
      await tester.pumpAndSettle();

      expect(
        find.descendant(
          of: find.byKey(const Key('dev_request_form_error')),
          matching: find
              .text('Too many requests filed (max 5/hour). Retry in 3600s.'),
        ),
        findsOneWidget,
      );
      expect(find.byKey(const Key('dev_request_id8')), findsNothing);
    });

    testWidgets('422 renders each message under the field it names',
        (tester) async {
      await pumpForm(tester, [_Reply(422, _invalidAll)]);
      // Sendable client-side; refused by the server on all three.
      await _fill(tester, title: 'x', body: 'y', doneWhen: 'z');

      await _tapSubmit(tester);
      await tester.pumpAndSettle();

      expect(_errorTextOf(tester, _titleField),
          'title is blank after normalization');
      expect(_errorTextOf(tester, _bodyField),
          'body is blank after normalization');
      expect(_errorTextOf(tester, _doneWhenField),
          'done_when is 1001 characters after normalization; the limit is 1000');
      expect(find.byKey(const Key('dev_request_form_error')), findsNothing,
          reason: 'every entry had a field to go under');
      expect(find.byKey(const Key('dev_request_id8')), findsNothing);

      // Editing a field drops its stale message, and only its own.
      await tester.enterText(_titleField, 'x2');
      await tester.pump();
      expect(_errorTextOf(tester, _titleField), isNull);
      expect(_errorTextOf(tester, _bodyField), isNotNull);
    });

    testWidgets('text only the server calls blank is the server\'s to refuse',
        (tester) async {
      await pumpForm(tester, [_Reply(422, _invalidZwspTitle)]);
      await _fill(tester, title: '​​');

      expect(_submitEnabled(tester), isTrue,
          reason: 'the form must not guess at FR-2 normalization');
      await _tapSubmit(tester);
      await tester.pumpAndSettle();

      expect(adapter.creates, hasLength(1));
      expect(_errorTextOf(tester, _titleField),
          'title is blank after normalization');
    });

    testWidgets('over a counter, submit still goes and the server decides',
        (tester) async {
      await pumpForm(tester, [_Reply(422, _invalidLongBody)]);
      await _fill(tester, body: 'x' * 4001);

      expect(find.text('4001/4000'), findsOneWidget);
      expect(_submitEnabled(tester), isTrue,
          reason: 'the server counts after normalization; no client count '
              'matches it, so the counter guides and does not block');
      await _tapSubmit(tester);
      await tester.pumpAndSettle();

      expect(adapter.creates, hasLength(1));
      expect(_errorTextOf(tester, _bodyField),
          'body is 4001 characters after normalization; the limit is 4000');
    });

    testWidgets('no response at all renders the generic message',
        (tester) async {
      adapter = _WireAdapter();
      final client = _clientOn(adapter);
      client.dio.httpClientAdapter = _ThrowingAdapter();
      GetIt.I.registerSingleton<ApiClient>(client);
      await tester.pumpWidget(
        const MaterialApp(home: AdminDevRequestNewScreen()),
      );
      await _fill(tester);

      await _tapSubmit(tester);
      await tester.pumpAndSettle();

      expect(
        find.descendant(
          of: find.byKey(const Key('dev_request_form_error')),
          matching: find.text("Couldn't file the request. Try again."),
        ),
        findsOneWidget,
      );
    });

    test('the counters carry the server\'s limits', () {
      // Run from app/; CI checks out the whole repository.
      final source = File('../libraries/utils/utils/models/dev_request.py')
          .readAsStringSync();
      int limit(String name) => int.parse(
            RegExp('^$name = (\\d+)\$', multiLine: true)
                .firstMatch(source)!
                .group(1)!,
          );
      expect(AdminDevRequestNewScreen.titleMaxLength, limit('TITLE_MAX_LENGTH'));
      expect(AdminDevRequestNewScreen.bodyMaxLength, limit('BODY_MAX_LENGTH'));
      expect(AdminDevRequestNewScreen.doneWhenMaxLength,
          limit('DONE_WHEN_MAX_LENGTH'));
    });

    testWidgets('each field shows its server limit', (tester) async {
      await pumpForm(tester, []);
      expect(tester.widget<TextField>(_titleField).maxLength,
          AdminDevRequestNewScreen.titleMaxLength);
      expect(tester.widget<TextField>(_bodyField).maxLength,
          AdminDevRequestNewScreen.bodyMaxLength);
      expect(tester.widget<TextField>(_doneWhenField).maxLength,
          AdminDevRequestNewScreen.doneWhenMaxLength);
    });
  });

  group('the route (real appRouter)', () {
    late _WireAdapter adapter;
    void Function(FlutterErrorDetails)? previousOnError;
    final errors = <String>[];

    void boot({required bool admin, List<_Reply>? replies}) {
      setupDependencies();
      GetIt.I.unregister<AuthService>();
      GetIt.I.registerSingleton<AuthService>(_AuthStub(admin: admin));
      adapter = _WireAdapter(replies);
      GetIt.I.unregister<ApiClient>();
      GetIt.I.registerSingleton<ApiClient>(_clientOn(adapter));
      resetRouter();
      resetPerfNavigatorObserver();
    }

    setUp(() async {
      // Here, not in boot(): reset is async, and inside a testWidgets body
      // it completes after the router has booted, clearing the stubs.
      await GetIt.I.reset();
      errors.clear();
      previousOnError = FlutterError.onError;
      FlutterError.onError = (details) => errors.add(details.toString());
    });

    tearDown(() async {
      FlutterError.onError = previousOnError;
      resetRouter();
      resetPerfNavigatorObserver();
      await GetIt.I.reset();
    });

    Future<void> pumpApp(WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(child: MaterialApp.router(routerConfig: appRouter)),
      );
      await tester.pump(const Duration(milliseconds: 100));
    }

    Future<void> settle(WidgetTester tester) async {
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
    }

    testWidgets('the form opens from its route alone, without the dashboard',
        (tester) async {
      boot(admin: true, replies: [_Reply(201, _created)]);
      await pumpApp(tester);

      appRouter.go(AdminDevRequestNewScreen.routePath);
      await settle(tester);

      expect(appRouter.state.matchedLocation, AdminDevRequestNewScreen.routePath);
      expect(find.byType(AdminDevRequestNewScreen), findsOneWidget);
      expect(find.byType(AdminDashboardScreen), findsNothing,
          reason: 'the form needs nothing from the dashboard');

      // Filed from a cold entry, Done has nothing to pop: it goes to /admin.
      await _fill(tester);
      await _tapSubmit(tester);
      await settle(tester);
      expect(adapter.creates, hasLength(1));
      await tester.tap(find.byKey(const Key('dev_request_done_button')));
      await settle(tester);
      expect(appRouter.state.matchedLocation, '/admin');
      expect(errors, isEmpty);
    });

    testWidgets('a push returns the filed id8 to whoever pushed',
        (tester) async {
      boot(admin: true, replies: [_Reply(201, _created)]);
      await pumpApp(tester);
      appRouter.go('/admin');
      await settle(tester);

      // How any trigger other than the tile would open it.
      final result =
          appRouter.push<String?>(AdminDevRequestNewScreen.routePath);
      await settle(tester);
      await _fill(tester);
      await _tapSubmit(tester);
      await settle(tester);
      await tester.tap(find.byKey(const Key('dev_request_done_button')));
      await settle(tester);

      expect(await result, '048298e4');
      expect(appRouter.state.matchedLocation, '/admin');
      expect(errors, isEmpty);
    });

    testWidgets('an admin reaches the form from the dashboard tile',
        (tester) async {
      boot(admin: true);
      await pumpApp(tester);
      appRouter.go('/admin');
      await settle(tester);

      final tile = find.byKey(const Key('admin_dev_request_tile'));
      await tester.scrollUntilVisible(tile, 200,
          scrollable: find.byType(Scrollable).first);
      expect(find.descendant(of: tile, matching: find.text('Request a change')),
          findsOneWidget);
      await tester.tap(tile);
      await settle(tester);

      expect(appRouter.state.matchedLocation, AdminDevRequestNewScreen.routePath);
      expect(find.byType(AdminDevRequestNewScreen), findsOneWidget);
      expect(errors, isEmpty);
    });

    testWidgets('a non-admin is shown neither the entry nor the form',
        (tester) async {
      boot(admin: false);
      await pumpApp(tester);

      appRouter.go('/admin');
      await settle(tester);
      expect(appRouter.state.matchedLocation, isNot(startsWith('/admin')));
      expect(find.byType(AdminDashboardScreen), findsNothing);
      expect(find.byKey(const Key('admin_dev_request_tile')), findsNothing);

      appRouter.go(AdminDevRequestNewScreen.routePath);
      await settle(tester);
      expect(appRouter.state.matchedLocation, isNot(startsWith('/admin')));
      expect(find.byType(AdminDevRequestNewScreen), findsNothing);
      expect(adapter.creates, isEmpty);
    });
  });
}

/// Fails every request before any response exists (no connection).
class _ThrowingAdapter implements HttpClientAdapter {
  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    throw DioException.connectionError(
      requestOptions: options,
      reason: 'test: no connection',
    );
  }
}
