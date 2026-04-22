import '../../../core/services/api_client.dart';
import '../../../core/state/mutation_bus.dart';
import '../models/calendar.dart';
import '../models/calendar_member.dart';

/// Service for calendar CRUD — wraps ApiClient.
class CalendarService {
  final ApiClient _apiClient;

  CalendarService(this._apiClient);

  Future<List<Calendar>> listCalendars() async {
    final response = await _apiClient.listCalendars();
    final data = response.data as Map<String, dynamic>;
    final items = (data['items'] as List).cast<Map<String, dynamic>>();
    return items.map(Calendar.fromJson).toList();
  }

  Future<Calendar> createCalendar(String name, {String? description}) async {
    final response = await _apiClient.createCalendar({
      'name': name,
      if (description != null && description.isNotEmpty)
        'description': description,
    });
    final payload = response.data as Map<String, dynamic>;
    emitMutation(CalendarCreated(
      calendarId: payload['id']?.toString() ?? '',
      calendar: payload,
    ));
    return Calendar.fromJson(payload);
  }

  Future<Calendar> getCalendar(String id) async {
    final response = await _apiClient.getCalendar(id);
    return Calendar.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Calendar> updateCalendar(
    String id, {
    String? name,
    String? description,
  }) async {
    final data = <String, dynamic>{};
    if (name != null) data['name'] = name;
    if (description != null) data['description'] = description;
    final response = await _apiClient.updateCalendar(id, data);
    final payload = response.data as Map<String, dynamic>;
    emitMutation(CalendarUpdated(calendarId: id, calendar: payload));
    return Calendar.fromJson(payload);
  }

  Future<void> deleteCalendar(String id) async {
    await _apiClient.deleteCalendar(id);
    emitMutation(CalendarDeleted(calendarId: id));
  }

  // Member management (cal-share-2)

  Future<List<CalendarMember>> listCalendarMembers(String calendarId) async {
    final response = await _apiClient.listCalendarMembers(calendarId);
    final data = response.data as Map<String, dynamic>;
    final items = (data['members'] as List).cast<Map<String, dynamic>>();
    return items.map(CalendarMember.fromJson).toList();
  }

  Future<void> updateCalendarMember(
    String calendarId,
    String userId, {
    required String role,
  }) async {
    await _apiClient.updateCalendarMember(calendarId, userId, {'role': role});
  }

  Future<void> removeCalendarMember(String calendarId, String userId) async {
    await _apiClient.removeCalendarMember(calendarId, userId);
  }

  Future<void> leaveCalendar(String calendarId) async {
    await _apiClient.leaveCalendar(calendarId);
  }
}
