import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/core/services/error_reporter.dart';

/// Unit tests for the DioException → backend-mirror parse added so
/// `audit_errors.py --drill client:DioException` shows which server
/// error_code actually fired, not just Dio's generic "validateStatus"
/// boilerplate.
///
/// The parsing lives in [ErrorReporter.buildMirrorPayload] — pure,
/// side-effect-free, hence unit-testable without driving the mirror
/// POST (which is intentionally no-op'd under `flutter test`).
void main() {
  DioException buildDioException({
    String method = 'POST',
    String path = '/v1/recipe-books/abc/import',
    int? statusCode = 400,
    Object? responseBody,
    String? dioMessage,
  }) {
    final reqOpts = RequestOptions(path: path, method: method);
    return DioException(
      requestOptions: reqOpts,
      response: statusCode != null
          ? Response<dynamic>(
              requestOptions: reqOpts,
              statusCode: statusCode,
              data: responseBody,
            )
          : null,
      type: DioExceptionType.badResponse,
      message: dioMessage,
    );
  }

  group('buildMirrorPayload — DioException with FastAPI envelope', () {
    test('extracts server error_code + error_message and surfaces both', () {
      final err = buildDioException(
        responseBody: {
          'error_code': 37,
          'error_message': 'URL is required for url source type',
          'data': <String, dynamic>{},
        },
        dioMessage: 'validateStatus...',
      );

      final payload = ErrorReporter.buildMirrorPayload(err);

      expect(payload.errorType, 'DioException');
      expect(payload.statusCode, 400);
      expect(payload.extras['http.method'], 'POST');
      expect(payload.extras['http.path'], '/v1/recipe-books/abc/import');
      expect(payload.extras['server.error_code'], 37);
      // Message carries both status + code + server detail — that's the
      // whole point: triage should not need to open the row.
      expect(payload.errorMessage, contains('POST /v1/recipe-books/abc/import'));
      expect(payload.errorMessage, contains('→ 400'));
      expect(payload.errorMessage, contains('[code=37]'));
      expect(
        payload.errorMessage,
        contains('URL is required for url source type'),
      );
      // Dio's generic message must NOT appear once the server's
      // error_message is present — it's the boilerplate we're trying
      // to replace.
      expect(payload.errorMessage, isNot(contains('validateStatus')));
    });

    test('falls back to Dio message when server body is not a map', () {
      final err = buildDioException(
        responseBody: '<html>502 Bad Gateway</html>',
        dioMessage: 'Connection error',
      );

      final payload = ErrorReporter.buildMirrorPayload(err);

      expect(payload.extras.containsKey('server.error_code'), isFalse);
      // No [code=…] part when the server didn't give us one.
      expect(payload.errorMessage, isNot(contains('[code=')));
      expect(payload.errorMessage, contains('Connection error'));
    });

    test('null body + null status does not crash', () {
      final err = DioException(
        requestOptions: RequestOptions(path: '/v1/some/path'),
        type: DioExceptionType.connectionError,
        message: 'Network unreachable',
      );

      final payload = ErrorReporter.buildMirrorPayload(err);

      expect(payload.errorType, 'DioException');
      expect(payload.statusCode, isNull);
      expect(payload.extras['http.path'], '/v1/some/path');
      expect(payload.extras.containsKey('server.error_code'), isFalse);
    });

    test('non-int error_code is ignored defensively', () {
      final err = buildDioException(
        responseBody: {
          // Shouldn't happen, but a misbehaving gateway could send a
          // string. Don't crash; just omit the field.
          'error_code': 'not-a-number',
          'error_message': 'some message',
        },
      );

      final payload = ErrorReporter.buildMirrorPayload(err);

      expect(payload.extras.containsKey('server.error_code'), isFalse);
      // error_message still surfaces.
      expect(payload.errorMessage, contains('some message'));
    });

    test('empty error_message string does not poison the mirror detail', () {
      final err = buildDioException(
        responseBody: {
          'error_code': 42,
          'error_message': '',
        },
        dioMessage: 'Dio fallback detail',
      );

      final payload = ErrorReporter.buildMirrorPayload(err);

      // Empty server message → fall back to Dio's message, and still
      // surface the code so triage keeps the signal.
      expect(payload.errorMessage, contains('[code=42]'));
      expect(payload.errorMessage, contains('Dio fallback detail'));
    });
  });

  group('buildMirrorPayload — non-Dio', () {
    test('falls through to runtimeType + toString', () {
      final err = StateError('bad state');
      final payload = ErrorReporter.buildMirrorPayload(err);

      expect(payload.errorType, 'StateError');
      expect(payload.errorMessage, contains('bad state'));
      expect(payload.statusCode, isNull);
      expect(payload.extras, isEmpty);
    });
  });

  group('buildMirrorPayload — seedExtras merging', () {
    test('caller-supplied extras are preserved alongside parsed fields', () {
      final err = buildDioException(
        responseBody: {'error_code': 168, 'error_message': 'bad source'},
      );
      final payload = ErrorReporter.buildMirrorPayload(
        err,
        seedExtras: {'caller.context': 'import.url.submit'},
      );
      expect(payload.extras['caller.context'], 'import.url.submit');
      expect(payload.extras['server.error_code'], 168);
      expect(payload.extras['http.method'], 'POST');
    });
  });
}
