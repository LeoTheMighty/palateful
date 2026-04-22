import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/di/injection.dart';
import '../../../core/state/mutation_bus.dart';
import '../models/calendar.dart';
import '../services/calendar_service.dart';

const _kActiveCalendarIdKey = 'active_calendar_id';

/// The list of calendars the user is a member of.
///
/// Subscribes to the MutationBus and invalidates on any calendar CRUD
/// mutation (create / update / delete). rmc-3 AC #4.
final calendarsListProvider = FutureProvider<List<Calendar>>((ref) async {
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (event is CalendarCreated ||
        event is CalendarUpdated ||
        event is CalendarDeleted ||
        event is CalendarArchived) {
      ref.invalidateSelf();
    }
  });
  ref.onDispose(sub.cancel);
  final service = getIt<CalendarService>();
  return service.listCalendars();
});

/// The currently-active calendar id.
///
/// `build()` resolves to a valid, non-archived calendar id the user owns or
/// is a member of. Priority: persisted-id-if-still-valid → user's
/// is_default=true → first calendar in the list. Null only transiently
/// during initial load. If the list is empty (defensive — impossible
/// post-backfill), state transitions to AsyncError with "Calendars
/// unavailable".
class ActiveCalendarNotifier extends AsyncNotifier<String?> {
  @override
  Future<String?> build() async {
    final calendars = await ref.watch(calendarsListProvider.future);
    if (calendars.isEmpty) {
      throw StateError('Calendars unavailable');
    }

    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_kActiveCalendarIdKey);
    if (stored != null && calendars.any((c) => c.id == stored)) {
      return stored;
    }

    // Fall back to the user's default calendar, then to the first one.
    final defaultCal = calendars.firstWhere(
      (c) => c.isDefault,
      orElse: () => calendars.first,
    );
    return defaultCal.id;
  }

  Future<void> setActive(String calendarId) async {
    state = AsyncData(calendarId);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kActiveCalendarIdKey, calendarId);
  }

  /// Called when the server returns 404 on the active id (e.g., another
  /// device deleted the calendar). Clears the persisted id, refetches
  /// the list, and re-resolves via `build`'s fallback chain.
  Future<void> clearInvalid() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kActiveCalendarIdKey);
    ref.invalidate(calendarsListProvider);
    // Re-running build() resolves the new active id from the (now empty)
    // preference + refreshed list.
    ref.invalidateSelf();
  }
}

final activeCalendarProvider =
    AsyncNotifierProvider<ActiveCalendarNotifier, String?>(
  ActiveCalendarNotifier.new,
);

/// Convenience: the active Calendar object, or null during load / error.
final activeCalendarProviderObject =
    Provider<AsyncValue<Calendar?>>((ref) {
  final activeId = ref.watch(activeCalendarProvider);
  final listAsync = ref.watch(calendarsListProvider);

  return activeId.when(
    data: (id) => listAsync.when(
      data: (list) => AsyncData(
        id == null
            ? null
            : list.firstWhere(
                (c) => c.id == id,
                orElse: () => list.isNotEmpty ? list.first : throw StateError('empty'),
              ),
      ),
      loading: () => const AsyncLoading(),
      error: (e, st) => AsyncError(e, st),
    ),
    loading: () => const AsyncLoading(),
    error: (e, st) => AsyncError(e, st),
  );
});
