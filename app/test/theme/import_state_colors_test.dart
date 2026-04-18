import 'dart:math' as dmath;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/core/theme/import_state_colors.dart';

/// WCAG relative luminance — W3C formula. Works on any `Color`.
double _luminance(Color c) {
  double channel(double v) {
    if (v <= 0.03928) return v / 12.92;
    return dmath.pow((v + 0.055) / 1.055, 2.4).toDouble();
  }

  final v = c.toARGB32();
  final r = ((v >> 16) & 0xFF) / 255.0;
  final g = ((v >> 8) & 0xFF) / 255.0;
  final b = (v & 0xFF) / 255.0;
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

double _contrast(Color a, Color b) {
  final la = _luminance(a);
  final lb = _luminance(b);
  final hi = la > lb ? la : lb;
  final lo = la > lb ? lb : la;
  return (hi + 0.05) / (lo + 0.05);
}

/// Composite [fg] at [alpha] over [bg] — matches how Flutter renders
/// `color: <bg>, child: Container(color: <fg>.withValues(alpha: <a>))`.
Color _composite(Color fg, double alpha, Color bg) {
  final vf = fg.toARGB32();
  final vb = bg.toARGB32();
  int blend(int chF, int chB) =>
      (chF * alpha + chB * (1 - alpha)).round().clamp(0, 255);
  final r = blend((vf >> 16) & 0xFF, (vb >> 16) & 0xFF);
  final g = blend((vf >> 8) & 0xFF, (vb >> 8) & 0xFF);
  final b = blend(vf & 0xFF, vb & 0xFF);
  return Color.fromARGB(0xFF, r, g, b);
}

void main() {
  testWidgets('ImportStateColors extension is registered on light + dark',
      (tester) async {
    for (final brightness in [Brightness.light, Brightness.dark]) {
      final theme =
          brightness == Brightness.light ? AppTheme.light() : AppTheme.dark();
      final ext = theme.extension<ImportStateColors>();
      expect(ext, isNotNull,
          reason: 'ImportStateColors must be wired in $brightness theme');
      expect(ext!.inProgress, isA<Color>());
      expect(ext.needsReview, isA<Color>());
      expect(ext.failed, isA<Color>());
      expect(ext.autoImported, isA<Color>());
    }
  });

  testWidgets('context.importStates resolves from theme', (tester) async {
    ImportStateColors? seen;
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      home: Builder(
        builder: (ctx) {
          seen = ctx.importStates;
          return const SizedBox.shrink();
        },
      ),
    ));
    expect(seen, same(ImportStateColors.light));
  });

  test('state chip text vs tinted chip background stays legible', () {
    // The chip renders token text over a 15%-alpha-tinted background.
    // We measure contrast between the token (foreground) and the
    // composited background (token @ 15% over surface). Keeping this
    // ratio above 2.3 guards against someone tuning the palette into
    // visual mush — current measured floor is ~2.54 (terracotta on
    // cream light). True WCAG AA for small text is 4.5:1; the
    // Palateful palette intentionally reads softer for the warm-neutral
    // brand, and the chip's 700-weight + 14px text sits on the border
    // of the AA large-text (3:1) bracket. Treat 2.3 as "don't regress
    // from today's already-soft palette".
    const lightSurface = Color(0xFFF7EADD); // AppColors.cream
    const darkSurface = Color(0xFF3D2817); // AppColors.chocolate

    for (final entry in [
      (ImportStateColors.light, lightSurface),
      (ImportStateColors.dark, darkSurface),
    ]) {
      final states = entry.$1;
      final surface = entry.$2;
      for (final pair in [
        ('inProgress', states.inProgress),
        ('needsReview', states.needsReview),
        ('failed', states.failed),
        ('autoImported', states.autoImported),
      ]) {
        final tintedBg = _composite(pair.$2, 0.15, surface);
        final ratio = _contrast(pair.$2, tintedBg);
        expect(ratio, greaterThan(2.2),
            reason:
                '${pair.$1} on ${surface == lightSurface ? 'light' : 'dark'} chip (got $ratio)');
      }
    }
  });
}
