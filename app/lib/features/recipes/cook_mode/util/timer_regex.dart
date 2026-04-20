/// cmt-4 — pure-Dart timer-extraction regex + `StepTimer` shape.
///
/// The frontend consumes step timers from TWO sources:
///   1. `step['timers']` (cmt-1 + cmt-2): structured list produced by the
///      backend extractor.
///   2. Fallback regex over the step's instruction text — used when
///      the structured list is empty/missing (legacy recipes).
///
/// This module exports the data class + the regex helper so both
/// `step_timers_row` and the manual-timer sheet can reason about the
/// same shape without importing `cook_mode_screen.dart`.

library;

/// A single timer entry displayed next to a cooking step.
///
/// * [durationMinutes] — clamp bound to `[1, 360]` by the backend; the
///   regex returns the LOWER bound of a range (e.g. "3-5 minutes" -> 3).
/// * [label] — one-word-ish description shown on the button
///   ("simmer", "bake", or "timer" when no better text is available).
/// * [rangeUpperLabel] — when the regex detected a range, this holds
///   the human-readable "3–5 min" string for the button's tooltip. Null
///   for single-value durations and for extractor-supplied timers.
class StepTimer {
  final int durationMinutes;
  final String label;
  final String? rangeUpperLabel;

  const StepTimer({
    required this.durationMinutes,
    required this.label,
    this.rangeUpperLabel,
  });

  /// Defensive parse for structured backend JSON. Rejects anything
  /// that doesn't look like a `{duration_minutes: int 1..360, label: String ≤40}`
  /// pair and returns `null` for callers to filter.
  static StepTimer? fromJson(dynamic raw) {
    if (raw is! Map) return null;
    final dur = raw['duration_minutes'];
    if (dur is! int || dur < 1 || dur > 360) return null;
    final labelRaw = raw['label'];
    var label = labelRaw is String ? labelRaw.trim() : '';
    if (label.length > 40) label = label.substring(0, 40);
    if (label.isEmpty) label = 'timer';
    return StepTimer(durationMinutes: dur, label: label);
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is StepTimer &&
        other.durationMinutes == durationMinutes &&
        other.label == label &&
        other.rangeUpperLabel == rangeUpperLabel;
  }

  @override
  int get hashCode =>
      Object.hash(durationMinutes, label, rangeUpperLabel);
}

// 2000-char cap prevents catastrophic backtracking on adversarial
// input; at most 10 matches returned so a single step can't produce
// an overwhelming button row.
const int _maxInstructionLength = 2000;
const int _maxMatches = 10;

// Single-value pattern: "10 minutes", "1.5 hours", "45 sec".
final RegExp _singlePattern = RegExp(
  r'(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)\b',
  caseSensitive: false,
);

// Range pattern (checked first): "3-5 min", "1 to 2 hours", "10–12 minutes".
final RegExp _rangePattern = RegExp(
  r'(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*'
  r'(h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)\b',
  caseSensitive: false,
);

int _toMinutes(double value, String unit) {
  final u = unit.toLowerCase();
  if (u.startsWith('h')) return (value * 60).round();
  if (u.startsWith('s')) {
    // Round up so "30 seconds" becomes a 1-min timer rather than
    // a no-op 0-minute entry. Anything shorter than 30 seconds ends
    // up under the 1-min clamp floor below.
    final rounded = (value / 60).round();
    return rounded < 1 ? 1 : rounded;
  }
  return value.round();
}

String _displayUnit(String unit) {
  final u = unit.toLowerCase();
  if (u.startsWith('h')) return 'hr';
  if (u.startsWith('s')) return 'sec';
  return 'min';
}

int _clamp(int minutes) {
  if (minutes < 1) return 1;
  if (minutes > 360) return 360;
  return minutes;
}

/// Extract timers from an instruction string.
///
/// Ranges beat singles — we scan the range pattern first and remove
/// overlapping single hits so `"3-5 min"` produces one 3-min timer
/// (with `rangeUpperLabel: "3–5 min in recipe"`) instead of a 3-min
/// AND a 5-min timer.
///
/// Returns an empty list (never null) when nothing matches.
List<StepTimer> extractTimers(String instruction) {
  if (instruction.isEmpty) return const [];
  final capped = instruction.length > _maxInstructionLength
      ? instruction.substring(0, _maxInstructionLength)
      : instruction;

  final results = <StepTimer>[];
  final occupiedRanges = <List<int>>[];

  for (final m in _rangePattern.allMatches(capped)) {
    if (results.length >= _maxMatches) break;
    final lower = double.tryParse(m.group(1) ?? '');
    final upper = double.tryParse(m.group(2) ?? '');
    final unit = m.group(3) ?? 'min';
    if (lower == null || upper == null) continue;
    final lowerMin = _clamp(_toMinutes(lower, unit));
    final displayUnit = _displayUnit(unit);
    final rangeLabel =
        '${_fmt(lower)}–${_fmt(upper)} $displayUnit in recipe';
    results.add(
      StepTimer(
        durationMinutes: lowerMin,
        label: 'timer',
        rangeUpperLabel: rangeLabel,
      ),
    );
    occupiedRanges.add([m.start, m.end]);
  }

  for (final m in _singlePattern.allMatches(capped)) {
    if (results.length >= _maxMatches) break;
    // Skip ranges we already consumed.
    final overlaps = occupiedRanges.any(
      (r) => m.start >= r[0] && m.end <= r[1],
    );
    if (overlaps) continue;
    final v = double.tryParse(m.group(1) ?? '');
    final unit = m.group(2) ?? 'min';
    if (v == null) continue;
    final minutes = _clamp(_toMinutes(v, unit));
    results.add(
      StepTimer(durationMinutes: minutes, label: 'timer'),
    );
  }

  return results;
}

String _fmt(double v) {
  if (v == v.truncate()) return v.toInt().toString();
  return v.toString();
}
