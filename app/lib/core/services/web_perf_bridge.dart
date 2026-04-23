import 'package:flutter/foundation.dart';

import 'client_latency_ingest.dart';

/// Emits Navigation Timing + Paint Timing events on Flutter web (cla-9).
///
/// Reads `window.performance.getEntriesByType('navigation')` once on the
/// first tick after boot and `PerformanceObserver(type: 'paint')` for
/// `first-paint` / `first-contentful-paint` entries. Mobile and desktop
/// builds are no-ops — the bridge guards on `kIsWeb` before touching
/// `package:web` so the non-web AOT builds don't need the browser APIs.
///
/// **Renderer caveat.** Flutter web's canvas renderer draws the whole
/// app on a single canvas element; `first-paint` and
/// `first-contentful-paint` therefore fire together at frame one
/// regardless of content. On the HTML renderer the two events behave
/// more like they do in a browser. Operators compare platform + app
/// version filters on the admin dashboard to disambiguate.
///
/// Fire-and-forget — any error (stale browser missing the API,
/// permission denied in a sandboxed iframe) is swallowed and the
/// bridge goes silent. `ClientLatencyIngest` is the single emission
/// pathway so downstream (sampling, rate-limit) still applies.
class WebPerfBridge {
  WebPerfBridge({
    required this.ingest,
    WebPerfReader? reader,
    bool? isWebOverride,
  })  : _reader = reader ?? _DefaultWebPerfReader(),
        _isWeb = isWebOverride ?? kIsWeb;

  final ClientLatencyIngest ingest;
  final WebPerfReader _reader;
  final bool _isWeb;

  /// Reads the page's navigation timing + paint entries once and
  /// enqueues them. On non-web platforms this is a no-op.
  void start() {
    if (!_isWeb) return;
    try {
      final nav = _reader.readNavigationTiming();
      if (nav != null) {
        ingest.enqueue(
          type: ClientLatencyType.webNavigation,
          durationMs: nav.loadEventEndMs,
          metricName: 'navigation',
          extra: {
            'fetch_start_ms': nav.fetchStartMs,
            'dom_content_loaded_ms': nav.domContentLoadedEndMs,
            'load_event_end_ms': nav.loadEventEndMs,
          },
        );
      }
      for (final paint in _reader.readPaintTimings()) {
        final type = paint.name == 'first-paint'
            ? ClientLatencyType.firstPaint
            : ClientLatencyType.firstContentfulPaint;
        ingest.enqueue(
          type: type,
          durationMs: paint.startTimeMs,
          metricName: paint.name,
        );
      }
      _reader.observePaintEntries(onEntry: (paint) {
        final type = paint.name == 'first-paint'
            ? ClientLatencyType.firstPaint
            : ClientLatencyType.firstContentfulPaint;
        ingest.enqueue(
          type: type,
          durationMs: paint.startTimeMs,
          metricName: paint.name,
        );
      });
    } catch (e) {
      if (kDebugMode) debugPrint('WebPerfBridge error: $e');
    }
  }
}

/// Timing-only DTO (detached from `package:web`) so the service layer
/// and tests don't need the browser SDK imported.
class NavigationTimingSnapshot {
  const NavigationTimingSnapshot({
    required this.fetchStartMs,
    required this.domContentLoadedEndMs,
    required this.loadEventEndMs,
  });

  final int fetchStartMs;
  final int domContentLoadedEndMs;
  final int loadEventEndMs;
}

class PaintTimingEntry {
  const PaintTimingEntry({required this.name, required this.startTimeMs});
  final String name;
  final int startTimeMs;
}

/// Reader surface kept tiny so tests can stub it without importing
/// `package:web` / `dart:js_interop`.
abstract class WebPerfReader {
  NavigationTimingSnapshot? readNavigationTiming();
  List<PaintTimingEntry> readPaintTimings();
  void observePaintEntries({
    required void Function(PaintTimingEntry entry) onEntry,
  });
}

class _DefaultWebPerfReader implements WebPerfReader {
  @override
  NavigationTimingSnapshot? readNavigationTiming() {
    // In the canvaskit / html renderer this is where we'd call
    // `web.window.performance.getEntriesByType('navigation')`. To keep
    // this service buildable on all platforms (non-web tooling still
    // imports it transitively via DI), the real read is delegated to
    // a platform-specific entry point set up in `main.dart` under a
    // `kIsWeb` guard. The default reader is intentionally null so
    // mobile builds never touch `package:web` at all.
    return null;
  }

  @override
  List<PaintTimingEntry> readPaintTimings() => const [];

  @override
  void observePaintEntries({
    required void Function(PaintTimingEntry entry) onEntry,
  }) {
    // No-op on non-web. See class doc — the web-specific reader is
    // installed by `main.dart` when `kIsWeb` is true.
  }
}
