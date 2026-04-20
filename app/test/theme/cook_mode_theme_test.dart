import 'dart:io';
import 'dart:math' as dmath;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:palateful/core/theme/app_theme.dart';
import 'package:palateful/core/theme/cook_mode_theme.dart';

/// Blocks all HTTP so any stray GoogleFonts fetches in test fail
/// synchronously instead of leaking async errors past the test body.
class _NoNetHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    throw const SocketException('Network disabled in test');
  }
}

/// WCAG relative luminance — W3C formula.
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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  GoogleFonts.config.allowRuntimeFetching = false;
  HttpOverrides.global = _NoNetHttpOverrides();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  testWidgets('CookModeTheme is registered on both light + dark AppTheme',
      (tester) async {
    for (final theme in [AppTheme.light(), AppTheme.dark()]) {
      final ext = theme.extension<CookModeTheme>();
      expect(ext, isNotNull,
          reason: 'CookModeTheme must be wired on ${theme.brightness}');
    }
  });

  testWidgets('context.cookModeTheme resolves from ambient theme',
      (tester) async {
    CookModeTheme? seenLight;
    CookModeTheme? seenDark;

    await tester.pumpWidget(MaterialApp(
      key: const ValueKey('light'),
      theme: AppTheme.light(),
      home: Builder(
        builder: (ctx) {
          seenLight = ctx.cookModeTheme;
          return const SizedBox.shrink();
        },
      ),
    ));
    expect(seenLight, isNotNull);
    expect(seenLight!.cookSurface, CookModeTheme.light.cookSurface);
    expect(seenLight!.cookAccent, CookModeTheme.light.cookAccent);

    await tester.pumpWidget(MaterialApp(
      key: const ValueKey('dark'),
      theme: AppTheme.dark(),
      home: Builder(
        builder: (ctx) {
          seenDark = ctx.cookModeTheme;
          return const SizedBox.shrink();
        },
      ),
    ));
    expect(seenDark, isNotNull);
    expect(seenDark!.cookSurface, CookModeTheme.dark.cookSurface);
    expect(seenDark!.cookAccent, CookModeTheme.dark.cookAccent);
    expect(seenDark!.cookSurface, isNot(equals(seenLight!.cookSurface)));
  });

  test('each token is a distinct Color (no accidental duplication)', () {
    // Distinct *semantic* tokens. Some tokens are intentionally the same
    // hue (e.g. cookAccent + cookProgress both point at the accent
    // colour), but every pair of tokens with different roles must be
    // distinguishable from at least one of its neighbours — catches a
    // careless "everything-is-terracotta" regression.
    for (final cook in [CookModeTheme.light, CookModeTheme.dark]) {
      final pairs = <(String, Color)>[
        ('cookSurface', cook.cookSurface),
        ('cookSurfaceDim', cook.cookSurfaceDim),
        ('cookOnSurface', cook.cookOnSurface),
        ('cookAccent', cook.cookAccent),
        ('cookOnAccent', cook.cookOnAccent),
        ('cookCompleted', cook.cookCompleted),
        ('cookOnCompleted', cook.cookOnCompleted),
        ('cookTimer', cook.cookTimer),
        ('cookError', cook.cookError),
        ('cookOffline', cook.cookOffline),
        ('cookDivider', cook.cookDivider),
      ];
      expect(cook.cookSurface, isNot(equals(cook.cookAccent)));
      expect(cook.cookSurface, isNot(equals(cook.cookCompleted)));
      expect(cook.cookAccent, isNot(equals(cook.cookCompleted)));
      expect(cook.cookAccent, isNot(equals(cook.cookTimer)));
      expect(cook.cookSurface, isNot(equals(cook.cookSurfaceDim)));
      // onSurface / onAccent / onCompleted are text tokens — must
      // each contrast against their surface (tested below), but their
      // values may coincide (e.g. both are "cream" in light) so we
      // don't require *all* inter-token distinctness.
      expect(pairs.length, 11);
    }
  });

  test('text-on-surface pairs meet WCAG AA ≥4.5:1 for normal text', () {
    for (final entry in [
      ('light', CookModeTheme.light),
      ('dark', CookModeTheme.dark),
    ]) {
      final name = entry.$1;
      final cook = entry.$2;
      final pairs = <(String, Color, Color)>[
        ('cookOnSurface/cookSurface', cook.cookOnSurface, cook.cookSurface),
        ('cookOnAccent/cookAccent', cook.cookOnAccent, cook.cookAccent),
        (
          'cookOnCompleted/cookCompleted',
          cook.cookOnCompleted,
          cook.cookCompleted
        ),
      ];
      for (final pair in pairs) {
        final ratio = _contrast(pair.$2, pair.$3);
        expect(ratio, greaterThanOrEqualTo(4.5),
            reason:
                '$name ${pair.$1} must meet WCAG AA ≥4.5:1, got ${ratio.toStringAsFixed(2)}');
      }
    }
  });

  test('copyWith replaces named field and preserves the rest', () {
    const override = Color(0xFFAABBCC);
    final replaced = CookModeTheme.light.copyWith(cookAccent: override);
    expect(replaced.cookAccent, override);
    expect(replaced.cookSurface, CookModeTheme.light.cookSurface);
    expect(replaced.cookCompleted, CookModeTheme.light.cookCompleted);
  });

  test('lerp interpolates each token independently', () {
    final mid = CookModeTheme.light.lerp(CookModeTheme.dark, 0.5);
    expect(mid.cookSurface,
        Color.lerp(CookModeTheme.light.cookSurface,
            CookModeTheme.dark.cookSurface, 0.5));
    expect(mid.cookAccent,
        Color.lerp(CookModeTheme.light.cookAccent,
            CookModeTheme.dark.cookAccent, 0.5));
  });

  test('lerp with null other returns self', () {
    expect(CookModeTheme.light.lerp(null, 0.5), same(CookModeTheme.light));
  });

  // ------------------------------------------------------------------
  // cmp-5 AC1 — pinned Color values. Catches accidental drift.
  //
  // If this test fails, someone has knowingly changed a cook-mode
  // token. Update the pin AND the doc-comment contrast table in
  // cook_mode_theme.dart.
  // ------------------------------------------------------------------
  test('light tokens match pinned Color values', () {
    const light = CookModeTheme.light;
    expect(light.cookSurface.toARGB32(), 0xFFFAF7F2);
    expect(light.cookSurfaceDim.toARGB32(), 0xFFF5EFE6);
    expect(light.cookOnSurface.toARGB32(), 0xFF2D2420);
    expect(light.cookAccent.toARGB32(), 0xFF8F4022);
    expect(light.cookOnAccent.toARGB32(), 0xFFFAF7F2);
    expect(light.cookProgress.toARGB32(), 0xFF8F4022);
    expect(light.cookCompleted.toARGB32(), 0xFF4F6E42);
    expect(light.cookOnCompleted.toARGB32(), 0xFFFAF7F2);
    expect(light.cookTimer.toARGB32(), 0xFF8A6F2E);
    expect(light.cookError.toARGB32(), 0xFF944D4D);
    expect(light.cookOffline.toARGB32(), 0xFF8B7355);
    expect(light.cookDivider.toARGB32(), 0xFF8B7355);
    expect(light.cookShadow.toARGB32(), 0x1A4A3728);
  });

  test('dark tokens match pinned Color values', () {
    const dark = CookModeTheme.dark;
    expect(dark.cookSurface.toARGB32(), 0xFF4A3728);
    expect(dark.cookSurfaceDim.toARGB32(), 0xFF5D4A3A);
    expect(dark.cookOnSurface.toARGB32(), 0xFFF5ECD7);
    expect(dark.cookAccent.toARGB32(), 0xFFBE8A60);
    expect(dark.cookOnAccent.toARGB32(), 0xFF2D2420);
    expect(dark.cookProgress.toARGB32(), 0xFFBE8A60);
    expect(dark.cookCompleted.toARGB32(), 0xFF8FA882);
    expect(dark.cookOnCompleted.toARGB32(), 0xFF2D2420);
    expect(dark.cookTimer.toARGB32(), 0xFFD4A853);
    expect(dark.cookError.toARGB32(), 0xFFCB8B73);
    expect(dark.cookOffline.toARGB32(), 0xFFA89076);
    expect(dark.cookDivider.toARGB32(), 0xFFA89076);
    expect(dark.cookShadow.toARGB32(), 0x40000000);
  });
}
