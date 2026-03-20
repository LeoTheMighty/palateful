import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/services/api_client.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../chat/chat_service.dart';

class CookModeChatSheet extends StatefulWidget {
  final String recipeId;
  final String recipeName;
  final String recipeContext;

  const CookModeChatSheet({
    super.key,
    required this.recipeId,
    required this.recipeName,
    required this.recipeContext,
  });

  @override
  State<CookModeChatSheet> createState() => _CookModeChatSheetState();
}

class _CookModeChatSheetState extends State<CookModeChatSheet> {
  final _chatService = ChatService(getIt<ApiClient>().dio);
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _speechToText = SpeechToText();

  String? _threadId;
  final List<_SheetMessage> _messages = [];
  bool _isSending = false;
  bool _isListening = false;
  bool _speechAvailable = false;

  @override
  void initState() {
    super.initState();
    _initSpeech();
  }

  Future<void> _initSpeech() async {
    try {
      _speechAvailable = await _speechToText.initialize(
        onError: (_) {
          if (mounted) setState(() => _isListening = false);
        },
        onStatus: (status) {
          if (mounted && (status == 'done' || status == 'notListening')) {
            setState(() => _isListening = false);
          }
        },
      );
    } catch (_) {
      _speechAvailable = false;
    }
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _speechToText.cancel();
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _startListening() {
    if (_isListening) return;
    HapticFeedback.mediumImpact();
    setState(() => _isListening = true);
    _speechToText.listen(
      onResult: _onSpeechResult,
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
    );
  }

  void _stopListening() {
    HapticFeedback.selectionClick();
    _speechToText.stop();
    setState(() => _isListening = false);
  }

  void _onSpeechResult(SpeechRecognitionResult result) {
    if (!mounted) return;
    setState(() => _controller.text = result.recognizedWords);
    if (result.finalResult && result.recognizedWords.isNotEmpty) {
      setState(() => _isListening = false);
      _sendMessage();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isSending) return;

    // Create thread on first message (before clearing input)
    if (_threadId == null) {
      try {
        final thread = await _chatService.createThread(
          title: 'Cooking: ${widget.recipeName}',
        );
        _threadId = thread.id;
      } catch (e) {
        if (mounted) {
          setState(() {
            _messages.add(_SheetMessage(
              role: 'assistant',
              content: 'Error creating chat: $e',
            ));
          });
        }
        return;
      }
    }
    _controller.clear();

    setState(() {
      _messages.add(_SheetMessage(role: 'user', content: text));
      _messages.add(_SheetMessage(
        role: 'assistant',
        content: '',
        isStreaming: true,
      ));
      _isSending = true;
    });
    _scrollToBottom();

    try {
      await for (final event in _chatService.sendMessage(
        _threadId!,
        text,
        recipeContext: widget.recipeContext,
      )) {
        if (!mounted) break;
        switch (event) {
          case TokenEvent(:final content):
            setState(() {
              _messages.last.content += content;
              _messages.last.isToolActivity = false;
            });
            _scrollToBottom();
          case ToolCallEvent(:final name):
            final label = switch (name) {
              'search_recipes' => 'Searching recipes…',
              'add_note_to_recipe' => 'Adding note…',
              'suggest_recipe' => 'Creating recipe…',
              _ => 'Working…',
            };
            setState(() {
              _messages.last.content = label;
              _messages.last.isToolActivity = true;
            });
          case ToolResultEvent():
            setState(() {
              _messages.last.content = '';
              _messages.last.isToolActivity = false;
            });
          case DoneEvent():
            setState(() => _messages.last.isStreaming = false);
          case ErrorEvent(:final message):
            setState(() {
              _messages.last.content = 'Error: $message';
              _messages.last.isStreaming = false;
            });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _messages.last.content = 'Error: $e';
          _messages.last.isStreaming = false;
        });
      }
    }
    if (mounted) setState(() => _isSending = false);
  }

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      heightFactor: 0.7,
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.chocolateDark,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          children: [
            // Drag handle
            Padding(
              padding: const EdgeInsets.only(top: 12, bottom: 8),
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.withOpacity(AppColors.warmIvory, 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),

            // Title
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Text(
                'Ask about ${widget.recipeName}',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.warmIvory,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),

            const Divider(height: 1, color: AppColors.chocolateLight),

            // Messages
            Expanded(
              child: _messages.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Text(
                          'Ask me anything about this recipe!\n\n'
                          '"Can I substitute butter for oil?"\n'
                          '"What temperature should the oven be?"\n'
                          '"What was step 3 again?"',
                          style: TextStyle(
                            color: AppColors.withOpacity(
                                AppColors.warmIvory, 0.5),
                            fontSize: 14,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    )
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.all(16),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) {
                        final msg = _messages[index];
                        return _buildMessage(msg);
                      },
                    ),
            ),

            // Input
            Container(
              padding: const EdgeInsets.fromLTRB(16, 8, 8, 16),
              decoration: BoxDecoration(
                color: AppColors.chocolate,
                border: Border(
                  top: BorderSide(
                    color: AppColors.withOpacity(AppColors.warmIvory, 0.1),
                  ),
                ),
              ),
              child: SafeArea(
                top: false,
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        style: const TextStyle(color: AppColors.warmIvory),
                        decoration: InputDecoration(
                          hintText: _isListening
                              ? 'Listening…'
                              : 'Ask a question…',
                          hintStyle: TextStyle(
                            color: AppColors.withOpacity(
                                AppColors.warmIvory, 0.4),
                          ),
                          filled: true,
                          fillColor: AppColors.chocolateDark,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(24),
                            borderSide: BorderSide.none,
                          ),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 10,
                          ),
                        ),
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                    if (_speechAvailable) ...[
                      const SizedBox(width: 4),
                      IconButton(
                        icon: Icon(
                          _isListening ? Icons.mic : Icons.mic_none,
                          color: _isListening
                              ? AppColors.terracotta
                              : AppColors.warmIvory,
                        ),
                        onPressed: _isSending
                            ? null
                            : (_isListening
                                ? _stopListening
                                : _startListening),
                        style: _isListening
                            ? IconButton.styleFrom(
                                backgroundColor: AppColors.withOpacity(
                                    AppColors.terracotta, 0.2),
                              )
                            : null,
                        tooltip: _isListening ? 'Stop listening' : 'Voice input',
                      ),
                    ],
                    const SizedBox(width: 4),
                    IconButton(
                      icon: const Icon(Icons.send, color: AppColors.terracotta),
                      onPressed: _isSending ? null : _sendMessage,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessage(_SheetMessage msg) {
    final isUser = msg.role == 'user';

    if (msg.isToolActivity) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          children: [
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppColors.terracotta,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              msg.content,
              style: TextStyle(
                color: AppColors.withOpacity(AppColors.warmIvory, 0.6),
                fontSize: 13,
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ),
      );
    }

    if (msg.isStreaming && msg.content.isEmpty) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          children: [
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppColors.terracotta,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              'Thinking…',
              style: TextStyle(
                color: AppColors.withOpacity(AppColors.warmIvory, 0.6),
                fontSize: 13,
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ),
      );
    }

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        decoration: BoxDecoration(
          color: isUser ? AppColors.terracotta : AppColors.chocolate,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          msg.content,
          style: const TextStyle(
            color: AppColors.warmIvory,
            fontSize: 15,
            height: 1.4,
          ),
        ),
      ),
    );
  }
}

class _SheetMessage {
  final String role;
  String content;
  bool isStreaming;
  bool isToolActivity;

  _SheetMessage({
    required this.role,
    required this.content,
    this.isStreaming = false,
    this.isToolActivity = false,
  });
}
