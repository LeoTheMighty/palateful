import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import 'chat_service.dart';

// ---------------------------------------------------------------------------
// Service provider
// ---------------------------------------------------------------------------

final chatServiceProvider = Provider<ChatService>((ref) {
  final apiClient = getIt<ApiClient>();
  return ChatService(apiClient.dio);
});

// ---------------------------------------------------------------------------
// Thread list
// ---------------------------------------------------------------------------

class ThreadListNotifier extends AsyncNotifier<List<ChatThread>> {
  @override
  Future<List<ChatThread>> build() => _fetch();

  Future<List<ChatThread>> _fetch() {
    return ref.read(chatServiceProvider).listThreads();
  }

  Future<ChatThread> createThread({String? title}) async {
    final thread =
        await ref.read(chatServiceProvider).createThread(title: title);
    state = AsyncData([thread, ...state.value ?? []]);
    return thread;
  }

  Future<void> deleteThread(String threadId) async {
    await ref.read(chatServiceProvider).deleteThread(threadId);
    state = AsyncData(
      (state.value ?? []).where((t) => t.id != threadId).toList(),
    );
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_fetch);
  }
}

final threadListProvider =
    AsyncNotifierProvider<ThreadListNotifier, List<ChatThread>>(
  ThreadListNotifier.new,
);

// ---------------------------------------------------------------------------
// Chat message model used by the active chat
// ---------------------------------------------------------------------------

class ActiveChatMessage {
  final String id;
  final String role;
  final String content;
  final bool isStreaming;
  final bool isToolActivity;

  const ActiveChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.isStreaming = false,
    this.isToolActivity = false,
  });

  ActiveChatMessage copyWith({
    String? content,
    bool? isStreaming,
    bool? isToolActivity,
  }) =>
      ActiveChatMessage(
        id: id,
        role: role,
        content: content ?? this.content,
        isStreaming: isStreaming ?? this.isStreaming,
        isToolActivity: isToolActivity ?? this.isToolActivity,
      );
}

// ---------------------------------------------------------------------------
// Active chat notifier
// ---------------------------------------------------------------------------

class ActiveChatNotifier
    extends AsyncNotifier<(String, List<ActiveChatMessage>)> {
  String? _threadId;

  @override
  Future<(String, List<ActiveChatMessage>)> build() async {
    // Start empty — caller sets thread via loadThread()
    return ('', <ActiveChatMessage>[]);
  }

  Future<void> loadThread(String threadId) async {
    _threadId = threadId;
    state = const AsyncLoading();
    final (thread, rawMessages) =
        await ref.read(chatServiceProvider).getThread(threadId);
    final messages = rawMessages
        .map((m) => ActiveChatMessage(
              id: m.id,
              role: m.role,
              content: m.content ?? '',
            ))
        .toList();
    state = AsyncData((thread.id, messages));
  }

  Future<void> sendMessage(String text) async {
    if (_threadId == null) return;
    final current = state.value;
    if (current == null) return;

    final (threadId, messages) = current;

    // Optimistically add user message
    final userMsg = ActiveChatMessage(
      id: 'temp-user-${DateTime.now().millisecondsSinceEpoch}',
      role: 'user',
      content: text,
    );
    // Add streaming placeholder for assistant
    final assistantMsg = ActiveChatMessage(
      id: 'temp-ai-${DateTime.now().millisecondsSinceEpoch}',
      role: 'assistant',
      content: '',
      isStreaming: true,
    );
    state = AsyncData((threadId, [...messages, userMsg, assistantMsg]));

    try {
      await for (final event in ref
          .read(chatServiceProvider)
          .sendMessage(_threadId!, text)) {
        final cur = state.value;
        if (cur == null) break;
        final (tid, msgs) = cur;

        switch (event) {
          case TokenEvent(:final content):
            final updated = msgs.map((m) {
              if (m.id == assistantMsg.id) {
                return m.copyWith(
                  content: m.content + content,
                  isToolActivity: false,
                );
              }
              return m;
            }).toList();
            state = AsyncData((tid, updated));

          case ToolCallEvent():
            final updated = msgs.map((m) {
              if (m.id == assistantMsg.id) {
                return m.copyWith(
                  content: 'Searching recipes…',
                  isToolActivity: true,
                );
              }
              return m;
            }).toList();
            state = AsyncData((tid, updated));

          case ToolResultEvent():
            // Tool result received — keep tool activity indicator until tokens stream
            break;

          case DoneEvent(:final messageId):
            final updated = msgs.map((m) {
              if (m.id == assistantMsg.id) {
                return ActiveChatMessage(
                  id: messageId,
                  role: 'assistant',
                  content: m.content,
                  isStreaming: false,
                );
              }
              return m;
            }).toList();
            state = AsyncData((tid, updated));

          case ErrorEvent(:final message):
            final updated = msgs.map((m) {
              if (m.id == assistantMsg.id) {
                return m.copyWith(
                  content: 'Error: $message',
                  isStreaming: false,
                  isToolActivity: false,
                );
              }
              return m;
            }).toList();
            state = AsyncData((tid, updated));
        }
      }
    } catch (e) {
      final cur = state.value;
      if (cur != null) {
        final (tid, msgs) = cur;
        final updated = msgs.map((m) {
          if (m.id == assistantMsg.id) {
            return m.copyWith(
              content: 'Error: $e',
              isStreaming: false,
            );
          }
          return m;
        }).toList();
        state = AsyncData((tid, updated));
      }
    }
  }
}

final activeChatProvider =
    AsyncNotifierProvider<ActiveChatNotifier, (String, List<ActiveChatMessage>)>(
  ActiveChatNotifier.new,
);
