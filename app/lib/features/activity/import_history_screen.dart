import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/state/mutation_bus.dart';
import '../../core/state/mutation_failure_copy.dart';
import '../../core/state/mutation_snackbar.dart';
import '../../core/theme/theme.dart';
import '../recipes/add_recipe/batch_parser_service.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';
import 'providers/activity_read_provider.dart';

/// Attention-first Import Activity screen.
///
/// Default view shows only actionable items (needs review, failed, processing).
/// "Show import history" toggle reveals completed/skipped jobs.
///
/// Retired in ahr-7 (epic-activity-hub-redesign): the standalone
/// `/activity/import-history` route now redirects to
/// `/activity?tab=imports`, and the Imports tab renders the new
/// color-sectioned [ImportsTab] body. This class has no callers; it
/// survives one release as deprecated to catch any in-flight push
/// payloads whose builders still construct it, then gets deleted in
/// the next epic's cleanup pass.
@Deprecated(
  'Replaced by ImportsTab + the /activity?tab=imports deep-link (ahr-7). '
  'Will be deleted in the follow-up epic after one release.',
)
class ImportHistoryScreen extends StatefulWidget {
  final bool embedded;

  const ImportHistoryScreen({super.key, this.embedded = false});

  @override
  State<ImportHistoryScreen> createState() => _ImportHistoryScreenState();
}

class _ImportHistoryScreenState extends State<ImportHistoryScreen> {
  final _apiClient = getIt<ApiClient>();
  final _batchService = getIt<BatchParserService>();
  final _readProvider = getIt<ActivityReadProvider>();

  // Attention view data: jobs grouped by status, with their items loaded
  List<_JobWithItems> _processingJobs = [];
  List<_JobWithItems> _reviewJobs = [];
  List<_JobWithItems> _failedJobs = [];

  // History (loaded on demand)
  List<dynamic> _historyJobs = [];
  bool _showHistory = false;
  bool _isLoadingHistory = false;

  // Local batch jobs from BatchParserService
  List<BatchParserJob> _localBatchJobs = [];
  StreamSubscription<List<BatchParserJob>>? _batchSubscription;

  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  @override
  void initState() {
    super.initState();
    _loadAttentionView();
    // Opening the Import Activity surface acknowledges the backend-stored
    // import_* activity rows. Scoped: non-import activities stay unread so
    // the main Activity tab badge reflects the untouched feed.
    _readProvider.markLoadedImportActivitiesRead();
    _localBatchJobs = _batchService.jobs
        .where((j) =>
            j.status != BatchJobStatus.succeeded &&
            j.status != BatchJobStatus.failed)
        .toList();
    _batchSubscription = _batchService.jobStream.listen((jobs) {
      if (mounted) {
        setState(() {
          _localBatchJobs = jobs
              .where((j) =>
                  j.status != BatchJobStatus.succeeded &&
                  j.status != BatchJobStatus.failed)
              .toList();
        });
      }
    });
  }

  @override
  void dispose() {
    _batchSubscription?.cancel();
    super.dispose();
  }

  Future<void> _loadAttentionView() async {
    setState(() {
      _isLoading = true;
      _error = null;
      // Clear stale history so it reloads if user toggles it again
      if (_showHistory) {
        _showHistory = false;
        _historyJobs = [];
      }
    });

    try {
      // Fetch jobs by status in parallel
      final results = await Future.wait([
        _apiClient.listImportJobs(status: 'processing', limit: 50),
        _apiClient.listImportJobs(status: 'awaiting_review', limit: 50),
        _apiClient.listImportJobs(status: 'failed', limit: 50),
      ]);
      if (!mounted) return;

      final processingRaw =
          List<dynamic>.from(results[0].data['jobs'] ?? []);
      final reviewRaw =
          List<dynamic>.from(results[1].data['jobs'] ?? []);
      final failedRaw =
          List<dynamic>.from(results[2].data['jobs'] ?? []);

      // Fetch items for review and failed jobs in parallel
      final allJobs = [...reviewRaw, ...failedRaw];
      final itemFutures = allJobs
          .map((job) => _apiClient.listImportItems(job['id'].toString()));
      final itemResults = await Future.wait(itemFutures);
      if (!mounted) return;

      final itemsByJobId = <String, List<dynamic>>{};
      for (var i = 0; i < allJobs.length; i++) {
        final jobId = allJobs[i]['id'].toString();
        itemsByJobId[jobId] =
            List<dynamic>.from(itemResults[i].data['items'] ?? []);
      }

      setState(() {
        _processingJobs = processingRaw
            .map((j) => _JobWithItems(job: j, items: []))
            .toList();
        _reviewJobs = reviewRaw
            .map((j) => _JobWithItems(
                  job: j,
                  items: (itemsByJobId[j['id'].toString()] ?? [])
                      .where((i) => i['status'] == 'awaiting_review')
                      .toList(),
                ))
            .where((jw) => jw.items.isNotEmpty)
            .toList();
        _failedJobs = failedRaw
            .map((j) => _JobWithItems(
                  job: j,
                  items: (itemsByJobId[j['id'].toString()] ?? [])
                      .where((i) => i['status'] == 'failed')
                      .toList(),
                ))
            .where((jw) => jw.items.isNotEmpty)
            .toList();
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load import activity';
        _errorDetail = ErrorReporter.detail(e);
        _isLoading = false;
      });
    }
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoadingHistory = true);
    try {
      final response =
          await _apiClient.listImportJobs(limit: 50);
      if (!mounted) return;
      setState(() {
        _historyJobs = List<dynamic>.from(response.data['jobs'] ?? []);
        _isLoadingHistory = false;
        _showHistory = true;
      });
    } catch (_) {
      if (mounted) {
        setState(() => _isLoadingHistory = false);
      }
    }
  }

  Future<void> _dismissAllFailed(_JobWithItems jobWithItems) async {
    final itemIds = jobWithItems.items
        .map((i) => i['id'].toString())
        .toList();
    final jobId = jobWithItems.job['id']?.toString();

    // Optimistic removal
    setState(() {
      _failedJobs.remove(jobWithItems);
    });

    try {
      final responses = await Future.wait(
        itemIds.map((id) => _apiClient.dismissImportItem(id)),
      );
      // rf-5: emit one ImportItemDismissed per successfully-dismissed
      // item + one ImportJobDismissed at the end if the parent job
      // flipped. Subscribers (imports-see-all, activity-read) refetch
      // or recompute on the event types they care about.
      for (var i = 0; i < itemIds.length; i++) {
        final data = responses[i].data;
        final payload =
            data is Map ? Map<String, dynamic>.from(data) : null;
        emitMutation(ImportItemDismissed(
          itemId: itemIds[i],
          item: payload?['item'] is Map
              ? Map<String, dynamic>.from(payload!['item'] as Map)
              : null,
          jobDismissed: payload?['job_dismissed'] == true,
          jobId: jobId,
        ));
      }
      if (jobId != null) {
        emitMutation(ImportJobDismissed(jobId: jobId));
      }
    } catch (_) {
      if (mounted) {
        _loadAttentionView();
        showMutationFailureSnackbar(
          context,
          MutationType.dismissAllFailed,
          () => _dismissAllFailed(jobWithItems),
        );
      }
    }
  }

  Future<void> _dismissSingleItem(
      _JobWithItems jobWithItems, dynamic item) async {
    final itemId = item['id'].toString();
    final jobId = jobWithItems.job['id']?.toString();

    // Optimistic removal
    setState(() {
      jobWithItems.items.removeWhere((i) => i['id'].toString() == itemId);
      if (jobWithItems.items.isEmpty) {
        _failedJobs.remove(jobWithItems);
      }
    });

    try {
      final response = await _apiClient.dismissImportItem(itemId);
      final data = response.data;
      final payload = data is Map ? Map<String, dynamic>.from(data) : null;
      final jobDismissed = payload?['job_dismissed'] == true;
      emitMutation(ImportItemDismissed(
        itemId: itemId,
        item: payload?['item'] is Map
            ? Map<String, dynamic>.from(payload!['item'] as Map)
            : null,
        jobDismissed: jobDismissed,
        jobId: jobId,
      ));
      if (jobDismissed && jobId != null) {
        emitMutation(ImportJobDismissed(jobId: jobId));
      }
    } catch (_) {
      if (mounted) {
        _loadAttentionView();
        showMutationFailureSnackbar(
          context,
          MutationType.dismissImportItem,
          () => _dismissSingleItem(jobWithItems, item),
        );
      }
    }
  }

  Future<void> _retrySingleItem(
      _JobWithItems jobWithItems, dynamic item) async {
    final itemId = item['id'].toString();
    final jobId = jobWithItems.job['id']?.toString();

    try {
      final response = await _apiClient.retryImportItem(itemId);
      if (!mounted) return;
      final data = response.data;
      final payload = data is Map ? Map<String, dynamic>.from(data) : null;
      emitMutation(ImportItemRetried(
        itemId: itemId,
        item: payload,
        jobId: jobId,
      ));
      // Optimistically remove from failed list; the next refresh will
      // pick up the item's new status.
      setState(() {
        jobWithItems.items.removeWhere((i) => i['id'].toString() == itemId);
        if (jobWithItems.items.isEmpty) {
          _failedJobs.remove(jobWithItems);
        }
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Retrying import…'),
          duration: Duration(seconds: 2),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      showMutationFailureSnackbar(
        context,
        MutationType.retryImportItem,
        () => _retrySingleItem(jobWithItems, item),
      );
    }
  }

  bool get _hasActionableItems =>
      _processingJobs.isNotEmpty ||
      _reviewJobs.isNotEmpty ||
      _failedJobs.isNotEmpty ||
      _localBatchJobs.isNotEmpty;

  int get _totalFailedItemCount =>
      _failedJobs.fold<int>(0, (sum, jw) => sum + jw.items.length);

  String _formatTime(String? dateStr) {
    if (dateStr == null) return '';
    final parsed = DateTime.tryParse(dateStr);
    if (parsed == null) return '';

    final date = parsed.toLocal();
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${date.month}/${date.day}/${date.year}';
  }

  String _contextualTime(dynamic job) {
    final status = job['status'] as String?;
    if (status == 'completed' || status == 'failed') {
      return _formatTime(job['completed_at']?.toString() ??
          job['created_at']?.toString());
    }
    if (status == 'processing') {
      return _formatTime(
          job['started_at']?.toString() ?? job['created_at']?.toString());
    }
    return _formatTime(job['created_at']?.toString());
  }

  /// Human-readable title for a history row.
  ///
  /// "0 / 1 imported" is unhelpful — it reads like a failure when the job
  /// might actually be in progress, or like "pending" when it's actually
  /// dead. Use the status to pick a specific phrase.
  String _historyJobTitle({
    required String? status,
    required int succeeded,
    required int total,
  }) {
    final recipeWord = succeeded == 1 ? 'recipe' : 'recipes';
    final totalWord = total == 1 ? 'recipe' : 'recipes';
    switch (status) {
      case 'completed':
        if (total == 0) return 'Completed';
        if (succeeded == total) return '$succeeded $recipeWord imported';
        if (succeeded == 0) return 'Import failed';
        return 'Imported $succeeded of $total';
      case 'failed':
        return 'Import failed';
      case 'processing':
        if (total == 0) return 'Importing…';
        return 'Importing $succeeded of $total…';
      case 'pending':
        return total == 0 ? 'Queued' : 'Queued $total $totalWord';
      case 'cancelled':
        return 'Cancelled';
      default:
        return total == 0 ? '—' : '$succeeded of $total';
    }
  }

  IconData _iconForSourceType(String? sourceType) {
    switch (sourceType) {
      case 'url':
        return Icons.link;
      case 'url_list':
        return Icons.list;
      case 'photo':
        return Icons.camera_alt;
      case 'text':
        return Icons.description;
      case 'spreadsheet':
        return Icons.table_chart;
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'audio':
        return Icons.mic;
      default:
        return Icons.import_export;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final body = _isLoading
        ? const Center(child: CircularProgressIndicator())
        : _error != null
            ? _buildError(colorScheme)
            : RefreshIndicator(
                onRefresh: _loadAttentionView,
                child: _buildBody(colorScheme, textTheme),
              );

    // ahr-2: when embedded inside ActivityScreen's tab shell, skip the
    // Scaffold/AppBar (the parent owns them). The "Clear all failed"
    // action is a destructive bulk operation — we keep it visible by
    // rendering a floating button above the body instead of in the app
    // bar when embedded. Keeping the action reachable beats hiding it.
    if (widget.embedded) {
      return body;
    }

    final failedCount = _totalFailedItemCount;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Import Activity'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        actions: [
          if (failedCount > 0)
            TextButton(
              onPressed: _handleClearAllFailed,
              style: TextButton.styleFrom(
                foregroundColor: colorScheme.error,
              ),
              child: Text(
                'Clear all failed ($failedCount)',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
        ],
      ),
      body: body,
    );
  }

  Future<void> _handleClearAllFailed() async {
    final count = _totalFailedItemCount;
    if (count == 0) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        final colorScheme = Theme.of(ctx).colorScheme;
        return AlertDialog(
          title: const Text('Dismiss all failed imports?'),
          content: Text(
            count == 1
                ? "Dismiss 1 failed import? This can't be undone."
                : "Dismiss $count failed imports? This can't be undone.",
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              style: TextButton.styleFrom(foregroundColor: colorScheme.error),
              child: const Text('Dismiss all'),
            ),
          ],
        );
      },
    );

    if (confirmed != true || !mounted) return;

    // Optimistic: drop every failed group from local state.
    final snapshot = List<_JobWithItems>.from(_failedJobs);
    setState(() => _failedJobs = []);

    try {
      final response = await _apiClient.dismissAllFailedImports();
      final dismissed = (response.data['dismissed_count'] as num?)?.toInt() ??
          count;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Dismissed $dismissed import${dismissed == 1 ? '' : 's'}',
          ),
          duration: const Duration(seconds: 3),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _failedJobs = snapshot);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to clear: $e'),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
    }
  }

  Widget _buildBody(ColorScheme colorScheme, TextTheme textTheme) {
    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        // Attention area
        if (_hasActionableItems) ...[
          // Local batch processing jobs
          if (_localBatchJobs.isNotEmpty)
            _buildLocalBatchSection(colorScheme, textTheme),

          // Server-side processing jobs
          if (_processingJobs.isNotEmpty)
            _buildProcessingSection(colorScheme, textTheme),

          // Needs review section (expanded by default)
          if (_reviewJobs.isNotEmpty)
            _buildReviewSection(colorScheme, textTheme),

          // Failed section
          if (_failedJobs.isNotEmpty)
            _buildFailedSection(colorScheme, textTheme),
        ] else ...[
          // All Set! resting state
          _buildAllSetState(colorScheme, textTheme),
        ],

        // History toggle — always visible
        const SizedBox(height: 16),
        _buildHistoryToggle(colorScheme, textTheme),

        // History content
        if (_showHistory && _historyJobs.isNotEmpty)
          _buildHistorySection(colorScheme, textTheme),
      ],
    );
  }

  // ── Section builders ──

  Widget _buildLocalBatchSection(
      ColorScheme colorScheme, TextTheme textTheme) {
    return _buildSection(
      colorScheme: colorScheme,
      textTheme: textTheme,
      icon: SizedBox(
        width: 18,
        height: 18,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
        ),
      ),
      label: 'Processing',
      color: colorScheme.primary,
      children: _localBatchJobs.map((job) {
        return _buildItemTile(
          colorScheme: colorScheme,
          textTheme: textTheme,
          leading: SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor:
                  AlwaysStoppedAnimation<Color>(colorScheme.primary),
            ),
          ),
          title: job.filename,
          subtitle: _batchStatusText(job.status),
          onTap: null,
        );
      }).toList(),
    );
  }

  Widget _buildProcessingSection(
      ColorScheme colorScheme, TextTheme textTheme) {
    return _buildSection(
      colorScheme: colorScheme,
      textTheme: textTheme,
      icon: SizedBox(
        width: 18,
        height: 18,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
        ),
      ),
      label: 'Processing',
      color: colorScheme.primary,
      children: _processingJobs.map((jw) {
        final job = jw.job;
        final total = job['total_items'] as int? ?? 0;
        final processed = job['processed_items'] as int? ?? 0;
        return _buildJobHeader(
          colorScheme: colorScheme,
          textTheme: textTheme,
          job: job,
          subtitle: '$processed / $total items processed',
        );
      }).toList(),
    );
  }

  Widget _buildReviewSection(ColorScheme colorScheme, TextTheme textTheme) {
    final appColors = context.appColors;
    final reviewColor = appColors.warning;

    return _buildSection(
      colorScheme: colorScheme,
      textTheme: textTheme,
      icon: Icon(Icons.circle, size: 14, color: reviewColor),
      label: 'Needs Review',
      color: reviewColor,
      children: _reviewJobs.expand((jw) {
        final job = jw.job;
        return [
          // Job header
          _buildJobHeader(
            colorScheme: colorScheme,
            textTheme: textTheme,
            job: job,
            subtitle:
                '${jw.items.length} item${jw.items.length == 1 ? '' : 's'} to review',
          ),
          // Expanded items
          ...jw.items.map((item) {
            final itemId = item['id']?.toString() ?? '';
            final recipeName =
                item['recipe_name'] as String? ?? 'Untitled';
            return _buildItemTile(
              colorScheme: colorScheme,
              textTheme: textTheme,
              leading:
                  Icon(Icons.circle, size: 10, color: reviewColor),
              title: recipeName,
              trailing: const Icon(Icons.chevron_right, size: 18),
              onTap: () => _onItemTap(itemId, jw),
            );
          }),
        ];
      }).toList(),
    );
  }

  Widget _buildFailedSection(ColorScheme colorScheme, TextTheme textTheme) {
    return _buildSection(
      colorScheme: colorScheme,
      textTheme: textTheme,
      icon: Icon(Icons.error, size: 18, color: colorScheme.error),
      label: 'Failed',
      color: colorScheme.error,
      children: _failedJobs.expand((jw) {
        final job = jw.job;
        return [
          _buildJobHeader(
            colorScheme: colorScheme,
            textTheme: textTheme,
            job: job,
            subtitle:
                '${jw.items.length} failed item${jw.items.length == 1 ? '' : 's'}',
          ),
          ...jw.items.map((item) {
            final itemId = item['id']?.toString() ?? '';
            final recipeName =
                item['recipe_name'] as String? ?? 'Untitled';
            final errorMsg = item['error_message'] as String?;
            return Dismissible(
              key: ValueKey('failed-item-$itemId'),
              direction: DismissDirection.endToStart,
              background: Container(
                color: colorScheme.error,
                alignment: Alignment.centerRight,
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: const Icon(Icons.delete_outline,
                    color: Colors.white),
              ),
              onDismissed: (_) => _dismissSingleItem(jw, item),
              child: _buildItemTile(
                colorScheme: colorScheme,
                textTheme: textTheme,
                leading: Icon(Icons.error_outline, size: 16,
                    color: colorScheme.error),
                title: recipeName,
                subtitle: errorMsg,
                subtitleColor: colorScheme.error,
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: Icon(Icons.refresh, size: 18,
                          color: colorScheme.primary),
                      tooltip: 'Retry',
                      onPressed: () => _retrySingleItem(jw, item),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      visualDensity: VisualDensity.compact,
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      icon: Icon(Icons.close, size: 18,
                          color: colorScheme.onSurfaceVariant),
                      tooltip: 'Dismiss',
                      onPressed: () => _dismissSingleItem(jw, item),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      visualDensity: VisualDensity.compact,
                    ),
                  ],
                ),
                onTap: () => _onItemTap(itemId, jw),
              ),
            );
          }),
          // Dismiss All Failed button
          if (jw.items.length > 1)
            Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 48, vertical: 4),
              child: TextButton(
                onPressed: () => _dismissAllFailed(jw),
                child: Text(
                  'Dismiss All Failed',
                  style: TextStyle(
                    color: colorScheme.error,
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
        ];
      }).toList(),
    );
  }

  Widget _buildAllSetState(ColorScheme colorScheme, TextTheme textTheme) {
    final appColors = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 80),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.check_circle, size: 64, color: appColors.success),
          const SizedBox(height: 16),
          Text(
            'All Set!',
            style: textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: colorScheme.onSurface,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHistoryToggle(ColorScheme colorScheme, TextTheme textTheme) {
    return Center(
      child: Column(
        children: [
          Divider(
            indent: 48,
            endIndent: 48,
            color: colorScheme.outlineVariant,
          ),
          const SizedBox(height: 4),
          _isLoadingHistory
              ? const Padding(
                  padding: EdgeInsets.all(8),
                  child: SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                )
              : TextButton.icon(
                  onPressed: _showHistory
                      ? () => setState(() => _showHistory = false)
                      : _loadHistory,
                  icon: Icon(
                    _showHistory ? Icons.expand_less : Icons.expand_more,
                    size: 18,
                  ),
                  label: Text(
                    _showHistory
                        ? 'Hide import history'
                        : 'Show import history',
                    style: textTheme.bodyMedium?.copyWith(
                      color: colorScheme.primary,
                    ),
                  ),
                ),
        ],
      ),
    );
  }

  Widget _buildHistorySection(ColorScheme colorScheme, TextTheme textTheme) {
    // Filter to only completed/skipped/cancelled jobs
    final historyOnly = _historyJobs.where((j) {
      final status = j['status'] as String?;
      return status == 'completed' ||
          status == 'cancelled' ||
          status == 'skipped';
    }).toList();

    if (historyOnly.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Center(
          child: Text(
            'No import history yet',
            style: textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: historyOnly.map((job) {
          final status = job['status'] as String?;
          final sourceType = job['source_type'] as String?;
          final jobId = job['id']?.toString() ?? '';
          final succeeded = job['succeeded_items'] as int? ?? 0;
          final total = job['total_items'] as int? ?? 0;
          final title = _historyJobTitle(
            status: status,
            succeeded: succeeded,
            total: total,
          );

          return Card(
            margin: const EdgeInsets.only(bottom: 6),
            color: colorScheme.surfaceContainerHighest
                .withValues(alpha: 0.5),
            child: ListTile(
              dense: true,
              leading: Icon(
                _iconForSourceType(sourceType),
                size: 18,
                color: colorScheme.onSurfaceVariant,
              ),
              title: Text(
                title,
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
              subtitle: Text(
                _contextualTime(job),
                style: textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
                ),
              ),
              trailing: _historyStatusIcon(status, colorScheme),
              onTap: () async {
                await context
                    .push('/recipes/import/review-list/$jobId');
                if (mounted) _loadAttentionView();
              },
            ),
          );
        }).toList(),
      ),
    );
  }

  // ── Reusable widgets ──

  Widget _buildSection({
    required ColorScheme colorScheme,
    required TextTheme textTheme,
    required Widget icon,
    required String label,
    required Color color,
    required List<Widget> children,
  }) {
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                icon,
                const SizedBox(width: 8),
                Text(
                  label,
                  style: textTheme.titleSmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          ...children,
        ],
      ),
    );
  }

  Widget _buildJobHeader({
    required ColorScheme colorScheme,
    required TextTheme textTheme,
    required dynamic job,
    required String subtitle,
  }) {
    final sourceType = job['source_type'] as String?;
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 8, 16, 2),
      child: Row(
        children: [
          Icon(
            _iconForSourceType(sourceType),
            size: 16,
            color: colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 8),
          Text(
            subtitle,
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w500,
            ),
          ),
          const Spacer(),
          Text(
            _contextualTime(job),
            style: textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildItemTile({
    required ColorScheme colorScheme,
    required TextTheme textTheme,
    required Widget leading,
    required String title,
    String? subtitle,
    Color? subtitleColor,
    Widget? trailing,
    VoidCallback? onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(40, 6, 16, 6),
        child: Row(
          children: [
            leading,
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: textTheme.bodyMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (subtitle != null)
                    Text(
                      subtitle,
                      style: textTheme.bodySmall?.copyWith(
                        color: subtitleColor ??
                            colorScheme.onSurfaceVariant,
                        fontSize: 11,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
            if (trailing != null) trailing,
          ],
        ),
      ),
    );
  }

  Widget? _historyStatusIcon(String? status, ColorScheme colorScheme) {
    final appColors = context.appColors;
    switch (status) {
      case 'completed':
        return Icon(Icons.check_circle, size: 16, color: appColors.success);
      case 'cancelled':
        return Icon(Icons.cancel, size: 16, color: colorScheme.outline);
      default:
        return Icon(Icons.remove_circle_outline,
            size: 16, color: colorScheme.outline);
    }
  }

  // ── Interaction handlers ──

  Future<void> _onItemTap(String itemId, _JobWithItems parentJob) async {
    final result = await context.push('/recipes/import/review/$itemId');
    if (!mounted) return;

    if (result != null) {
      // Item was acted on (approved or dismissed) — optimistically remove it
      setState(() {
        parentJob.items
            .removeWhere((i) => i['id'].toString() == itemId);
        if (parentJob.items.isEmpty) {
          _reviewJobs.remove(parentJob);
          _failedJobs.remove(parentJob);
        }
      });
    } else {
      // User closed without acting — refresh to catch any server-side changes
      _loadAttentionView();
    }
  }

  String _batchStatusText(BatchJobStatus status) {
    switch (status) {
      case BatchJobStatus.uploading:
        return 'Uploading...';
      case BatchJobStatus.submitting:
        return 'Submitting...';
      case BatchJobStatus.polling:
        return 'Processing...';
      default:
        return '';
    }
  }

  Widget _buildError(ColorScheme colorScheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                _error!,
                style: TextStyle(color: colorScheme.onErrorContainer),
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadAttentionView,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Internal model pairing a job with its actionable items.
class _JobWithItems {
  final dynamic job;
  final List<dynamic> items;

  _JobWithItems({required this.job, required this.items});
}
