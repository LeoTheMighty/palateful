import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/chat/chat_provider.dart';
import 'package:palateful/features/chat/chat_screen.dart';
import 'package:palateful/features/chat/widgets/message_bubble.dart';

// ---------------------------------------------------------------------------
// Fake notifier — extends ActiveChatNotifier, overrides build() and actions
// ---------------------------------------------------------------------------

class _FakeActiveChatNotifier extends ActiveChatNotifier {
  final List<ActiveChatMessage> initialMessages;

  _FakeActiveChatNotifier({this.initialMessages = const []});

  @override
  Future<(String, List<ActiveChatMessage>)> build() async {
    return ('thread-123', List<ActiveChatMessage>.from(initialMessages));
  }

  @override
  Future<void> loadThread(String threadId) async {
    // Pre-loaded — no-op
  }

  @override
  Future<void> sendMessage(String text) async {
    final current = state.value;
    if (current == null) return;
    final (tid, msgs) = current;
    state = AsyncData((
      tid,
      [
        ...msgs,
        ActiveChatMessage(
          id: 'user-${DateTime.now().millisecondsSinceEpoch}',
          role: 'user',
          content: text,
        ),
      ],
    ));
  }
}

Widget _buildTestApp({
  List<ActiveChatMessage> messages = const [],
}) {
  return ProviderScope(
    overrides: [
      activeChatProvider.overrideWith(
          () => _FakeActiveChatNotifier(initialMessages: messages)),
    ],
    child: const MaterialApp(
      home: ChatScreen(threadId: 'thread-123'),
    ),
  );
}

void main() {
  group('ChatScreen', () {
    testWidgets('renders AppBar with correct title', (tester) async {
      await tester.pumpWidget(_buildTestApp());
      await tester.pump();

      expect(find.text('AI Assistant'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('renders message bubbles when messages exist', (tester) async {
      final messages = [
        ActiveChatMessage(id: '1', role: 'user', content: 'Hello AI'),
        ActiveChatMessage(
            id: '2', role: 'assistant', content: 'Hello! How can I help?'),
      ];
      await tester.pumpWidget(_buildTestApp(messages: messages));
      await tester.pump();

      expect(find.byType(MessageBubble), findsNWidgets(2));
      expect(find.text('Hello AI'), findsOneWidget);
      expect(find.text('Hello! How can I help?'), findsOneWidget);
    });

    testWidgets('send button is present', (tester) async {
      await tester.pumpWidget(_buildTestApp());
      await tester.pump();

      expect(find.byIcon(Icons.send), findsOneWidget);
    });

    testWidgets('typing and sending adds user message bubble', (tester) async {
      await tester.pumpWidget(_buildTestApp());
      await tester.pump();

      await tester.enterText(find.byType(TextField), 'Find me pasta');
      await tester.pump();

      await tester.tap(find.byType(IconButton));
      await tester.pumpAndSettle();

      expect(find.text('Find me pasta'), findsOneWidget);
    });

    testWidgets('streaming message shows typing indicator', (tester) async {
      final messages = [
        ActiveChatMessage(
            id: '1', role: 'assistant', content: '', isStreaming: true),
      ];
      await tester.pumpWidget(_buildTestApp(messages: messages));
      await tester.pump();

      expect(find.text('Thinking…'), findsOneWidget);
    });

    testWidgets('tool activity shows searching indicator', (tester) async {
      final messages = [
        ActiveChatMessage(
          id: '1',
          role: 'assistant',
          content: 'Searching recipes…',
          isToolActivity: true,
        ),
      ];
      await tester.pumpWidget(_buildTestApp(messages: messages));
      await tester.pump();

      expect(find.text('Searching recipes…'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsWidgets);
    });
  });
}
