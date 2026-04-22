import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../models/meal_event.dart';
import '../services/meal_calendar_service.dart';

/// Range-windowed meal-event list provider keyed by (start, end, calendarId).
///
/// rmc-3 AC #5. Subscribes to `MealEvent*` + `RecurrenceRule*` events.
/// Range-containment filter for event-scoped events narrows invalidations
/// to windows actually affected; recurrence-rule events invalidate
/// unconditionally because materialization can land events in any range.
///
/// Invalidation flows through a **100ms subscriber-side debounce** — a
/// recurrence materialization that emits 52 `MealEventCreated` back-to-back
/// triggers exactly one refetch (epic Locked Decision #4; rmc-4 AC #3
/// stress test).
final mealEventsByRangeProvider = FutureProvider.family
    .autoDispose<List<MealEvent>, MealEventsRangeKey>((ref, key) async {
  Timer? debounce;
  ref.onDispose(() => debounce?.cancel());
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (!_rangeShouldInvalidate(event, key)) return;
    debounce?.cancel();
    debounce = Timer(const Duration(milliseconds: 100), () {
      debounce = null;
      ref.invalidateSelf();
    });
  });
  ref.onDispose(sub.cancel);
  return getIt<MealCalendarService>().listMealEvents(
    key.start,
    key.end,
    calendarId: key.calendarId,
  );
});

/// Per-day meal-event list provider keyed by (date, calendarId).
///
/// Same 100ms coalescer as the range provider — day detail sheets
/// opened during a recurrence materialization do not refetch per-event.
final mealEventsByDayProvider = FutureProvider.family
    .autoDispose<List<MealEvent>, MealEventsDayKey>((ref, key) async {
  Timer? debounce;
  ref.onDispose(() => debounce?.cancel());
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (!_dayShouldInvalidate(event, key)) return;
    debounce?.cancel();
    debounce = Timer(const Duration(milliseconds: 100), () {
      debounce = null;
      ref.invalidateSelf();
    });
  });
  ref.onDispose(sub.cancel);
  final dayStart = DateTime(key.date.year, key.date.month, key.date.day);
  final dayEnd = dayStart.add(const Duration(days: 1));
  final events = await getIt<MealCalendarService>().listMealEvents(
    dayStart,
    dayEnd,
    calendarId: key.calendarId,
  );
  return events.where((e) => _sameLocalDay(e.scheduledAt, key.date)).toList();
});

/// Upcoming meal-event list provider keyed by `mealId`.
///
/// Used by Meal detail's "Upcoming plans" row. Subscribes to the
/// MealEvent union filtered by `event.meal_id == mealId` — recurrence
/// rules that reference this meal also invalidate (coarse filter —
/// rule payload may or may not mention the meal id, so any
/// `RecurrenceRule*` triggers a refetch via the same coalescer).
final upcomingEventsForMealProvider = FutureProvider.family
    .autoDispose<List<MealEvent>, String>((ref, mealId) async {
  Timer? debounce;
  ref.onDispose(() => debounce?.cancel());
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (!_upcomingShouldInvalidate(event, mealId)) return;
    debounce?.cancel();
    debounce = Timer(const Duration(milliseconds: 100), () {
      debounce = null;
      ref.invalidateSelf();
    });
  });
  ref.onDispose(sub.cancel);
  // Forward-looking window — from now to 90 days out. The service's
  // listMealEvents accepts a range; we post-filter by mealId since
  // there is no server-side "events for meal" endpoint today.
  final now = DateTime.now();
  final end = now.add(const Duration(days: 90));
  final events = await getIt<MealCalendarService>().listMealEvents(
    now,
    end,
  );
  return events.where((e) => e.mealId == mealId).toList();
});

/// Key for [mealEventsByRangeProvider]. Record-like — operator== + hashCode
/// override so Riverpod re-uses the same family instance when the same
/// (start, end, calendarId) triple is requested.
class MealEventsRangeKey {
  const MealEventsRangeKey({
    required this.start,
    required this.end,
    this.calendarId,
  });

  final DateTime start;
  final DateTime end;
  final String? calendarId;

  @override
  bool operator ==(Object other) =>
      other is MealEventsRangeKey &&
      other.start == start &&
      other.end == end &&
      other.calendarId == calendarId;

  @override
  int get hashCode => Object.hash(start, end, calendarId);
}

/// Key for [mealEventsByDayProvider]. Date is truncated to a local-midnight
/// DateTime at the call site; sub-day fields are ignored for equality.
class MealEventsDayKey {
  const MealEventsDayKey({required this.date, this.calendarId});

  final DateTime date;
  final String? calendarId;

  @override
  bool operator ==(Object other) =>
      other is MealEventsDayKey &&
      other.date == date &&
      other.calendarId == calendarId;

  @override
  int get hashCode => Object.hash(date, calendarId);
}

bool _rangeShouldInvalidate(MutationEvent event, MealEventsRangeKey key) {
  return switch (event) {
    MealEventCreated() => _eventInRange(event.event, key),
    MealEventUpdated() => _eventInRange(event.event, key),
    MealEventCompleted() => _eventInRange(event.event, key),
    MealEventDeleted(calendarId: final c) =>
      c == null || key.calendarId == null || c == key.calendarId,
    MealEventArchived() => true,
    RecurrenceRuleCreated() => true,
    RecurrenceRuleUpdated() => true,
    RecurrenceRuleDeleted() => true,
    _ => false,
  };
}

bool _dayShouldInvalidate(MutationEvent event, MealEventsDayKey key) {
  return switch (event) {
    MealEventCreated() => _eventOnDay(event.event, key),
    MealEventUpdated() => _eventOnDay(event.event, key),
    MealEventCompleted() => _eventOnDay(event.event, key),
    MealEventDeleted(calendarId: final c) =>
      c == null || key.calendarId == null || c == key.calendarId,
    MealEventArchived() => true,
    RecurrenceRuleCreated() => true,
    RecurrenceRuleUpdated() => true,
    RecurrenceRuleDeleted() => true,
    _ => false,
  };
}

bool _upcomingShouldInvalidate(MutationEvent event, String mealId) {
  return switch (event) {
    MealEventCreated(:final event) =>
      (event['meal_id'] as String?) == mealId,
    MealEventUpdated(:final event) =>
      (event['meal_id'] as String?) == mealId,
    MealEventCompleted(:final event) =>
      (event['meal_id'] as String?) == mealId,
    MealEventDeleted() => true,
    MealEventArchived() => true,
    RecurrenceRuleCreated() => true,
    RecurrenceRuleUpdated() => true,
    RecurrenceRuleDeleted() => true,
    _ => false,
  };
}

bool _eventInRange(Map<String, dynamic> payload, MealEventsRangeKey key) {
  if (key.calendarId != null) {
    final c = payload['calendar_id'] as String?;
    if (c != null && c != key.calendarId) return false;
  }
  final scheduled = payload['scheduled_at'];
  if (scheduled is! String) return true; // unknown → be safe
  final at = DateTime.tryParse(scheduled)?.toLocal();
  if (at == null) return true;
  // Day-level comparison — callers pass `end` as the last day's midnight,
  // so treating it as an exclusive upper bound would drop events later
  // than 00:00 on the final day.
  final eventDay = DateTime(at.year, at.month, at.day);
  final startDay = DateTime(key.start.year, key.start.month, key.start.day);
  final endDay = DateTime(key.end.year, key.end.month, key.end.day);
  return !eventDay.isBefore(startDay) && !eventDay.isAfter(endDay);
}

bool _eventOnDay(Map<String, dynamic> payload, MealEventsDayKey key) {
  if (key.calendarId != null) {
    final c = payload['calendar_id'] as String?;
    if (c != null && c != key.calendarId) return false;
  }
  final scheduled = payload['scheduled_at'];
  if (scheduled is! String) return true;
  final at = DateTime.tryParse(scheduled)?.toLocal();
  if (at == null) return true;
  return _sameLocalDay(at, key.date);
}

bool _sameLocalDay(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;
