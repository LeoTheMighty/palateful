import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/services/api_client.dart';
import '../models/import_batch.dart';

const Duration _activePollInterval = Duration(seconds: 5);
const Duration _idlePollInterval = Duration(seconds: 30);
const Duration _recentlyCompletedRetention = Duration(minutes: 5);
const Duration _justStartedHighlightDuration = Duration(seconds: 3);

class ImportBatchesNotifier extends AsyncNotifier<ImportBatchesState>
    with WidgetsBindingObserver {
  Timer? _pollTimer;
  bool _appActive = true;
  // Snapshots of recently-completed batches indexed by id, with the time they
  // first appeared in a terminal state.
  final Map<String, ImportBatch> _recent = {};
  final Map<String, DateTime> _recentSeenAt = {};
  // Set of batch IDs to highlight as "just started"
  final Set<String> _justStarted = {};

  ApiClient get _apiClient => getIt<ApiClient>();

  Set<String> get justStartedBatchIds => Set.unmodifiable(_justStarted);

  @override
  Future<ImportBatchesState> build() async {
    WidgetsBinding.instance.addObserver(this);
    ref.onDispose(() {
      _pollTimer?.cancel();
      WidgetsBinding.instance.removeObserver(this);
    });
    final initial = await _fetch();
    _schedulePoll(initial);
    return initial;
  }

  /// Force an immediate refresh — used by the photo capture screen right after
  /// successful batch submission so the new row appears within one frame.
  Future<void> refresh() async {
    try {
      final fresh = await _fetch();
      state = AsyncData(fresh);
      _schedulePoll(fresh);
    } catch (e, st) {
      // Don't tear down state on a transient refresh error
      state = AsyncError(e, st);
    }
  }

  /// Mark a batch as freshly submitted so the strip can pulse it for ~3s.
  void markJustStarted(String batchId) {
    _justStarted.add(batchId);
    Future.delayed(_justStartedHighlightDuration, () {
      _justStarted.remove(batchId);
      // Re-emit current state so widgets watching `justStartedBatchIds` rebuild
      if (state.hasValue) {
        state = AsyncData(state.value!);
      }
    });
  }

  /// Optimistically hide a batch from the strip without waiting for a
  /// server round-trip. Used by the dismiss flow in mvp-8 so tapping
  /// Dismiss feels instant. If the user taps Undo within the snackbar
  /// window, [locallyRestoreBatch] puts it back.
  ///
  /// NOTE: local state only. Once the next refresh lands, whatever the
  /// server returns wins — so the caller is responsible for firing the
  /// backend dismiss call before/alongside this.
  void locallyRemoveBatch(String batchId) {
    if (!state.hasValue) return;
    final current = state.value!;
    state = AsyncData(
      ImportBatchesState(
        active: current.active.where((b) => b.id != batchId).toList(),
        recentlyCompleted:
            current.recentlyCompleted.where((b) => b.id != batchId).toList(),
      ),
    );
  }

  /// Undo a prior [locallyRemoveBatch] by stitching the batch back into
  /// the active list. Only restores if the batch was previously present.
  void locallyRestoreBatch(ImportBatch batch) {
    if (!state.hasValue) return;
    final current = state.value!;
    // Dedupe guard — refresh may have already put it back.
    final alreadyThere = current.all.any((b) => b.id == batch.id);
    if (alreadyThere) return;
    state = AsyncData(
      ImportBatchesState(
        active: batch.isActive ? [batch, ...current.active] : current.active,
        recentlyCompleted: batch.isActive
            ? current.recentlyCompleted
            : [batch, ...current.recentlyCompleted],
      ),
    );
  }

  Future<ImportBatchesState> _fetch() async {
    final response = await _apiClient.listParserBatches(
      activeOnly: false,
      limit: 20,
    );
    final raw = (response.data['batches'] as List?) ?? const [];
    final all = raw
        .whereType<Map>()
        .map((m) => ImportBatch.fromJson(m.cast<String, dynamic>()))
        .toList();

    final now = DateTime.now();
    final active = <ImportBatch>[];

    // Track newly-terminal batches into the recent map
    for (final b in all) {
      if (b.isActive) {
        active.add(b);
        // If a batch was previously recent and is now active again (unlikely
        // but possible), drop it from recent.
        _recent.remove(b.id);
        _recentSeenAt.remove(b.id);
      } else if (b.isTerminal) {
        if (!_recent.containsKey(b.id)) {
          _recentSeenAt[b.id] = now;
        }
        _recent[b.id] = b;
      }
    }

    // Evict recently-completed batches older than the retention window
    final expired = <String>[];
    _recentSeenAt.forEach((id, seenAt) {
      if (now.difference(seenAt) > _recentlyCompletedRetention) {
        expired.add(id);
      }
    });
    for (final id in expired) {
      _recent.remove(id);
      _recentSeenAt.remove(id);
    }

    final recentlyCompleted = _recent.values.toList()
      ..sort((a, b) => (b.completedAt ?? b.createdAt)
          .compareTo(a.completedAt ?? a.createdAt));

    return ImportBatchesState(
      active: active,
      recentlyCompleted: recentlyCompleted,
    );
  }

  void _schedulePoll(ImportBatchesState snapshot) {
    _pollTimer?.cancel();
    if (!_appActive) return;
    final hasActive = snapshot.active.isNotEmpty;
    final interval = hasActive ? _activePollInterval : _idlePollInterval;
    _pollTimer = Timer(interval, () async {
      try {
        final fresh = await _fetch();
        state = AsyncData(fresh);
        _schedulePoll(fresh);
      } catch (_) {
        // On transient failure, keep last good state and retry on the
        // active interval so we recover quickly.
        _pollTimer = Timer(_activePollInterval, () {
          if (state.hasValue) _schedulePoll(state.value!);
        });
      }
    });
  }

  @override
  // ignore: avoid_renaming_method_parameters
  void didChangeAppLifecycleState(AppLifecycleState lifecycle) {
    final wasActive = _appActive;
    _appActive = lifecycle == AppLifecycleState.resumed;
    if (!_appActive) {
      _pollTimer?.cancel();
      _pollTimer = null;
    } else if (!wasActive && state.hasValue) {
      // Resume immediately
      refresh();
    }
  }
}

final importBatchesProvider =
    AsyncNotifierProvider<ImportBatchesNotifier, ImportBatchesState>(
  ImportBatchesNotifier.new,
);
