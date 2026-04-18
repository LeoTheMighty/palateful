import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import 'providers/activity_archive_provider.dart';
import 'providers/imports_actionable_badge_provider.dart';
import 'widgets/import_row.dart';
import 'widgets/import_state_section.dart';

/// Four-section Imports tab (blue / yellow / red / green). Replaces
/// the embedded `ImportHistoryScreen` that ahr-2 shipped as an
/// interim body. Ships the shell + swipe rules; the See-all footer
/// arrives in ahr-5, the color-token theme extension in ahr-6.
class ImportsTab extends ConsumerStatefulWidget {
  const ImportsTab({super.key});

  @override
  ConsumerState<ImportsTab> createState() => _ImportsTabState();
}

/// In-progress job statuses: a job in any of these lands in the Blue
/// section. Item-level statuses `pending`/`extracting`/`matching`/
/// `awaiting_parser` are covered by their parent job's status — items
/// of awaiting-review/failed/completed jobs are handled per-item.
const _inProgressJobStatuses = {
  'pending',
  'processing',
  'extracting',
  'matching',
  'awaiting_parser',
};

class _ImportsTabState extends ConsumerState<ImportsTab>
    with AutomaticKeepAliveClientMixin {
  final _apiClient = getIt<ApiClient>();

  List<_JobView> _inProgress = [];
  List<_ItemView> _needsReview = [];
  List<_ItemView> _failed = [];
  List<_ItemView> _autoImported = [];

  bool _isLoading = true;
  String? _error;
  Timer? _pollTimer;

  /// Per-id monotonic nonce — bumped every time we restore an archived
  /// row. See `NotificationsTab` for the Dismissible-key rationale.
  final Map<String, int> _restoreNonce = {};

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _load(silent: true);
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }

    try {
      // Fetch jobs by status in parallel — the four buckets mirror
      // the four sections, though items are the row granularity for
      // three of the four.
      final results = await Future.wait([
        _apiClient.listImportJobs(status: 'processing', limit: 50),
        _apiClient.listImportJobs(status: 'awaiting_review', limit: 50),
        _apiClient.listImportJobs(status: 'failed', limit: 50),
        _apiClient.listImportJobs(status: 'completed', limit: 50),
      ]);
      if (!mounted) return;

      final rawInProgress = List<dynamic>.from(results[0].data['jobs'] ?? []);
      final rawReview = List<dynamic>.from(results[1].data['jobs'] ?? []);
      final rawFailed = List<dynamic>.from(results[2].data['jobs'] ?? []);
      final rawCompleted = List<dynamic>.from(results[3].data['jobs'] ?? []);

      // Items: fetch per-job for awaiting_review / failed / completed —
      // per-job payloads are small (<=50 items), and no batched endpoint
      // exists. In-progress stays job-level — no item fetch needed.
      final itemJobs = [...rawReview, ...rawFailed, ...rawCompleted];
      final itemFutures = itemJobs
          .map((j) => _apiClient.listImportItems(j['id'].toString()));
      final itemResults = await Future.wait(itemFutures);
      if (!mounted) return;

      final itemsByJobId = <String, List<dynamic>>{};
      for (var i = 0; i < itemJobs.length; i++) {
        final jobId = itemJobs[i]['id'].toString();
        itemsByJobId[jobId] =
            List<dynamic>.from(itemResults[i].data['items'] ?? []);
      }

      // Build per-section view-model lists.
      final inProgress = rawInProgress
          .where((j) =>
              _inProgressJobStatuses.contains(j['status']?.toString()))
          .map<_JobView>(_JobView.fromJson)
          .toList();

      final needsReview = rawReview
          .expand<_ItemView>((j) => (itemsByJobId[j['id'].toString()] ?? [])
              .where((i) => i['status'] == 'awaiting_review')
              .map((i) => _ItemView.fromJson(i, j)))
          .toList()
        ..sort(_byCreatedAtDesc);

      final failed = rawFailed
          .expand<_ItemView>((j) => (itemsByJobId[j['id'].toString()] ?? [])
              .where((i) => i['status'] == 'failed')
              .map((i) => _ItemView.fromJson(i, j)))
          .toList()
        ..sort(_byCreatedAtDesc);

      final autoImported = rawCompleted
          .expand<_ItemView>((j) => (itemsByJobId[j['id'].toString()] ?? [])
              .where((i) =>
                  i['status'] == 'completed' &&
                  i['created_recipe_id'] != null)
              .map((i) => _ItemView.fromJson(i, j)))
          .toList()
        ..sort(_byCreatedAtDesc);

      setState(() {
        _inProgress = inProgress;
        _needsReview = needsReview;
        _failed = failed;
        _autoImported = autoImported;
        _isLoading = false;
      });

      // Actionable = blue + yellow + red. Green excluded.
      final actionable =
          inProgress.length + needsReview.length + failed.length;
      ref.read(importsActionableBadgeProvider.notifier).set(actionable);
    } catch (e, st) {
      if (!mounted) return;
      if (!silent) {
        setState(() {
          _error = 'Failed to load imports';
          _isLoading = false;
        });
      }
      ErrorReporter.report(e, st, area: 'activity', operation: 'imports_tab_load');
    }
  }

  Future<void> _archiveItem(_ItemView item) async {
    if (!mounted) return;
    final id = item.id;
    ref.read(importItemArchiveProvider.notifier).add(id);

    // Capture these before the await — reaching for `context` after the
    // call returns is fraught (the widget may have disposed mid-call).
    final messenger = ScaffoldMessenger.of(context);
    final errorBg = Theme.of(context).colorScheme.error;

    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: const Text('Archived'),
        duration: const Duration(seconds: 3),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () => _undoArchive(id),
        ),
      ),
    );

    String? errorMessage;
    try {
      await _apiClient.archiveImportItem(id);
    } on DioException catch (e) {
      errorMessage = e.response?.statusCode == 409
          ? "Can't archive while importing"
          : "Couldn't archive, try again";
    } catch (_) {
      errorMessage = "Couldn't archive, try again";
    }

    if (errorMessage == null || !mounted) return;

    setState(() {
      _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
    });
    ref.read(importItemArchiveProvider.notifier).remove(id);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: Text(errorMessage),
        backgroundColor: errorBg,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  Future<void> _undoArchive(String id) async {
    if (!mounted) return;
    setState(() {
      _restoreNonce[id] = (_restoreNonce[id] ?? 0) + 1;
    });
    ref.read(importItemArchiveProvider.notifier).remove(id);
    try {
      await _apiClient.unarchiveImportItem(id);
    } catch (_) {
      // Silent.
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final locallyArchived = ref.watch(importItemArchiveProvider);

    if (_isLoading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));

    // Filter each section against the local archive set so a swiped
    // row stays hidden across the next poll.
    final visibleReview = _needsReview
        .where((i) => !locallyArchived.contains(i.id))
        .toList();
    final visibleFailed = _failed
        .where((i) => !locallyArchived.contains(i.id))
        .toList();
    final visibleAutoImported = _autoImported
        .where((i) => !locallyArchived.contains(i.id))
        .toList();
    final visibleInProgress = _inProgress;

    final allEmpty = visibleInProgress.isEmpty &&
        visibleReview.isEmpty &&
        visibleFailed.isEmpty &&
        visibleAutoImported.isEmpty;

    if (allEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 80),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.check_circle_outline,
                      size: 64,
                      color: colorScheme.onSurfaceVariant
                          .withValues(alpha: 0.5)),
                  const SizedBox(height: 16),
                  Text('All clear — no imports yet',
                      style: textTheme.titleMedium?.copyWith(
                          color: colorScheme.onSurfaceVariant)),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 32),
        children: [
          ImportStateSection(
            label: 'In Progress',
            count: visibleInProgress.length,
            color: colorScheme.primary,
            children: visibleInProgress
                .map((j) => _buildInProgressRow(j, colorScheme))
                .toList(),
          ),
          ImportStateSection(
            label: 'Needs Review',
            count: visibleReview.length,
            color: colorScheme.tertiary,
            children: visibleReview
                .map((i) => _buildSwipeableItemRow(
                      item: i,
                      stateColor: colorScheme.tertiary,
                      chipLabel: 'Needs Review',
                      onTap: () => context
                          .push('/recipes/import/review/${i.id}'),
                    ))
                .toList(),
          ),
          ImportStateSection(
            label: 'Failed',
            count: visibleFailed.length,
            color: colorScheme.error,
            children: visibleFailed
                .map((i) => _buildSwipeableItemRow(
                      item: i,
                      stateColor: colorScheme.error,
                      chipLabel: 'Failed',
                      onTap: () => context
                          .push('/recipes/import/review/${i.id}'),
                    ))
                .toList(),
          ),
          ImportStateSection(
            label: 'Auto-Imported',
            count: visibleAutoImported.length,
            color: colorScheme.secondary,
            children: visibleAutoImported
                .map((i) => _buildSwipeableItemRow(
                      item: i,
                      stateColor: colorScheme.secondary,
                      chipLabel: 'Auto-Imported',
                      onTap: () {
                        final recipeId = i.createdRecipeId;
                        if (recipeId != null) {
                          context.push('/recipes/$recipeId');
                        }
                      },
                    ))
                .toList(),
          ),
        ],
      ),
    );
  }

  /// In Progress rows render without any `Dismissible` wrapper — the
  /// absence of swipe affordance is the "blue is read-only" signal.
  /// Trailing slot is a small progress glyph (non-interactive).
  Widget _buildInProgressRow(_JobView job, ColorScheme colorScheme) {
    final total = job.totalItems;
    final done = job.processedItems;
    final statusLabel = total > 0
        ? 'Importing $done of $total'
        : 'Importing…';
    return ImportRow(
      id: job.id,
      sourceIcon: _iconForSourceType(job.sourceType),
      title: _jobTitle(job),
      statusLabel: statusLabel,
      stateColor: colorScheme.primary,
      stateChipLabel: 'In Progress',
      timeLabel: _formatTime(job.createdAt),
      trailing: SizedBox(
        width: 16,
        height: 16,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
        ),
      ),
      onTap: () => context.push('/recipes/import/review-list/${job.id}'),
    );
  }

  Widget _buildSwipeableItemRow({
    required _ItemView item,
    required Color stateColor,
    required String chipLabel,
    required VoidCallback onTap,
  }) {
    final colorScheme = Theme.of(context).colorScheme;
    final nonce = _restoreNonce[item.id] ?? 0;
    return Dismissible(
      key: ValueKey('import-item-${item.id}-$nonce'),
      direction: DismissDirection.endToStart,
      background: Container(
        color: colorScheme.error,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: const Icon(Icons.archive_outlined, color: Colors.white),
      ),
      onDismissed: (_) => _archiveItem(item),
      child: ImportRow(
        id: item.id,
        sourceIcon: _iconForSourceType(item.sourceType),
        title: item.title,
        statusLabel: item.statusLabel,
        stateColor: stateColor,
        stateChipLabel: chipLabel,
        timeLabel: _formatTime(item.createdAt),
        trailing: const Icon(Icons.chevron_right, size: 20),
        onTap: onTap,
      ),
    );
  }

  // ── helpers ─────────────────────────────────────────────────────────

  static IconData _iconForSourceType(String? sourceType) {
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

  static String _jobTitle(_JobView job) {
    final total = job.totalItems;
    if (job.sourceType == 'url' && job.sourceUrl != null) {
      return job.sourceUrl!;
    }
    if (total > 0) return '${job.sourceType ?? "Import"} ($total)';
    return job.sourceType ?? 'Import';
  }

  static int _byCreatedAtDesc(_ItemView a, _ItemView b) {
    final ca = a.createdAt;
    final cb = b.createdAt;
    if (ca == null && cb == null) return 0;
    if (ca == null) return 1;
    if (cb == null) return -1;
    return cb.compareTo(ca);
  }

  static String _formatTime(DateTime? date) {
    if (date == null) return '';
    final local = date.toLocal();
    final now = DateTime.now();
    final diff = now.difference(local);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${local.month}/${local.day}/${local.year}';
  }
}

// ── view models ────────────────────────────────────────────────────────

class _JobView {
  final String id;
  final String? sourceType;
  final String? sourceUrl;
  final int totalItems;
  final int processedItems;
  final DateTime? createdAt;

  _JobView({
    required this.id,
    required this.sourceType,
    required this.sourceUrl,
    required this.totalItems,
    required this.processedItems,
    required this.createdAt,
  });

  factory _JobView.fromJson(dynamic j) => _JobView(
        id: j['id'].toString(),
        sourceType: j['source_type'] as String?,
        sourceUrl: j['source_url'] as String?,
        totalItems: (j['total_items'] as num?)?.toInt() ?? 0,
        processedItems: (j['processed_items'] as num?)?.toInt() ?? 0,
        createdAt: j['created_at'] != null
            ? DateTime.tryParse(j['created_at'].toString())
            : null,
      );
}

class _ItemView {
  final String id;
  final String title;
  final String? sourceType;
  final String? statusLabel;
  final String? createdRecipeId;
  final DateTime? createdAt;

  _ItemView({
    required this.id,
    required this.title,
    required this.sourceType,
    required this.statusLabel,
    required this.createdRecipeId,
    required this.createdAt,
  });

  factory _ItemView.fromJson(dynamic item, dynamic parentJob) {
    final errorMsg = (item['error_message'] as String?)?.trim();
    final status = item['status']?.toString();
    final name = item['recipe_name']?.toString();

    final label = switch (status) {
      'failed' =>
        errorMsg != null && errorMsg.isNotEmpty ? errorMsg : 'Failed',
      'awaiting_review' => 'Needs review',
      'completed' => 'Imported',
      _ => status,
    };

    return _ItemView(
      id: item['id'].toString(),
      title: (name != null && name.isNotEmpty) ? name : 'Untitled',
      sourceType: (item['source_type'] ?? parentJob['source_type']) as String?,
      statusLabel: label,
      createdRecipeId: item['created_recipe_id']?.toString(),
      createdAt: item['created_at'] != null
          ? DateTime.tryParse(item['created_at'].toString())
          : null,
    );
  }
}
