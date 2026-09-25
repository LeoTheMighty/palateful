import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'error_reporter.dart';

/// Tells **"never signed in on this browser"** apart from **"signed in and
/// lost it"**.
///
/// At startup those two states are identical from the SDK's point of view:
/// silent auth fails with `login_required` either way. That is why web
/// session loss has been invisible — every occurrence looked like a first
/// visit, so nothing was ever reported and the user simply saw a login
/// screen. This marker is the only thing that distinguishes them.
///
/// Deliberately platform-neutral and in its own file rather than inside
/// `auth_service_web.dart`: that file is behind a `dart.library.html`
/// conditional import, so nothing in it can be unit-tested on the VM. The
/// decision that matters — *is this a loss worth reporting?* — lives here
/// where tests can drive it. `SharedPreferences` is already a dependency,
/// is localStorage-backed on web, and has a test mock.
class WebSessionMarker {
  WebSessionMarker({SharedPreferencesLoader? loader})
      : _load = loader ?? SharedPreferences.getInstance;

  static const String key = 'auth.hadWebSession';

  /// Storage failing is reported **once per process**. It is a persistent
  /// condition (private mode, blocked site data), not an event, and the
  /// read happens on every startup — reporting each time would bury the
  /// signal under its own repetition.
  static bool _reportedStorageFailure = false;

  final SharedPreferencesLoader _load;

  /// Whether this process should report a storage failure now.
  ///
  /// The report itself is written **inline in each catch**, not behind a
  /// helper: `tools/silent_catch_scan.py` requires
  /// `ErrorReporter.report*(` in the catch body and deliberately will not
  /// follow a call out of it, because it cannot verify what the callee
  /// does. That rule caught the first version of this class, which
  /// `debugPrint`-ed and moved on — and it was right to. Storage being
  /// unavailable means session persistence is **silently degraded**: no
  /// marker is written, so a later session loss goes unreported and looks
  /// like a first visit. This file exists to make that failure class
  /// visible, so it must not fail invisibly itself.
  static bool _shouldReportStorageFailure() {
    if (_reportedStorageFailure) return false;
    _reportedStorageFailure = true;
    return true;
  }

  @visibleForTesting
  static void resetStorageFailureReported() =>
      _reportedStorageFailure = false;

  /// True when this browser has completed a login at least once.
  ///
  /// Any storage failure answers **false**. Claiming a session was lost
  /// when we cannot tell would report a first visit as a bug, and a
  /// false alarm in an alert nobody can act on is worse than silence —
  /// private mode and blocked site data both land here.
  Future<bool> had() async {
    try {
      final prefs = await _load();
      return prefs.getBool(key) ?? false;
    } catch (e, st) {
      debugPrint('WebSessionMarker read failed: $e');
      if (_shouldReportStorageFailure()) {
        ErrorReporter.reportPreAuth(e, st,
            area: 'auth',
            operation: 'webSessionMarker.read',
            extras: {'failureMode': 'sessionMarkerStorageUnavailable'});
      }
      return false;
    }
  }

  Future<void> record() => _write(true);

  /// Clear the marker — on logout, and after reporting a loss.
  Future<void> clear() => _write(false);

  Future<void> _write(bool value) async {
    try {
      final prefs = await _load();
      if (value) {
        await prefs.setBool(key, true);
      } else {
        await prefs.remove(key);
      }
    } catch (e, st) {
      debugPrint('WebSessionMarker write failed: $e');
      if (_shouldReportStorageFailure()) {
        ErrorReporter.reportPreAuth(e, st,
            area: 'auth',
            operation: 'webSessionMarker.write',
            extras: {'failureMode': 'sessionMarkerStorageUnavailable'});
      }
    }
  }

  /// Should a declined silent auth be reported as a lost session?
  ///
  /// Clears the marker when it returns true, so one loss reports **once**
  /// rather than on every subsequent reload — the `?error=` re-report
  /// problem in `auth_service_web.dart` is the same mistake, and this
  /// avoids repeating it.
  Future<bool> consumeIfLost() async {
    if (!await had()) return false;
    await clear();
    return true;
  }
}

typedef SharedPreferencesLoader = Future<SharedPreferences> Function();
