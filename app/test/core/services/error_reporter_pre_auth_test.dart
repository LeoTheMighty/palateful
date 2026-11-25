import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/error_reporter.dart';

/// authrep1 AC #2: pre-auth failures go to Crashlytics, NOT the error_logs
/// mirror.
///
/// The mirror POSTs `/v1/users/me/client-errors`, which is behind
/// `get_current_user_async`. A user whose credentials just failed to restore
/// cannot authenticate that POST, and `_postMirror` swallows the resulting
/// 401 — so mirroring a pre-auth event loses it and leaves a spurious 401 in
/// the API logs. These tests assert the routing, which is invisible at
/// runtime precisely because both failure paths are silent.
///
/// [ErrorReporter.testMirrorHook] fires before the debug/E2E suppression
/// check, so these tests distinguish "not mirrored because pre-auth" from
/// "not mirrored because `flutter test` runs in debug".
void main() {
  late List<String> mirrored;

  setUp(() {
    mirrored = [];
    ErrorReporter.testMirrorHook = (area, operation) {
      mirrored.add('$area/$operation');
    };
  });

  tearDown(() {
    ErrorReporter.testMirrorHook = null;
    ErrorReporter.testReportHook = null;
  });

  test('report() mirrors to the backend', () {
    ErrorReporter.report(StateError('boom'), StackTrace.current,
        area: 'auth', operation: 'logout');
    expect(mirrored, ['auth/logout']);
  });

  test('reportPreAuth() does not mirror', () {
    ErrorReporter.reportPreAuth(StateError('boom'), StackTrace.current,
        area: 'auth', operation: 'restoreCredentials');
    expect(mirrored, isEmpty);
  });

  test('the two are otherwise the same call — both reach the report hook', () {
    final seen = <String?>[];
    ErrorReporter.testReportHook = (error, stack,
        {area, operation, extras, fatal = false}) {
      seen.add(operation);
    };

    ErrorReporter.report(StateError('a'), null, area: 'auth', operation: 'logout');
    ErrorReporter.reportPreAuth(StateError('b'), null,
        area: 'auth', operation: 'login');

    expect(seen, ['logout', 'login']);
  });

  test('a run of pre-auth reports never mirrors — the cold-start loop', () {
    // The shape behind "the login doesn't hold": restore fails on every
    // launch. Each one would be a 401 against /client-errors.
    for (var i = 0; i < 5; i++) {
      ErrorReporter.reportPreAuth(StateError('attempt $i'), null,
          area: 'auth', operation: 'restoreCredentials');
    }
    expect(mirrored, isEmpty);
  });
}
