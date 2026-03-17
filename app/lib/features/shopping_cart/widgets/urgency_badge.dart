import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
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

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : 8,
        vertical: compact ? 2 : 4,
      ),
      decoration: BoxDecoration(
        color: _backgroundColor,
        borderRadius: BorderRadius.circular(compact ? 4 : 6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!compact) ...[
            Icon(
              _icon,
              size: 12,
              color: _foregroundColor,
            ),
            const SizedBox(width: 4),
          ],
          Text(
            urgency.displayName,
            style: TextStyle(
              fontSize: compact ? 10 : 11,
              fontWeight: FontWeight.w600,
              color: _foregroundColor,
            ),
          ),
        ],
      ),
    );
  }

  Color get _backgroundColor {
    switch (urgency) {
      case UrgencyLevel.overdue:
        return AppColors.errorLight;
      case UrgencyLevel.urgent:
        return AppColors.warningLight;
      case UrgencyLevel.today:
        return AppColors.infoLight;
      case UrgencyLevel.soon:
        return AppColors.successLight;
      default:
        return Colors.transparent;
    }
  }

  Color get _foregroundColor {
    switch (urgency) {
      case UrgencyLevel.overdue:
        return AppColors.errorDark;
      case UrgencyLevel.urgent:
        return AppColors.warningDark;
      case UrgencyLevel.today:
        return AppColors.infoDark;
      case UrgencyLevel.soon:
        return AppColors.successDark;
      default:
        return AppColors.textSecondary;
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
    final isOverdue = _remaining.isNegative;
    final color = isOverdue ? AppColors.error : AppColors.hazelnut;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isOverdue ? AppColors.errorLight : AppColors.beige,
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
                color: AppColors.textSecondary,
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
