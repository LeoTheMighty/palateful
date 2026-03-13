import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Custom page that respects the system Reduce Motion preference.
/// Uses instant transitions when Reduce Motion is enabled.
CustomTransitionPage<void> buildReduceMotionPage({
  required BuildContext context,
  required GoRouterState state,
  required Widget child,
}) {
  final reduceMotion = MediaQuery.of(context).disableAnimations;
  return CustomTransitionPage<void>(
    key: state.pageKey,
    child: child,
    transitionDuration: reduceMotion ? Duration.zero : const Duration(milliseconds: 300),
    reverseTransitionDuration: reduceMotion ? Duration.zero : const Duration(milliseconds: 300),
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      if (reduceMotion) return child;
      return FadeTransition(opacity: animation, child: child);
    },
  );
}
