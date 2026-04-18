import 'package:flutter/material.dart';

import '../../../core/theme/import_state_colors.dart';
import '../models/import_item_telemetry.dart';

const _stageOrder = ['parsed', 'extracted', 'matched', 'created'];

/// Compact 4-dot pill: at-a-glance stage scan for the collapsed Blue
/// (in-progress) row. Each dot maps 1:1 to a pipeline stage:
/// **parsed · extracted · matched · created**. Filled for completed
/// stages, outlined for not-reached, and the current stage pulses
/// (opacity oscillation).
///
/// Failed stages render filled in the `failed` color. Nothing after a
/// failed stage pulses — once a stage fails, the pipeline is done.
class CompactStagePill extends StatelessWidget {
  /// Telemetry payload. When null (e.g. job-level blue rows that have
  /// no per-item telemetry), callers can pass a synthetic stage list
  /// computed from `last_successful_stage`. For this widget we just
  /// consume the four-stage array.
  final ImportItemTelemetry telemetry;

  const CompactStagePill({super.key, required this.telemetry});

  @override
  Widget build(BuildContext context) {
    final entries = _entriesInOrder(telemetry);
    final currentIdx = _currentStageIndex(entries);

    return Semantics(
      container: true,
      label: _semanticLabel(entries, currentIdx),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < entries.length; i++) ...[
            if (i > 0) const SizedBox(width: 3),
            _StageDot(
              entry: entries[i],
              isCurrent: i == currentIdx,
            ),
          ],
        ],
      ),
    );
  }

  static List<StageEntry> _entriesInOrder(ImportItemTelemetry t) {
    return [
      for (final name in _stageOrder)
        t.stage(name) ?? StageEntry(stage: name, status: 'pending'),
    ];
  }

  static int _currentStageIndex(List<StageEntry> entries) {
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].status == 'pending') return i;
      if (entries[i].status == 'failed') return -1;
    }
    return -1;
  }

  static String _semanticLabel(List<StageEntry> entries, int currentIdx) {
    final parts = <String>[];
    for (var i = 0; i < entries.length; i++) {
      final name = entries[i].stage;
      String word;
      switch (entries[i].status) {
        case 'ok':
          word = 'done';
        case 'failed':
          word = 'failed';
        case 'skipped':
          word = 'skipped';
        default:
          word = i == currentIdx ? 'in progress' : 'pending';
      }
      parts.add('$name $word');
    }
    return 'Pipeline: ${parts.join(', ')}';
  }
}

class _StageDot extends StatefulWidget {
  final StageEntry entry;
  final bool isCurrent;

  const _StageDot({required this.entry, required this.isCurrent});

  @override
  State<_StageDot> createState() => _StageDotState();
}

class _StageDotState extends State<_StageDot>
    with SingleTickerProviderStateMixin {
  AnimationController? _pulse;

  @override
  void initState() {
    super.initState();
    if (widget.isCurrent) _startPulse();
  }

  @override
  void didUpdateWidget(covariant _StageDot old) {
    super.didUpdateWidget(old);
    if (old.isCurrent != widget.isCurrent) {
      if (widget.isCurrent) {
        _startPulse();
      } else {
        _pulse?.dispose();
        _pulse = null;
      }
    }
  }

  void _startPulse() {
    _pulse?.dispose();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulse?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final states = context.importStates;
    final cs = Theme.of(context).colorScheme;

    final isDone = widget.entry.status == 'ok';
    final isFailed = widget.entry.status == 'failed';
    final isPending = widget.entry.status == 'pending';

    final fillColor = isFailed
        ? states.failed
        : (isDone ? states.autoImported : states.inProgress);
    final outlineColor = cs.outlineVariant;

    final filled = isDone || isFailed || widget.isCurrent;

    Widget dot(double alpha) {
      return Container(
        width: 7,
        height: 7,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: filled
              ? fillColor.withValues(alpha: alpha)
              : cs.surfaceContainerHighest,
          border: filled
              ? null
              : Border.all(color: outlineColor, width: 1),
        ),
      );
    }

    if (widget.isCurrent && isPending) {
      final c = _pulse;
      if (c == null) return dot(1.0);
      return AnimatedBuilder(
        animation: c,
        builder: (_, _) => dot(0.4 + 0.6 * c.value),
      );
    }
    return dot(1.0);
  }
}
