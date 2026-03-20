import 'package:flutter/widgets.dart';

const double kMobileBreakpoint = 600.0;
const double kTabletBreakpoint = 905.0;

class ResponsiveUtils {
  static double screenWidth(BuildContext context) =>
      MediaQuery.of(context).size.width;

  static bool isMobile(BuildContext context) =>
      screenWidth(context) < kMobileBreakpoint;

  static bool isTablet(BuildContext context) =>
      screenWidth(context) >= kMobileBreakpoint &&
      screenWidth(context) < kTabletBreakpoint;

  static bool isDesktop(BuildContext context) =>
      screenWidth(context) >= kTabletBreakpoint;

  static int recipeGridColumns(BuildContext context) {
    final w = screenWidth(context);
    if (w >= kTabletBreakpoint) return 3;
    if (w >= kMobileBreakpoint) return 2;
    return 1;
  }

  static double maxContentWidth(BuildContext context) =>
      isMobile(context) ? double.infinity : 720.0;
}
