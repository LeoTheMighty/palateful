import 'package:flutter/material.dart';

import '../../../core/theme/import_state_colors.dart';
import '../models/import_item_telemetry.dart';

const _stageOrder = ['parsed', 'extracted', 'matched', 'created'];
const _stageLabels = {
  'parsed': 'Parsed',
  'extracted': 'Extracted',
  'matched': 'Matched',
  'created': 'Created',
};

/// Horizontal 4-chip strip rendered inside [ImportRowExpansion] showing
/// each pipeline stage's outcome.
///
/// Derivation: the current stage is the first entry whose status is
/// `pending` AND every preceding entry is terminal (ok / failed /
/// skipped). A `failed` stage stops advancement. If every stage is
/// pending, the first one is marked current. Stages after a failed one
/// render as `—` (not reached).
///
/// Hover / long-press per chip surfaces a tooltip with stage duration
/// + relative timestamp.
class StageTimeline extends StatelessWidget {
  final ImportItemTelemetry telemetry;

  const StageTimeline({super.key, required this.telemetry});

  @override
  Widget build(BuildContext context) {
    final chips = <Widget>[];
    final entries = _entriesInOrder(telemetry);
    final currentIdx = _currentStageIndex(entries);

    for (var i = 0; i < entries.length; i++) {
      final entry = entries[i];
      final kind = _kindFor(entry, i, currentIdx);
      chips.add(_StageChip(entry: entry, kind: kind));
      if (i < entries.length - 1) {
        chips.add(const SizedBox(width: 4));
      }
    }

    return Semantics(
      container: true,
      label: 'Stage timeline',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: chips,
      ),
    );
  }

  static List<StageEntry> _entriesInOrder(ImportItemTelemetry t) {
    return [
      for (final name in _stageOrder)
        t.stage(name) ??
            StageEntry(stage: name, status: 'pending'),
    ];
  }

  /// Returns -1 if no stage is pending (all terminal), else the index
  /// of the first pending entry whose predecessors are all terminal.
  /// A preceding `failed` stops progression — nothing after it is
  /// "current", just "not reached".
  static int _currentStageIndex(List<StageEntry> entries) {
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].status == 'pending') return i;
      if (entries[i].status == 'failed') return -1;
    }
    return -1;
  }

  static _ChipKind _kindFor(
    StageEntry entry,
    int idx,
    int currentIdx,
  ) {
    switch (entry.status) {
      case 'ok':
        return _ChipKind.done;
      case 'failed':
        return _ChipKind.failed;
      case 'skipped':
        return _ChipKind.notReached;
    }
    // pending — either current or unreached.
    if (idx == currentIdx) return _ChipKind.current;
    return _ChipKind.notReached;
  }
}

enum _ChipKind { done, current, failed, notReached }

class _StageChip extends StatelessWidget {
  final StageEntry entry;
  final _ChipKind kind;

  const _StageChip({required this.entry, required this.kind});

  @override
  Widget build(BuildContext context) {
    final label = _stageLabels[entry.stage] ?? entry.stage;
    final tooltip = _tooltipFor(entry);
    final semantic = _semanticFor(label, entry, kind);

    return Tooltip(
      message: tooltip,
      child: Semantics(
        container: true,
        label: semantic,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: _bgColor(context, kind),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _Glyph(kind: kind, color: _fgColor(context, kind)),
              const SizedBox(width: 4),
              Text(
                label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: _fgColor(context, kind),
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _tooltipFor(StageEntry e) {
    final durationPart = e.durationMs != null
        ? _formatDuration(e.durationMs!)
        : null;
    final agoPart = e.completedAt != null
        ? _formatAgo(e.completedAt!)
        : (e.startedAt != null ? _formatAgo(e.startedAt!) : null);

    final parts = <String>[
      _stageLabels[e.stage] ?? e.stage,
      _statusWord(e.status),
      if (durationPart != null) durationPart,
      if (agoPart != null) agoPart,
    ];
    return parts.join(' · ');
  }

  String _semanticFor(String label, StageEntry e, _ChipKind kind) {
    final statusWord = switch (kind) {
      _ChipKind.done => 'completed',
      _ChipKind.current => 'current',
      _ChipKind.failed => 'failed',
      _ChipKind.notReached => 'not reached',
    };
    final suffix = e.durationMs != null
        ? ', ${_formatDuration(e.durationMs!)}'
        : '';
    return '$label · $statusWord$suffix';
  }

  Color _bgColor(BuildContext context, _ChipKind kind) {
    final states = context.importStates;
    final cs = Theme.of(context).colorScheme;
    switch (kind) {
      case _ChipKind.done:
        return states.autoImported.withValues(alpha: 0.15);
      case _ChipKind.current:
        return states.inProgress.withValues(alpha: 0.15);
      case _ChipKind.failed:
        return states.failed.withValues(alpha: 0.15);
      case _ChipKind.notReached:
        return cs.surfaceContainerHighest;
    }
  }

  Color _fgColor(BuildContext context, _ChipKind kind) {
    final states = context.importStates;
    final cs = Theme.of(context).colorScheme;
    switch (kind) {
      case _ChipKind.done:
        return states.autoImported;
      case _ChipKind.current:
        return states.inProgress;
      case _ChipKind.failed:
        return states.failed;
      case _ChipKind.notReached:
        return cs.onSurfaceVariant;
    }
  }

  static String _statusWord(String status) {
    switch (status) {
      case 'ok':
        return 'completed';
      case 'pending':
        return 'pending';
      case 'failed':
        return 'failed';
      case 'skipped':
        return 'skipped';
      default:
        return status;
    }
  }

  static String _formatDuration(int ms) {
    if (ms < 1000) return '${ms}ms';
    final secs = ms / 1000;
    if (secs < 60) {
      return secs < 10
          ? '${secs.toStringAsFixed(1)}s'
          : '${secs.toStringAsFixed(0)}s';
    }
    final mins = secs / 60;
    return '${mins.toStringAsFixed(0)}m';
  }

  static String _formatAgo(DateTime when) {
    final diff = DateTime.now().difference(when.toLocal());
    if (diff.inSeconds < 60) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}

class _Glyph extends StatefulWidget {
  final _ChipKind kind;
  final Color color;

  const _Glyph({required this.kind, required this.color});

  @override
  State<_Glyph> createState() => _GlyphState();
}

class _GlyphState extends State<_Glyph>
    with SingleTickerProviderStateMixin {
  AnimationController? _pulse;

  @override
  void initState() {
    super.initState();
    if (widget.kind == _ChipKind.current) _startPulse();
  }

  @override
  void didUpdateWidget(covariant _Glyph oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.kind != widget.kind) {
      if (widget.kind == _ChipKind.current) {
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
    switch (widget.kind) {
      case _ChipKind.done:
        return Icon(Icons.check, size: 14, color: widget.color);
      case _ChipKind.failed:
        return Icon(Icons.close, size: 14, color: widget.color);
      case _ChipKind.notReached:
        return Text(
          '—',
          style: TextStyle(color: widget.color, fontSize: 14, height: 1),
        );
      case _ChipKind.current:
        final c = _pulse;
        if (c == null) {
          return Icon(Icons.hourglass_bottom, size: 14, color: widget.color);
        }
        return AnimatedBuilder(
          animation: c,
          builder: (_, _) {
            final alpha = 0.4 + 0.6 * c.value;
            return Icon(
              Icons.hourglass_bottom,
              size: 14,
              color: widget.color.withValues(alpha: alpha),
            );
          },
        );
    }
  }
}
