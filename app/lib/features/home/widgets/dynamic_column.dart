import 'filter_bottom_sheet.dart' show SortOption;

/// Resolves the dynamic-column header label and per-row value text for
/// a given [SortOption]. The table view's "lens is the sort" model
/// (see epic `recipe-list-organization`) means whichever sort the user
/// picked is the column they see — no separate column-picker UI.
class DynamicColumnSpec {
  final String label;
  final String Function(Map<String, dynamic> recipe) resolveValue;

  const DynamicColumnSpec({required this.label, required this.resolveValue});
}

/// Returns the header label + per-row value resolver for [sort]. The
/// `Title`-alpha case (not modelled in [SortOption] today) and the
/// shuffle-by-`random` case both fall back to the "Last cooked" lens
/// — alpha is already obvious from the title column, and `random`
/// has no meaningful per-row value.
DynamicColumnSpec dynamicColumnFor(SortOption sort) {
  switch (sort) {
    case SortOption.lastCooked:
      return DynamicColumnSpec(
        label: 'Last cooked',
        resolveValue: (r) => _formatRelativeDate(r['last_cooked']),
      );
    case SortOption.quickest:
      return DynamicColumnSpec(
        label: 'Cook time',
        resolveValue: _formatCookTime,
      );
    case SortOption.newest:
      return DynamicColumnSpec(
        label: 'Added',
        resolveValue: (r) => _formatRelativeDate(r['created_at']),
      );
    case SortOption.best:
      return DynamicColumnSpec(
        label: 'Cooked',
        resolveValue: (r) => _formatTimesCooked(r['times_cooked']),
      );
    case SortOption.popular:
      return DynamicColumnSpec(
        label: 'Popular',
        resolveValue: (r) => _formatScore(r['popularity']),
      );
    case SortOption.random:
      // No meaningful value for random; mirror "Last cooked" so the
      // column still says *something* useful.
      return DynamicColumnSpec(
        label: 'Last cooked',
        resolveValue: (r) => _formatRelativeDate(r['last_cooked']),
      );
  }
}

/// Format a [DateTime] as the dynamic-column's tight relative-date
/// vocabulary. Used by the table-view column resolver for date-shaped
/// sorts and by `recipe_book_detail_screen` so the home and book
/// surfaces read identically when the user toggles between them.
/// Returns "—" for null / unparseable / future dates.
String formatDynamicColumnRelativeDate(DateTime? when) {
  if (when == null) return '—';
  final diff = DateTime.now().difference(when.toLocal());
  if (diff.isNegative) return '—';
  if (diff.inMinutes < 1) return 'Just now';
  if (diff.inHours < 1) return '${diff.inMinutes}m ago';
  if (diff.inHours < 24) return '${diff.inHours}h ago';
  if (diff.inDays == 1) return 'Yesterday';
  if (diff.inDays < 7) return '${diff.inDays}d ago';
  if (diff.inDays < 30) return '${(diff.inDays / 7).floor()}w ago';
  if (diff.inDays < 365) return '${(diff.inDays / 30).floor()}mo ago';
  return '${(diff.inDays / 365).floor()}y ago';
}

String _formatRelativeDate(dynamic value) {
  if (value == null) return '—';
  final s = value.toString();
  if (s.isEmpty) return '—';
  return formatDynamicColumnRelativeDate(DateTime.tryParse(s));
}

String _formatCookTime(Map<String, dynamic> r) {
  final prep = (r['prep_time'] as num?)?.toInt() ?? 0;
  final cook = (r['cook_time'] as num?)?.toInt() ?? 0;
  final total = prep + cook;
  if (total <= 0) return '—';
  return '$total min';
}

String _formatTimesCooked(dynamic value) {
  final n = (value as num?)?.toInt() ?? 0;
  if (n <= 0) return '—';
  return n == 1 ? '1×' : '$n×';
}

String _formatScore(dynamic value) {
  if (value == null) return '—';
  final n = (value as num?)?.toDouble();
  if (n == null) return '—';
  return n.toStringAsFixed(1);
}
