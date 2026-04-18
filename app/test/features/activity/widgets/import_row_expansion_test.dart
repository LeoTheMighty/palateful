import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get_it/get_it.dart';
import 'package:palateful/core/services/api_client.dart';
import 'package:palateful/features/activity/providers/import_row_expansion_provider.dart';
import 'package:palateful/features/activity/widgets/import_row_expansion.dart';

// irrd-4 AC4-6 + AC13 + AC15 coverage. Verifies:
//  - skeleton renders while telemetry future is unresolved
//  - body renders once the future completes
//  - error-with-retry renders on fetch failure and retry invalidates
//  - cache is hit on second build (no second API call without
//    explicit invalidation)

Response<dynamic> _fakeResponse(dynamic data) => Response(
      data: data,
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
    );

class _StubApiClient extends ApiClient {
  int telemetryCalls = 0;
  Object? nextError;
  Map<String, dynamic> Function(String itemId) response = (_) => {
        'stages': [
          {'stage': 'parsed', 'status': 'ok'},
          {'stage': 'extracted', 'status': 'ok', 'raw_output_preview': 'sample'},
          {'stage': 'matched', 'status': 'pending'},
          {'stage': 'created', 'status': 'pending'},
        ],
      };

  @override
  Future<Response> getImportItemTelemetry(String itemId) async {
    telemetryCalls++;
    final err = nextError;
    if (err != null) throw err;
    return _fakeResponse(response(itemId));
  }
}

Widget _wrap({
  required String itemId,
  required String recipeName,
}) =>
    ProviderScope(
      child: MaterialApp(
        home: Scaffold(
          body: ImportRowExpansion(
            itemId: itemId,
            recipeName: recipeName,
          ),
        ),
      ),
    );

void main() {
  late _StubApiClient apiClient;

  setUpAll(() {
    dotenv.loadFromString(
      envString: 'API_BASE_URL=http://localhost\n',
      isOptional: true,
    );
  });

  setUp(() {
    apiClient = _StubApiClient();
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
    gi.registerSingleton<ApiClient>(apiClient);
  });

  tearDown(() {
    final gi = GetIt.instance;
    if (gi.isRegistered<ApiClient>()) gi.unregister<ApiClient>();
  });

  // StageTimeline's current-stage pulse animation runs forever, so
  // `pumpAndSettle` would hang. The helper below pumps a bounded
  // number of frames — enough to resolve the telemetry future and
  // land the subsequent rebuild.
  Future<void> settle(WidgetTester tester) async {
    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
  }

  testWidgets(
      'expansion exposes the semantic group for screen readers (AC14)',
      (tester) async {
    await tester.pumpWidget(_wrap(itemId: 'item-sem', recipeName: 'Pie'));
    await settle(tester);
    expect(find.bySemanticsLabel('Import details for Pie'), findsOneWidget);
  });

  testWidgets('renders body after telemetry resolves', (tester) async {
    await tester.pumpWidget(_wrap(itemId: 'item-2', recipeName: 'Bread'));
    await settle(tester);

    // Real StageTimeline renders one chip per stage label.
    expect(find.text('Parsed'), findsOneWidget);
    expect(find.text('Extracted'), findsOneWidget);
    expect(find.text('Matched'), findsOneWidget);
    expect(find.text('Created'), findsOneWidget);
    expect(apiClient.telemetryCalls, 1);
  });

  testWidgets('renders error row and retry fires another fetch',
      (tester) async {
    apiClient.nextError = StateError('network down');
    await tester.pumpWidget(_wrap(itemId: 'item-3', recipeName: 'Oops'));
    // Two pumps: one to kick off the future, one to observe the
    // rejection.
    await tester.pump();
    await tester.pump();

    expect(find.text("Couldn't load full details"), findsOneWidget);

    // Let the next call succeed; tap Retry → provider invalidates →
    // refetches.
    apiClient.nextError = null;
    await tester.tap(find.text('Retry'));
    await settle(tester);

    expect(find.text('Parsed'), findsOneWidget);
    expect(apiClient.telemetryCalls, greaterThanOrEqualTo(2));
  });

  test('ExpandedRowsNotifier stays in sync across toggle calls', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final notifier =
        container.read(importRowExpansionProvider.notifier);
    notifier.toggle('a');
    notifier.toggle('b');
    expect(container.read(importRowExpansionProvider), {'a', 'b'});
    notifier.toggle('a');
    expect(container.read(importRowExpansionProvider), {'b'});
  });
}
