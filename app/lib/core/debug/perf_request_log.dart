import 'package:flutter/foundation.dart';

/// Single HTTP request observed by the debug perf interceptor.
@immutable
class PerfRequestEntry {
  const PerfRequestEntry({
    required this.timestamp,
    required this.method,
    required this.path,
    required this.statusCode,
    required this.duration,
    this.errorMessage,
  });

  final DateTime timestamp;
  final String method;
  final String path;
  final int? statusCode;
  final Duration duration;
  final String? errorMessage;
}

/// kDebugMode-only ring buffer of recent HTTP requests, feeding the
/// [PerfOverlay]. Capacity 100; the overlay renders them scrollably.
///
/// In release builds the backing interceptor is not installed (see
/// `main.dart` kDebugMode gate), so [add] is never called and the
/// notifier stays empty. The class itself is cheap — a ValueNotifier
/// holding an empty list — but the recommended release pattern is for
/// callers to skip reaching this file at all.
class PerfRequestLog {
  PerfRequestLog._();

  static const int capacity = 100;

  static final PerfRequestLog instance = PerfRequestLog._();

  /// Newest-first list of at most [capacity] entries. Wrapped in a
  /// ValueNotifier so the overlay's ValueListenableBuilder rebuilds
  /// on every push.
  final ValueNotifier<List<PerfRequestEntry>> entries =
      ValueNotifier(const []);

  void add(PerfRequestEntry entry) {
    final next = <PerfRequestEntry>[entry, ...entries.value];
    if (next.length > capacity) {
      next.removeRange(capacity, next.length);
    }
    entries.value = next;
  }

  @visibleForTesting
  void clear() {
    entries.value = const [];
  }
}
