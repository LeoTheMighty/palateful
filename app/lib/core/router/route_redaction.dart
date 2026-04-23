// Client-side path-parameter redaction for client-latency telemetry
// (cla-4). Mirrors
// `services/api/src/api/v1/client_latency/route_redaction.py` — the
// server rejects any event whose `route` still carries a raw UUID or
// long-numeric id with a 422.
//
// We prefer go_router's template path (`/recipes/:id`) when available,
// which is already redacted. This helper runs as a backstop for code
// paths that land a concrete URL (deep-link handlers, raw
// `route.settings.name`, tab-swap reporting).

final _uuidRe = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
);
final _numericIdRe = RegExp(r'^\d{4,}$');

/// Returns `true` when every path segment is either literal text, a
/// template placeholder (`:id` / `{id}`), or empty. Returns `false` on
/// the first raw UUID or 4-plus-digit segment.
///
/// A `null` or empty input is considered redacted — some event types
/// (app_start, MetricKit) carry no route.
bool isRouteRedacted(String? route) {
  if (route == null || route.isEmpty) return true;
  final path = route.split('?').first.split('#').first;
  for (final segment in path.split('/')) {
    if (segment.isEmpty) continue;
    if (segment.startsWith(':') || segment.startsWith('{')) continue;
    if (_uuidRe.hasMatch(segment)) return false;
    if (_numericIdRe.hasMatch(segment)) return false;
  }
  return true;
}

/// Replaces any UUID or 4-plus-digit segment with `:id`. Pass-through
/// for already-redacted or empty routes. Query string + fragment are
/// stripped.
String? redactRoute(String? route) {
  if (route == null || route.isEmpty) return route;
  final path = route.split('?').first.split('#').first;
  final redacted = <String>[];
  for (final segment in path.split('/')) {
    if (segment.isEmpty) {
      redacted.add(segment);
      continue;
    }
    if (segment.startsWith(':') || segment.startsWith('{')) {
      redacted.add(segment);
      continue;
    }
    if (_uuidRe.hasMatch(segment) || _numericIdRe.hasMatch(segment)) {
      redacted.add(':id');
      continue;
    }
    redacted.add(segment);
  }
  return redacted.join('/');
}
