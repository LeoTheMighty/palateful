import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';

import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/admin/admin_metrics_screen.dart';
import 'package:palateful/features/admin/widgets/latency_sparkline.dart';

class _FakeApiClient extends ApiClient {
  _FakeApiClient({
    required this.endpointResponse,
    required this.taskResponse,
  });

  final Map<String, dynamic> endpointResponse;
  final Map<String, dynamic> taskResponse;
  int endpointCalls = 0;
  int taskCalls = 0;
  final List<String> windowsSeen = [];

  @override
  Future<Response> getEndpointMetrics({String window = '24h'}) async {
    endpointCalls++;
    windowsSeen.add(window);
    return Response(
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
      data: endpointResponse,
    );
  }

  @override
  Future<Response> getTaskMetrics({String window = '24h'}) async {
    taskCalls++;
    return Response(
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
      data: taskResponse,
    );
  }
}

Map<String, dynamic> _endpointRow({
  String method = 'GET',
  String path = '/v1/recipes',
  int p95 = 100,
  List<double>? sparkline,
}) {
  return {
    'method': method,
    'normalized_path': path,
    'p50_ms': 50,
    'p95_ms': p95,
    'p99_ms': p95 + 200,
    'count': 10,
    'error_rate': 0.0,
    'sparkline': sparkline ?? List<double>.filled(24, 50.0),
  };
}

Map<String, dynamic> _taskRow({
  String name = 'worker.import.ocr_extract',
  int p95 = 60000,
  double failureRate = 0.12,
  List<double>? sparkline,
}) {
  return {
    'task_name': name,
    'p50_ms': 40000,
    'p95_ms': p95,
    'p99_ms': p95 + 10000,
    'count': 100,
    'failure_rate': failureRate,
    'sparkline': sparkline ?? List<double>.filled(24, 55000.0),
  };
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

  Widget wrap(Widget child) => MaterialApp(home: child);

  testWidgets('loads with 24h window and renders endpoint + task rows',
      (tester) async {
    final fake = _FakeApiClient(
      endpointResponse: {
        'window': '24h',
        'rows': [_endpointRow(path: '/v1/recipes/{recipe_id}', p95: 2100)],
      },
      taskResponse: {
        'window': '24h',
        'rows': [_taskRow()],
      },
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminMetricsScreen()));
    await tester.pumpAndSettle();

    expect(fake.windowsSeen.first, equals('24h'));
    expect(find.textContaining('/v1/recipes/{recipe_id}'), findsOneWidget);
    expect(find.textContaining('worker.import.ocr_extract'), findsOneWidget);
    expect(find.byType(LatencySparkline), findsNWidgets(2));
  });

  testWidgets('empty-state message renders when no rows returned',
      (tester) async {
    final fake = _FakeApiClient(
      endpointResponse: {'window': '24h', 'rows': <Map<String, dynamic>>[]},
      taskResponse: {'window': '24h', 'rows': <Map<String, dynamic>>[]},
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminMetricsScreen()));
    await tester.pumpAndSettle();

    expect(
      find.text('No samples yet — check back after some traffic.'),
      findsNWidgets(2),
    );
  });

  testWidgets('changing window re-queries both endpoints', (tester) async {
    final fake = _FakeApiClient(
      endpointResponse: {'window': '24h', 'rows': <Map<String, dynamic>>[]},
      taskResponse: {'window': '24h', 'rows': <Map<String, dynamic>>[]},
    );
    GetIt.I.registerSingleton<ApiClient>(fake);

    await tester.pumpWidget(wrap(const AdminMetricsScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('1h'));
    await tester.pumpAndSettle();

    expect(fake.endpointCalls, greaterThanOrEqualTo(2));
    expect(fake.windowsSeen.last, equals('1h'));
  });
}
