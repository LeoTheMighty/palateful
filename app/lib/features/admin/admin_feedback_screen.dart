import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';

/// Admin-only feedback inbox. Lists user-submitted feedback with filter
/// chips (Unread / Read / Archived / All). Tapping a row opens a detail
/// drawer with the full body, context JSON, and Mark Read / Archive
/// buttons that apply optimistically (local flip immediately, API fires
/// in the background; reverts + error snackbar on failure).
class AdminFeedbackScreen extends StatefulWidget {
  final String? initialStatus;

  const AdminFeedbackScreen({super.key, this.initialStatus});

  @override
  State<AdminFeedbackScreen> createState() => _AdminFeedbackScreenState();
}

class _AdminFeedbackScreenState extends State<AdminFeedbackScreen> {
  static const List<({String key, String label})> _filters = [
    (key: 'unread', label: 'Unread'),
    (key: 'read', label: 'Read'),
    (key: 'archived', label: 'Archived'),
    (key: 'all', label: 'All'),
  ];

  final _apiClient = getIt<ApiClient>();

  String _status = 'unread';
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;
  List<Map<String, dynamic>> _items = [];
  int _total = 0;

  @override
  void initState() {
    super.initState();
    final fromRoute = widget.initialStatus;
    if (fromRoute != null &&
        _filters.any((f) => f.key == fromRoute)) {
      _status = fromRoute;
    }
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await _apiClient.getAdminFeedback(status: _status);
      if (!mounted) return;
      final data = response.data as Map<String, dynamic>;
      final items = (data['items'] as List<dynamic>?) ?? [];
      setState(() {
        _items = items.cast<Map<String, dynamic>>();
        _total = (data['total'] as int?) ?? items.length;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load feedback.';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  Future<void> _selectFilter(String key) async {
    if (_status == key) return;
    setState(() => _status = key);
    await _fetch();
  }

  /// Optimistic status update with rollback on failure. The row flips
  /// locally, the API fires in the background, and on any failure we
  /// revert and show an error snackbar.
  Future<void> _updateStatus(
    Map<String, dynamic> item,
    String newStatus,
  ) async {
    final oldStatus = item['status'] as String;
    final id = item['id'] as String;

    setState(() {
      item['status'] = newStatus;
      // If the filter no longer matches, hide locally
      if (_status != 'all' && _status != newStatus) {
        _items = _items.where((r) => r['id'] != id).toList();
        _total = (_total - 1).clamp(0, 1 << 31);
      }
    });

    try {
      final response =
          await _apiClient.updateFeedbackStatus(id, newStatus);
      if (!mounted) return;
      final updatedAt = (response.data as Map?)?['updated_at'] as String?;
      if (updatedAt != null) {
        // Reflect server's authoritative updated_at in the local item if
        // it's still visible.
        final visible = _items.firstWhere(
          (r) => r['id'] == id,
          orElse: () => {},
        );
        if (visible.isNotEmpty) {
          visible['updated_at'] = updatedAt;
        }
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        item['status'] = oldStatus;
        // If we optimistically hid the row, re-insert it at the top so
        // the user sees the rollback.
        if (_items.every((r) => r['id'] != id)) {
          _items = [item, ..._items];
          _total += 1;
        }
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Couldn't update — tap to retry"),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: Text('Feedback', style: textTheme.titleLarge),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: Column(
        children: [
          _buildFilterBar(colorScheme),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? _buildError(colorScheme, textTheme)
                    : _buildList(colorScheme, textTheme),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterBar(ColorScheme colorScheme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: _filters.map((f) {
            final selected = f.key == _status;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: FilterChip(
                key: Key('feedback_filter_${f.key}'),
                label: Text(f.label),
                selected: selected,
                onSelected: (_) => _selectFilter(f.key),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildError(ColorScheme colorScheme, TextTheme textTheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 56, color: colorScheme.error),
            const SizedBox(height: 12),
            Text(
              _error!,
              style: textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
            if (_errorDetail != null) ...[
              const SizedBox(height: 8),
              Text(
                _errorDetail!,
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _fetch,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildList(ColorScheme colorScheme, TextTheme textTheme) {
    if (_items.isEmpty) {
      return Center(
        child: Text(
          'No feedback in this filter yet.',
          style: textTheme.bodyMedium?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _fetch,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        itemCount: _items.length,
        itemBuilder: (context, i) => _buildItem(_items[i], colorScheme, textTheme),
      ),
    );
  }

  Widget _buildItem(
    Map<String, dynamic> item,
    ColorScheme colorScheme,
    TextTheme textTheme,
  ) {
    final body = (item['body'] as String?) ?? '';
    final preview = body.length > 120 ? '${body.substring(0, 120)}…' : body;
    final displayName =
        (item['user_display_name'] as String?) ?? 'Unknown user';
    final category = item['category'] as String?;
    final context_ =
        (item['context'] as Map?)?.cast<String, dynamic>() ?? {};
    final appVersion = context_['app_version'] as String?;
    final platform = context_['platform'] as String?;
    final status = item['status'] as String? ?? 'unread';
    final createdAt = _formatTimestamp(item['created_at'] as String?);

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Material(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          key: Key('feedback_item_${item['id']}'),
          borderRadius: BorderRadius.circular(12),
          onTap: () => _openDetailDrawer(item),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        displayName,
                        style: textTheme.titleSmall,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Text(
                      createdAt,
                      style: textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    if (category != null)
                      _chip(category, colorScheme, textTheme),
                    if (appVersion != null) ...[
                      const SizedBox(width: 6),
                      _chip('v$appVersion', colorScheme, textTheme),
                    ],
                    if (platform != null) ...[
                      const SizedBox(width: 6),
                      _chip(platform, colorScheme, textTheme),
                    ],
                    if (status != 'unread') ...[
                      const SizedBox(width: 6),
                      _chip(status, colorScheme, textTheme),
                    ],
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  preview,
                  style: textTheme.bodyMedium,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _chip(String label, ColorScheme cs, TextTheme tt) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: cs.primaryContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: tt.labelSmall?.copyWith(color: cs.onPrimaryContainer),
      ),
    );
  }

  String _formatTimestamp(String? ts) {
    if (ts == null) return '';
    try {
      final dt = DateTime.parse(ts).toLocal();
      final diff = DateTime.now().difference(dt);
      if (diff.inMinutes < 1) return 'just now';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${dt.month}/${dt.day}/${dt.year}';
    } catch (_) {
      return ts;
    }
  }

  void _openDetailDrawer(Map<String, dynamic> item) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetCtx) => _FeedbackDetailSheet(
        item: item,
        onMarkRead: (item['status'] == 'unread')
            ? () {
                Navigator.of(sheetCtx).pop();
                _updateStatus(item, 'read');
              }
            : null,
        onArchive: (item['status'] != 'archived')
            ? () {
                Navigator.of(sheetCtx).pop();
                _updateStatus(item, 'archived');
              }
            : null,
      ),
    );
  }
}

class _FeedbackDetailSheet extends StatelessWidget {
  final Map<String, dynamic> item;
  final VoidCallback? onMarkRead;
  final VoidCallback? onArchive;

  const _FeedbackDetailSheet({
    required this.item,
    this.onMarkRead,
    this.onArchive,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final body = (item['body'] as String?) ?? '';
    final email = item['user_email'] as String?;
    final displayName = item['user_display_name'] as String?;
    final context_ =
        (item['context'] as Map?)?.cast<String, dynamic>() ?? {};

    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      minChildSize: 0.4,
      maxChildSize: 0.95,
      builder: (_, scrollController) => SingleChildScrollView(
        controller: scrollController,
        padding: const EdgeInsets.fromLTRB(24, 24, 24, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Feedback', style: textTheme.titleLarge),
            if (displayName != null) ...[
              const SizedBox(height: 4),
              Text(displayName, style: textTheme.bodyMedium),
            ],
            if (email != null) ...[
              const SizedBox(height: 2),
              Text(
                email,
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            const SizedBox(height: 16),
            Text(body, style: textTheme.bodyMedium),
            const SizedBox(height: 24),
            Text('Context', style: textTheme.titleSmall),
            const SizedBox(height: 4),
            if (context_.isEmpty)
              Text(
                'No context captured.',
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              )
            else
              ...context_.entries.map(
                (e) => Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    '${e.key}: ${e.value}',
                    style: textTheme.bodySmall,
                  ),
                ),
              ),
            const SizedBox(height: 24),
            Row(
              children: [
                if (onMarkRead != null) ...[
                  FilledButton.icon(
                    key: const Key('feedback_mark_read_button'),
                    onPressed: onMarkRead,
                    icon: const Icon(Icons.mark_email_read_outlined),
                    label: const Text('Mark Read'),
                  ),
                  const SizedBox(width: 12),
                ],
                if (onArchive != null)
                  OutlinedButton.icon(
                    key: const Key('feedback_archive_button'),
                    onPressed: onArchive,
                    icon: const Icon(Icons.archive_outlined),
                    label: const Text('Archive'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
