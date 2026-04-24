import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../config/environment.dart';
import 'api_client.dart';

/// Central error reporter for Palateful.
///
/// Two responsibilities:
///   1. Format caught errors for in-app display via [detail].
///   2. Forward caught errors to Firebase Crashlytics as non-fatal events
///      via [report] / [guard].
///
/// Reporting is a no-op in debug builds, E2E mode, and on web. `firebase_crashlytics`
/// has no web implementation, so every call site routes through this class to
/// keep the guard in one place. Server-side errors from web users are still
/// captured by the API's `error_logs` middleware.
class ErrorReporter {
  ErrorReporter._();
  static final instance = ErrorReporter._();

  /// Test-only hook. When set, every [report] call invokes the hook
  /// instead of touching Crashlytics / debugPrint. Tests register a
  /// capture, run the code under test, then inspect captured args.
  @visibleForTesting
  static ReportHook? testReportHook;

  /// Test-only hook. When set, every [log] call invokes the hook.
  @visibleForTesting
  static void Function(String message)? testLogHook;

  /// API client used to mirror [report]/[log] events into server-side
  /// `error_logs` (service="client") via `POST /v1/users/me/client-errors`.
  /// Bound once from `main.dart` after DI setup. `null` before binding —
  /// mirror calls are then no-ops. Fire-and-forget; mirror-own-failure
  /// is swallowed to avoid recursion.
  static ApiClient? _mirrorClient;

  /// Wire the API client used for backend-mirror POSTs. Call once after
  /// DI setup (see main.dart). Idempotent.
  static void bindApiClient(ApiClient client) {
    _mirrorClient = client;
  }

  /// Clear the mirror binding (logout path). After this, mirror calls
  /// no-op until [bindApiClient] is called again with a fresh client.
  static void clearApiClient() {
    _mirrorClient = null;
  }

  /// Extract a debug-friendly detail string from any caught error.
  /// Used by screens to show expandable debug info alongside user-facing
  /// error messages.
  static String detail(Object error) {
    if (error is DioException) {
      final parts = <String>[];
      final req = error.requestOptions;
      parts.add('${req.method} ${req.path}');
      if (error.response != null) {
        parts.add('Status: ${error.response!.statusCode}');
        final data = error.response!.data;
        if (data != null) {
          parts.add('Body: ${data.toString().length > 500 ? '${data.toString().substring(0, 500)}...' : data}');
        }
      } else {
        parts.add('Type: ${error.type.name}');
        parts.add('Message: ${error.message}');
      }
      return parts.join('\n');
    }
    return error.toString();
  }

  /// True when Crashlytics calls should be suppressed. `kIsWeb` is included
  /// because `firebase_crashlytics` has no web platform implementation —
  /// calling it on web throws `MissingPluginException` at startup.
  static bool get _reportingDisabled => kDebugMode || kE2EMode || kIsWeb;

  /// True when the backend mirror POST should be suppressed. Debug +
  /// E2E skip mirroring so local iteration doesn't pollute prod
  /// error_logs. Web is allowed — our backend works from web.
  static bool get _backendMirrorDisabled => kDebugMode || kE2EMode;

  /// Fire-and-forget backend mirror. Any failure (including the
  /// `/client-errors` endpoint 5xx'ing) is swallowed — a mirror that
  /// reported its own failure via [report] would recurse. The Dio
  /// interceptor in `api_client.dart` also skips 5xx reporting for
  /// `/client-errors` as a second line of defense.
  // Mirrors `services/api/src/api/v1/user/record_client_error.py` Pydantic
  // constraints. Oversized payloads return 422 and are silently dropped,
  // so clamp here to keep the mirror best-effort.
  static const int _maxErrorTypeLen = 120;
  static const int _maxErrorMessageLen = 2000;
  static const int _maxAreaLen = 64;
  static const int _maxOperationLen = 128;

  static String? _clamp(String? value, int maxLen) {
    if (value == null) return null;
    if (value.isEmpty) return null;
    if (value.length <= maxLen) return value;
    return value.substring(0, maxLen);
  }

  static void _mirrorToBackend({
    required String errorType,
    required String errorMessage,
    String? area,
    String? operation,
    Map<String, Object?>? extras,
    int? statusCode,
  }) {
    if (_backendMirrorDisabled) return;
    final client = _mirrorClient;
    if (client == null) return;
    final clampedType = _clamp(errorType, _maxErrorTypeLen);
    final clampedMessage = _clamp(errorMessage, _maxErrorMessageLen);
    // error_type / error_message are required with min_length=1 server-side.
    // If either is empty after clamping, substitute a sentinel rather than
    // dropping the event entirely — an anonymous row is still useful signal.
    unawaited(_postMirror(
      client,
      errorType: clampedType ?? 'UnknownError',
      errorMessage: clampedMessage ?? '(empty)',
      area: _clamp(area, _maxAreaLen),
      operation: _clamp(operation, _maxOperationLen),
      extras: extras,
      statusCode: statusCode,
    ));
  }

  static Future<void> _postMirror(
    ApiClient client, {
    required String errorType,
    required String errorMessage,
    String? area,
    String? operation,
    Map<String, Object?>? extras,
    int? statusCode,
  }) async {
    try {
      await client
          .recordClientError(
            errorType: errorType,
            errorMessage: errorMessage,
            area: area,
            operation: operation,
            extras: extras,
            statusCode: statusCode,
          )
          .timeout(const Duration(seconds: 3));
    } catch (_) {
      // Never recurse. The mirror's own failure is intentionally dropped.
    }
  }

  /// Enable Crashlytics collection and wire fatal-error handlers. Safe to
  /// call from every platform — no-ops when reporting is disabled (debug,
  /// E2E, or web), so callers don't need their own kIsWeb guard.
  static Future<void> initialize() async {
    if (_reportingDisabled) return;
    final crashlytics = FirebaseCrashlytics.instance;
    await crashlytics.setCrashlyticsCollectionEnabled(true);
    FlutterError.onError = crashlytics.recordFlutterFatalError;
    PlatformDispatcher.instance.onError = (error, stack) {
      crashlytics.recordError(error, stack, fatal: true);
      return true;
    };
  }

  /// Tag subsequent crash reports with the given user id. Pass an empty
  /// string on logout to clear the association.
  static void setUserIdentifier(String id) {
    if (_reportingDisabled) return;
    FirebaseCrashlytics.instance.setUserIdentifier(id);
  }

  /// Record a caught error as a non-fatal Crashlytics event.
  ///
  /// [area] is a coarse feature tag (e.g. `'import.url'`, `'auth'`,
  /// `'recipe.detail'`). [operation] is the specific action that failed
  /// (e.g. `'submitUrl'`, `'refreshToken'`). Both are attached as custom
  /// keys so crashes can be filtered in the dashboard.
  ///
  /// For [DioException]s the method, path, and status code are attached
  /// as custom keys. Request/response bodies are never sent — recipe
  /// content is user-generated PII.
  static void report(
    Object error,
    StackTrace? stack, {
    String? area,
    String? operation,
    Map<String, Object?>? extras,
    bool fatal = false,
  }) {
    final hook = testReportHook;
    if (hook != null) {
      hook(error, stack, area: area, operation: operation, extras: extras, fatal: fatal);
      return;
    }

    // Mirror to backend regardless of Crashlytics suppression state —
    // a web or debug session still benefits from an error_logs row when
    // bound to a real backend.
    _mirrorReportToBackend(error, area: area, operation: operation, extras: extras);

    if (_reportingDisabled) {
      debugPrint(
        '[ErrorReporter] (suppressed) area=$area op=$operation error=$error',
      );
      return;
    }

    final crashlytics = FirebaseCrashlytics.instance;

    if (area != null) {
      crashlytics.setCustomKey('area', area);
    }
    if (operation != null) {
      crashlytics.setCustomKey('operation', operation);
    }
    if (extras != null) {
      for (final entry in extras.entries) {
        final value = entry.value;
        if (value != null) {
          crashlytics.setCustomKey(entry.key, value);
        }
      }
    }

    String? reason;
    if (error is DioException) {
      final req = error.requestOptions;
      final status = error.response?.statusCode;
      crashlytics.setCustomKey('http.method', req.method);
      crashlytics.setCustomKey('http.path', req.path);
      if (status != null) {
        crashlytics.setCustomKey('http.status', status);
      }
      reason = 'API ${req.method} ${req.path}'
          '${status != null ? ' → $status' : ''}';
    } else if (operation != null) {
      reason = operation;
    }

    crashlytics.recordError(
      error,
      stack,
      reason: reason,
      fatal: fatal,
    );
  }

  /// Wrap an async operation, reporting any thrown error to Crashlytics
  /// and then rethrowing so callers can still handle UX (show snackbar,
  /// update error state, etc.).
  ///
  /// ```dart
  /// final recipe = await ErrorReporter.guard(
  ///   () => _apiClient.getRecipe(id),
  ///   area: 'recipe.detail',
  ///   operation: 'loadRecipe',
  /// );
  /// ```
  static Future<T> guard<T>(
    Future<T> Function() body, {
    required String area,
    String? operation,
    Map<String, Object?>? extras,
  }) async {
    try {
      return await body();
    } catch (e, st) {
      report(
        e,
        st,
        area: area,
        operation: operation,
        extras: extras,
      );
      rethrow;
    }
  }

  /// Append a breadcrumb to the Crashlytics log. Shown alongside the
  /// stack trace in the dashboard when a crash is reported.
  static void log(String message) {
    final hook = testLogHook;
    if (hook != null) {
      hook(message);
      return;
    }

    // Mirror breadcrumbs into server-side error_logs as service="client",
    // error_type="ClientLog" rows. Lets us read Leo's boot-time push flow
    // (the ensureRegistered breadcrumbs from push-diag-2) from the same
    // audit_errors.py pipeline as server errors.
    _mirrorToBackend(errorType: 'ClientLog', errorMessage: message);

    if (_reportingDisabled) {
      debugPrint('[ErrorReporter.log] $message');
      return;
    }
    FirebaseCrashlytics.instance.log(message);
  }

  /// Translate a [report] call into the mirror-POST shape. Split out so
  /// DioException-specific metadata (method, path, status) is hoisted
  /// into `extras` + `status_code` for audit_errors.py rollups.
  static void _mirrorReportToBackend(
    Object error, {
    String? area,
    String? operation,
    Map<String, Object?>? extras,
  }) {
    String mirrorType;
    String mirrorMessage;
    int? statusCode;
    final mirrorExtras = <String, Object?>{...?extras};
    if (error is DioException) {
      mirrorType = 'DioException';
      statusCode = error.response?.statusCode;
      final req = error.requestOptions;
      mirrorExtras['http.method'] = req.method;
      mirrorExtras['http.path'] = req.path;
      final suffix = statusCode != null ? ' → $statusCode' : '';
      final detailPart = error.message != null ? ': ${error.message}' : '';
      mirrorMessage = '${req.method} ${req.path}$suffix$detailPart';
    } else {
      mirrorType = error.runtimeType.toString();
      mirrorMessage = error.toString();
    }
    _mirrorToBackend(
      errorType: mirrorType,
      errorMessage: mirrorMessage,
      area: area,
      operation: operation,
      extras: mirrorExtras.isEmpty ? null : mirrorExtras,
      statusCode: statusCode,
    );
  }
}

/// Test-only callback signature for capturing [ErrorReporter.report] invocations.
typedef ReportHook = void Function(
  Object error,
  StackTrace? stack, {
  String? area,
  String? operation,
  Map<String, Object?>? extras,
  bool fatal,
});

/// Navigator observer that records screen transitions as Crashlytics
/// breadcrumbs and tags the current route as a custom key. Lets us see
/// which screen the user was on when a crash or non-fatal error occurred.
class CrashlyticsNavObserver extends NavigatorObserver {
  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    _record('push', route);
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    _record('pop', previousRoute);
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    _record('replace', newRoute);
  }

  void _record(String action, Route<dynamic>? route) {
    final name = route?.settings.name;
    if (name == null || name.isEmpty) return;
    ErrorReporter.log('nav.$action $name');
    if (!ErrorReporter._reportingDisabled) {
      FirebaseCrashlytics.instance.setCustomKey('route', name);
    }
  }
}
