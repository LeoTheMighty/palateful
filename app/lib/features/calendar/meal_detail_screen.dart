import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';
import 'models/meal_event.dart';
import 'services/meal_calendar_service.dart';

/// Lightweight read-mostly meal-event detail screen, served by the
/// `/calendar/meals/:id` deep-link route. Push notifications for
/// meal_event_invite / meal_event_reminder / meal_event_updated land
/// here so the user doesn't have to scroll-find the right tile.
///
/// Intentionally minimal: title, time, recipe card (if any), participant
/// list, RSVP buttons (when current user is a participant). The full
/// edit surface lives in the existing meal-edit sheet — open from the
/// bottom-nav Calendar tab. This screen is a target, not a workspace.
class MealEventDetailScreen extends StatefulWidget {
  final String mealEventId;

  const MealEventDetailScreen({super.key, required this.mealEventId});

  @override
  State<MealEventDetailScreen> createState() => _MealEventDetailScreenState();
}

class _MealEventDetailScreenState extends State<MealEventDetailScreen> {
  final _apiClient = getIt<ApiClient>();
  final _calendarService = getIt<MealCalendarService>();

  bool _isLoading = true;
  String? _error;
  MealEvent? _event;
  List<_Participant> _participants = const [];
  String? _currentUserId;
  bool _rsvpInFlight = false;
  bool _reminderInFlight = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await _apiClient.getMealEvent(widget.mealEventId);
      final data = response.data as Map<String, dynamic>;
      final event = MealEvent.fromJson(data);
      final participants = ((data['participants'] as List?) ?? const [])
          .cast<Map<String, dynamic>>()
          .map(_Participant.fromJson)
          .toList();

      // Best-effort current-user lookup so we know whether to show RSVP buttons.
      String? me;
      try {
        final meResp = await _apiClient.getMe();
        me = (meResp.data as Map<String, dynamic>)['id'] as String?;
      } catch (_) {
        me = null;
      }

      if (!mounted) return;
      setState(() {
        _event = event;
        _participants = participants;
        _currentUserId = me;
        _isLoading = false;
      });
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'calendar',
        operation: 'meal_detail.load',
        extras: {'meal_event_id': widget.mealEventId},
      );
      if (!mounted) return;
      setState(() {
        _error = "Couldn't load this meal";
        _isLoading = false;
      });
    }
  }

  _Participant? get _myParticipant {
    final id = _currentUserId;
    if (id == null) return null;
    for (final p in _participants) {
      if (p.userId == id) return p;
    }
    return null;
  }

  Future<void> _rsvp(String status) async {
    if (_rsvpInFlight) return;
    setState(() => _rsvpInFlight = true);
    try {
      await _apiClient.respondToMealInvite(widget.mealEventId, status);
      // Optimistic local update so the chips re-render without a round-trip.
      setState(() {
        _participants = [
          for (final p in _participants)
            if (p.userId == _currentUserId)
              p.copyWith(status: status)
            else
              p,
        ];
      });
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'calendar',
        operation: 'meal_detail.rsvp',
        extras: {
          'meal_event_id': widget.mealEventId,
          'status': status,
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to update your RSVP.')),
      );
    } finally {
      if (mounted) setState(() => _rsvpInFlight = false);
    }
  }

  /// Wall-clock slot defaults. KEEP IN SYNC with
  /// `app/lib/features/calendar/widgets/plan_meal_sheet.dart::_mealDefaultTime`
  /// and the backend's `MEAL_SLOT_DEFAULT_TIMES` constant.
  TimeOfDay _slotDefault(MealType type) {
    switch (type) {
      case MealType.breakfast:
        return const TimeOfDay(hour: 8, minute: 0);
      case MealType.lunch:
        return const TimeOfDay(hour: 12, minute: 0);
      case MealType.dinner:
        return const TimeOfDay(hour: 18, minute: 30);
      case MealType.snack:
        return const TimeOfDay(hour: 15, minute: 0);
    }
  }

  TimeOfDay? _parseTimeOfDay(String? hhmm) {
    if (hhmm == null || hhmm.length < 4) return null;
    final parts = hhmm.split(':');
    if (parts.length < 2) return null;
    final h = int.tryParse(parts[0]);
    final m = int.tryParse(parts[1]);
    if (h == null || m == null) return null;
    return TimeOfDay(hour: h, minute: m);
  }

  String _wire(TimeOfDay t) {
    final hh = t.hour.toString().padLeft(2, '0');
    final mm = t.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  String _formatTimeOfDay(TimeOfDay t) {
    final hour12 = t.hour == 0 ? 12 : (t.hour > 12 ? t.hour - 12 : t.hour);
    final mm = t.minute.toString().padLeft(2, '0');
    final ampm = t.hour < 12 ? 'AM' : 'PM';
    return '$hour12:$mm $ampm';
  }

  Future<void> _pickReminderTime() async {
    if (_reminderInFlight) return;
    final event = _event;
    if (event == null) return;

    final override = _parseTimeOfDay(event.mealReminderTime);
    final initial = override ?? _slotDefault(event.mealType);

    final picked = await showTimePicker(
      context: context,
      initialTime: initial,
    );
    if (picked == null || !mounted) return;
    await _saveReminder(_wire(picked));
  }

  Future<void> _resetReminder() async {
    if (_reminderInFlight) return;
    // Explicit null clears the override → backend falls back to slot
    // default (meal-1 Update handler uses model_fields_set to tell the
    // difference from omit).
    await _saveReminder(null);
  }

  Future<void> _saveReminder(String? wire) async {
    final event = _event;
    if (event == null) return;
    setState(() => _reminderInFlight = true);
    try {
      final updated = await _calendarService.setMealReminderTime(
        event.id,
        wire,
      );
      if (!mounted) return;
      setState(() {
        _event = updated;
      });
    } catch (e, st) {
      ErrorReporter.report(
        e,
        st,
        area: 'calendar',
        operation: 'meal_detail.set_reminder_time',
        extras: {
          'meal_event_id': event.id,
          'reminder_time': wire ?? 'null',
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to update reminder time.')),
      );
    } finally {
      if (mounted) setState(() => _reminderInFlight = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Meal'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildContent(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64),
            const SizedBox(height: 16),
            Text(
              "Couldn't load this meal — open Calendar instead.",
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => context.go('/calendar'),
              child: const Text('Open Calendar'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    final event = _event!;
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(event.title, style: textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(
          _formatScheduledAt(event.scheduledAt),
          style: textTheme.bodyLarge?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            Chip(label: Text(event.mealType.displayName)),
            if (event.isShared) const Chip(label: Text('Shared')),
          ],
        ),
        const SizedBox(height: 16),

        _buildReminderRow(event),

        const SizedBox(height: 16),

        if (event.recipe != null) _buildRecipeCard(event.recipe!),
        if (event.mealSummary != null) _buildMealSummaryCard(event.mealSummary!),

        const SizedBox(height: 24),

        if (_myParticipant != null) ...[
          Text('Your RSVP', style: textTheme.titleMedium),
          const SizedBox(height: 8),
          _buildRsvpRow(),
          const SizedBox(height: 24),
        ],

        if (_participants.isNotEmpty) ...[
          Text(
            'Participants (${_participants.length})',
            style: textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          ..._participants.map(_buildParticipantRow),
        ],

        const SizedBox(height: 32),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: () => context.go('/calendar'),
            icon: const Icon(Icons.calendar_today),
            label: const Text('Open in Calendar'),
          ),
        ),
      ],
    );
  }

  Widget _buildReminderRow(MealEvent event) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final override = _parseTimeOfDay(event.mealReminderTime);
    final resolved = _parseTimeOfDay(event.reminderTime) ??
        override ??
        _slotDefault(event.mealType);
    final hasOverride = override != null;

    return Column(
      key: const Key('meal_detail_reminder_row'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              'Reminder',
              style: textTheme.titleSmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const Spacer(),
            if (hasOverride)
              TextButton(
                onPressed: _reminderInFlight ? null : _resetReminder,
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
        InkWell(
          onTap: _reminderInFlight ? null : _pickReminderTime,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
                  _formatTimeOfDay(resolved),
                  style: TextStyle(
                    fontSize: 15,
                    color: colorScheme.onSurface,
                  ),
                ),
                if (!hasOverride) ...[
                  const SizedBox(width: 8),
                  Text(
                    '(${event.mealType.displayName} default)',
                    style: TextStyle(
                      fontSize: 12,
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                const Spacer(),
                if (_reminderInFlight)
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  Icon(
                    Icons.edit_outlined,
                    size: 18,
                    color: colorScheme.onSurfaceVariant,
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRecipeCard(RecipeSummary recipe) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push('/recipes/${recipe.id}'),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (recipe.imageUrl != null)
              SizedBox(
                width: 96,
                height: 96,
                child: CachedNetworkImage(
                  imageUrl: recipe.imageUrl!,
                  fit: BoxFit.cover,
                  errorWidget: (_, _, _) =>
                      const Icon(Icons.restaurant_menu),
                ),
              ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      recipe.name,
                      style: Theme.of(context).textTheme.titleMedium,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (recipe.totalMinutes != null) ...[
                      const SizedBox(height: 6),
                      Text(
                        '${recipe.totalMinutes} min',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const Padding(
              padding: EdgeInsets.all(8),
              child: Icon(Icons.chevron_right),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMealSummaryCard(MealSummary summary) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.restaurant_outlined),
        title: Text(summary.name),
        subtitle: Text('${summary.componentCount} components'),
      ),
    );
  }

  Widget _buildRsvpRow() {
    final me = _myParticipant;
    if (me == null) return const SizedBox.shrink();
    return Wrap(
      spacing: 8,
      children: [
        for (final option in const [
          ('accepted', 'Accept', Icons.check_circle_outline),
          ('maybe', 'Maybe', Icons.help_outline),
          ('declined', 'Decline', Icons.cancel_outlined),
        ])
          FilterChip(
            label: Text(option.$2),
            avatar: Icon(option.$3, size: 18),
            selected: me.status == option.$1,
            onSelected:
                _rsvpInFlight ? null : (_) => _rsvp(option.$1),
          ),
      ],
    );
  }

  Widget _buildParticipantRow(_Participant p) {
    final colorScheme = Theme.of(context).colorScheme;
    final label = p.userName ?? p.userEmail ?? 'Unknown';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const CircleAvatar(child: Icon(Icons.person)),
      title: Text(label),
      subtitle: Text(p.role),
      trailing: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: _statusBg(p.status, colorScheme),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          _statusLabel(p.status),
          style: TextStyle(color: _statusFg(p.status, colorScheme)),
        ),
      ),
    );
  }

  String _formatScheduledAt(DateTime localTime) {
    const weekdays = [
      'Monday', 'Tuesday', 'Wednesday', 'Thursday',
      'Friday', 'Saturday', 'Sunday',
    ];
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    final weekday = weekdays[localTime.weekday - 1];
    final month = months[localTime.month - 1];
    final hour24 = localTime.hour;
    final hour12 = hour24 == 0 ? 12 : (hour24 > 12 ? hour24 - 12 : hour24);
    final ampm = hour24 < 12 ? 'AM' : 'PM';
    final mm = localTime.minute.toString().padLeft(2, '0');
    return '$weekday, $month ${localTime.day} • $hour12:$mm $ampm';
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'accepted':
        return 'Going';
      case 'declined':
        return "Can't go";
      case 'maybe':
        return 'Maybe';
      default:
        return 'Pending';
    }
  }

  Color _statusBg(String status, ColorScheme cs) {
    switch (status) {
      case 'accepted':
        return cs.primaryContainer;
      case 'declined':
        return cs.errorContainer;
      case 'maybe':
        return cs.tertiaryContainer;
      default:
        return cs.surfaceContainerHighest;
    }
  }

  Color _statusFg(String status, ColorScheme cs) {
    switch (status) {
      case 'accepted':
        return cs.onPrimaryContainer;
      case 'declined':
        return cs.onErrorContainer;
      case 'maybe':
        return cs.onTertiaryContainer;
      default:
        return cs.onSurfaceVariant;
    }
  }
}

class _Participant {
  final String userId;
  final String? userName;
  final String? userEmail;
  final String status;
  final String role;

  const _Participant({
    required this.userId,
    required this.status,
    required this.role,
    this.userName,
    this.userEmail,
  });

  _Participant copyWith({String? status}) => _Participant(
        userId: userId,
        userName: userName,
        userEmail: userEmail,
        status: status ?? this.status,
        role: role,
      );

  factory _Participant.fromJson(Map<String, dynamic> json) => _Participant(
        userId: json['user_id'] as String,
        userName: json['user_name'] as String?,
        userEmail: json['user_email'] as String?,
        status: json['status'] as String? ?? 'pending',
        role: json['role'] as String? ?? 'guest',
      );
}
