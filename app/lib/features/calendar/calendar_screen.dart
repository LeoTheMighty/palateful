import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/di/injection.dart';
import '../../core/services/auth_service.dart';
import '../../core/state/mutation_failure_copy.dart';
import '../../core/state/mutation_snackbar.dart';
import '../../core/theme/theme.dart';
import '../../shared/widgets/default_change_sheet.dart';
import '../shopping_cart/models/shopping_list.dart';
import '../shopping_cart/services/shopping_cart_service.dart';
import 'models/meal_event.dart';
import 'models/calendar.dart';
import 'providers/active_calendar_provider.dart';
import 'providers/meal_events_provider.dart';
import 'services/meal_calendar_service.dart';
import 'widgets/calendar_create_dialog.dart';
import 'widgets/calendar_settings_sheet.dart';
import 'widgets/calendar_switcher_header.dart';
import 'widgets/day_detail_sheet.dart';
import 'widgets/meal_detail_sheet.dart';
import 'widgets/plan_meal_sheet.dart';
import '../../core/services/error_reporter.dart';
import '../recipes/cook_mode/widgets/post_cook_feedback_sheet.dart';
import '../../core/services/api_client.dart';
import '../../core/services/recipe_cache_service.dart';
import '../meals/widgets/meal_tile.dart' show kMealComponentCountLabel;

/// Calendar tab — week view showing scheduled meal events.
///
/// rmc-3: grid state is driven by [mealEventsByRangeProvider] rather than
/// an imperative `_loadEvents()` + `_eventsByDay` map. Every mutation
/// site in `MealCalendarService` emits a MutationBus event; the provider
/// subscribes with a 100ms coalescer and re-fetches. Pending deletes
/// (for the optimistic-undo affordance) are tracked locally so the
/// provider's source-of-truth list can be filtered without touching
/// server state during the undo window.
class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  final _service = getIt<MealCalendarService>();
  final _cartService = getIt<ShoppingCartService>();

  /// Monday of the currently displayed week.
  late DateTime _weekStart;

  /// Session-scoped set of event ids whose ingredients have been added to a
  /// shopping list in the current week. Cleared whenever the user moves to
  /// a new week.
  final Set<String> _addedEventIds = <String>{};

  /// Event ids the user tapped Unschedule on. Filtered out of the grid
  /// optimistically during the 3-second undo window. Cleared on undo
  /// (event reappears) or on commit (the delete fires and the provider
  /// re-fetches without the event).
  final Set<String> _pendingDeleteIds = <String>{};

  @override
  void initState() {
    super.initState();
    _weekStart = _mondayOf(DateTime.now());
  }

  DateTime _mondayOf(DateTime date) {
    final diff = date.weekday - DateTime.monday;
    return DateTime(date.year, date.month, date.day - diff);
  }

  DateTime get _weekEnd => _weekStart.add(const Duration(days: 6));

  List<DateTime> get _weekDays => List.generate(
        7,
        (i) => _weekStart.add(Duration(days: i)),
      );

  DateTime _dayKey(DateTime dt) => DateTime(dt.year, dt.month, dt.day);

  /// Resolve the active calendar id synchronously for provider keying.
  String? get _activeCalendarId => ref.watch(activeCalendarProvider).value;

  MealEventsRangeKey get _rangeKey => MealEventsRangeKey(
        start: _weekStart,
        end: _weekEnd,
        calendarId: _activeCalendarId,
      );

  /// Events for the active week, grouped by day — derived from the
  /// range provider's value (or the previous value during refetch, via
  /// `AsyncValue.value` — the loading-flicker guard inherited from
  /// the rf-3 homeContentProvider pattern).
  Map<DateTime, List<MealEvent>> _groupByDay(List<MealEvent> events) {
    final byDay = <DateTime, List<MealEvent>>{};
    for (final e in events) {
      if (_pendingDeleteIds.contains(e.id)) continue;
      final key = _dayKey(e.scheduledAt);
      byDay.putIfAbsent(key, () => []).add(e);
    }
    return byDay;
  }

  void _previousWeek() {
    setState(() {
      _weekStart = _weekStart.subtract(const Duration(days: 7));
      _addedEventIds.clear();
    });
  }

  void _nextWeek() {
    setState(() {
      _weekStart = _weekStart.add(const Duration(days: 7));
      _addedEventIds.clear();
    });
  }

  Future<void> _refreshGrid() async {
    ref.invalidate(mealEventsByRangeProvider(_rangeKey));
    await ref.read(mealEventsByRangeProvider(_rangeKey).future);
  }

  Future<void> _deleteEvent(MealEvent event) async {
    try {
      await _service.deleteMealEvent(event.id, calendarId: _activeCalendarId);
    } catch (_) {
      if (!mounted) return;
      showMutationFailureSnackbar(
        context,
        MutationType.deleteMealEvent,
        () => _deleteEvent(event),
      );
    }
  }

  /// Unschedule with optimistic removal + 3s snackbar undo (locked
  /// decision #3 + bugs-cal-1 AC #3). Recurring series collapse silently
  /// under the current backend — see locked decision #20 + the audit
  /// filed as bugs-cal-3b.
  void _unscheduleWithUndo(MealEvent event) {
    setState(() => _pendingDeleteIds.add(event.id));

    var undone = false;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('Meal unscheduled'),
        duration: const Duration(seconds: 3),
        action: SnackBarAction(
          label: 'Undo',
          onPressed: () {
            undone = true;
            if (!mounted) return;
            setState(() => _pendingDeleteIds.remove(event.id));
          },
        ),
      ),
    );

    // Wait past the snackbar window before committing the server-side
    // delete. If the user tapped Undo, skip the call entirely. Fire the
    // delete even if the widget unmounted — matches pre-refactor
    // behavior (the server source-of-truth must reflect the user's
    // intent, and the provider invalidation happens via MealEventDeleted
    // regardless of this widget's lifecycle).
    final calendarIdAtDispatch = _activeCalendarId;
    Future.delayed(const Duration(seconds: 3), () async {
      if (undone) return;
      try {
        await _service.deleteMealEvent(event.id,
            calendarId: calendarIdAtDispatch);
        if (mounted) {
          setState(() => _pendingDeleteIds.remove(event.id));
        }
      } catch (_) {
        if (!mounted) return;
        // Restore on failure and let the user retry manually.
        setState(() => _pendingDeleteIds.remove(event.id));
        showMutationFailureSnackbar(
          context,
          MutationType.deleteMealEvent,
          () => _unscheduleWithUndo(event),
        );
      }
    });
  }

  Future<void> _rescheduleEvent(MealEvent event, DateTime newLocal) async {
    try {
      await _service.rescheduleMealEvent(event.id, newLocal);
    } catch (_) {
      if (!mounted) return;
      showMutationFailureSnackbar(
        context,
        MutationType.rescheduleMealEvent,
        () => _rescheduleEvent(event, newLocal),
      );
    }
  }

  Future<void> _markMealCooked(MealEvent event) async {
    final recipe = event.recipe;
    if (recipe == null) return; // gated by the button's disabled state

    final apiClient = getIt<ApiClient>();
    final recipeCache = getIt<RecipeCacheService>();
    // Kick off the status write independent of the feedback sheet so the
    // pantry decrement fires whether or not the user rates. Failure is
    // surfaced via snackbar but doesn't block the feedback flow.
    unawaited(() async {
      try {
        await _service.markMealCompleted(event.id);
      } catch (_) {
        if (!mounted) return;
        showMutationFailureSnackbar(
          context,
          MutationType.markMealCompleted,
          () => _markMealCooked(event),
        );
      }
    }());

    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surfaceContainerLow,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetCtx) => PostCookFeedbackSheet(
        recipeId: recipe.id,
        recipeName: recipe.name,
        apiClient: apiClient,
        recipeCache: recipeCache,
        isOffline: false,
        onComplete: () => Navigator.of(sheetCtx).pop(),
      ),
    );
  }

  void _openMealDetailSheet(MealEvent event) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => MealDetailSheet(
        event: event,
        onReschedule: (newLocal) => _rescheduleEvent(event, newLocal),
        onUnschedule: () => _unscheduleWithUndo(event),
        onMarkCooked:
            event.recipe == null ? null : () => _markMealCooked(event),
        onSeriesEnded: () {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
                content: Text('Series ended. Future occurrences removed.')),
          );
        },
      ),
    );
  }

  void _openDayDetailSheet(DateTime day) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => DayDetailSheet(
        day: day,
        calendarId: _activeCalendarId,
        onMealTap: _openMealDetailSheet,
        onPlanMeal: () => _openQuickAdd(date: day),
      ),
    );
  }

  Future<void> _addIngredientsFromEvent(MealEvent event) async {
    assert(
      event.recipe != null || event.mealId != null,
      '_addIngredientsFromEvent requires a linked recipe or meal',
    );
    final authService = getIt<AuthService>();
    List<ShoppingList> lists;
    try {
      lists = await _cartService.getShoppingLists();
    } catch (_) {
      if (!mounted) return;
      showMutationFailureSnackbar(
        context,
        MutationType.loadShoppingLists,
        () => _addIngredientsFromEvent(event),
      );
      return;
    }

    if (lists.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('No shopping lists — tap + to create one')),
        );
      }
      return;
    }

    ShoppingList? targetList;
    final defaultId = authService.defaultShoppingListId;

    if (defaultId != null) {
      final match = lists.where((l) => l.id == defaultId);
      if (match.isNotEmpty) {
        targetList = match.first;
      } else {
        _cartService.setDefaultShoppingList(null);
      }
    }
    if (targetList == null && lists.length == 1) {
      targetList = lists.first;
    } else if (targetList == null) {
      if (!mounted) return;
      final selected = await showModalBottomSheet<ShoppingList>(
        context: context,
        builder: (ctx) => SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'Choose a shopping list',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
                ),
              ),
              ...lists.map((list) => ListTile(
                    title: Text(list.name),
                    subtitle: Text('${list.items.length} item(s)'),
                    onTap: () => Navigator.pop(ctx, list),
                  )),
            ],
          ),
        ),
      );
      if (selected == null) return;
      targetList = selected;
      _cartService.setDefaultShoppingList(targetList.id);
    }

    try {
      int itemsAdded;
      if (event.mealId != null) {
        // Meal event — route through the per-event endpoint that fan-outs
        // + dedupes via `aggregate_meal_ingredients` server-side.
        final response = await getIt<ApiClient>().addMealEventToShoppingList(
          event.id,
          {'shopping_list_id': targetList.id},
        );
        final data = response.data as Map<String, dynamic>;
        itemsAdded = (data['items_added'] as num?)?.toInt() ?? 0;
      } else {
        final result = await _cartService.populateFromRecipe(
            targetList.id, event.recipe!.id);
        itemsAdded = result.itemsAdded;
      }
      if (mounted) {
        if (itemsAdded > 0) {
          setState(() => _addedEventIds.add(event.id));
        }
        final n = itemsAdded;
        final label = n == 1 ? '1 ingredient' : '$n ingredients';
        final listName =
            targetList.name.isEmpty ? 'Shopping List' : targetList.name;
        final hasOtherLists = lists.length > 1;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Added $label to $listName'),
            action: hasOtherLists
                ? SnackBarAction(
                    label: 'Change',
                    onPressed: () {
                      if (!mounted) return;
                      showDefaultChangeSheet(
                        context: context,
                        lists: lists,
                        currentListId: targetList!.id,
                      );
                    },
                  )
                : null,
          ),
        );
      }
    } catch (_) {
      if (!mounted) return;
      showMutationFailureSnackbar(
        context,
        MutationType.addEventIngredients,
        () => _addIngredientsFromEvent(event),
      );
    }
  }

  void _showEventOptions(MealEvent event) {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit_calendar_outlined),
              title: const Text('Reschedule'),
              onTap: () async {
                Navigator.pop(ctx);
                await showModalBottomSheet<bool>(
                  context: context,
                  isScrollControlled: true,
                  builder: (_) => PlanMealSheet(
                    recipeId: event.recipe?.id,
                    recipeName: event.title,
                    eventId: event.id,
                    initialDate: event.scheduledAt,
                    initialMealType: event.mealType,
                  ),
                );
                // Provider emits on update; no explicit reload needed.
              },
            ),
            if (event.recipe != null)
              ListTile(
                leading: const Icon(Icons.add_shopping_cart_outlined),
                title: const Text('Add to shopping list'),
                onTap: () {
                  Navigator.pop(ctx);
                  _addIngredientsFromEvent(event);
                },
              ),
            ListTile(
              leading: Icon(
                Icons.delete_outline,
                color: Theme.of(context).colorScheme.error,
              ),
              title: Text(
                'Remove',
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
              onTap: () {
                Navigator.pop(ctx);
                _deleteEvent(event);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _openQuickAdd({DateTime? date}) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => PlanMealSheet(
        initialDate: date ?? DateTime.now(),
      ),
    );
    // Provider emits on successful create; no result-based reload.
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: _buildAppBar(),
      body: _buildBody(),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _openQuickAdd(),
        child: const Icon(Icons.add),
      ),
    );
  }

  Future<void> _openCreateCalendarDialog() async {
    await showDialog<Calendar>(
      context: context,
      builder: (_) => const CalendarCreateDialog(),
    );
    // createCalendar emits CalendarCreated; calendarsListProvider refreshes.
  }

  Future<void> _openCalendarSettings(Calendar cal) async {
    final calendars = ref.read(calendarsListProvider).value ?? const [];
    final owned = calendars.where((c) => c.isOwner).length;
    final isLast = owned <= 1;
    await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => CalendarSettingsSheet(
        calendar: cal,
        isLastCalendar: isLast,
      ),
    );
    // deleteCalendar / updateCalendar emit; calendarsListProvider refetches.
  }

  PreferredSizeWidget _buildAppBar() {
    final colorScheme = Theme.of(context).colorScheme;
    return AppBar(
      backgroundColor: colorScheme.surface,
      elevation: 0,
      title: CalendarSwitcherHeader(
        onCreateCalendar: _openCreateCalendarDialog,
        onOpenSettings: _openCalendarSettings,
      ),
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(48),
        child: Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: _buildWeekNavigator(),
        ),
      ),
    );
  }

  Widget _buildWeekNavigator() {
    final colorScheme = Theme.of(context).colorScheme;
    final startMonth = _monthAbbr(_weekStart.month);
    final endMonth = _monthAbbr(_weekEnd.month);
    final label = _weekStart.month == _weekEnd.month
        ? '$startMonth ${_weekStart.day}–${_weekEnd.day}'
        : '$startMonth ${_weekStart.day} – $endMonth ${_weekEnd.day}';

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          icon: const Icon(Icons.chevron_left),
          onPressed: _previousWeek,
          color: colorScheme.onSurface,
        ),
        Text(
          label,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: colorScheme.onSurface,
          ),
        ),
        IconButton(
          icon: const Icon(Icons.chevron_right),
          onPressed: _nextWeek,
          color: colorScheme.onSurface,
        ),
      ],
    );
  }

  Widget _buildBody() {
    final colorScheme = Theme.of(context).colorScheme;
    final asyncEvents = ref.watch(mealEventsByRangeProvider(_rangeKey));
    final lastValue = asyncEvents.value;

    // Hard-error state only when there's no data at all — otherwise keep
    // showing the last-known grid and let the user retry inline via
    // pull-to-refresh.
    if (lastValue == null && asyncEvents.hasError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'Failed to load calendar',
              style: TextStyle(color: colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 8),
            Text(
              ErrorReporter.detail(asyncEvents.error!),
              style: TextStyle(
                  fontSize: 11, color: colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _refreshGrid,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    // Render the day columns straight through. `lastValue ?? []` gives an
    // empty grid during the first load — matches the pre-refactor
    // behavior where day headers render while events are in flight.
    final eventsByDay = _groupByDay(lastValue ?? const []);
    return RefreshIndicator(
      onRefresh: _refreshGrid,
      color: colorScheme.primary,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          children:
              _weekDays.map((d) => _buildDayColumn(d, eventsByDay)).toList(),
        ),
      ),
    );
  }

  Widget _buildDayColumn(
    DateTime day,
    Map<DateTime, List<MealEvent>> eventsByDay,
  ) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;

    final today = _dayKey(DateTime.now());
    final isToday = _dayKey(day) == today;
    final events = eventsByDay[_dayKey(day)] ?? const <MealEvent>[];

    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final dayName = dayNames[day.weekday - 1];

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color:
            isToday ? colorScheme.surfaceContainerHighest : colorScheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: isToday
            ? Border.all(color: colorScheme.primary.withValues(alpha: 0.4))
            : Border.all(color: colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Day header
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: isToday ? colorScheme.primary : Colors.transparent,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    '${day.day}',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: isToday
                          ? colorScheme.onPrimary
                          : colorScheme.onSurface,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  dayName,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: isToday
                        ? colorScheme.primary
                        : colorScheme.onSurfaceVariant,
                  ),
                ),
                const Spacer(),
                SizedBox(
                  width: 28,
                  height: 28,
                  child: IconButton(
                    icon: Icon(Icons.add, size: 16, color: colorScheme.primary),
                    padding: EdgeInsets.zero,
                    tooltip: 'Add meal',
                    onPressed: () => _openQuickAdd(date: day),
                  ),
                ),
              ],
            ),
          ),

          if (events.isEmpty)
            GestureDetector(
              onTap: () => _openDayDetailSheet(day),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Row(
                  children: [
                    Icon(Icons.add_circle_outline,
                        size: 14, color: appColors.textDisabled),
                    const SizedBox(width: 6),
                    Text(
                      'Tap to plan a meal',
                      style: TextStyle(
                        fontSize: 13,
                        color: appColors.textDisabled,
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            ...events.map((event) => _buildEventTile(event)),
        ],
      ),
    );
  }

  Widget _buildEventTile(MealEvent event) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;
    final isMealEvent = event.mealId != null;
    final mealThumbUrl =
        (event.mealSummary?.componentImageUrls.isNotEmpty ?? false)
            ? event.mealSummary!.componentImageUrls.first
            : null;

    return InkWell(
      // Every tap now opens the meal detail sheet (bugs-cal-1 AC #7 —
      // "Bare tap on meal always opens the sheet"). Direct navigation to
      // the recipe is done from inside the sheet's primary button.
      onTap: () => _openMealDetailSheet(event),
      onLongPress: () => _showEventOptions(event),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
        child: Row(
          children: [
            // Recipe thumbnail or meal type icon
            Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    color: colorScheme.surfaceContainerHighest,
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: isMealEvent
                      ? (mealThumbUrl != null
                          ? Image.network(
                              mealThumbUrl,
                              fit: BoxFit.cover,
                              errorBuilder: (_, _, _) => Icon(
                                Icons.layers,
                                color: colorScheme.secondary,
                                size: 22,
                              ),
                            )
                          : Icon(
                              Icons.layers,
                              color: colorScheme.secondary,
                              size: 22,
                            ))
                      : (event.recipe?.imageUrl != null
                          ? Image.network(
                              event.recipe!.imageUrl!,
                              fit: BoxFit.cover,
                              errorBuilder: (_, _, _) =>
                                  _mealTypeIcon(event.mealType, colorScheme),
                            )
                          : _mealTypeIcon(event.mealType, colorScheme)),
                ),
                if (event.recurrenceRuleId != null)
                  Positioned(
                    top: -2,
                    right: -2,
                    child: Semantics(
                      label: 'Recurring meal',
                      child: Container(
                        padding: const EdgeInsets.all(2),
                        decoration: BoxDecoration(
                          color: colorScheme.surface,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          Icons.repeat,
                          size: 12,
                          color: colorScheme.onSurface.withValues(alpha: 0.55),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(width: 12),

            // Title + meal type
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (isMealEvent) ...[
                        Icon(
                          Icons.layers,
                          size: 12,
                          color: colorScheme.onSurface.withValues(alpha: 0.6),
                        ),
                        const SizedBox(width: 4),
                      ],
                      Flexible(
                        child: Text(
                          event.title,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: colorScheme.onSurface,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: colorScheme.outlineVariant,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      event.mealType.displayName,
                      style: TextStyle(
                        fontSize: 11,
                        color: colorScheme.secondary,
                      ),
                    ),
                  ),
                  if (isMealEvent && event.mealSummary != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      kMealComponentCountLabel(
                          event.mealSummary!.componentCount),
                      style: TextStyle(
                        fontSize: 11,
                        color: appColors.textDisabled,
                      ),
                    ),
                  ] else if (event.recipe?.totalMinutes != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      '${event.recipe!.totalMinutes} min',
                      style: TextStyle(
                        fontSize: 11,
                        color: appColors.textDisabled,
                      ),
                    ),
                  ],
                ],
              ),
            ),

            // Per-card shopping-cart / added-check icon. Rendered when
            // the event has a linked recipe OR Meal — no placeholder
            // SizedBox in the free-text case, matching the chevron's
            // visibility rule. The IconButton swallows its own tap so the
            // row-level onTap (meal detail sheet) does NOT fire when the
            // user aims for the icon.
            //
            // The outer `Semantics(excludeSemantics: true)` replaces the
            // IconButton's own semantics with a richer label. The tooltip is
            // kept for visual long-press discoverability, but is excluded
            // from the a11y tree so screen-reader users hear our "double-tap
            // to add again" hint in the checked state.
            if (event.recipe != null || isMealEvent)
              Semantics(
                button: true,
                label: _addedEventIds.contains(event.id)
                    ? 'Added to shopping list, double-tap to add again'
                    : 'Add to shopping list',
                onTap: () => _addIngredientsFromEvent(event),
                excludeSemantics: true,
                child: SizedBox(
                  width: 32,
                  height: 32,
                  child: IconButton(
                    padding: EdgeInsets.zero,
                    iconSize: 18,
                    tooltip: _addedEventIds.contains(event.id)
                        ? 'Added to shopping list'
                        : 'Add to shopping list',
                    icon: Icon(
                      _addedEventIds.contains(event.id)
                          ? Icons.check
                          : Icons.add_shopping_cart_outlined,
                      color: _addedEventIds.contains(event.id)
                          ? colorScheme.onSurface.withValues(alpha: 0.45)
                          : colorScheme.onSurface.withValues(alpha: 0.75),
                    ),
                    onPressed: () => _addIngredientsFromEvent(event),
                  ),
                ),
              ),

            // Chevron if navigable
            if (event.recipe != null || isMealEvent)
              Icon(
                Icons.chevron_right,
                size: 16,
                color: appColors.textTertiary,
              ),
          ],
        ),
      ),
    );
  }

  Widget _mealTypeIcon(MealType type, ColorScheme colorScheme) {
    IconData icon;
    switch (type) {
      case MealType.breakfast:
        icon = Icons.free_breakfast_outlined;
      case MealType.lunch:
        icon = Icons.lunch_dining_outlined;
      case MealType.dinner:
        icon = Icons.dinner_dining_outlined;
      case MealType.snack:
        icon = Icons.cookie_outlined;
    }
    return Icon(icon, color: colorScheme.secondary, size: 22);
  }

  String _monthAbbr(int month) {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return months[month - 1];
  }
}
