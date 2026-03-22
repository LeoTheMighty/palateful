/// Parse a quantity display string to a numeric value.
/// Returns null if the string is empty or unparseable.
double? parseQuantity(String? display) {
  if (display == null || display.trim().isEmpty) return null;
  final s = display.trim();

  // Mixed number: "1 1/2"
  final mixed = RegExp(r'^(\d+)\s+(\d+)/(\d+)$').firstMatch(s);
  if (mixed != null) {
    final whole = int.parse(mixed.group(1)!);
    final num = int.parse(mixed.group(2)!);
    final den = int.parse(mixed.group(3)!);
    if (den == 0) return null;
    return whole + num / den;
  }

  // Simple fraction: "1/2"
  final frac = RegExp(r'^(\d+)/(\d+)$').firstMatch(s);
  if (frac != null) {
    final num = int.parse(frac.group(1)!);
    final den = int.parse(frac.group(2)!);
    if (den == 0) return null;
    return num / den;
  }

  // Decimal or integer
  return double.tryParse(s);
}

/// Common fractions we recognize: (value, display string).
final _fractions = <(double, String)>[
  (0.125, '1/8'),
  (0.25, '1/4'),
  (1.0 / 3.0, '1/3'),
  (0.375, '3/8'),
  (0.5, '1/2'),
  (2.0 / 3.0, '2/3'),
  (0.75, '3/4'),
  (0.875, '7/8'),
];

/// Format a numeric quantity into a clean display string.
/// Uses fractions where natural (1/2, 1/3, 1/4, etc.) and falls back
/// to clean decimal rounding for unusual values.
String formatQuantity(double value) {
  if (value <= 0) return '';

  // Exact integer
  if ((value - value.roundToDouble()).abs() < 0.001 &&
      value == value.round()) {
    return value.round().toString();
  }

  final whole = value.floor();
  final fractional = value - whole;

  // Try to match fractional part to a common fraction
  for (final (fracValue, fracDisplay) in _fractions) {
    if ((fractional - fracValue).abs() < 0.02) {
      if (whole == 0) return fracDisplay;
      return '$whole $fracDisplay';
    }
  }

  // Fallback: round to 2 decimal places, strip trailing zeros
  final rounded = value.toStringAsFixed(2)
      .replaceAll(RegExp(r'0+$'), '')
      .replaceAll(RegExp(r'\.$'), '');
  return rounded;
}

/// Scale a quantity display string by a given factor and return a formatted string.
/// Returns the original string unchanged if parsing fails or quantity is null/empty.
String scaleQuantityDisplay(String? display, double scaleFactor) {
  if (scaleFactor == 1.0) return display ?? '';
  final parsed = parseQuantity(display);
  if (parsed == null) return display ?? '';
  return formatQuantity(parsed * scaleFactor);
}
