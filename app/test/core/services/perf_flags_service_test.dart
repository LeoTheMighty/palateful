import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/perf_flags_service.dart';

/// Stub HttpClientAdapter that returns whatever JSON the handler supplies,
/// or delays past the test's fetch-timeout to simulate a slow endpoint.
class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this._handler);

  final Future<ResponseBody> Function(RequestOptions) _handler;
  final List<String> calls = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls.add(options.path);
    return _handler(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody _jsonBody(Map<String, Object?> payload, {int statusCode = 200}) {
  final bytes = utf8.encode(jsonEncode(payload));
  return ResponseBody.fromBytes(
    bytes,
    statusCode,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );
}

Dio _dioWith(_StubAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.example'));
  dio.httpClientAdapter = adapter;
  return dio;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('defaults default-on before first fetch completes', () {
    final adapter = _StubAdapter((_) async => _jsonBody({
          'ingest_enabled': false,
          'sampling_rate': 0.1,
        }));
    final service = PerfFlagsService.withDio(_dioWith(adapter));
    expect(service.ingestEnabled, isTrue);
    expect(service.samplingRate, 1.0);
    service.dispose();
  });

  test('initialize populates values from the endpoint', () async {
    final adapter = _StubAdapter((_) async => _jsonBody({
          'ingest_enabled': false,
          'sampling_rate': 0.25,
        }));
    final service = PerfFlagsService.withDio(_dioWith(adapter));
    await service.initialize();

    expect(adapter.calls, ['/v1/flags/perf']);
    expect(service.ingestEnabled, isFalse);
    expect(service.samplingRate, 0.25);
    service.dispose();
  });

  test('initialize swallows 500 errors and keeps default-on state', () async {
    final adapter = _StubAdapter((_) async => _jsonBody(
          {'error': 'boom'},
          statusCode: 500,
        ));
    final service = PerfFlagsService.withDio(_dioWith(adapter));
    await service.initialize();
    expect(service.ingestEnabled, isTrue);
    expect(service.samplingRate, 1.0);
    service.dispose();
  });

  test(
    'initialize times out past fetchTimeout without blocking boot',
    () async {
      final adapter = _StubAdapter((_) async {
        // Simulate an endpoint that never answers within the window.
        await Future<void>.delayed(const Duration(seconds: 5));
        return _jsonBody({'ingest_enabled': false, 'sampling_rate': 0.0});
      });
      final service = PerfFlagsService.withDio(
        _dioWith(adapter),
        fetchTimeout: const Duration(milliseconds: 50),
      );
      final stopwatch = Stopwatch()..start();
      await service.initialize();
      stopwatch.stop();
      expect(stopwatch.elapsed, lessThan(const Duration(milliseconds: 500)));
      expect(service.ingestEnabled, isTrue);
      expect(service.samplingRate, 1.0);
      service.dispose();
    },
  );

  test(
    'refresh loop re-fetches every refreshInterval and dispose stops it',
    () async {
      var hits = 0;
      final adapter = _StubAdapter((_) async {
        hits++;
        return _jsonBody({
          'ingest_enabled': hits.isEven,
          'sampling_rate': 1.0,
        });
      });
      final service = PerfFlagsService.withDio(
        _dioWith(adapter),
        refreshInterval: const Duration(milliseconds: 30),
      );
      await service.initialize();
      expect(hits, 1);

      // Let the periodic timer tick twice — 30ms × 2 = 60ms with slack.
      await Future<void>.delayed(const Duration(milliseconds: 110));
      expect(hits, greaterThanOrEqualTo(3));

      service.dispose();
      final stopped = hits;
      await Future<void>.delayed(const Duration(milliseconds: 120));
      expect(hits, stopped, reason: 'dispose cancels the refresh timer');
    },
  );

  test('malformed sampling_rate (out of range) is ignored', () async {
    final adapter = _StubAdapter((_) async => _jsonBody({
          'ingest_enabled': false,
          'sampling_rate': 2.5, // invalid
        }));
    final service = PerfFlagsService.withDio(_dioWith(adapter));
    await service.initialize();
    expect(service.ingestEnabled, isFalse);
    expect(service.samplingRate, 1.0, reason: 'clamped via ignore');
    service.dispose();
  });
}
