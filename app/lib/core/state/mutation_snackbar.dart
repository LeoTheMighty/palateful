import 'package:flutter/material.dart';

import 'mutation_failure_copy.dart';

/// Single entry point for "the mutation failed, let the user retry" toasts.
///
/// All mutation UI handlers route their catch-blocks through this — no
/// ad-hoc `ScaffoldMessenger.showSnackBar(SnackBar(...))` in new code
/// (epic Design Principle #6).
///
/// Copy (`"Couldn't <verb> <noun>"`) comes from [mutationFailureCopy] keyed
/// by [type]. If a new UI handler appears without a matching copy entry,
/// this falls back to a generic string — the regression is caught by
/// adding the type to the map, not by the UI crashing.
///
/// The [ScaffoldMessenger] for the passed [context] clears any existing
/// Snackbar first so rapid-failure sequences don't queue four-deep
/// ambiguous toasts (epic UX Risk — "Snackbar width at 320px").
void showMutationFailureSnackbar(
  BuildContext context,
  MutationType type,
  VoidCallback retry, {
  Duration visibleFor = const Duration(seconds: 5),
}) {
  final copy = mutationFailureCopy[type];
  final title = copy?.title ?? "Couldn't complete that action";

  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;

  messenger.removeCurrentSnackBar();
  messenger.showSnackBar(
    SnackBar(
      content: Text(title),
      duration: visibleFor,
      behavior: SnackBarBehavior.floating,
      action: SnackBarAction(
        label: 'Retry',
        onPressed: retry,
      ),
    ),
  );
}
