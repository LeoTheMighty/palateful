import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/di/injection.dart';
import '../../core/services/auth_service.dart';
import '../../core/theme/theme.dart';
import '../../shared/widgets/default_change_sheet.dart';
import '../shopping_cart/models/shopping_list.dart';
import '../shopping_cart/services/shopping_cart_service.dart';
import 'models/meal_event.dart';
import 'models/calendar.dart';
import 'providers/active_calendar_provider.dart';
import 'services/meal_calendar_service.dart';
import 'widgets/calendar_create_dialog.dart';
import 'widgets/calendar_settings_sheet.dart';
import 'widgets/calendar_switcher_header.dart';
import 'widgets/day_detail_sheet.dart';
import 'widgets/meal_detail_sheet.dart';
import 'widgets/plan_meal_sheet.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';
import '../recipes/cook_mode/widgets/post_cook_feedback_sheet.dart';
import '../../core/services/api_client.dart';
import '../../core/services/recipe_cache_service.dart';

/// Calendar tab — week view showing scheduled meal events.
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

  /// Events keyed by date (time zeroed out to midnight local).
  Map<DateTime, List<MealEvent>> _eventsByDay = {};
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  /// Incremented on every load; prevents stale responses from overwriting newer state.
  int _loadGeneration = 0;

  bool _isGeneratingList = false;

  @override
  void initState() {
    super.initState();
    _weekStart = _mondayOf(DateTime.now());
    _loadEvents();
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

  Future<void> _loadEvents() async {
    _loadGeneration++;
    final generation = _loadGeneration;
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      // Scope to the active calendar when resolved. Before the provider
      // settles (first frame), fall back to the legacy union behavior so
      // the grid doesn't block on calendar boot.
      final activeId = ref.read(activeCalendarProvider).value;
      final events = await _service.listMealEvents(
        _weekStart,
        _weekEnd,
        calendarId: activeId,
      );
      if (generation != _loadGeneration) return;
      final Map<DateTime, List<MealEvent>> byDay = {};
      for (final e in events) {
        final key = _dayKey(e.scheduledAt);
        byDay.putIfAbsent(key, () => []).add(e);
      }
      if (mounted) {
        setState(() {
          _eventsByDay = byDay;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (generation != _loadGeneration) return;
      if (mounted) {
        setState(() {
          _error = 'Failed to load calendar';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  void _previousWeek() {
    setState(() => _weekStart = _weekStart.subtract(const Duration(days: 7)));
    _loadEvents();
  }

  void _nextWeek() {
    setState(() => _weekStart = _weekStart.add(const Duration(days: 7)));
    _loadEvents();
  }

  Future<void> _deleteEvent(MealEvent event) async {
    try {
      await _service.deleteMealEvent(event.id);
      _loadEvents();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to remove meal')),
        );
      }
    }
  }

  /// Unschedule with optimistic removal + 3s snackbar undo (locked
  /// decision #3 + bugs-cal-1 AC #3). Recurring series collapse silently
  /// under the current backend — see locked decision #20 + the audit
  /// filed as bugs-cal-3b.
  void _unscheduleWithUndo(MealEvent event) {
    final key = _dayKey(event.scheduledAt);
    final list = _eventsByDay[key];
    final index = list?.indexWhere((e) => e.id == event.id) ?? -1;

    // Optimistic: remove from local grouping.
    if (list != null && index >= 0) {
      setState(() {
        list.removeAt(index);
        if (list.isEmpty) _eventsByDay.remove(key);
      });
    }

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
            setState(() {
              final restored = _eventsByDay.putIfAbsent(key, () => []);
              restored.insert(index < 0 ? 0 : index.clamp(0, restored.length), event);
            });
          },
        ),
      ),
    );

    // Wait past the snackbar window before committing the server-side
    // delete. If the user tapped Undo, we skip the call entirely.
    Future.delayed(const Duration(seconds: 3), () async {
      if (undone) return;
      try {
        await _service.deleteMealEvent(event.id);
      } catch (_) {
        if (!mounted) return;
        // Restore on failure so the UI matches the server.
        _loadEvents();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to unschedule meal')),
        );
      }
    });
  }

  Future<void> _rescheduleEvent(MealEvent event, DateTime newLocal) async {
    try {
      await _service.rescheduleMealEvent(event.id, newLocal);
      if (!mounted) return;
      _loadEvents();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to reschedule meal')),
        );
      }
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
        if (mounted) _loadEvents();
      } catch (_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to mark cooked')),
          );
        }
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
        onMarkCooked: event.recipe == null ? null : () => _markMealCooked(event),
        onSeriesEnded: () {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Series ended. Future occurrences removed.')),
          );
          _loadEvents();
        },
      ),
    );
  }

  void _openDayDetailSheet(DateTime day) {
    final events = _eventsByDay[_dayKey(day)] ?? const <MealEvent>[];
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => DayDetailSheet(
        day: day,
        events: events,
        onMealTap: _openMealDetailSheet,
        onPlanMeal: () => _openQuickAdd(date: day),
      ),
    );
  }

  Future<void> _addIngredientsFromEvent(MealEvent event) async {
    assert(event.recipe != null, '_addIngredientsFromEvent requires a linked recipe');
    final authService = getIt<AuthService>();
    List<ShoppingList> lists;
    try {
      lists = await _cartService.getShoppingLists();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to load shopping lists')),
        );
      }
      return;
    }

    if (lists.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No shopping lists — tap + to create one')),
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
      final result =
          await _cartService.populateFromRecipe(targetList.id, event.recipe!.id);
      if (mounted) {
        final n = result.itemsAdded;
        final label = n == 1 ? '1 ingredient' : '$n ingredients';
        final listName = targetList.name.isEmpty ? 'Shopping List' : targetList.name;
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to add ingredients')),
        );
      }
    }
  }

  Future<void> _generateWeeklyShoppingList() async {
    if (_isGeneratingList) return;
    setState(() => _isGeneratingList = true);

    // Capture week range immediately — _weekStart can change if the user
    // navigates weeks while this async method is awaiting.
    final weekStart = _weekStart;
    final weekEnd = _weekEnd;

    try {
      List<ShoppingList> lists;
      try {
        lists = await _cartService.getShoppingLists();
      } catch (_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to load shopping lists')),
          );
        }
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

      // Bulk action: always show picker with default pre-selected
      final ShoppingList targetList;
      if (lists.length == 1) {
        targetList = lists.first;
      } else {
        if (!mounted) return;
        final defaultId = getIt<AuthService>().defaultShoppingListId;
        // Sort default list to top
        final sortedLists = List<ShoppingList>.from(lists);
        if (defaultId != null) {
          sortedLists.sort((a, b) {
            if (a.id == defaultId) return -1;
            if (b.id == defaultId) return 1;
            return 0;
          });
        }
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
                ...sortedLists.map((list) => ListTile(
                      title: Text(list.name),
                      subtitle: Text('${list.items.length} item(s)'),
                      trailing: list.id == defaultId
                          ? const Icon(Icons.star, size: 16, color: Colors.amber)
                          : null,
                      onTap: () => Navigator.pop(ctx, list),
                    )),
              ],
            ),
          ),
        );
        if (selected == null) return;
        targetList = selected;
      }

      try {
        final result = await _cartService.populateFromCalendarRange(
            targetList.id, weekStart, weekEnd);
        if (mounted) {
          if (result.mealEventsIncluded == 0) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                  content: Text('No planned meals with recipes this week')),
            );
            return;
          }
          final n = result.itemsAdded;
          final m = result.mealEventsIncluded;
          final itemLabel = n == 1 ? '1 ingredient' : '$n ingredients';
          final mealLabel = m == 1 ? '1 meal' : '$m meals';
          final weeklyListName = targetList.name.isEmpty ? 'Shopping List' : targetList.name;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content: Text(
                    'Added $itemLabel from $mealLabel to $weeklyListName')),
          );
        }
      } catch (_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to generate shopping list')),
          );
        }
      }
    } finally {
      if (mounted) setState(() => _isGeneratingList = false);
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
                final result = await showModalBottomSheet<bool>(
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
                if (result == true) _loadEvents();
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
                style: TextStyle(
                    color: Theme.of(context).colorScheme.error),
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
    ).then((result) {
      if (result == true) _loadEvents();
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    // Reload events whenever the active calendar changes.
    ref.listen<AsyncValue<String?>>(activeCalendarProvider, (prev, next) {
      if (prev?.value != next.value && next is AsyncData) {
        _loadEvents();
      }
    });
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
    // createCalendar + setActive already fired inside the dialog. The
    // ref.listen on activeCalendarProvider triggers _loadEvents.
  }

  Future<void> _openCalendarSettings(Calendar cal) async {
    final calendars = ref.read(calendarsListProvider).value ?? const [];
    final owned = calendars.where((c) => c.isOwner).length;
    final isLast = owned <= 1;
    final result = await showModalBottomSheet<String>(
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
    if (result == 'deleted' && mounted) {
      // Provider already re-resolves; trigger a grid reload.
      _loadEvents();
    }
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
      actions: [
        IconButton(
          icon: const Icon(Icons.add_shopping_cart_outlined),
          color: colorScheme.onSurface,
          tooltip: 'Add week to shopping list',
          onPressed: _generateWeeklyShoppingList,
        ),
      ],
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
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error!,
                style: TextStyle(color: colorScheme.onSurfaceVariant)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadEvents,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadEvents,
      color: colorScheme.primary,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          children: _weekDays.map(_buildDayColumn).toList(),
        ),
      ),
    );
  }

  Widget _buildDayColumn(DateTime day) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;

    final today = _dayKey(DateTime.now());
    final isToday = _dayKey(day) == today;
    final events = _eventsByDay[_dayKey(day)] ?? [];

    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final dayName = dayNames[day.weekday - 1];

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: isToday ? colorScheme.surfaceContainerHighest : colorScheme.surface,
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
                    Icon(Icons.add_circle_outline, size: 14, color: appColors.textDisabled),
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
                  child: event.recipe?.imageUrl != null
                      ? Image.network(
                          event.recipe!.imageUrl!,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => _mealTypeIcon(event.mealType, colorScheme),
                        )
                      : _mealTypeIcon(event.mealType, colorScheme),
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
                  Text(
                    event.title,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: colorScheme.onSurface,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
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
                  if (event.recipe?.totalMinutes != null) ...[
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

            // Chevron if navigable
            if (event.recipe != null)
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
