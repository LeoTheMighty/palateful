import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import '../../core/state/mutation_bus.dart';
import '../../core/state/import_job_statuses.dart';
import '../../core/theme/import_state_colors.dart';
import '../recipes/add_recipe/models/import_batch.dart';
import 'models/import_item_telemetry.dart';
import 'providers/activity_archive_provider.dart';
import 'providers/activity_read_provider.dart';
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
/// section (job-granularity — we show "Importing 3 of 10" rather than
/// one row per pending item).
/// Job-level in-progress test. Lives in
/// `core/state/import_job_statuses.dart` so this file and the parser-batch
/// model cannot drift apart — two hand-kept sets in two files only happened
/// to partition the server's vocabulary, and one new server status would
/// have reproduced "the badge says 1 and the tab is empty" in a new shape.
/// An unrecognised status counts as in-progress, so it renders.
bool _isInProgressJob(dynamic j) => isJobInProgress(j['status']?.toString());

/// Bucketing is driven by `item.status`, not `job.status`. A completed
/// job can still hold failed / awaiting_review / skipped items, and the
/// opposite is also true — so relying on the parent job's status to
/// decide where an item lands made most items disappear (see bug
/// diagnosis 2026-04-20). Items land in exactly one section.

class _ImportsTabState extends ConsumerState<ImportsTab>
    with AutomaticKeepAliveClientMixin {
  final _apiClient = getIt<ApiClient>();
  final _readProvider = getIt<ActivityReadProvider>();

  List<_JobView> _inProgress = [];

  /// Parser batches that produced no ImportJobs and are past the grace
  /// window — dead, not slow. Rendered in Failed (see parsercap1).
  List<_JobView> _stalledBatches = [];
  List<_ItemView> _needsReview = [];
  List<_ItemView> _failed = [];
  List<_ItemView> _autoImported = [];
  List<_ItemView> _skipped = [];

  bool _isLoading = true;
  String? _error;
  VoidCallback? _disposeTickListener;

  /// Per-id monotonic nonce — bumped every time we restore an archived
  /// row. See `NotificationsTab` for the Dismissible-key rationale.
  final Map<String, int> _restoreNonce = {};

  @override
  bool get wantKeepAlive => true;

  /// MutationBus subscription — reloads silently when any import item
  /// changes elsewhere in the app (e.g., `Dismiss` on the per-item review
  /// screen, retry from the see-all footer, etc.). Without this the tab's
  /// local `_needsReview` / `_failed` state goes stale until the 30s tick
  /// or a manual pull-to-refresh.
  StreamSubscription<MutationEvent>? _busSub;

  @override
  void initState() {
    super.initState();
    _load();
    // pfc-1: subscribe to the shared 30s tick. `contributesUnreadCount`
    // stays false — this tab fetches `/v1/import-jobs` + `/v1/import-
    // items`, neither of which carries the bell count.
    _disposeTickListener = _readProvider.registerTickListener(
      () => _load(silent: true),
    );
    _busSub = mutationBusStream().listen((event) {
      if (event is ImportItemDismissed || event is ImportItemRetried) {
        _load(silent: true);
      }
    });
  }

  @override
  void dispose() {
    _disposeTickListener?.call();
    _disposeTickListener = null;
    _busSub?.cancel();
    _busSub = null;
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
      // One fetch of every non-archived job, then ONE batched fetch of
      // every item across those jobs (ffm-2). We deliberately do NOT
      // pre-filter by job.status: items in a `completed` job can be
      // `failed` / `awaiting_review` / `skipped`, and the inverse is
      // also true (an `awaiting_review` job can hold a `failed` item).
      // Bucketing happens by ``item.status`` below.
      final jobsResponse =
          await _apiClient.listImportJobs(limit: 100);
      if (!mounted) return;
      final rawJobs =
          List<dynamic>.from(jobsResponse.data['jobs'] ?? []);

      final itemsByJobId = <String, List<dynamic>>{};
      if (rawJobs.isNotEmpty) {
        final jobIds = rawJobs.map((j) => j['id'].toString()).toList();
        // Backend caps at 50 job_ids per call — `listImportJobs`
        // limit above is 100, so chunk to stay under the cap on the
        // rare power-user edge case.
        for (var start = 0; start < jobIds.length; start += 50) {
          final chunk =
              jobIds.sublist(start, (start + 50).clamp(0, jobIds.length));
          final batchResponse =
              await _apiClient.listImportItemsBatch(chunk);
          if (!mounted) return;
          final rawItems =
              List<dynamic>.from(batchResponse.data['items'] ?? []);
          for (final item in rawItems) {
            final jobId = item['job_id']?.toString();
            if (jobId == null) continue;
            itemsByJobId.putIfAbsent(jobId, () => <dynamic>[]).add(item);
          }
        }
      }

      // Blue — job-granularity. Items in pending/extracting/matching
      // states are represented by their parent job (e.g. "Importing 3
      // of 10") rather than one row per in-flight item.
      final inProgress =
          rawJobs.where(_isInProgressJob).map<_JobView>(_JobView.fromJson).toList();

      // impvis1: a photo import exists as a ParserBatch BEFORE it fans out
      // into ImportJobs, and the two queries above cannot see it. That is
      // the gap Leo hit — the Add Recipe strip counted "1 import in
      // progress" from this very endpoint while this tab rendered nothing.
      // Only batches with no ImportJob of their own are synthesised here;
      // once a batch has fanned out, its jobs are already above and a
      // second row would double-count one import.
      //
      // Note the two lists are filtered by different columns server-side:
      // a batch's `import_jobs` exclude dismissed rows
      // (`list_parser_batches.py:51`) while `rawJobs` excludes archived ones
      // (`list_import_jobs.py:74-75`). Nothing writes `ImportJob.archived_at`
      // today, so the two cannot disagree yet; if something starts to, an
      // archived-but-not-dismissed job would resurrect its batch here.
      final renderedJobIds = rawJobs.map((j) => j['id'].toString()).toSet();
      final now = DateTime.now();
      final orphanBatches = (await _loadPreFanOutBatches())
          .where((b) =>
              b.importJobs.every((ij) => !renderedJobIds.contains(ij.id)))
          .toList();
      if (!mounted) return;

      inProgress.addAll(
        orphanBatches.where((b) => b.isInFlightAt(now)).map(_JobView.fromBatch),
      );

      // Past the grace window with no ImportJobs, a batch is not slow — it
      // is dead, and saying "In Progress" about it is a spinner that never
      // stops. Measured case (parsercap1): batch 9384da8a submitted
      // 19:10:33Z, its AWS Batch job never started, three attempts died on
      // `instance-terminated-no-capacity`, terminal FAILED at 22:17Z, zero
      // ImportJobs ever created. Nothing server-side reconciles the batch
      // row, so it still reads `submitted` — age is the only signal the
      // client has, which is why this says "never started" rather than
      // claiming to know the cause.
      // Only batches that never fanned out. One whose jobs exist but are
      // absent from `rawJobs` (dismissed, say) is not dead — its jobs are
      // accounted for elsewhere, and calling it failed would be a second
      // row for an import the user already dealt with.
      final stalledBatches = orphanBatches
          .where((b) => !b.isInFlightAt(now) && !b.hasFannedOut)
          .map(_JobView.fromStalledBatch)
          .toList();

      // Auto-Imported + Skipped cut off at 30 days — older entries are
      // reachable via See-all. Needs Review + Failed are actionable, so
      // they show regardless of age.
      final cutoff = DateTime.now().subtract(const Duration(days: 30));
      // job id -> how many of its items are still in flight while the job
      // itself is not. One row per job, never one per item.
      final stragglersByJob = <String, int>{};
      final needsReview = <_ItemView>[];
      final failed = <_ItemView>[];
      final autoImported = <_ItemView>[];
      final skipped = <_ItemView>[];

      for (final j in rawJobs) {
        for (final i in itemsByJobId[j['id'].toString()] ?? const []) {
          final itemStatus = i['status']?.toString();
          final view = _ItemView.fromJson(i, j);
          switch (itemStatus) {
            case 'awaiting_review':
              needsReview.add(view);
            case 'failed':
              failed.add(view);
            case 'completed':
              if (i['created_recipe_id'] == null) break;
              if (view.createdAt != null &&
                  view.createdAt!.isBefore(cutoff)) {
                break;
              }
              autoImported.add(view);
            case 'skipped':
              if (view.createdAt != null &&
                  view.createdAt!.isBefore(cutoff)) {
                break;
              }
              skipped.add(view);
            case 'pending':
            case 'extracting':
            case 'matching':
              // Normally covered by the parent job's Blue row. When the
              // parent has moved on, nothing rendered these at all while
              // `imports_actionable` counted every one.
              //
              // Counted per JOB, not per item. `awaiting_review` is not an
              // in-progress status but the job is still running —
              // `create_recipe_task.py:465-483` flips a job to
              // `awaiting_review` as soon as one item needs review, with
              // the rest still `pending` — so one row per item turned a
              // 50-URL bulk import into 48 rows and broke this section's
              // job-granularity rule.
              if (!_isInProgressJob(j)) {
                stragglersByJob.update(
                  j['id'].toString(),
                  (n) => n + 1,
                  ifAbsent: () => 1,
                );
              }
            default:
              break;
          }
        }
      }

      for (final j in rawJobs) {
        final jobId = j['id'].toString();
        final straggling = stragglersByJob[jobId];
        if (straggling == null) continue;
        // A cancelled import's leftovers are abandoned, not in flight —
        // rendering "Importing 0 of 17" for an import the user cancelled
        // would be a lie with a progress ring on it.
        if (kAbandonedJobStatuses.contains(j['status']?.toString())) continue;
        inProgress.add(_JobView.fromStragglers(j, straggling));
      }

      // Newest first, like every other section — a batch row that has just
      // been created is the newest thing on screen and was rendering under
      // older jobs because this list alone was never sorted.
      inProgress.sort((a, b) {
        final at = a.createdAt, bt = b.createdAt;
        if (at == null && bt == null) return 0;
        if (at == null) return 1;
        if (bt == null) return -1;
        return bt.compareTo(at);
      });
      needsReview.sort(_byCreatedAtDesc);
      failed.sort(_byCreatedAtDesc);
      autoImported.sort(_byCreatedAtDesc);
      skipped.sort(_byCreatedAtDesc);

      setState(() {
        _stalledBatches = stalledBatches;
        _inProgress = inProgress;
        _needsReview = needsReview;
        _failed = failed;
        _autoImported = autoImported;
        _skipped = skipped;
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

  /// Active parser batches that have not yet produced an ImportJob.
  ///
  /// Failure here must not take the whole tab down with it: jobs and items
  /// are the main surface, and a batches outage should cost the pre-fan-out
  /// rows only. Reported rather than swallowed, so the degradation is
  /// visible in Crashlytics instead of looking like "no imports".
  Future<List<ImportBatch>> _loadPreFanOutBatches() async {
    try {
      final response = await _apiClient.listParserBatches(
        activeOnly: true,
        limit: 20,
      );
      final raw = (response.data['batches'] as List?) ?? const [];
      return raw
          .whereType<Map>()
          .map((m) => ImportBatch.fromJson(m.cast<String, dynamic>()))
          // `isActive` (the raw status), NOT `isInFlight`: the caller
          // partitions these into still-working and dead, and filtering by
          // in-flight here would drop the dead ones before they could be
          // rendered as failed.
          .where((b) => b.isActive)
          .toList();
    } catch (e, st) {
      ErrorReporter.report(e, st,
          area: 'activity', operation: 'imports_tab_batches');
      return const [];
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
        content: const Text('Dismissed'),
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
      // rf-5: emit so home-surface subscribers (imports-see-all,
      // activity-read badge) react without waiting on a poll tick.
      // This is the epic's one UI-handler emit exception — flagged
      // as cleanup debt in the epic Risks section (pull into an
      // ImportItemService in a follow-on).
      emitMutation(ImportItemDismissed(
        itemId: id,
        item: null,
        jobDismissed: false,
      ));
      // afh-4: See-all count bumps by 1. Fire-and-forget so the
      // snackbar UX stays instant.
      if (mounted) {
        unawaited(
          ref.read(importsSeeAllCountProvider.notifier).refresh(),
        );
      }
    } on DioException catch (e) {
      errorMessage = e.response?.statusCode == 409
          ? "Can't dismiss while importing"
          : "Couldn't dismiss, try again";
    } catch (_) {
      errorMessage = "Couldn't dismiss, try again";
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
    final visibleSkipped = _skipped
        .where((i) => !locallyArchived.contains(i.id))
        .toList();
    final visibleInProgress = _inProgress;

    final allEmpty = visibleInProgress.isEmpty &&
        _stalledBatches.isEmpty &&
        visibleReview.isEmpty &&
        visibleFailed.isEmpty &&
        visibleAutoImported.isEmpty &&
        visibleSkipped.isEmpty;

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
            count: visibleFailed.length + _stalledBatches.length,
            color: stateColors.failed,
            children: [
              ..._stalledBatches
                  .map((b) => _buildStalledBatchRow(b, stateColors)),
              ...visibleFailed.map((i) => _buildSwipeableItemRow(
                    item: i,
                    stateColor: stateColors.failed,
                    chipLabel: 'Failed',
                    rowState: ImportRowState.failed,
                    onTap: () =>
                        context.push('/recipes/import/review/${i.id}'),
                  )),
            ],
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
          // Skipped lands in a neutral/muted section — the parser ran
          // to completion but produced no recipe (duplicate, low-
          // confidence photo, etc.). Not actionable; rendering it
          // tells the user "yes your photo was processed, just nothing
          // came out" instead of silently dropping the activity.
          ImportStateSection(
            label: 'Skipped',
            count: visibleSkipped.length,
            color: colorScheme.outline,
            children: visibleSkipped
                .map((i) => _buildSwipeableItemRow(
                      item: i,
                      stateColor: colorScheme.outline,
                      chipLabel: 'Skipped',
                      rowState: ImportRowState.skipped,
                      onTap: () => context
                          .push('/recipes/import/review/${i.id}'),
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
    // A batch row speaks for a parser batch, and what is true about one is
    // narrower than "Importing X of N": the photos have been accepted and
    // are waiting for a GPU machine. The server never records the moment a
    // machine picks them up — `parser_batch_completion.py` writes only on
    // terminal — so "Parsing…" is not a state this client can honestly
    // render (impstat1). Waiting, and for how long, is.
    final batch = job.batch;
    final statusLabel = batch != null
        ? 'Waiting for a parser machine · queued ${_formatDuration(batch.ageAt(DateTime.now()))}'
        : total > 0
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
      expansion: batch == null ? null : _buildBatchExpansion(batch, states),
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
        onTap: job.openable
            ? () => context.push('/recipes/import/review-list/${job.id}')
            : null,
      ),
    );
  }

  /// A batch whose parser job never produced anything.
  ///
  /// No swipe and no tap: there is no ImportItem to archive and no
  /// ImportJob to open — the rows behind it were never created. The copy
  /// says what is known (it never started) and not what caused it; the
  /// client cannot tell a capacity failure from a crash, and nothing
  /// server-side has marked the batch failed at all (parsercap1).
  Widget _buildStalledBatchRow(_JobView view, ImportStateColors states) {
    final photos = view.totalItems;
    final b = view.batch;
    return _ExpandableRow(
      rowId: view.id,
      recipeName: photos == 1 ? '1 photo' : '$photos photos',
      itemIdForTelemetry: null,
      retryCount: 0,
      lastRetryAt: null,
      errorMessage: null,
      sourceType: 'photo',
      sourceReference: null,
      confidenceScore: null,
      confidenceSource: null,
      rowState: null,
      onReview: null,
      onRetry: null,
      onViewRecipe: null,
      onArchive: null,
      expansion: b == null ? null : _buildBatchExpansion(b, states),
      row: ImportRow(
        id: view.id,
        sourceIcon: _iconForSourceType('photo'),
        title: photos == 1 ? '1 photo' : '$photos photos',
        // Not "failed": nothing has failed, and nothing has succeeded
        // either. Past the watcher's budget nobody is looking at this batch
        // any more, and the only path left is a callback that does not
        // retry (cbretry1). That is what the row says, and it offers no
        // retry because no endpoint can resubmit a batch.
        statusLabel:
            "This import stopped responding. It hasn't been picked up by "
            'a parser machine.',
        stateColor: states.failed,
        stateChipLabel: 'Stuck',
        timeLabel: _formatTime(view.createdAt),
        trailing: ImportRowCaret(
          rowId: view.id,
          recipeName: photos == 1 ? '1 photo' : '$photos photos',
        ),
      ),
    );
  }

  /// The per-photo detail a batch row expands to show.
  ///
  /// `jobs[]` has been on the wire since the endpoint was written and no UI
  /// has ever rendered it (impstat1). Expansion rather than navigation
  /// because a pre-fan-out batch has no ImportJob to navigate to.
  Widget _buildBatchExpansion(ImportBatch b, ImportStateColors states) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final photo in b.jobs)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(photo.displayName),
                        Text(
                          _photoStatusLabel(photo.status),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        if (photo.errorMessage != null &&
                            photo.errorMessage!.isNotEmpty)
                          Text(
                            photo.errorMessage!,
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(color: states.failed),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          if (b.jobs.isEmpty)
            // Real and worth saying: the batch exists, the photos were
            // accepted, and no per-photo record has been created yet.
            Text(
              'No per-photo detail yet — the parser has not started.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      ),
    );
  }

  /// Plain-language per-photo status. `running` is absent deliberately: the
  /// server never writes it (see impstat1's spec), so rendering copy for it
  /// would be inventing a state.
  String _photoStatusLabel(String status) {
    switch (status) {
      case 'pending':
      case 'submitted':
        return 'Waiting for a parser machine';
      case 'succeeded':
        return 'Parsed';
      case 'failed':
        return 'Failed to parse';
      default:
        return status;
    }
  }

  /// "2 min", "85 min", "3 h 5 min" — coarse on purpose. A queue wait is
  /// not precise enough to warrant seconds, and false precision is the
  /// habit this surface is trying to break.
  String _formatDuration(Duration d) {
    if (d.inMinutes < 1) return 'less than a minute';
    if (d.inMinutes < 60) return '${d.inMinutes} min';
    final hours = d.inHours;
    final mins = d.inMinutes % 60;
    return mins == 0 ? '$hours h' : '$hours h $mins min';
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
      // rf-5: emit so see-all + activity-read refetch immediately.
      emitMutation(ImportItemRetried(
        itemId: item.id,
        item: null,
      ));
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
      case ImportRowState.skipped:
        break;
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

  /// A custom expansion body, for rows with no `item_id` to hang the
  /// telemetry expansion off — a parser batch, which expands to per-photo
  /// detail from `jobs[]` instead (impstat1).
  final Widget? expansion;

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
    this.expansion,
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
        if (expanded && expansion != null) expansion!,
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

  /// False when [id] is not a real ImportJob id — a synthesised row for a
  /// parser batch that has not fanned out. Those rows have nothing to open.
  final bool openable;

  /// The parser batch this row stands for, when it stands for one. Carries
  /// the per-photo `jobs` the row expands to show — data the API has always
  /// sent and the UI never rendered (impstat1).
  final ImportBatch? batch;
  final String? sourceType;
  final String? sourceUrl;
  final int totalItems;
  final int processedItems;
  final DateTime? createdAt;

  _JobView({
    required this.id,
    this.openable = true,
    this.batch,
    required this.sourceType,
    required this.sourceUrl,
    required this.totalItems,
    required this.processedItems,
    required this.createdAt,
  });

  /// A parser batch that has not fanned out yet. `group_count` is the
  /// photo count, which is what the user is waiting on, so it reads as
  /// "Importing 0 of 3" rather than a bare spinner.
  ///
  /// `openable: false` — there is no ImportJob behind this row yet, and the
  /// review-list route takes a UUID. Pushing `batch:<uuid>` at it produced
  /// a 500 and an `error_logs` row per tap, on the row the user is most
  /// likely to tap because it is the one they are waiting on.
  factory _JobView.fromBatch(ImportBatch b) => _JobView(
        id: 'batch:${b.id}',
        openable: false,
        batch: b,
        sourceType: 'photo',
        sourceUrl: null,
        totalItems: b.groupCount,
        processedItems: 0,
        createdAt: b.createdAt,
      );

  /// A batch that produced no ImportJobs and is past the grace window.
  /// Same shape as [fromBatch] — nothing to open, because there is still no
  /// ImportJob behind it.
  factory _JobView.fromStalledBatch(ImportBatch b) => _JobView(
        id: 'batch:${b.id}',
        openable: false,
        batch: b,
        sourceType: 'photo',
        sourceUrl: null,
        totalItems: b.groupCount,
        processedItems: 0,
        createdAt: b.createdAt,
      );

  /// Items still in flight under a job that has already moved on, summarised
  /// as one row for the job. Keeps the job's real id, so the row opens the
  /// same review list as any other job row.
  factory _JobView.fromStragglers(dynamic j, int straggling) => _JobView(
        id: j['id'].toString(),
        sourceType: j['source_type'] as String?,
        sourceUrl: j['source_url'] as String?,
        totalItems: straggling,
        processedItems: 0,
        createdAt: j['created_at'] != null
            ? DateTime.tryParse(j['created_at'].toString())
            : null,
      );

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
