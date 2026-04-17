import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/import_activity_detail.dart';

Widget _host(Widget child) => MaterialApp(
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

void main() {
  group('ImportActivityDetail', () {
    testWidgets('renders error row for failed items with Show more toggle',
        (tester) async {
      final longError = 'A ' * 200; // > two-line preview
      await tester.pumpWidget(_host(ImportActivityDetail(item: {
        'id': 'i-1',
        'status': 'failed',
        'error_message': longError,
        'source_type': 'url',
        'source_url': 'https://example.com/recipe',
        'retry_count': 2,
        'created_at': '2026-04-16T12:00:00Z',
        'updated_at': '2026-04-16T12:05:00Z',
      })));
      await tester.pump();

      expect(find.text('Error'), findsOneWidget);
      expect(find.text('Show more'), findsOneWidget);
      expect(find.text('Show less'), findsNothing);

      await tester.tap(find.text('Show more'));
      await tester.pump();

      expect(find.text('Show less'), findsOneWidget);
    });

    testWidgets('no error row when error_message is null', (tester) async {
      await tester.pumpWidget(_host(ImportActivityDetail(item: {
        'id': 'i-1',
        'status': 'completed',
        'source_type': 'url',
        'source_url': 'https://example.com/recipe',
        'retry_count': 0,
        'created_at': '2026-04-16T12:00:00Z',
        'updated_at': '2026-04-16T12:00:00Z',
      })));
      await tester.pump();

      expect(find.text('Error'), findsNothing);
      expect(find.textContaining('URL'), findsOneWidget);
      expect(find.text('Stage'), findsOneWidget);
    });

    testWidgets('retry row hidden when retry_count is 0', (tester) async {
      await tester.pumpWidget(_host(ImportActivityDetail(item: {
        'id': 'i-1',
        'status': 'completed',
        'source_type': 'url',
        'source_url': 'https://example.com/recipe',
        'retry_count': 0,
        'created_at': '2026-04-16T12:00:00Z',
        'updated_at': '2026-04-16T12:00:00Z',
      })));
      await tester.pump();

      expect(find.textContaining('Retries'), findsNothing);
    });

    testWidgets('retry row visible when retry_count > 0', (tester) async {
      await tester.pumpWidget(_host(ImportActivityDetail(item: {
        'id': 'i-1',
        'status': 'failed',
        'error_message': 'boom',
        'source_type': 'url',
        'retry_count': 3,
        'created_at': '2026-04-16T12:00:00Z',
        'updated_at': '2026-04-16T12:00:00Z',
      })));
      await tester.pump();

      expect(find.text('Retries: 3'), findsOneWidget);
    });

    testWidgets('short error message has no Show more', (tester) async {
      await tester.pumpWidget(_host(ImportActivityDetail(item: {
        'id': 'i-1',
        'status': 'failed',
        'error_message': 'nope',
        'source_type': 'url',
        'retry_count': 0,
        'created_at': '2026-04-16T12:00:00Z',
        'updated_at': '2026-04-16T12:00:00Z',
      })));
      await tester.pump();

      expect(find.text('nope'), findsOneWidget);
      expect(find.text('Show more'), findsNothing);
    });

    testWidgets('empty item map renders nothing', (tester) async {
      await tester.pumpWidget(_host(const ImportActivityDetail(item: {})));
      await tester.pump();

      expect(find.text('Error'), findsNothing);
      expect(find.text('Stage'), findsNothing);
    });

    testWidgets('source_reference surfaces when present', (tester) async {
      await tester.pumpWidget(_host(ImportActivityDetail(item: {
        'id': 'i-1',
        'status': 'extracting',
        'source_type': 'spreadsheet',
        'source_reference': 'row 12',
        'retry_count': 0,
        'created_at': '2026-04-16T12:00:00Z',
        'updated_at': '2026-04-16T12:00:00Z',
      })));
      await tester.pump();

      expect(find.textContaining('row 12'), findsOneWidget);
    });
  });
}
