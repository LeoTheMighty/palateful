import 'dart:convert';

import 'package:dio/dio.dart';

sealed class ChatEvent {}

class TokenEvent extends ChatEvent {
  final String content;
  TokenEvent(this.content);
}

class ToolCallEvent extends ChatEvent {
  final String name;
  ToolCallEvent(this.name);
}

class RecipeResult {
  final String id;
  final String name;
  final String? recipeBookName;
  final int? totalTime;
  final double? relevanceScore;

  RecipeResult({
    required this.id,
    required this.name,
    this.recipeBookName,
    this.totalTime,
    this.relevanceScore,
  });

  factory RecipeResult.fromJson(Map<String, dynamic> json) => RecipeResult(
        id: json['id'] as String,
        name: json['name'] as String,
        recipeBookName: json['recipe_book_name'] as String?,
        totalTime: json['total_time'] as int?,
        relevanceScore: (json['relevance_score'] as num?)?.toDouble(),
      );
}

class ToolResultEvent extends ChatEvent {
  final String name;
  final List<RecipeResult>? recipes;
  ToolResultEvent(this.name, {this.recipes});
}

class DoneEvent extends ChatEvent {
  final String messageId;
  DoneEvent(this.messageId);
}

class ErrorEvent extends ChatEvent {
  final String message;
  ErrorEvent(this.message);
}

class ChatThread {
  final String id;
  final String? title;
  final DateTime createdAt;
  final int messageCount;
  final String? lastMessage;

  ChatThread({
    required this.id,
    this.title,
    required this.createdAt,
    required this.messageCount,
    this.lastMessage,
  });

  factory ChatThread.fromJson(Map<String, dynamic> json) => ChatThread(
        id: json['id'] as String,
        title: json['title'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        messageCount: json['message_count'] as int? ?? 0,
        lastMessage: json['last_message'] as String?,
      );
}

class ChatMessage {
  final String id;
  final String role;
  final String? content;
  final DateTime createdAt;

  ChatMessage({
    required this.id,
    required this.role,
    this.content,
    required this.createdAt,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id'] as String,
        role: json['role'] as String,
        content: json['content'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class ChatService {
  final Dio _dio;

  ChatService(this._dio);

  Future<ChatThread> createThread({String? title}) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/chat/threads',
      data: {'title': title},
    );
    return ChatThread.fromJson(response.data!);
  }

  Future<List<ChatThread>> listThreads() async {
    final response = await _dio.get<Map<String, dynamic>>('/v1/chat/threads');
    final items = response.data!['items'] as List<dynamic>;
    return items
        .map((e) => ChatThread.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<(ChatThread, List<ChatMessage>)> getThread(String threadId) async {
    final response =
        await _dio.get<Map<String, dynamic>>('/v1/chat/threads/$threadId');
    final data = response.data!;
    final thread = ChatThread.fromJson(data);
    final messages = (data['messages'] as List<dynamic>)
        .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
        .toList();
    return (thread, messages);
  }

  Future<void> deleteThread(String threadId) async {
    await _dio.delete('/v1/chat/threads/$threadId');
  }

  Stream<ChatEvent> sendMessage(String threadId, String text,
      {String? recipeContext}) async* {
    final response = await _dio.post(
      '/v1/chat/threads/$threadId/messages',
      data: {
        'message': text,
        if (recipeContext != null) 'recipe_context': recipeContext,
      },
      options: Options(responseType: ResponseType.stream),
    );

    final stream = (response.data as ResponseBody).stream;
    final buffer = StringBuffer();

    await for (final chunk in stream) {
      buffer.write(utf8.decode(chunk));
      final raw = buffer.toString();

      // SSE events are delimited by double newline.
      // Only consume complete events; retain any trailing partial event.
      final lastDelimiter = raw.lastIndexOf('\n\n');
      if (lastDelimiter == -1) continue; // no complete event yet

      final complete = raw.substring(0, lastDelimiter + 2);
      buffer.clear();
      buffer.write(raw.substring(lastDelimiter + 2)); // keep partial tail

      for (final part in complete.split('\n\n')) {
        final trimmed = part.trim();
        if (!trimmed.startsWith('data: ')) continue;
        final jsonStr = trimmed.substring(6).trim();
        if (jsonStr.isEmpty) continue;

        final data = jsonDecode(jsonStr) as Map<String, dynamic>;
        switch (data['type'] as String?) {
          case 'token':
            yield TokenEvent(data['content'] as String);
          case 'tool_call':
            yield ToolCallEvent(data['name'] as String);
          case 'tool_result':
            final recipesRaw = data['recipes'] as List<dynamic>?;
            final recipes = recipesRaw
                ?.map((e) => RecipeResult.fromJson(e as Map<String, dynamic>))
                .toList();
            yield ToolResultEvent(data['name'] as String, recipes: recipes);
          case 'done':
            yield DoneEvent(data['message_id'] as String);
          case 'error':
            yield ErrorEvent(data['message'] as String? ?? 'Unknown error');
        }
      }
    }
  }
}
