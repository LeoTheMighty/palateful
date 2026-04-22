import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/di/injection.dart';
import '../../../core/theme/theme.dart';
import '../models/calendar.dart';
import '../models/meal_event.dart';
import '../providers/active_calendar_provider.dart';
import '../services/meal_calendar_service.dart';
import 'calendar_picker_sheet.dart';
import 'meal_autocomplete_field.dart';
import 'recipe_autocomplete_field.dart';
import 'recurrence_field.dart';

/// Infers meal type from current hour.
MealType inferMealType() {
  final hour = DateTime.now().hour;
  if (hour < 10) return MealType.breakfast;
  if (hour < 14) return MealType.lunch;
  if (hour < 20) return MealType.dinner;
  return MealType.snack;
}

/// Which entity the plan-meal sheet is currently binding to. Toggled by
/// the Recipe / Meal `SegmentedButton` at the top of the picker row.
enum PlanMealType { recipe, meal }

/// Bottom sheet for planning a meal on the calendar.
///
/// Supports three picker modes via the Recipe / Meal SegmentedButton:
/// - **Recipe pre-filled** (launched from recipe detail): `recipeId` +
///   `recipeName` lock the autocomplete to a single recipe.
/// - **Recipe quick add** (calendar FAB / day "+"): empty autocomplete,
///   free-text + recent-meals + recipe-search supported.
/// - **Meal mode** (Meal detail "Plan for Date"): launches with
///   `initialPlanMealType: PlanMealType.meal` and optionally a
///   pre-filled `initialMealId` + `initialMealName`.
///
/// Edit mode (reschedule) is triggered by `eventId` and shows a subtitle
/// instead of the picker row.
class PlanMealSheet extends ConsumerStatefulWidget {
  final String? recipeId;
  final String? recipeName;

  /// When provided, the sheet is in edit mode — updates this event.
  final String? eventId;
  final DateTime? initialDate;
  final MealType? initialMealType;

  /// Seed for the Calendar row. Falls back to
  /// [activeCalendarProvider]'s current value at open time.
  final String? initialCalendarId;

  /// Default picker mode. Recipe everywhere except "Plan for Date" from
  /// Meal detail, which flips to Meal with a pre-filled linked chip.
  final PlanMealType initialPlanMealType;

  /// Optional pre-filled Meal id for Meal-mode launches.
  final String? initialMealId;

  /// Optional pre-filled Meal name for Meal-mode launches.
  final String? initialMealName;

  const PlanMealSheet({
    super.key,
    this.recipeId,
    this.recipeName,
    this.eventId,
    this.initialDate,
    this.initialMealType,
    this.initialCalendarId,
    this.initialPlanMealType = PlanMealType.recipe,
    this.initialMealId,
    this.initialMealName,
  });

  @override
  ConsumerState<PlanMealSheet> createState() => _PlanMealSheetState();
}

class _PlanMealSheetState extends ConsumerState<PlanMealSheet> {
  final _service = getIt<MealCalendarService>();
  final _nameController = TextEditingController();

  late DateTime _selectedDate;
  late MealType _selectedMealType;
  late PlanMealType _planMealType;
  bool _isSaving = false;
  List<String> _recentMeals = [];

  /// Seeded once at sheet open from `activeCalendarProvider`. Changing
  /// this via the Calendar row mutates form state only — it never
  /// mutates the provider (principle #5: active and target are distinct
  /// pieces of state).
  String? _targetCalendarId;

  /// Recipe id picked via the autocomplete. Null when the user is in
  /// free-text mode (either they never tapped a match or they explicitly
  /// detached). When the widget was opened from a recipe detail page (so
  /// [widget.recipeId] is non-null), that wins.
  String? _pickedRecipeId;

  /// Picked Meal when [_planMealType] is `PlanMealType.meal`. Save is
  /// disabled until this is non-null.
  MealPick? _pickedMeal;

  /// Non-null when the user has configured the meal to repeat.
  RecurrenceValue? _recurrence;

  /// User's per-meal "Remind me at" override. Null = use slot default
  /// (shown as greyed caption). Set via the time picker; cleared via
  /// the Reset-to-default inline action. On save, null → key omitted
  /// from payload (backend falls back to slot default); override → sent
  /// as "HH:MM".
  TimeOfDay? _mealReminderOverride;

  bool get _isEditMode => widget.eventId != null;
  bool get _hasRecipe => widget.recipeId != null;
  String? get _effectiveRecipeId => widget.recipeId ?? _pickedRecipeId;
  bool get _isMealMode => _planMealType == PlanMealType.meal;

  @override
  void initState() {
    super.initState();
    _selectedDate = widget.initialDate ?? DateTime.now();
    _selectedMealType = widget.initialMealType ?? inferMealType();
    _planMealType = widget.initialPlanMealType;
    if (widget.recipeName != null) {
      _nameController.text = widget.recipeName!;
    }
    // Seed target calendar once — explicit override from caller wins,
    // else snapshot the active calendar at open.
    _targetCalendarId = widget.initialCalendarId ??
        ref.read(activeCalendarProvider).value;
    // Meal-mode pre-fill: surface the linked chip + name immediately so
    // the user only has to pick date/time/repeats.
    if (_isMealMode &&
        widget.initialMealId != null &&
        widget.initialMealName != null) {
      _pickedMeal = MealPick(
        mealId: widget.initialMealId!,
        name: widget.initialMealName!,
        componentCount: 0,
      );
    }
    _loadRecentMeals();
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _loadRecentMeals() async {
    final prefs = await SharedPreferences.getInstance();
    final meals = prefs.getStringList('recent_free_text_meals') ?? [];
    if (mounted) {
      setState(() => _recentMeals = meals);
    }
  }

  Future<void> _saveRecentMeal(String name) async {
    if (name.isEmpty || _hasRecipe) return;
    final prefs = await SharedPreferences.getInstance();
    final meals = prefs.getStringList('recent_free_text_meals') ?? [];
    meals.remove(name); // Remove duplicates
    meals.insert(0, name); // Add to front
    if (meals.length > 10) meals.removeLast();
    await prefs.setStringList('recent_free_text_meals', meals);
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

  /// Writable calendars the user can target. In this epic, "writable"
  /// is just "owned" — editor-role support arrives in the sharing epic.
  List<Calendar> get _writableCalendars {
    final all = ref.read(calendarsListProvider).value ?? const [];
    return all.where((c) => c.isOwner).toList();
  }

  Widget _buildCalendarRow(ColorScheme colorScheme) {
    final writable = _writableCalendars;
    if (writable.length < 2) return const SizedBox.shrink();
    final selectedName = writable
        .firstWhere(
          (c) => c.id == _targetCalendarId,
          orElse: () => writable.first,
        )
        .name;
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Calendar',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: _pickCalendar,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.event_note_outlined,
                    size: 18,
                    color: colorScheme.primary,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      selectedName,
                      style: TextStyle(
                        fontSize: 15,
                        color: colorScheme.onSurface,
                      ),
                    ),
                  ),
                  Icon(
                    Icons.arrow_drop_down,
                    color: colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _pickCalendar() async {
    final writable = _writableCalendars;
    if (writable.length < 2) return;
    final picked = await showModalBottomSheet<Calendar>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: CalendarPickerSheet(
            calendars: writable,
            activeId: _targetCalendarId,
            onSelect: (c) => Navigator.of(context).pop(c),
          ),
        ),
      ),
    );
    if (picked != null && mounted) {
      setState(() => _targetCalendarId = picked.id);
    }
  }

  /// Whether Save can be dispatched for the current mode. In Meal mode,
  /// the user must have picked a meal from the autocomplete (free-text
  /// is not permitted — foundation's uniqueness guarantee on `meals`
  /// means a meal identity must be resolved upfront).
  ///
  /// Recipe mode keeps the legacy "always enabled, validate on tap"
  /// behavior so the text controller doesn't need to drive rebuilds.
  bool get _canSave {
    if (_isSaving) return false;
    if (_isMealMode) {
      return _pickedMeal != null;
    }
    return true;
  }

  Future<void> _save() async {
    if (_isSaving) return;
    if (_isMealMode && _pickedMeal == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Pick a meal to plan')),
      );
      return;
    }
    if (!_isMealMode && _nameController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a meal name')),
      );
      return;
    }

    setState(() => _isSaving = true);

    final mealTime = _mealDefaultTime(_selectedMealType);
    final scheduledAt = DateTime(
      _selectedDate.year,
      _selectedDate.month,
      _selectedDate.day,
      mealTime.$1,
      mealTime.$2,
    );

    final title = _isMealMode
        ? _pickedMeal!.name
        : _nameController.text.trim();

    try {
      if (_isEditMode) {
        await _service.updateMealEvent(
          widget.eventId!,
          scheduledAt: scheduledAt,
          mealType: _selectedMealType,
        );
      } else if (_recurrence != null) {
        await _service.createRecurrenceRule(
          mealType: _selectedMealType,
          weekdays: _recurrence!.weekdays,
          interval: _recurrence!.interval,
          monthlyNth: _recurrence!.monthlyNth,
          startDate: _selectedDate,
          endDate: _recurrence!.endDate,
          tzName: _deviceTzName(),
          calendarId: _targetCalendarId ?? '',
          title: _isMealMode
              ? null
              : (_effectiveRecipeId == null ? title : null),
          recipeId: _isMealMode ? null : _effectiveRecipeId,
          mealId: _isMealMode ? _pickedMeal!.mealId : null,
          isShared: true,
        );
      } else {
        await _service.createMealEvent(
          title: title,
          scheduledAt: scheduledAt,
          mealType: _selectedMealType,
          calendarId: _targetCalendarId ?? '',
          recipeId: _isMealMode ? null : _effectiveRecipeId,
          mealId: _isMealMode ? _pickedMeal!.mealId : null,
          isShared: true,
          mealReminderTime: _mealReminderOverride == null
              ? null
              : _reminderTimeWire(_mealReminderOverride!),
        );
        // Only save to the free-text recent list when the meal isn't
        // linked to a real recipe OR a Meal; otherwise the chip row
        // starts polluting with duplicates of real titles.
        if (!_isMealMode && _effectiveRecipeId == null) {
          await _saveRecentMeal(title);
        }
      }

      if (mounted) {
        Navigator.pop(context, true);
        final message = _isEditMode
            ? 'Meal rescheduled'
            : _recurrence != null
                ? 'Repeating ${_selectedMealType.displayName.toLowerCase()}s added.'
                : '$title added to calendar';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message)),
        );
      }
    } catch (e) {
      setState(() => _isSaving = false);
      if (mounted) {
        final message = _recurrence != null
            ? "Couldn't save repeating meal. Try again."
            : 'Failed to save. Please try again.';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message)),
        );
      }
    }
  }

  /// Best-effort IANA TZ name. DateTime.now().timeZoneName returns
  /// abbreviations like "PDT" on some platforms; for those we fall back to
  /// a UTC-offset string that the server validates and rejects, surfacing
  /// the preserve-form-state error path. In production use the `timezone`
  /// package to get the actual IANA name.
  String _deviceTzName() {
    final name = DateTime.now().timeZoneName;
    // Heuristic: IANA names contain '/' (e.g. "America/Los_Angeles").
    if (name.contains('/')) return name;
    // Fall back to UTC when we can't resolve a real IANA name.
    return 'UTC';
  }

  /// Resolved reminder time: override when set, else the current slot's
  /// default. This is what the picker displays + what gets formatted
  /// into `meal_reminder_time` when an override is present.
  TimeOfDay get _effectiveReminderTime {
    if (_mealReminderOverride != null) return _mealReminderOverride!;
    final (h, m) = _mealDefaultTime(_selectedMealType);
    return TimeOfDay(hour: h, minute: m);
  }

  String _formatTimeOfDay(TimeOfDay t) {
    final hour12 = t.hour == 0 ? 12 : (t.hour > 12 ? t.hour - 12 : t.hour);
    final mm = t.minute.toString().padLeft(2, '0');
    final ampm = t.hour < 12 ? 'AM' : 'PM';
    return '$hour12:$mm $ampm';
  }

  /// Serialize TimeOfDay as "HH:MM" (24h) for the API payload. Matches
  /// the backend's `time` column wire format.
  String _reminderTimeWire(TimeOfDay t) {
    final hh = t.hour.toString().padLeft(2, '0');
    final mm = t.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  Future<void> _pickReminderTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _effectiveReminderTime,
    );
    if (picked != null && mounted) {
      setState(() => _mealReminderOverride = picked);
    }
  }

  void _resetReminderToDefault() {
    setState(() => _mealReminderOverride = null);
  }

  Widget _buildReminderRow(ColorScheme colorScheme) {
    final effective = _effectiveReminderTime;
    final hasOverride = _mealReminderOverride != null;
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'Remind me at',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
              const Spacer(),
              if (hasOverride)
                TextButton(
                  onPressed: _resetReminderToDefault,
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    minimumSize: const Size(0, 28),
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: const Text(
                    'Reset to default',
                    style: TextStyle(fontSize: 12),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          GestureDetector(
            key: const Key('remind_me_at_row'),
            onTap: _pickReminderTime,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.notifications_outlined,
                    size: 18,
                    color: colorScheme.primary,
                  ),
                  const SizedBox(width: 12),
                  Text(
                    _formatTimeOfDay(effective),
                    style: TextStyle(
                      fontSize: 15,
                      color: colorScheme.onSurface,
                    ),
                  ),
                  if (!hasOverride) ...[
                    const SizedBox(width: 8),
                    Text(
                      '${_selectedMealType.displayName} default',
                      style: TextStyle(
                        fontSize: 12,
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  const Spacer(),
                  Icon(
                    Icons.chevron_right,
                    color: colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Wall-clock default reminder time per meal slot. KEEP IN SYNC with
  /// `MEAL_SLOT_DEFAULT_TIMES` in
  /// `libraries/utils/utils/models/meal_event.py` — the backend
  /// scheduler reads its copy when `meal_reminder_time` is null, so a
  /// drift here means the user sees one time in the picker and gets
  /// pinged at a different one.
  (int, int) _mealDefaultTime(MealType type) {
    switch (type) {
      case MealType.breakfast:
        return (8, 0);
      case MealType.lunch:
        return (12, 0);
      case MealType.dinner:
        return (18, 30);
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
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  _isEditMode
                      ? 'Reschedule Meal'
                      : _hasRecipe
                          ? 'Plan for...'
                          : 'Add a Meal',
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

            // SegmentedButton: Recipe | Meal. Hidden in edit mode (the
            // event's mode is immutable post-create) and when the sheet
            // is pinned to a specific recipe from the recipe detail
            // screen.
            if (!_isEditMode && !_hasRecipe) ...[
              const SizedBox(height: 8),
              SegmentedButton<PlanMealType>(
                segments: const [
                  ButtonSegment(
                    value: PlanMealType.recipe,
                    label: Text('Recipe'),
                    icon: Icon(Icons.menu_book_outlined),
                  ),
                  ButtonSegment(
                    value: PlanMealType.meal,
                    label: Text('Meal'),
                    icon: Icon(Icons.layers),
                  ),
                ],
                selected: {_planMealType},
                onSelectionChanged: (s) {
                  setState(() {
                    _planMealType = s.first;
                    // Clear the other side's linkage so a stale pick can't
                    // leak across modes.
                    if (_planMealType == PlanMealType.meal) {
                      _pickedRecipeId = null;
                      _nameController.clear();
                    } else {
                      _pickedMeal = null;
                    }
                  });
                },
              ),
              const SizedBox(height: 16),
            ],

            // Picker row — layout depends on (edit, hasRecipe, mode).
            if (!_isEditMode) ...[
              if (_hasRecipe)
                // Launched from a recipe detail page — recipe is already
                // pinned; keep the read-only field shape.
                TextField(
                  controller: _nameController,
                  decoration: InputDecoration(
                    hintText: widget.recipeName,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                  ),
                  textCapitalization: TextCapitalization.sentences,
                  readOnly: true,
                )
              else if (_isMealMode)
                MealAutocompleteField(
                  initialMeal: _pickedMeal,
                  onPicked: (picked) {
                    setState(() => _pickedMeal = picked);
                  },
                )
              else
                // Quick-add recipe mode: autocomplete against the user's
                // recipes + fall back to free-text. Recent chips live
                // inside the autocomplete's empty-state results area.
                RecipeAutocompleteField(
                  controller: _nameController,
                  recentMeals: _recentMeals,
                  onPicked: (picked) {
                    setState(() {
                      _pickedRecipeId = picked.recipeId;
                    });
                  },
                ),
              const SizedBox(height: 16),
            ] else ...[
              // Edit mode: show recipe name as subtitle
              Text(
                _nameController.text,
                style: TextStyle(
                  fontSize: 14,
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 24),
            ],

            // Calendar row — hidden entirely when the user has only one
            // writable calendar (principle #11: no dead UI for the solo
            // case). Seeded from the active calendar on open; changing
            // here mutates form state only.
            _buildCalendarRow(colorScheme),

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
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
                      // Switching meal type only changes the *displayed*
                      // default when no override is set; an override is
                      // preserved across slot switches (the user's
                      // explicit choice wins). Matches meal-2 AC 3.
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

            // "Remind me at" picker. Default tracks the current slot;
            // user can override per-meal. Override persists across
            // meal-type switches (meal-2 AC 3).
            _buildReminderRow(colorScheme),

            // Repeats section — hidden in edit mode (series-level edits
            // happen from the manage screen, not the reschedule flow).
            if (!_isEditMode) ...[
              const SizedBox(height: 20),
              Text(
                'Repeats',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              RecurrenceField(
                value: _recurrence,
                anchorDate: _selectedDate,
                onChanged: (v) => setState(() => _recurrence = v),
              ),
            ],

            const SizedBox(height: 28),

            // Save button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: (_canSave) ? _save : null,
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
                        _isEditMode
                            ? 'Reschedule'
                            : _recurrence != null
                                ? 'Add Recurring Meal'
                                : 'Add to Calendar',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
            ),
          ],
        ),
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
