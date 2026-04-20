/// cmt-4 — horizontally-scrollable row of timer buttons below the
/// current step's instruction card.
///
/// Consumes `List<StepTimer>` from either source (extracted or
/// regex fallback — the rendering is source-agnostic). Overflow is
/// handled by horizontal scroll; there is no fixed button cap beyond
/// the 10-per-step cap that `extractTimers` already enforces.

library;

import 'package:flutter/material.dart';
import '../util/cook_timer_token.dart';
import '../util/timer_regex.dart';

typedef StartTimerCallback = void Function(Duration duration, String label);

class StepTimersRow extends StatelessWidget {
  final List<StepTimer> timers;
  final StartTimerCallback onStart;

  const StepTimersRow({
    super.key,
    required this.timers,
    required this.onStart,
  });

  @override
  Widget build(BuildContext context) {
    if (timers.isEmpty) return const SizedBox.shrink();
    final accent = resolveCookTimer(context);
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < timers.length; i++) ...[
            _TimerButton(timer: timers[i], accent: accent, onStart: onStart),
            if (i < timers.length - 1) const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

String _displayLabel(StepTimer t) {
  if (t.label == 'timer' || t.label.isEmpty) {
    return '${t.durationMinutes} min';
  }
  return '${t.durationMinutes} min ${t.label}';
}

class _TimerButton extends StatelessWidget {
  final StepTimer timer;
  final Color accent;
  final StartTimerCallback onStart;

  const _TimerButton({
    required this.timer,
    required this.accent,
    required this.onStart,
  });

  @override
  Widget build(BuildContext context) {
    final label = _displayLabel(timer);
    final button = OutlinedButton.icon(
      onPressed: () => onStart(
        Duration(minutes: timer.durationMinutes),
        timer.label,
      ),
      icon: const Icon(Icons.timer),
      label: Text(label),
      style: OutlinedButton.styleFrom(
        foregroundColor: accent,
        side: BorderSide(color: accent),
      ),
    );
    final tooltipMessage = timer.rangeUpperLabel;
    if (tooltipMessage == null) return button;
    return Tooltip(message: tooltipMessage, child: button);
  }
}
