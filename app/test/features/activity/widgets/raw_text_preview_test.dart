import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/activity/widgets/raw_text_preview.dart';

// irrd-5: RawTextPreview hides its monospaced body behind a "Show / Hide"
// toggle, surfaces a Truncated pill when the server-side preview was
// capped, and copies via the system clipboard.

Widget _wrap(Widget child) =>
    MaterialApp(home: Scaffold(body: child));

void main() {
  testWidgets('empty text renders the "no preview yet" line',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const RawTextPreview(label: 'OCR', text: ''),
    ));
    await tester.pump();

    expect(find.text('OCR: no preview yet'), findsOneWidget);
    expect(find.byIcon(Icons.expand_more), findsNothing);
  });

  testWidgets('starts collapsed, tap expands, tap collapses', (tester) async {
    await tester.pumpWidget(_wrap(
      const RawTextPreview(
        label: 'Parsed text',
        text: '1 cup flour\n2 eggs',
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Show parsed text'), findsOneWidget);
    expect(find.byIcon(Icons.expand_more), findsOneWidget);

    await tester.tap(find.text('Show parsed text'));
    await tester.pumpAndSettle();

    expect(find.text('Hide parsed text'), findsOneWidget);
    expect(find.byIcon(Icons.expand_less), findsOneWidget);
    expect(find.text('1 cup flour\n2 eggs'), findsOneWidget);

    await tester.tap(find.text('Hide parsed text'));
    await tester.pumpAndSettle();

    expect(find.text('Show parsed text'), findsOneWidget);
    expect(find.text('1 cup flour\n2 eggs'), findsNothing);
  });

  testWidgets('truncated=true renders the Truncated pill', (tester) async {
    await tester.pumpWidget(_wrap(
      const RawTextPreview(
        label: 'OCR',
        text: 'abc',
        truncated: true,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Truncated'), findsOneWidget);
  });

  testWidgets('truncated=false hides the Truncated pill', (tester) async {
    await tester.pumpWidget(_wrap(
      const RawTextPreview(
        label: 'OCR',
        text: 'abc',
        truncated: false,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Truncated'), findsNothing);
  });

  testWidgets('copy button writes to clipboard and shows snackbar',
      (tester) async {
    final messages = <MethodCall>[];
    TestWidgetsFlutterBinding.ensureInitialized();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        messages.add(call);
      }
      return null;
    });

    await tester.pumpWidget(_wrap(
      const RawTextPreview(
        label: 'OCR',
        text: 'hello clipboard',
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Show ocr'));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithIcon(IconButton, Icons.copy));
    await tester.pumpAndSettle();

    expect(messages, isNotEmpty);
    final args = messages.first.arguments as Map<Object?, Object?>?;
    expect(args?['text'], 'hello clipboard');
    expect(find.text('Copied'), findsOneWidget);
  });

  testWidgets('semantic label flips on expansion', (tester) async {
    await tester.pumpWidget(_wrap(
      const RawTextPreview(
        label: 'OCR',
        text: 'five bytes',
      ),
    ));
    await tester.pumpAndSettle();

    expect(
      find.byWidgetPredicate(
        (w) => w is Semantics && w.properties.label == 'Show ocr',
      ),
      findsOneWidget,
    );

    await tester.tap(find.text('Show ocr'));
    await tester.pumpAndSettle();

    // Expanded: label includes char count.
    expect(
      find.byWidgetPredicate(
        (w) =>
            w is Semantics &&
            w.properties.label == 'OCR · 10 characters',
      ),
      findsOneWidget,
    );
  });
}
