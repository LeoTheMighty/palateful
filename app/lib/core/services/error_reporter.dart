import 'package:dio/dio.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../config/environment.dart';

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
    if (_reportingDisabled) {
      debugPrint('[ErrorReporter.log] $message');
      return;
    }
    FirebaseCrashlytics.instance.log(message);
  }
}

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
