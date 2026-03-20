import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/utils/responsive.dart';

Widget _buildWithWidth(double width, Widget child) {
  return MediaQuery(
    data: MediaQueryData(size: Size(width, 800)),
    child: MaterialApp(home: child),
  );
}

void main() {
  group('ResponsiveUtils breakpoints', () {
    testWidgets('isMobile true below 600', (tester) async {
      late bool result;
      await tester.pumpWidget(_buildWithWidth(
        599,
        Builder(builder: (ctx) {
          result = ResponsiveUtils.isMobile(ctx);
          return const SizedBox();
        }),
      ));
      expect(result, isTrue);
    });

    testWidgets('isMobile false at 600', (tester) async {
      late bool result;
      await tester.pumpWidget(_buildWithWidth(
        600,
        Builder(builder: (ctx) {
          result = ResponsiveUtils.isMobile(ctx);
          return const SizedBox();
        }),
      ));
      expect(result, isFalse);
    });

    testWidgets('isTablet true at 600', (tester) async {
      late bool result;
      await tester.pumpWidget(_buildWithWidth(
        600,
        Builder(builder: (ctx) {
          result = ResponsiveUtils.isTablet(ctx);
          return const SizedBox();
        }),
      ));
      expect(result, isTrue);
    });

    testWidgets('isTablet false at 905', (tester) async {
      late bool result;
      await tester.pumpWidget(_buildWithWidth(
        905,
        Builder(builder: (ctx) {
          result = ResponsiveUtils.isTablet(ctx);
          return const SizedBox();
        }),
      ));
      expect(result, isFalse);
    });

    testWidgets('isDesktop true at 905', (tester) async {
      late bool result;
      await tester.pumpWidget(_buildWithWidth(
        905,
        Builder(builder: (ctx) {
          result = ResponsiveUtils.isDesktop(ctx);
          return const SizedBox();
        }),
      ));
      expect(result, isTrue);
    });

    testWidgets('recipeGridColumns: 1 below 600', (tester) async {
      late int cols;
      await tester.pumpWidget(_buildWithWidth(
        400,
        Builder(builder: (ctx) {
          cols = ResponsiveUtils.recipeGridColumns(ctx);
          return const SizedBox();
        }),
      ));
      expect(cols, 1);
    });

    testWidgets('recipeGridColumns: 2 at 700', (tester) async {
      late int cols;
      await tester.pumpWidget(_buildWithWidth(
        700,
        Builder(builder: (ctx) {
          cols = ResponsiveUtils.recipeGridColumns(ctx);
          return const SizedBox();
        }),
      ));
      expect(cols, 2);
    });

    testWidgets('recipeGridColumns: 3 at 1200', (tester) async {
      late int cols;
      await tester.pumpWidget(_buildWithWidth(
        1200,
        Builder(builder: (ctx) {
          cols = ResponsiveUtils.recipeGridColumns(ctx);
          return const SizedBox();
        }),
      ));
      expect(cols, 3);
    });

    testWidgets('maxContentWidth is infinity on mobile', (tester) async {
      late double maxWidth;
      await tester.pumpWidget(_buildWithWidth(
        400,
        Builder(builder: (ctx) {
          maxWidth = ResponsiveUtils.maxContentWidth(ctx);
          return const SizedBox();
        }),
      ));
      expect(maxWidth, double.infinity);
    });

    testWidgets('maxContentWidth is 720 on desktop', (tester) async {
      late double maxWidth;
      await tester.pumpWidget(_buildWithWidth(
        1200,
        Builder(builder: (ctx) {
          maxWidth = ResponsiveUtils.maxContentWidth(ctx);
          return const SizedBox();
        }),
      ));
      expect(maxWidth, 720.0);
    });
  });
}
