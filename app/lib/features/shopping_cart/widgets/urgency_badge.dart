import 'package:flutter/material.dart';
import '../../../core/theme/theme.dart';
import '../models/shopping_list_item.dart';

/// Badge showing urgency level for shopping list items.
class UrgencyBadge extends StatelessWidget {
  final UrgencyLevel urgency;
  final bool compact;

  const UrgencyBadge({
    super.key,
    required this.urgency,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    if (urgency == UrgencyLevel.none || urgency == UrgencyLevel.normal) {
      return const SizedBox.shrink();
    }

    final appColors = context.appColors;
    final colorScheme = Theme.of(context).colorScheme;
    final bgColor = _backgroundColor(appColors);
    final fgColor = _foregroundColor(appColors, colorScheme);

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : 8,
        vertical: compact ? 2 : 4,
      ),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(compact ? 4 : 6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!compact) ...[
            Icon(
              _icon,
              size: 12,
              color: fgColor,
            ),
            const SizedBox(width: 4),
          ],
          Text(
            urgency.displayName,
            style: TextStyle(
              fontSize: compact ? 10 : 11,
              fontWeight: FontWeight.w600,
              color: fgColor,
            ),
          ),
        ],
      ),
    );
  }

  Color _backgroundColor(PalatefulColors appColors) {
    switch (urgency) {
      case UrgencyLevel.overdue:
        return appColors.errorLight;
      case UrgencyLevel.urgent:
        return appColors.warningLight;
      case UrgencyLevel.today:
        return appColors.infoLight;
      case UrgencyLevel.soon:
        return appColors.successLight;
      default:
        return Colors.transparent;
    }
  }

  Color _foregroundColor(PalatefulColors appColors, ColorScheme colorScheme) {
    switch (urgency) {
      case UrgencyLevel.overdue:
        return colorScheme.error;
      case UrgencyLevel.urgent:
        return appColors.warning;
      case UrgencyLevel.today:
        return appColors.info;
      case UrgencyLevel.soon:
        return appColors.success;
      default:
        return colorScheme.onSurfaceVariant;
    }
  }

  IconData get _icon {
    switch (urgency) {
      case UrgencyLevel.overdue:
        return Icons.error_outline;
      case UrgencyLevel.urgent:
        return Icons.schedule;
      case UrgencyLevel.today:
        return Icons.today;
      case UrgencyLevel.soon:
        return Icons.event;
      default:
        return Icons.check_circle_outline;
    }
  }
}

/// Countdown timer for meal prep deadlines.
class CountdownTimer extends StatefulWidget {
  final DateTime deadline;
  final String? label;

  const CountdownTimer({
    super.key,
    required this.deadline,
    this.label,
  });

  @override
  State<CountdownTimer> createState() => _CountdownTimerState();
}

class _CountdownTimerState extends State<CountdownTimer> {
  late Duration _remaining;

  @override
  void initState() {
    super.initState();
    _updateRemaining();
  }

  void _updateRemaining() {
    setState(() {
      _remaining = widget.deadline.difference(DateTime.now());
    });

    // Update every minute
    if (_remaining.isNegative || _remaining.inMinutes < 60) {
      Future.delayed(const Duration(seconds: 30), () {
        if (mounted) _updateRemaining();
      });
    } else {
      Future.delayed(const Duration(minutes: 1), () {
        if (mounted) _updateRemaining();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;
    final isOverdue = _remaining.isNegative;
    final color = isOverdue ? colorScheme.error : colorScheme.secondary;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isOverdue ? appColors.errorLight : colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isOverdue ? Icons.warning_amber : Icons.timer_outlined,
            size: 14,
            color: color,
          ),
          const SizedBox(width: 4),
          Text(
            _formatDuration(),
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
          if (widget.label != null) ...[
            const SizedBox(width: 4),
            Text(
              widget.label!,
              style: TextStyle(
                fontSize: 11,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _formatDuration() {
    final duration = _remaining.isNegative ? -_remaining : _remaining;
    final prefix = _remaining.isNegative ? '-' : '';

    if (duration.inDays > 0) {
      return '$prefix${duration.inDays}d ${duration.inHours % 24}h';
    } else if (duration.inHours > 0) {
      return '$prefix${duration.inHours}h ${duration.inMinutes % 60}m';
    } else {
      return '$prefix${duration.inMinutes}m';
    }
  }
}
