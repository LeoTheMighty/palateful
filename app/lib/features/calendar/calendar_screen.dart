import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/di/injection.dart';
import '../../core/theme/app_colors.dart';
import '../shopping_cart/models/shopping_list.dart';
import '../shopping_cart/services/shopping_cart_service.dart';
import 'models/meal_event.dart';
import 'services/meal_calendar_service.dart';
import 'widgets/plan_meal_sheet.dart';

/// Calendar tab — week view showing scheduled meal events.
class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  final _service = getIt<MealCalendarService>();
  final _cartService = getIt<ShoppingCartService>();

  /// Monday of the currently displayed week.
  late DateTime _weekStart;

  /// Events keyed by date (time zeroed out to midnight local).
  Map<DateTime, List<MealEvent>> _eventsByDay = {};
  bool _isLoading = true;
  String? _error;

  /// Incremented on every load; prevents stale responses from overwriting newer state.
  int _loadGeneration = 0;

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
      final events = await _service.listMealEvents(_weekStart, _weekEnd);
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

  Future<void> _addIngredientsFromEvent(MealEvent event) async {
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

    final ShoppingList targetList;
    if (lists.length == 1) {
      targetList = lists.first;
    } else {
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
    }

    try {
      final result =
          await _cartService.populateFromRecipe(targetList.id, event.recipe!.id);
      if (mounted) {
        final n = result.itemsAdded;
        final label = n == 1 ? '1 ingredient' : '$n ingredients';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Added $label to ${targetList.name}')),
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
                    recipeId: event.recipe?.id ?? '',
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.cream,
      appBar: _buildAppBar(),
      body: _buildBody(),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: AppColors.cream,
      elevation: 0,
      title: _buildWeekNavigator(),
    );
  }

  Widget _buildWeekNavigator() {
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
          color: AppColors.textPrimary,
        ),
        Text(
          label,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
        IconButton(
          icon: const Icon(Icons.chevron_right),
          onPressed: _nextWeek,
          color: AppColors.textPrimary,
        ),
      ],
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error!,
                style: const TextStyle(color: AppColors.textSecondary)),
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
      color: AppColors.chocolate,
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
    final today = _dayKey(DateTime.now());
    final isToday = _dayKey(day) == today;
    final events = _eventsByDay[_dayKey(day)] ?? [];

    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final dayName = dayNames[day.weekday - 1];

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: isToday ? AppColors.warmIvory : AppColors.warmWhite,
        borderRadius: BorderRadius.circular(12),
        border: isToday
            ? Border.all(color: AppColors.chocolate.withValues(alpha: 0.4))
            : Border.all(color: AppColors.divider),
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
                    color: isToday ? AppColors.chocolate : Colors.transparent,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    '${day.day}',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: isToday
                          ? Colors.white
                          : AppColors.textPrimary,
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
                        ? AppColors.chocolate
                        : AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),

          if (events.isEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: Text(
                'No meals planned',
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.textDisabled,
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
    return InkWell(
      onTap: () {
        if (event.recipe != null) {
          context.push('/recipes/${event.recipe!.id}');
        }
      },
      onLongPress: () => _showEventOptions(event),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
        child: Row(
          children: [
            // Recipe thumbnail or meal type icon
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: AppColors.beige,
              ),
              clipBehavior: Clip.antiAlias,
              child: event.recipe?.imageUrl != null
                  ? Image.network(
                      event.recipe!.imageUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _mealTypeIcon(event.mealType),
                    )
                  : _mealTypeIcon(event.mealType),
            ),
            const SizedBox(width: 12),

            // Title + meal type
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    event.title,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.beigeAccent,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      event.mealType.displayName,
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.hazelnut,
                      ),
                    ),
                  ),
                  if (event.recipe?.totalMinutes != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      '${event.recipe!.totalMinutes} min',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textDisabled,
                      ),
                    ),
                  ],
                ],
              ),
            ),

            // Chevron if navigable
            if (event.recipe != null)
              const Icon(
                Icons.chevron_right,
                size: 16,
                color: AppColors.textTertiary,
              ),
          ],
        ),
      ),
    );
  }

  Widget _mealTypeIcon(MealType type) {
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
    return Icon(icon, color: AppColors.hazelnut, size: 22);
  }

  String _monthAbbr(int month) {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return months[month - 1];
  }
}
