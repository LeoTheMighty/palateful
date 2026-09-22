import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/import_activity_detail.dart';

/// Base instant for every fixture timestamp in this file.
///
/// `ImportActivityDetail` renders both `created_at` and `updated_at`
/// through `_formatTime` (import_activity_detail.dart:449) — a
/// `DateTime.now()`-relative formatter whose output string changes as
/// the fixture ages ('2h ago' → '3d ago' → '5mo ago' → '4/16/2026').
/// Absolute dates would rot silently here, so anchor to `now`.
/// The base sits 90 minutes back, not 2 hours: every `_formatTime` in
/// play buckets by whole hours, and a base exactly on the 1h/2h boundary
/// made `_at(0)` render '2h ago' while `_at(5)` rendered '1h ago'. At 90
/// minutes every offset used here stays inside one bucket with ~20
/// minutes of headroom, so two fixtures "five minutes apart" also read
/// the same. Nothing asserts these labels today; this keeps the first
/// test that does from being flaky by construction.
final DateTime _fixtureBase =
    DateTime.now().toUtc().subtract(const Duration(minutes: 90));

/// A fixture timestamp `minutesAfterBase` past [_fixtureBase]. Offsets
/// preserve the original fixtures' relative ordering and — where the
/// original had `created_at == updated_at` — their exact equality,
/// which `_buildTimestamps` (import_activity_detail.dart:320) tests to
/// decide whether to render the "Updated …" half of the row at all.
String _at(int minutesAfterBase) =>
    _fixtureBase.add(Duration(minutes: minutesAfterBase)).toIso8601String();

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
        'created_at': _at(0),
        'updated_at': _at(5),
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
        'created_at': _at(0),
        'updated_at': _at(0),
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
        'created_at': _at(0),
        'updated_at': _at(0),
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
        'created_at': _at(0),
        'updated_at': _at(0),
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
        'created_at': _at(0),
        'updated_at': _at(0),
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
        'created_at': _at(0),
        'updated_at': _at(0),
      })));
      await tester.pump();

      expect(find.textContaining('row 12'), findsOneWidget);
    });
  });
}
