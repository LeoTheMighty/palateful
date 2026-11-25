import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/error_reporter.dart';
import '../widgets/feedback_sheet.dart';
import 'feedback_cache_service.dart';
import 'profile_service.dart';

export '../widgets/feedback_sheet.dart' show FeedbackTrigger;

/// The one way into the feedback sheet, and the one flush of its offline
/// queue (PRD FR-9, design § Feedback launcher).
///
/// Moved, not rewritten, out of `ProfileScreen` (`_openFeedbackSheet`,
/// `_flushFeedbackQueue`, `_captureFeedbackContext`). Two things are new:
///
/// - the caller supplies the route and the [FeedbackTrigger], so an entry
///   point other than Profile's tile can open the same sheet;
/// - [flushQueue] is called from the app root at startup and on every
///   resume as well as from Profile, so queued feedback sends whichever
///   screen is mounted. Concurrent calls share one run: Profile and the
///   app root both observe the same resume, and two independent runs would
///   each read the queue and send every entry twice.
///
/// Platform comes from [defaultTargetPlatform] and `kIsWeb`, never
/// `dart:io`, which does not exist on web.
class FeedbackLauncher {
  FeedbackLauncher({
    FeedbackCacheService? cache,
    Future<bool> Function()? isOffline,
    ApiClient Function()? apiClient,
    ProfileService Function()? profileService,
  })  : _cache = cache ?? FeedbackCacheService(),
        _isOfflineProbe = isOffline,
        _apiClient = apiClient ?? (() => getIt<ApiClient>()),
        _profileService = profileService ?? (() => getIt<ProfileService>());

  /// The app's launcher. Profile and the app root must share one instance,
  /// or their flushes cannot coalesce. Its dependencies resolve from `getIt`
  /// at call time, as Profile's fields did.
  static final FeedbackLauncher instance = FeedbackLauncher();

  final FeedbackCacheService _cache;
  final Future<bool> Function()? _isOfflineProbe;
  final ApiClient Function() _apiClient;
  final ProfileService Function() _profileService;

  Future<int>? _inFlight;

  /// Shows the feedback sheet over [context]'s route.
  ///
  /// [route] is the location the user was on; any query string or fragment
  /// is dropped before it is sent (FR-9: the path only).
  Future<void> open(
    BuildContext context, {
    required FeedbackTrigger trigger,
    required String route,
  }) async {
    final platform = feedbackPlatform();
    final offline = await _isOffline();
    if (!context.mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetCtx) => FeedbackSheet(
        apiClient: _apiClient(),
        cache: _cache,
        isOffline: offline,
        platform: platform,
        currentRoute: routePath(route),
        trigger: trigger,
        onComplete: (online) {
          Navigator.of(sheetCtx).pop();
          if (!context.mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                online
                    ? 'Thanks — feedback sent'
                    : "Saved — we'll send it when you're back online.",
              ),
            ),
          );
        },
      ),
    );
  }

  /// Sends every queued feedback entry and returns how many went out.
  ///
  /// Never throws. An entry whose send fails stays queued for the next
  /// call. A call made while a flush is running joins that flush and gets
  /// its count, rather than starting a second one.
  Future<int> flushQueue() =>
      _inFlight ??= _flush().whenComplete(() => _inFlight = null);

  Future<int> _flush() async {
    try {
      final pending = await _cache.getPendingFeedback();
      if (pending.isEmpty) return 0;
      if (await _isOffline()) return 0;

      int sent = 0;
      final stillQueued = <Map<String, dynamic>>[];
      for (final entry in pending) {
        final body = entry['body'] as String?;
        if (body == null || body.isEmpty) continue;
        try {
          await _profileService().submitFeedback(
            body: body,
            category: entry['category'] as String?,
            context: entry['context'] as Map<String, dynamic>?,
          );
          sent++;
        } catch (e, st) {
          // Network flapped mid-flush, or the server refused the entry —
          // keep it queued. Reported because an entry the server refuses
          // for good would otherwise retry on every resume, unseen.
          ErrorReporter.report(e, st,
              area: 'feedback', operation: 'flushQueue.submit');
          stillQueued.add(entry);
        }
      }

      // Rewrite the queue with only the ones that failed to send.
      await _cache.clearPendingFeedback();
      for (final leftover in stillQueued) {
        await _cache.queueFeedback(
          body: leftover['body'] as String,
          category: leftover['category'] as String?,
          context: leftover['context'] as Map<String, dynamic>?,
        );
      }
      return sent;
    } catch (e, st) {
      // A malformed queue entry (a cast above) is the reachable case. Best
      // effort for the caller, but not silent.
      ErrorReporter.report(e, st, area: 'feedback', operation: 'flushQueue');
      return 0;
    }
  }

  Future<bool> _isOffline() async {
    final probe = _isOfflineProbe;
    if (probe != null) return probe();
    try {
      final results = await Connectivity().checkConnectivity();
      return results.contains(ConnectivityResult.none);
    } catch (e, st) {
      // Unknown connectivity is treated as online, as before: the send
      // itself falls back to the queue if it fails.
      ErrorReporter.report(e, st,
          area: 'feedback', operation: 'checkConnectivity');
      return false;
    }
  }
}

/// The `platform` sent in the feedback context: `web` on web, otherwise
/// `ios` or `android` from [defaultTargetPlatform], and none elsewhere.
///
/// On web [defaultTargetPlatform] reports the browser's OS, so it must not
/// be read there. [isWeb] and [platform] exist for tests; `kIsWeb` is a
/// compile-time constant.
@visibleForTesting
String? feedbackPlatform({bool isWeb = kIsWeb, TargetPlatform? platform}) {
  if (isWeb) return 'web';
  switch (platform ?? defaultTargetPlatform) {
    case TargetPlatform.iOS:
      return 'ios';
    case TargetPlatform.android:
      return 'android';
    case TargetPlatform.fuchsia:
    case TargetPlatform.linux:
    case TargetPlatform.macOS:
    case TargetPlatform.windows:
      return null;
  }
}

/// [route] without its query string or fragment.
@visibleForTesting
String routePath(String route) {
  final cut = route.indexOf(RegExp(r'[?#]'));
  return cut < 0 ? route : route.substring(0, cut);
}
