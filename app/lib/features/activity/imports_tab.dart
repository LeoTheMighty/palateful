import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../core/theme/import_state_colors.dart';
import 'models/import_item_telemetry.dart';
import 'providers/activity_archive_provider.dart';
import 'providers/import_item_telemetry_provider.dart';
import 'providers/import_row_expansion_provider.dart';
import 'providers/imports_see_all_provider.dart';
import 'providers/see_all_count_provider.dart';
import 'widgets/empty_state_gateway_link.dart';
import 'widgets/awaiting_review_reason_chip.dart';
import 'widgets/compact_stage_pill.dart';
import 'widgets/confidence_badge.dart';
import 'widgets/import_row.dart';
import 'widgets/import_row_caret.dart';
import 'widgets/import_row_expansion.dart';
import 'widgets/import_row_expansion_actions.dart';
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
      // in the green section) — anything older than 30d lives in the
      // See-all footer now, which pulls directly from the server via
      // `importsSeeAllProvider` (afh-4). No tab-level >30d cache.
      final cutoff = DateTime.now().subtract(const Duration(days: 30));
      final autoImported = <_ItemView>[];
      for (final j in rawCompleted) {
        for (final i in itemsByJobId[j['id'].toString()] ?? []) {
          if (i['status'] != 'completed') continue;
          final createdIso = i['created_at']?.toString();
          final created = createdIso != null
              ? DateTime.tryParse(createdIso)
              : null;
          final isOver30d = created != null && created.isBefore(cutoff);
          if (!isOver30d && i['created_recipe_id'] != null) {
            autoImported.add(_ItemView.fromJson(i, j));
          }
        }
      }
      autoImported.sort(_byCreatedAtDesc);

      setState(() {
        _inProgress = inProgress;
        _needsReview = needsReview;
        _failed = failed;
        _autoImported = autoImported;
        _isLoading = false;
      });

      // afh-4: See-all count is server-side (ImportsSeeAllCountProvider).
      // Refresh after each poll so the footer label stays in sync with
      // archived / aged-out item deltas.
      if (mounted) {
        unawaited(
          ref.read(importsSeeAllCountProvider.notifier).refresh(),
        );
      }

      // abi-4: the orphan `importsActionableBadgeProvider` was deleted —
      // the bell now reads `imports_actionable` straight from the
      // server via ActivityReadProvider, which the 30s poll refreshes.
      // Local tab state stays source of truth for this widget's own
      // section rendering.
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
      // afh-4: See-all count bumps by 1. Fire-and-forget so the
      // snackbar UX stays instant.
      if (mounted) {
        unawaited(
          ref.read(importsSeeAllCountProvider.notifier).refresh(),
        );
      }
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
      if (mounted) {
        unawaited(
          ref.read(importsSeeAllCountProvider.notifier).refresh(),
        );
      }
    } catch (_) {
      // Silent.
    }
  }

  /// Pull-to-refresh: re-fetch active jobs/items + see-all count; if
  /// See-all is expanded, reset its cursor and re-fetch page 1.
  Future<void> _refreshAll() async {
    await _load();
    if (!mounted) return;
    await ref.read(importsSeeAllCountProvider.notifier).refresh();
    if (!mounted) return;
    if (ref.read(importsSeeAllExpandedProvider)) {
      await ref.read(importsSeeAllProvider.notifier).refreshFromTop();
    }
  }

  /// afh-5 — tap-handler for the empty-state gateway link. Expands
  /// the See-all footer AND animates scroll to bring it into view.
  Future<void> _expandAndScrollToSeeAll() async {
    ref.read(importsSeeAllExpandedProvider.notifier).setExpanded(true);
    final state = ref.read(importsSeeAllProvider);
    if (!state.hasLoadedFirstPage && !state.isLoading) {
      unawaited(ref.read(importsSeeAllProvider.notifier).loadNextPage());
    }
    if (!mounted) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final pos = Scrollable.maybeOf(context)?.position;
      if (pos == null || !pos.hasContentDimensions) return;
      pos.animateTo(
        pos.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
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
      final countAsync = ref.watch(importsSeeAllCountProvider);
      final historyCount = countAsync.maybeWhen(
        data: (t) => t.total,
        orElse: () => 0,
      );
      return RefreshIndicator(
        onRefresh: _refreshAll,
        child: ListView(
          // afh-4 AC6 — scroll offset persists across tab switches.
          key: const PageStorageKey<String>('imports-tab-empty-list'),
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
                  // afh-5 — inline "See past imports (N)" gateway
                  // when lifetime history exists. Tapping expands the
                  // See-all footer below AND auto-scrolls to it.
                  EmptyStateGatewayLink(
                    count: historyCount,
                    label: 'See past imports',
                    onTap: _expandAndScrollToSeeAll,
                  ),
                ],
              ),
            ),
            // See-all is still reachable even when live sections are
            // empty — archived items + >30d history always live here.
            const SeeAllFooter(),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refreshAll,
      child: ListView(
        // afh-4 AC6 — scroll offset persists across tab switches.
        key: const PageStorageKey<String>('imports-tab-list'),
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
                      rowState: ImportRowState.needsReview,
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
                      rowState: ImportRowState.failed,
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
                      rowState: ImportRowState.autoImported,
                      onTap: () {
                        final recipeId = i.createdRecipeId;
                        if (recipeId != null) {
                          context.push('/recipes/$recipeId');
                        }
                      },
                    ))
                .toList(),
          ),
          const SeeAllFooter(),
        ],
      ),
    );
  }

  /// In Progress rows render without any `Dismissible` wrapper — the
  /// absence of swipe affordance is the "blue is read-only" signal.
  /// Trailing slot stacks a read-only progress ring under an interactive
  /// caret (irrd-4 AC12) so blue rows also get rich-detail expansion.
  /// The title line mounts a `CompactStagePill` synthesized from the
  /// job's aggregate status (irrd-6 AC2) so Leo gets his at-a-glance
  /// stage scan without expanding.
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
      rowState: null,
      onReview: null,
      onRetry: null,
      onViewRecipe: null,
      onArchive: null,
      row: ImportRow(
        id: job.id,
        sourceIcon: _iconForSourceType(job.sourceType),
        title: _jobTitle(job),
        statusLabel: statusLabel,
        stateColor: states.inProgress,
        stateChipLabel: 'In Progress',
        timeLabel: _formatTime(job.createdAt),
        leadingInlineContent: CompactStagePill(
          telemetry: _synthesizeJobTelemetry(done, total),
        ),
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

  /// Synthesizes a stage timeline for a blue (in-progress) job row.
  /// `parsed` is `ok` when the job has processed at least one item;
  /// everything else stays `pending` so the current-stage pulse lands
  /// on `extracted`.
  ImportItemTelemetry _synthesizeJobTelemetry(int done, int total) {
    return ImportItemTelemetry(stages: [
      StageEntry(
        stage: 'parsed',
        status: done > 0 || total > 0 ? 'ok' : 'pending',
      ),
      const StageEntry(stage: 'extracted', status: 'pending'),
      const StageEntry(stage: 'matched', status: 'pending'),
      const StageEntry(stage: 'created', status: 'pending'),
    ]);
  }

  Future<void> _retryItem(_ItemView item) async {
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _apiClient.retryImportItem(item.id);
      if (!mounted) return;
      // Next poll will redraw the row's statusLabel; invalidate
      // telemetry so the expansion's stage timeline refetches once
      // the task completes.
      ref.invalidate(importItemTelemetryProvider(item.id));
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        const SnackBar(
          content: Text('Retrying'),
          duration: Duration(seconds: 2),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        SnackBar(
          content: const Text("Couldn't retry, try again"),
          backgroundColor: Theme.of(context).colorScheme.error,
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }

  Widget _buildSwipeableItemRow({
    required _ItemView item,
    required Color stateColor,
    required String chipLabel,
    required ImportRowState rowState,
    required VoidCallback onTap,
  }) {
    final colorScheme = Theme.of(context).colorScheme;
    final nonce = _restoreNonce[item.id] ?? 0;

    // Yellow rows surface the confidence badge + reason chip inline
    // with the title (irrd-6 AC1). Other states leave the slot empty.
    Widget? inline;
    if (rowState == ImportRowState.needsReview) {
      inline = Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          ConfidenceBadge(
            score: item.confidenceScore,
            source: item.confidenceSource,
            dense: true,
          ),
          if (item.awaitingReviewReason != null) ...[
            const SizedBox(width: 4),
            AwaitingReviewReasonChip(reason: item.awaitingReviewReason),
          ],
        ],
      );
    }

    VoidCallback? onReview;
    VoidCallback? onRetry;
    VoidCallback? onViewRecipe;
    switch (rowState) {
      case ImportRowState.needsReview:
        onReview = () => context.push('/recipes/import/review/${item.id}');
      case ImportRowState.failed:
        onRetry = () => _retryItem(item);
      case ImportRowState.autoImported:
        final recipeId = item.createdRecipeId;
        if (recipeId != null) {
          onViewRecipe = () => context.push('/recipes/$recipeId');
        }
      case ImportRowState.inProgress:
        break;
    }

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
        rowState: rowState,
        onReview: onReview,
        onRetry: onRetry,
        onViewRecipe: onViewRecipe,
        onArchive: () => _archiveItem(item),
        row: ImportRow(
          id: item.id,
          sourceIcon: _iconForSourceType(item.sourceType),
          title: item.title,
          statusLabel: item.statusLabel,
          stateColor: stateColor,
          stateChipLabel: chipLabel,
          timeLabel: _formatTime(item.createdAt),
          leadingInlineContent: inline,
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
  final ImportRowState? rowState;
  final VoidCallback? onReview;
  final VoidCallback? onRetry;
  final VoidCallback? onViewRecipe;
  final VoidCallback? onArchive;
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
    required this.rowState,
    required this.onReview,
    required this.onRetry,
    required this.onViewRecipe,
    required this.onArchive,
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
            rowState: rowState,
            onReview: onReview,
            onRetry: onRetry,
            onViewRecipe: onViewRecipe,
            onArchive: onArchive,
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
  final String? awaitingReviewReason;

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
    required this.awaitingReviewReason,
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
      awaitingReviewReason: item['awaiting_review_reason'] as String?,
    );
  }
}
