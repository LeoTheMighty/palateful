import 'package:flutter/material.dart';

import '../../../core/services/api_client.dart';
import '../services/feedback_cache_service.dart';

/// Bottom sheet that lets the user send a one-off note to the admin.
///
/// Modelled on `PostCookFeedbackSheet`: bottom-pinned, Material text
/// field, send button with spinner while submission is in flight. Writes
/// to the admin-inbox endpoint when online; falls back to the offline
/// queue via [FeedbackCacheService] when `isOffline` is true (or the
/// network call throws).
class FeedbackSheet extends StatefulWidget {
  final ApiClient? apiClient;
  final FeedbackCacheService cache;
  final bool isOffline;

  /// Called after the user taps Send. Receives `true` if the submission
  /// was sent online, `false` if it was queued offline. Parent decides
  /// which snackbar copy to show — keeps this widget context-agnostic.
  final ValueChanged<bool> onComplete;

  /// Snapshot of the route the user was on when they tapped "Send
  /// Feedback". Included in the context envelope so the admin can see
  /// where the complaint came from.
  final String? currentRoute;

  /// Platform / app_version captured by the caller. Optional —
  /// the widget doesn't resolve them itself so tests can inject.
  final String? platform;
  final String? appVersion;

  const FeedbackSheet({
    super.key,
    this.apiClient,
    required this.cache,
    required this.isOffline,
    required this.onComplete,
    this.currentRoute,
    this.platform,
    this.appVersion,
  });

  @override
  State<FeedbackSheet> createState() => _FeedbackSheetState();
}

class _FeedbackSheetState extends State<FeedbackSheet> {
  static const int _maxLength = 4000;
  static const int _warnLength = 3900;
  static const List<String> _categories = [
    'bug',
    'idea',
    'praise',
    'other',
  ];

  final _bodyController = TextEditingController();
  String? _category;
  bool _isSending = false;

  @override
  void initState() {
    super.initState();
    _bodyController.addListener(_onBodyChanged);
  }

  @override
  void dispose() {
    _bodyController.removeListener(_onBodyChanged);
    _bodyController.dispose();
    super.dispose();
  }

  void _onBodyChanged() {
    // Rebuild so the character counter + Send enabled state refresh.
    setState(() {});
  }

  bool get _canSend {
    final trimmed = _bodyController.text.trim();
    return !_isSending &&
        trimmed.isNotEmpty &&
        trimmed.length <= _maxLength;
  }

  Map<String, dynamic>? _buildContext() {
    final ctx = <String, dynamic>{};
    if (widget.appVersion != null) ctx['app_version'] = widget.appVersion;
    if (widget.platform != null) ctx['platform'] = widget.platform;
    if (widget.currentRoute != null) ctx['route'] = widget.currentRoute;
    return ctx.isEmpty ? null : ctx;
  }

  Future<void> _submit() async {
    final body = _bodyController.text.trim();
    if (body.isEmpty) return;

    setState(() => _isSending = true);
    final ctx = _buildContext();

    // If we're already offline, skip the network attempt entirely — queue
    // and return. If we're online, try the network and on any failure
    // (network / non-2xx / api client missing) fall back to the queue.
    if (widget.isOffline || widget.apiClient == null) {
      await widget.cache.queueFeedback(
        body: body,
        category: _category,
        context: ctx,
      );
      if (!mounted) return;
      setState(() => _isSending = false);
      widget.onComplete(false);
      return;
    }

    try {
      await widget.apiClient!.submitFeedback(
        body: body,
        category: _category,
        context: ctx,
      );
      if (!mounted) return;
      setState(() => _isSending = false);
      widget.onComplete(true);
    } catch (_) {
      // Treat any error as "queue for retry" — matches the PostCookFeedback
      // fallback. The 401 refresh interceptor retries once before we land
      // here, so at this point the request genuinely couldn't be sent.
      await widget.cache.queueFeedback(
        body: body,
        category: _category,
        context: ctx,
      );
      if (!mounted) return;
      setState(() => _isSending = false);
      widget.onComplete(false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final length = _bodyController.text.length;
    final over = length > _maxLength;
    final warn = length > _warnLength;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        24,
        20,
        24,
        MediaQuery.of(context).viewInsets.bottom + 36,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Drag handle (visual only)
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: colorScheme.onSurface.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 20),
          Center(
            child: Text(
              'Send feedback',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: colorScheme.onSurface,
              ),
            ),
          ),
          const SizedBox(height: 4),
          Center(
            child: Text(
              'Your note goes straight to the team.',
              style: TextStyle(
                fontSize: 13,
                color: colorScheme.onSurface.withValues(alpha: 0.65),
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Category dropdown
          DropdownButtonFormField<String?>(
            key: const Key('feedback_category_dropdown'),
            initialValue: _category,
            decoration: InputDecoration(
              labelText: 'Category (optional)',
              enabledBorder: OutlineInputBorder(
                borderSide:
                    BorderSide(color: colorScheme.primaryContainer),
                borderRadius: BorderRadius.circular(8),
              ),
              focusedBorder: OutlineInputBorder(
                borderSide: BorderSide(color: colorScheme.tertiary),
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            items: [
              const DropdownMenuItem<String?>(
                value: null,
                child: Text('—'),
              ),
              ..._categories.map(
                (c) => DropdownMenuItem<String?>(
                  value: c,
                  child: Text(c[0].toUpperCase() + c.substring(1)),
                ),
              ),
            ],
            onChanged: (v) => setState(() => _category = v),
          ),
          const SizedBox(height: 12),

          // Body text field
          TextField(
            key: const Key('feedback_body_field'),
            controller: _bodyController,
            maxLines: 6,
            minLines: 4,
            maxLength: _maxLength,
            style: TextStyle(color: colorScheme.onSurface),
            decoration: InputDecoration(
              hintText: "What's on your mind?",
              hintStyle: TextStyle(
                color: colorScheme.onSurface.withValues(alpha: 0.5),
              ),
              counterText: '',
              enabledBorder: OutlineInputBorder(
                borderSide:
                    BorderSide(color: colorScheme.primaryContainer),
                borderRadius: BorderRadius.circular(8),
              ),
              focusedBorder: OutlineInputBorder(
                borderSide: BorderSide(color: colorScheme.tertiary),
                borderRadius: BorderRadius.circular(8),
              ),
              filled: true,
              fillColor: colorScheme.onSurface.withValues(alpha: 0.05),
            ),
          ),
          const SizedBox(height: 6),

          // Live character counter (goes red at >3900)
          Align(
            alignment: Alignment.centerRight,
            child: Text(
              '$length/$_maxLength',
              key: const Key('feedback_char_counter'),
              style: TextStyle(
                fontSize: 12,
                color: over
                    ? colorScheme.error
                    : warn
                        ? colorScheme.error.withValues(alpha: 0.8)
                        : colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
          ),
          const SizedBox(height: 16),

          FilledButton(
            key: const Key('feedback_send_button'),
            onPressed: _canSend ? _submit : null,
            style: FilledButton.styleFrom(
              backgroundColor: colorScheme.tertiary,
              foregroundColor: colorScheme.onSurface,
              minimumSize: const Size.fromHeight(48),
            ),
            child: _isSending
                ? SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      color: colorScheme.onSurface,
                      strokeWidth: 2,
                    ),
                  )
                : const Text('Send'),
          ),
        ],
      ),
    );
  }
}
