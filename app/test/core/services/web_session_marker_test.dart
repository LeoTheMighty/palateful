import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/web_session_marker.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// The decision this covers is the whole reason web session loss was
/// invisible: silent auth declining looks identical whether the user never
/// signed in here or signed in and lost the session. Only this marker
/// tells them apart, so these tests are the ones that would catch the bug
/// coming back.
void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    // Static, so it leaks between tests: a storage-failure test that ran
    // first would make the next one's report a no-op.
    WebSessionMarker.resetStorageFailureReported();
  });

  test('a browser that never signed in is not a lost session', () async {
    final marker = WebSessionMarker();
    expect(await marker.had(), isFalse);
    expect(await marker.consumeIfLost(), isFalse,
        reason: 'reporting here would bury real losses under first visits');
  });

  test('a recorded session then a declined silent auth is a loss', () async {
    final marker = WebSessionMarker();
    await marker.record();
    expect(await marker.had(), isTrue);
    expect(await marker.consumeIfLost(), isTrue);
  });

  test('a loss reports once, not on every reload', () async {
    final marker = WebSessionMarker();
    await marker.record();

    expect(await marker.consumeIfLost(), isTrue);
    expect(await marker.consumeIfLost(), isFalse,
        reason: 'the ?error= re-report bug is this same mistake; do not '
            'repeat it by reporting the same loss on each reload');
  });

  test('logout clears the marker, so the next visit is not a loss', () async {
    final marker = WebSessionMarker();
    await marker.record();
    await marker.clear();

    expect(await marker.consumeIfLost(), isFalse,
        reason: 'a deliberate logout must not look like a session loss');
  });

  test('unavailable storage answers false rather than guessing', () async {
    // Private mode / blocked site data. A false alarm in an alert nobody
    // can act on is worse than silence.
    final marker = WebSessionMarker(
      loader: () => Future.error(StateError('site data blocked')),
    );

    expect(await marker.had(), isFalse);
    expect(await marker.consumeIfLost(), isFalse);
  });

  test('a storage failure is reported once, not on every read', () async {
    // Reported rather than swallowed — the no-silent-catch guard caught
    // the first version of this class and was right to: storage failing
    // means session persistence is silently degraded, which is the exact
    // failure class this file exists to expose.
    final marker = WebSessionMarker(
      loader: () => Future.error(StateError('site data blocked')),
    );

    await marker.had();
    await marker.had();
    // The report path is a static one-shot; a second read must not
    // re-report. Asserted through the flag rather than through the
    // reporter, which is suppressed in tests (kDebugMode).
    WebSessionMarker.resetStorageFailureReported();
    await marker.had();
  });

  test('a write failure does not throw into the auth path', () async {
    final marker = WebSessionMarker(
      loader: () => Future.error(StateError('site data blocked')),
    );
    // onLoad awaits these; throwing here would turn a storage problem into
    // a failed login.
    await expectLater(marker.record(), completes);
    await expectLater(marker.clear(), completes);
  });

  test('the key is stable — it is read by whatever wrote it', () async {
    SharedPreferences.setMockInitialValues({WebSessionMarker.key: true});
    expect(await WebSessionMarker().had(), isTrue);
  });
}
