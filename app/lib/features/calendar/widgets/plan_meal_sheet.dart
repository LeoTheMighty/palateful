import 'package:flutter/material.dart';
import '../../../core/di/injection.dart';
import '../../../core/theme/theme.dart';
import '../models/meal_event.dart';
import '../services/meal_calendar_service.dart';

/// Bottom sheet for planning a recipe on the meal calendar.
///
/// Used from recipe detail ("Plan for...") and from the calendar screen
/// when rescheduling an existing event.
class PlanMealSheet extends StatefulWidget {
  final String recipeId;
  final String recipeName;

  /// When provided, the sheet is in edit mode — updates this event.
  final String? eventId;
  final DateTime? initialDate;
  final MealType? initialMealType;

  const PlanMealSheet({
    super.key,
    required this.recipeId,
    required this.recipeName,
    this.eventId,
    this.initialDate,
    this.initialMealType,
  });

  @override
  State<PlanMealSheet> createState() => _PlanMealSheetState();
}

class _PlanMealSheetState extends State<PlanMealSheet> {
  final _service = getIt<MealCalendarService>();

  late DateTime _selectedDate;
  late MealType _selectedMealType;
  bool _isSaving = false;

  bool get _isEditMode => widget.eventId != null;

  @override
  void initState() {
    super.initState();
    _selectedDate = widget.initialDate ?? DateTime.now();
    _selectedMealType = widget.initialMealType ?? MealType.dinner;
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime.now().subtract(const Duration(days: 30)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() {
        _selectedDate = DateTime(
          picked.year,
          picked.month,
          picked.day,
          _selectedDate.hour,
          _selectedDate.minute,
        );
      });
    }
  }

  Future<void> _save() async {
    if (_isSaving) return;
    setState(() => _isSaving = true);

    // Combine date with a reasonable meal-type default time
    final mealTime = _mealDefaultTime(_selectedMealType);
    final scheduledAt = DateTime(
      _selectedDate.year,
      _selectedDate.month,
      _selectedDate.day,
      mealTime.$1,
      mealTime.$2,
    );

    try {
      if (_isEditMode) {
        await _service.updateMealEvent(
          widget.eventId!,
          scheduledAt: scheduledAt,
          mealType: _selectedMealType,
        );
      } else {
        await _service.createMealEvent(
          title: widget.recipeName,
          scheduledAt: scheduledAt,
          mealType: _selectedMealType,
          recipeId: widget.recipeId,
          isShared: true,
        );
      }

      if (mounted) {
        Navigator.pop(context, true);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _isEditMode
                  ? 'Meal rescheduled'
                  : '${widget.recipeName} added to calendar',
            ),
          ),
        );
      }
    } catch (e) {
      setState(() => _isSaving = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to save. Please try again.')),
        );
      }
    }
  }

  (int, int) _mealDefaultTime(MealType type) {
    switch (type) {
      case MealType.breakfast:
        return (8, 0);
      case MealType.lunch:
        return (12, 0);
      case MealType.dinner:
        return (18, 0);
      case MealType.snack:
        return (15, 0);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;

    return Padding(
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 24,
        bottom: 24 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _isEditMode ? 'Reschedule Meal' : 'Plan for...',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.onSurface,
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.pop(context),
                color: colorScheme.onSurfaceVariant,
              ),
            ],
          ),

          const SizedBox(height: 4),

          // Recipe name
          Text(
            widget.recipeName,
            style: TextStyle(
              fontSize: 14,
              color: colorScheme.onSurfaceVariant,
            ),
          ),

          const SizedBox(height: 24),

          // Date picker row
          Text(
            'Date',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: _pickDate,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.calendar_today_outlined,
                    size: 18,
                    color: colorScheme.primary,
                  ),
                  const SizedBox(width: 12),
                  Text(
                    _formatDate(_selectedDate),
                    style: TextStyle(
                      fontSize: 15,
                      color: colorScheme.onSurface,
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    Icons.chevron_right,
                    color: appColors.textTertiary,
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // Meal type selector
          Text(
            'Meal Type',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: MealType.values.map((type) {
              final isSelected = type == _selectedMealType;
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: GestureDetector(
                    onTap: () => setState(() => _selectedMealType = type),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      decoration: BoxDecoration(
                        color: isSelected
                            ? colorScheme.primary
                            : colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        type.displayName,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: isSelected
                              ? colorScheme.onPrimary
                              : colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),

          const SizedBox(height: 28),

          // Save button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _isSaving ? null : _save,
              style: ElevatedButton.styleFrom(
                backgroundColor: colorScheme.primary,
                foregroundColor: colorScheme.onPrimary,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: _isSaving
                  ? SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: colorScheme.onPrimary,
                      ),
                    )
                  : Text(
                      _isEditMode ? 'Reschedule' : 'Add to Calendar',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final tomorrow = today.add(const Duration(days: 1));
    final d = DateTime(date.year, date.month, date.day);

    if (d == today) return 'Today';
    if (d == tomorrow) return 'Tomorrow';

    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final weekday = days[date.weekday - 1];
    return '$weekday, ${months[date.month - 1]} ${date.day}';
  }
}
