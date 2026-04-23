import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';

import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/admin/admin_client_metrics_tab.dart';

class _FakeApiClient extends ApiClient {
  _FakeApiClient();

  // Call recorders keyed by endpoint.
  final List<Map<String, String?>> routeCalls = [];
  final List<Map<String, String?>> endpointCalls = [];
  final List<Map<String, String?>> jankCalls = [];
  final List<Map<String, String?>> sparklineCalls = [];

  Map<String, dynamic> routesResponse = {
    'window': '24h',
    'rows': <Map<String, dynamic>>[],
  };
  Map<String, dynamic> endpointsResponse = {
    'window': '24h',
    'rows': <Map<String, dynamic>>[],
  };
  Map<String, dynamic> jankResponse = {
    'window': '24h',
    'rows': <Map<String, dynamic>>[],
  };
  Map<String, List<double>> sparklineByMetric = {
    'app_start': List<double>.filled(24, 0.0),
    'route_paint': List<double>.filled(24, 0.0),
    'network_request': List<double>.filled(24, 0.0),
    'frame_jank_p95': List<double>.filled(24, 0.0),
  };

  Response _wrap(Map<String, dynamic> data) => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: data,
      );

  @override
  Future<Response> getClientRouteMetrics({
    String window = '24h',
    String? platform,
    String? appVersion,
    String? route,
  }) async {
    routeCalls.add({
      'window': window,
      'platform': platform,
      'app_version': appVersion,
      'route': route,
    });
    return _wrap(routesResponse);
  }

  @override
  Future<Response> getClientEndpointMetrics({
    String window = '24h',
    String? platform,
    String? appVersion,
    String? route,
  }) async {
    endpointCalls.add({
      'window': window,
      'platform': platform,
      'app_version': appVersion,
      'route': route,
    });
    return _wrap(endpointsResponse);
  }

  @override
  Future<Response> getClientJankMetrics({
    String window = '24h',
    String? platform,
    String? appVersion,
    String? route,
  }) async {
    jankCalls.add({
      'window': window,
      'platform': platform,
      'app_version': appVersion,
      'route': route,
    });
    return _wrap(jankResponse);
  }

  @override
  Future<Response> getClientSparkline({
    required String metric,
    String window = '24h',
    String? platform,
    String? appVersion,
    String? route,
    String? endpoint,
  }) async {
    sparklineCalls.add({
      'metric': metric,
      'window': window,
      'platform': platform,
      'app_version': appVersion,
      'route': route,
      'endpoint': endpoint,
    });
    return _wrap({
      'metric': metric,
      'window': window,
      'bucket_seconds': 3600,
      'buckets': sparklineByMetric[metric] ?? List<double>.filled(24, 0.0),
    });
  }
}

void _setTallViewport(WidgetTester tester) {
  // Tall viewport so the full Client tab (stat cards + 3 tables) renders
  // without ListView lazy-building chopping off the bottom.
  tester.view.physicalSize = const Size(1200, 3000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    await dotenv.load(mergeWith: {'API_BASE_URL': 'http://localhost:8000'});
  });

  setUp(() {
    if (GetIt.I.isRegistered<ApiClient>()) {
      GetIt.I.unregister<ApiClient>();
    }
  });

  Widget wrap(Widget child) => MaterialApp(
        home: Scaffold(body: child),
      );

  testWidgets('fetches all four client endpoints on mount', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    expect(fake.routeCalls, hasLength(1));
    expect(fake.endpointCalls, hasLength(1));
    expect(fake.jankCalls, hasLength(1));
    // One sparkline call per metric (cold-start, route-paint, network, jank).
    expect(fake.sparklineCalls, hasLength(4));
    final metrics = fake.sparklineCalls.map((c) => c['metric']).toSet();
    expect(
      metrics,
      equals({'app_start', 'route_paint', 'network_request', 'frame_jank_p95'}),
    );
    // Default window is 24h, platform filter is unset.
    expect(fake.routeCalls.first['window'], '24h');
    expect(fake.routeCalls.first['platform'], isNull);
  });

  testWidgets('renders stat card labels', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    expect(find.text('Cold-start (peak)'), findsOneWidget);
    expect(find.text('Route paint p95 (worst)'), findsOneWidget);
    expect(find.text('Network p95 (worst)'), findsOneWidget);
    expect(find.text('Jank build p95 (worst)'), findsOneWidget);
  });

  testWidgets('renders three drilldown section headers', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    expect(find.text('Routes'), findsOneWidget);
    expect(find.text('Endpoints'), findsOneWidget);
    expect(find.text('Frame jank'), findsOneWidget);
  });

  testWidgets('binds route row data into the routes table', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    fake.routesResponse = {
      'window': '24h',
      'rows': [
        {
          'route': '/books/list',
          'p50_ms': 120,
          'p95_ms': 450,
          'p99_ms': 900,
          'count': 42,
        },
      ],
    };
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    expect(find.text('/books/list'), findsOneWidget);
    expect(find.text('450'), findsWidgets);
  });

  testWidgets('binds endpoint row data into the endpoints table',
      (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    fake.endpointsResponse = {
      'window': '24h',
      'rows': [
        {
          'method': 'GET',
          'endpoint': '/v1/books/foo',
          'p50_ms': 85,
          'p95_ms': 320,
          'p99_ms': 780,
          'count': 512,
        },
      ],
    };
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    expect(find.textContaining('GET /v1/books/foo'), findsOneWidget);
  });

  testWidgets('binds jank row data into the jank table', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    fake.jankResponse = {
      'window': '24h',
      'rows': [
        {
          'route': '/profile',
          'build_p95_ms': 28,
          'raster_p95_ms': 11,
          'count': 1337,
        },
      ],
    };
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    expect(find.text('/profile'), findsOneWidget);
    expect(find.text('28'), findsWidgets);
  });

  testWidgets('stat card shows max p95 across route rows', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    fake.routesResponse = {
      'window': '24h',
      'rows': [
        {
          'route': '/home',
          'p50_ms': 100,
          'p95_ms': 300,
          'p99_ms': 500,
          'count': 10,
        },
        {
          'route': '/books/:id',
          'p50_ms': 150,
          'p95_ms': 1100,
          'p99_ms': 1500,
          'count': 5,
        },
      ],
    };
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    // Worst route p95 is 1100 ms.
    expect(find.text('1100 ms'), findsOneWidget);
  });

  testWidgets('switching platform re-queries with the filter', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    expect(fake.routeCalls, hasLength(1));
    expect(fake.routeCalls.first['platform'], isNull);

    await tester.tap(find.text('iOS'));
    await tester.pumpAndSettle();

    expect(fake.routeCalls.length, greaterThanOrEqualTo(2));
    expect(fake.routeCalls.last['platform'], equals('ios'));
  });

  testWidgets('app_version filter is forwarded on Apply', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextField, 'app_version'),
      '1.0.55+68',
    );
    await tester.tap(find.text('Apply'));
    await tester.pumpAndSettle();

    expect(fake.routeCalls.last['app_version'], equals('1.0.55+68'));
  });

  testWidgets('30d window re-queries with 30d', (tester) async {
    _setTallViewport(tester);
    final fake = _FakeApiClient();
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminClientMetricsTab()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('30d'));
    await tester.pumpAndSettle();

    expect(fake.routeCalls.last['window'], equals('30d'));
  });
}
