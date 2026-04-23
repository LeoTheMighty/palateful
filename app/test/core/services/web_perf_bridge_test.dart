import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/client_latency_ingest.dart';
import 'package:palateful/core/services/perf_flags_service.dart';
import 'package:palateful/core/services/web_perf_bridge.dart';

class _StubAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromBytes(
      utf8.encode(jsonEncode({'ok': true})),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _StaticFlags implements PerfFlagsService {
  @override
  bool ingestEnabled = true;
  @override
  double samplingRate = 1.0;
  @override
  Future<void> initialize() async {}
  @override
  void dispose() {}
}

class _FakeReader implements WebPerfReader {
  _FakeReader({
    this.navigation,
    this.paintTimings = const [],
  });

  NavigationTimingSnapshot? navigation;
  List<PaintTimingEntry> paintTimings;
  void Function(PaintTimingEntry)? _observer;

  @override
  NavigationTimingSnapshot? readNavigationTiming() => navigation;

  @override
  List<PaintTimingEntry> readPaintTimings() => paintTimings;

  @override
  void observePaintEntries({
    required void Function(PaintTimingEntry entry) onEntry,
  }) {
    _observer = onEntry;
  }

  /// Simulate an async paint entry arriving after observation started.
  void pushPaintEntry(PaintTimingEntry entry) {
    _observer?.call(entry);
  }
}

ClientLatencyIngest _makeIngest() {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.example'));
  dio.httpClientAdapter = _StubAdapter();
  return ClientLatencyIngest.withDio(
    dio: dio,
    flags: _StaticFlags(),
    platform: ClientLatencyPlatform.web,
    appVersion: '1.0.0+1',
    flushInterval: const Duration(days: 1),
    flushThreshold: 10000,
    random: Random(0),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('start() is a no-op on non-web platforms', () {
    final ingest = _makeIngest();
    final reader = _FakeReader(
      navigation: const NavigationTimingSnapshot(
        fetchStartMs: 0,
        domContentLoadedEndMs: 50,
        loadEventEndMs: 100,
      ),
    );
    final bridge = WebPerfBridge(
      ingest: ingest,
      reader: reader,
      isWebOverride: false,
    );
    bridge.start();
    expect(ingest.queuedEventCount, 0);
    ingest.dispose();
  });

  test('emits web_navigation when readNavigationTiming returns a value', () {
    final ingest = _makeIngest();
    final reader = _FakeReader(
      navigation: const NavigationTimingSnapshot(
        fetchStartMs: 10,
        domContentLoadedEndMs: 220,
        loadEventEndMs: 450,
      ),
    );
    final bridge = WebPerfBridge(
      ingest: ingest,
      reader: reader,
      isWebOverride: true,
    );
    bridge.start();
    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('emits first_paint + first_contentful_paint from initial read', () {
    final ingest = _makeIngest();
    final reader = _FakeReader(
      paintTimings: const [
        PaintTimingEntry(name: 'first-paint', startTimeMs: 120),
        PaintTimingEntry(
          name: 'first-contentful-paint',
          startTimeMs: 180,
        ),
      ],
    );
    final bridge = WebPerfBridge(
      ingest: ingest,
      reader: reader,
      isWebOverride: true,
    );
    bridge.start();
    expect(ingest.queuedEventCount, 2);
    ingest.dispose();
  });

  test('async paint entries via observer also emit events', () {
    final ingest = _makeIngest();
    final reader = _FakeReader();
    final bridge = WebPerfBridge(
      ingest: ingest,
      reader: reader,
      isWebOverride: true,
    );
    bridge.start();
    expect(ingest.queuedEventCount, 0);
    reader.pushPaintEntry(const PaintTimingEntry(
      name: 'first-paint',
      startTimeMs: 85,
    ));
    expect(ingest.queuedEventCount, 1);
    ingest.dispose();
  });

  test('emitter swallows reader exceptions silently', () {
    final ingest = _makeIngest();
    final throwingReader = _ThrowingReader();
    final bridge = WebPerfBridge(
      ingest: ingest,
      reader: throwingReader,
      isWebOverride: true,
    );
    // Should not throw — errors are caught per the bridge's contract.
    bridge.start();
    expect(ingest.queuedEventCount, 0);
    ingest.dispose();
  });
}

class _ThrowingReader implements WebPerfReader {
  @override
  NavigationTimingSnapshot? readNavigationTiming() =>
      throw StateError('no navigation API available');

  @override
  List<PaintTimingEntry> readPaintTimings() => const [];

  @override
  void observePaintEntries({
    required void Function(PaintTimingEntry entry) onEntry,
  }) {}
}
