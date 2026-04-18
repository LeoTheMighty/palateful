import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../core/theme/import_state_colors.dart';
import 'providers/activity_archive_provider.dart';
import 'providers/import_row_expansion_provider.dart';
import 'providers/imports_actionable_badge_provider.dart';
import 'widgets/import_row.dart';
import 'widgets/import_row_caret.dart';
import 'widgets/import_row_expansion.dart';
import 'widgets/import_state_section.dart';
import 'widgets/see_all_footer.dart';

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
  int _seeAllCount = 0;

  /// Completed items older than 30 days — kept alongside live data so
  /// the See-all footer can render them without a second fetch.
  List<dynamic> _completedOver30d = [];

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

      // Split completed items into "recent auto-imported" (≤30d, still
      // in the green section) vs "older than 30d" (see-all footer).
      final cutoff = DateTime.now().subtract(const Duration(days: 30));
      final autoImported = <_ItemView>[];
      final completedOver30d = <dynamic>[];
      for (final j in rawCompleted) {
        for (final i in itemsByJobId[j['id'].toString()] ?? []) {
          if (i['status'] != 'completed') continue;
          final createdIso = i['created_at']?.toString();
          final created = createdIso != null
              ? DateTime.tryParse(createdIso)
              : null;
          final isOver30d = created != null && created.isBefore(cutoff);
          if (isOver30d) {
            completedOver30d.add({...i, 'source_type': i['source_type'] ?? j['source_type']});
          } else if (i['created_recipe_id'] != null) {
            autoImported.add(_ItemView.fromJson(i, j));
          }
        }
      }
      autoImported.sort(_byCreatedAtDesc);

      // Count of archived items across all statuses. Lightweight
      // additional call — used only for the See-all N. This runs on
      // every poll but the endpoint is cheap and server-cached.
      var archivedCount = 0;
      try {
        final archivedResponse = await _apiClient.listImportJobs(
          archivedOnly: true,
          limit: 1,
          includeArchived: true,
        );
        if (!mounted) return;
        // The API returns jobs, not item count — but ahr-1 documents
        // that jobs ARE the list scope here. For the footer's N we use
        // the response's `total` if provided, else fall back to the
        // `jobs` length. (Either number is good enough for "See all
        // (N)" — the precise count gets authoritative on expand-fetch.)
        final total = (archivedResponse.data['total'] as num?)?.toInt();
        final jobs = (archivedResponse.data['jobs'] as List?)?.length ?? 0;
        archivedCount = total ?? jobs;
      } catch (_) {
        // Non-fatal — footer just falls back to >30d count only.
      }

      setState(() {
        _inProgress = inProgress;
        _needsReview = needsReview;
        _failed = failed;
        _autoImported = autoImported;
        _completedOver30d = completedOver30d;
        _seeAllCount = archivedCount + completedOver30d.length;
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
    final stateColors = context.importStates;
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
            // See-all is still reachable even when live sections are
            // empty — archived items + >30d history always live here.
            SeeAllFooter(
              count: _seeAllCount,
              onLoad: _loadSeeAllRows,
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
            color: stateColors.inProgress,
            children: visibleInProgress
                .map((j) => _buildInProgressRow(j, stateColors))
                .toList(),
          ),
          ImportStateSection(
            label: 'Needs Review',
            count: visibleReview.length,
            color: stateColors.needsReview,
            children: visibleReview
                .map((i) => _buildSwipeableItemRow(
                      item: i,
                      stateColor: stateColors.needsReview,
                      chipLabel: 'Needs Review',
                      onTap: () => context
                          .push('/recipes/import/review/${i.id}'),
                    ))
                .toList(),
          ),
          ImportStateSection(
            label: 'Failed',
            count: visibleFailed.length,
            color: stateColors.failed,
            children: visibleFailed
                .map((i) => _buildSwipeableItemRow(
                      item: i,
                      stateColor: stateColors.failed,
                      chipLabel: 'Failed',
                      onTap: () => context
                          .push('/recipes/import/review/${i.id}'),
                    ))
                .toList(),
          ),
          ImportStateSection(
            label: 'Auto-Imported',
            count: visibleAutoImported.length,
            color: stateColors.autoImported,
            children: visibleAutoImported
                .map((i) => _buildSwipeableItemRow(
                      item: i,
                      stateColor: stateColors.autoImported,
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
          SeeAllFooter(
            count: _seeAllCount,
            onLoad: _loadSeeAllRows,
          ),
        ],
      ),
    );
  }

  /// Fetches archived jobs + their items and combines with the
  /// already-loaded >30d completed items. Called lazily by the footer
  /// on first expand; result is cached by the footer itself.
  Future<List<SeeAllItemView>> _loadSeeAllRows() async {
    final archivedRows = <SeeAllItemView>[];
    try {
      final jobsResponse = await _apiClient.listImportJobs(
        archivedOnly: true,
        includeArchived: true,
        limit: 100,
      );
      final archivedJobs =
          List<dynamic>.from(jobsResponse.data['jobs'] ?? []);
      final itemResults = await Future.wait(archivedJobs.map(
        (j) => _apiClient.listImportItems(j['id'].toString()),
      ));
      for (var i = 0; i < archivedJobs.length; i++) {
        final j = archivedJobs[i];
        final items = List<dynamic>.from(itemResults[i].data['items'] ?? []);
        for (final item in items) {
          archivedRows.add(_seeAllViewFromRaw(item, j));
        }
      }
    } catch (_) {
      // Swallow — we'll still surface >30d rows.
    }

    final over30dRows = _completedOver30d.map((m) {
      return _seeAllViewFromRaw(m, const {});
    }).toList();

    final all = [...archivedRows, ...over30dRows];
    all.sort((a, b) {
      final ka = a.archivedAt ?? a.createdAt;
      final kb = b.archivedAt ?? b.createdAt;
      if (ka == null && kb == null) return 0;
      if (ka == null) return 1;
      if (kb == null) return -1;
      return kb.compareTo(ka);
    });
    return all;
  }

  static SeeAllItemView _seeAllViewFromRaw(dynamic item, dynamic parentJob) {
    final parent = parentJob is Map ? parentJob : const {};
    return SeeAllItemView(
      id: item['id'].toString(),
      title: (item['recipe_name']?.toString().isNotEmpty ?? false)
          ? item['recipe_name'].toString()
          : 'Untitled',
      sourceType:
          (item['source_type'] ?? parent['source_type']) as String?,
      statusLabel: item['status']?.toString(),
      archivedAt: item['archived_at'] != null
          ? DateTime.tryParse(item['archived_at'].toString())
          : null,
      createdAt: item['created_at'] != null
          ? DateTime.tryParse(item['created_at'].toString())
          : null,
    );
  }

  /// In Progress rows render without any `Dismissible` wrapper — the
  /// absence of swipe affordance is the "blue is read-only" signal.
  /// Trailing slot stacks a read-only progress ring under an interactive
  /// caret (irrd-4 AC12) so blue rows also get rich-detail expansion.
  Widget _buildInProgressRow(_JobView job, ImportStateColors states) {
    final total = job.totalItems;
    final done = job.processedItems;
    final statusLabel = total > 0
        ? 'Importing $done of $total'
        : 'Importing…';
    return _ExpandableRow(
      rowId: job.id,
      recipeName: _jobTitle(job),
      // Blue rows have no single item_id to hang telemetry off — the
      // expansion is job-level and skips the per-item telemetry fetch.
      itemIdForTelemetry: null,
      retryCount: 0,
      lastRetryAt: null,
      errorMessage: null,
      sourceType: job.sourceType,
      sourceReference: null,
      confidenceScore: null,
      confidenceSource: null,
      row: ImportRow(
        id: job.id,
        sourceIcon: _iconForSourceType(job.sourceType),
        title: _jobTitle(job),
        statusLabel: statusLabel,
        stateColor: states.inProgress,
        stateChipLabel: 'In Progress',
        timeLabel: _formatTime(job.createdAt),
        trailing: ImportRowCaret(
          rowId: job.id,
          recipeName: _jobTitle(job),
          showProgressRing: true,
          progressColor: states.inProgress,
        ),
        onTap: () => context.push('/recipes/import/review-list/${job.id}'),
      ),
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
      child: _ExpandableRow(
        rowId: item.id,
        recipeName: item.title,
        itemIdForTelemetry: item.id,
        retryCount: item.retryCount,
        lastRetryAt: item.lastRetryAt,
        errorMessage: item.errorMessage,
        sourceType: item.sourceType,
        sourceReference: item.sourceReference,
        confidenceScore: item.confidenceScore,
        confidenceSource: item.confidenceSource,
        row: ImportRow(
          id: item.id,
          sourceIcon: _iconForSourceType(item.sourceType),
          title: item.title,
          statusLabel: item.statusLabel,
          stateColor: stateColor,
          stateChipLabel: chipLabel,
          timeLabel: _formatTime(item.createdAt),
          trailing: ImportRowCaret(
            rowId: item.id,
            recipeName: item.title,
          ),
          onTap: onTap,
        ),
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

// ── row + expansion composition ────────────────────────────────────────

/// Composes an `ImportRow` with an inline `ImportRowExpansion` rendered
/// below it when the row's id lives in the `importRowExpansionProvider`
/// set. Uses `select` to keep the rebuild scoped to this row only —
/// expanding row A does not rebuild row B's widget tree.
class _ExpandableRow extends ConsumerWidget {
  final String rowId;
  final String recipeName;

  /// Separate from `rowId` because in-progress rows are keyed on the
  /// job id (there's no single item to hang telemetry off), and the
  /// telemetry endpoint is item-level. `null` skips the fetch and the
  /// expansion renders nothing (job-level blue rows).
  final String? itemIdForTelemetry;

  final int retryCount;
  final DateTime? lastRetryAt;
  final String? errorMessage;
  final String? sourceType;
  final String? sourceReference;
  final double? confidenceScore;
  final String? confidenceSource;
  final Widget row;

  const _ExpandableRow({
    required this.rowId,
    required this.recipeName,
    required this.itemIdForTelemetry,
    required this.retryCount,
    required this.lastRetryAt,
    required this.errorMessage,
    required this.sourceType,
    required this.sourceReference,
    required this.confidenceScore,
    required this.confidenceSource,
    required this.row,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final expanded = ref.watch(
      importRowExpansionProvider.select((s) => s.contains(rowId)),
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        row,
        if (expanded && itemIdForTelemetry != null)
          ImportRowExpansion(
            itemId: itemIdForTelemetry!,
            recipeName: recipeName,
            retryCount: retryCount,
            lastRetryAt: lastRetryAt,
            errorMessage: errorMessage,
            sourceType: sourceType,
            sourceReference: sourceReference,
            confidenceScore: confidenceScore,
            confidenceSource: confidenceSource,
          ),
      ],
    );
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
  final String? sourceReference;
  final String? statusLabel;
  final String? errorMessage;
  final String? createdRecipeId;
  final DateTime? createdAt;
  final int retryCount;
  final DateTime? lastRetryAt;
  final double? confidenceScore;
  final String? confidenceSource;

  _ItemView({
    required this.id,
    required this.title,
    required this.sourceType,
    required this.sourceReference,
    required this.statusLabel,
    required this.errorMessage,
    required this.createdRecipeId,
    required this.createdAt,
    required this.retryCount,
    required this.lastRetryAt,
    required this.confidenceScore,
    required this.confidenceSource,
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

    final rawConfidence = item['confidence_score'];
    return _ItemView(
      id: item['id'].toString(),
      title: (name != null && name.isNotEmpty) ? name : 'Untitled',
      sourceType: (item['source_type'] ?? parentJob['source_type']) as String?,
      sourceReference: item['source_url']?.toString(),
      statusLabel: label,
      errorMessage: errorMsg,
      createdRecipeId: item['created_recipe_id']?.toString(),
      createdAt: item['created_at'] != null
          ? DateTime.tryParse(item['created_at'].toString())
          : null,
      retryCount: (item['retry_count'] as num?)?.toInt() ?? 0,
      lastRetryAt: item['last_retry_at'] != null
          ? DateTime.tryParse(item['last_retry_at'].toString())
          : null,
      confidenceScore: rawConfidence is num
          ? rawConfidence.toDouble()
          : null,
      confidenceSource: item['confidence_source'] as String?,
    );
  }
}
