import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/client_latency_ingest.dart';
import 'package:palateful/core/services/perf_flags_service.dart';
import 'package:palateful/core/services/perf_navigator_observer.dart';

class _StubAdapter implements HttpClientAdapter {
  final List<RequestOptions> requests = [];
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return ResponseBody.fromBytes(
      utf8.encode(jsonEncode({'success': true, 'data': {'accepted': 0}})),
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

ClientLatencyIngest _ingestFor(_StubAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.example'));
  dio.httpClientAdapter = adapter;
  return ClientLatencyIngest.withDio(
    dio: dio,
    flags: _StaticFlags(),
    platform: ClientLatencyPlatform.ios,
    appVersion: '1.0.0+1',
    flushInterval: const Duration(days: 1),
    flushThreshold: 1000,
    random: Random(0),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('didPush enqueues a route_paint event with redacted route',
      (tester) async {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    String? currentPath = '/recipes/:id';
    final observer = PerfNavigatorObserver(
      ingestResolver: () => ingest,
      routePathResolver: () => currentPath,
    );

    await tester.pumpWidget(MaterialApp(
      navigatorObservers: [observer],
      home: _HomeScreen(onGo: (context) {
        currentPath = '/recipes/:id/edit';
        Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => const _DetailScreen(),
        ));
      }),
    ));

    // Initial push of HomeScreen fires didPush; advance one frame so
    // the observer's post-frame callback executes.
    await tester.pump();
    expect(ingest.queuedEventCount, 1);

    await tester.tap(find.text('Go'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    // Initial + push = 2 events.
    expect(ingest.queuedEventCount, 2);

    ingest.dispose();
  });

  testWidgets('didPush with raw UUID in fullPath is scrubbed', (tester) async {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    const rawUrl = '/recipes/550e8400-e29b-41d4-a716-446655440000';
    final observer = PerfNavigatorObserver(
      ingestResolver: () => ingest,
      routePathResolver: () => rawUrl,
    );

    await tester.pumpWidget(MaterialApp(
      navigatorObservers: [observer],
      home: const _HomeScreen(),
    ));
    await tester.pump();

    expect(ingest.queuedEventCount, 1);
    // Flush + capture must run outside the widget test's fake clock,
    // otherwise the Dio Future waits forever.
    await tester.runAsync(() async {
      await ingest.flushNow();
    });
    expect(adapter.requests, hasLength(1));
    final body = adapter.requests.first.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    expect(event['route'], '/recipes/:id');
    expect(event['type'], 'route_paint');
    ingest.dispose();
  });

  testWidgets('reportTabSwap emits an event using the supplied route',
      (tester) async {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final observer = PerfNavigatorObserver(
      ingestResolver: () => ingest,
      routePathResolver: () => '/home',
    );

    await tester.pumpWidget(MaterialApp(
      navigatorObservers: [observer],
      home: const _HomeScreen(),
    ));
    await tester.pump();
    // Clear the initial didPush event so the tab-swap event is the only
    // one this test captures.
    await tester.runAsync(() => ingest.flushNow());
    adapter.requests.clear();

    observer.reportTabSwap('/profile');
    await tester.runAsync(() => ingest.flushNow());
    expect(adapter.requests, hasLength(1));
    final body = adapter.requests.first.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    expect(event['route'], '/profile');
    expect(event['duration_ms'], 0);
    ingest.dispose();
  });

  testWidgets('didReplace also emits an event', (tester) async {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final navKey = GlobalKey<NavigatorState>();
    final observer = PerfNavigatorObserver(
      ingestResolver: () => ingest,
      routePathResolver: () => '/home',
    );

    await tester.pumpWidget(MaterialApp(
      navigatorKey: navKey,
      navigatorObservers: [observer],
      home: const _HomeScreen(),
    ));
    await tester.pump();
    final beforeReplace = ingest.queuedEventCount;

    navKey.currentState!.pushReplacement(MaterialPageRoute(
      builder: (_) => const _DetailScreen(),
    ));
    await tester.pump();
    await tester.pump();
    expect(ingest.queuedEventCount, beforeReplace + 1);
    ingest.dispose();
  });

  testWidgets('reportTabSwap with null falls back to resolver',
      (tester) async {
    final adapter = _StubAdapter();
    final ingest = _ingestFor(adapter);
    final observer = PerfNavigatorObserver(
      ingestResolver: () => ingest,
      routePathResolver: () => '/cart',
    );

    await tester.pumpWidget(MaterialApp(
      navigatorObservers: [observer],
      home: const _HomeScreen(),
    ));
    await tester.pump();
    await tester.runAsync(() => ingest.flushNow());
    adapter.requests.clear();

    observer.reportTabSwap();
    await tester.runAsync(() => ingest.flushNow());
    final body = adapter.requests.first.data as Map<String, dynamic>;
    final event = (body['events'] as List).first as Map<String, dynamic>;
    expect(event['route'], '/cart');
    ingest.dispose();
  });
}

class _HomeScreen extends StatelessWidget {
  const _HomeScreen({this.onGo});
  final void Function(BuildContext)? onGo;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ElevatedButton(
          onPressed: onGo == null ? null : () => onGo!(context),
          child: const Text('Go'),
        ),
      ),
    );
  }
}

class _DetailScreen extends StatelessWidget {
  const _DetailScreen();
  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Center(child: Text('Detail')));
}
