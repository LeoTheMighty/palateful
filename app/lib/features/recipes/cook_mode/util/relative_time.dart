/// Human-readable relative time formatter used by the cook-mode Resume
/// gate sheet. Pure — `now` is parameterised so unit tests can pin
/// deterministic values at every boundary.
///
/// Boundaries:
///   < 1 min           → "just now"
///   < 2 min           → "1 min ago"
///   < 1 h             → "N min ago"
///   < 2 h             → "1 h ago"
///   < 24 h            → "N h ago"
///   < 48 h            → "yesterday"
///   < 7 days          → "N days ago"
///   otherwise         → "N weeks ago"
String relativeTime(DateTime then, {DateTime? now}) {
  final reference = now ?? DateTime.now();
  final diff = reference.difference(then);
  if (diff.isNegative) return 'just now';
  if (diff.inSeconds < 60) return 'just now';
  if (diff.inMinutes < 60) {
    final m = diff.inMinutes;
    return m == 1 ? '1 min ago' : '$m min ago';
  }
  if (diff.inHours < 24) {
    final h = diff.inHours;
    return h == 1 ? '1 h ago' : '$h h ago';
  }
  if (diff.inHours < 48) return 'yesterday';
  if (diff.inDays < 7) return '${diff.inDays} days ago';
  final weeks = diff.inDays ~/ 7;
  return weeks == 1 ? '1 week ago' : '$weeks weeks ago';
}
