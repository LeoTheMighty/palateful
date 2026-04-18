import '../../../core/services/api_client.dart';
import '../models/calendar.dart';

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
    return Calendar.fromJson(response.data as Map<String, dynamic>);
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
    return Calendar.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteCalendar(String id) async {
    await _apiClient.deleteCalendar(id);
  }
}
