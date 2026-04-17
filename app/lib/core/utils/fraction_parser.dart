/// Parse + format quantity fractions for ingredient editors.
///
/// Mirrors the server-side `libraries/utils/utils/formatting.py`
/// `_decimal_to_fraction` algorithm (`Fraction.limit_denominator(8)`) so a
/// value formatted by the backend for display renders identically when
/// parsed back on the client, and vice-versa.
///
/// Parse accepts:
/// - integers: `2`
/// - decimals: `0.5`, `1.25`, `0.333`
/// - simple fractions: `1/2`, `3/8`
/// - mixed numbers: `1 1/2`, `2 3/4`
///
/// Format produces:
/// - integer string for integer values (`2` → `"2"`)
/// - fraction string for values with `limit_denominator(8)` fractional part
///   (`0.5` → `"1/2"`, `0.333` → `"1/3"`, `1.25` → `"1 1/4"`)
double? parseFraction(String? input) {
  if (input == null) return null;
  final s = input.trim();
  if (s.isEmpty) return null;

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

/// Format a numeric quantity as a fraction string (or integer when exact),
/// mirroring Python's `Fraction(value).limit_denominator(8)` algorithm.
String formatFraction(double value) {
  if (value.isNaN || value.isInfinite) return '';
  if (value == 0) return '0';

  // Clean integer case.
  if ((value - value.roundToDouble()).abs() < 1e-9) {
    return value.round().toString();
  }

  final isNegative = value < 0;
  final abs = value.abs();
  final whole = abs.floor();
  final remainder = abs - whole;

  if (remainder < 1e-9) {
    final s = whole.toString();
    return isNegative ? '-$s' : s;
  }

  final (num, den) = _limitDenominator(remainder, 8);

  // If rounding pushed the remainder to a whole (e.g., 0.999 → 1/1),
  // roll up the whole part.
  if (num == den) {
    final s = (whole + 1).toString();
    return isNegative ? '-$s' : s;
  }
  if (num == 0) {
    final s = whole.toString();
    return isNegative ? '-$s' : s;
  }

  if (whole == 0) {
    final s = '$num/$den';
    return isNegative ? '-$s' : s;
  }
  final s = '$whole $num/$den';
  return isNegative ? '-$s' : s;
}

/// Return `(numerator, denominator)` approximating `value ∈ [0, 1)` with
/// denominator ≤ `maxDen`, mirroring Python's
/// `Fraction.limit_denominator(maxDen)` for a fractional value.
///
/// Implementation: iterate denominators `1..maxDen` and pick the
/// `(round(value * d), d)` pair that minimizes absolute error, preferring
/// smaller denominators on ties.
(int, int) _limitDenominator(double value, int maxDen) {
  var bestNum = 0;
  var bestDen = 1;
  var bestErr = double.infinity;
  for (var d = 1; d <= maxDen; d++) {
    final n = (value * d).round();
    final err = (value - n / d).abs();
    if (err < bestErr - 1e-12) {
      bestNum = n;
      bestDen = d;
      bestErr = err;
    }
  }
  // Reduce (e.g., 2/4 → 1/2) so output looks canonical.
  final g = _gcd(bestNum, bestDen);
  return (bestNum ~/ g, bestDen ~/ g);
}

int _gcd(int a, int b) {
  a = a.abs();
  b = b.abs();
  while (b != 0) {
    final t = b;
    b = a % b;
    a = t;
  }
  return a == 0 ? 1 : a;
}
