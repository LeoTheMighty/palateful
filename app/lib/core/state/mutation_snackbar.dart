import 'package:flutter/material.dart';

import 'mutation_failure_copy.dart';

/// Single entry point for "the mutation failed, let the user retry" toasts.
///
/// All mutation UI handlers route their catch-blocks through this — no
/// ad-hoc `ScaffoldMessenger.showSnackBar(SnackBar(...))` in new code
/// (epic Design Principle #6). The rp-5 grep guard enforces this at CI.
///
/// Copy (`"Couldn't <verb> <noun>"`) comes from [mutationFailureCopy] keyed
/// by [type]. An [suffix] appends a trailing clause (e.g. `" — offline"`).
///
/// The optional [rollback] fires **once, synchronously, before the
/// Snackbar is shown**, for optimistic-UI sites that need to revert a
/// `setState` before the user sees the failure message (rp-2 notification
/// prefs toggle is the canonical example).
///
/// The [ScaffoldMessenger] for the passed [context] clears any existing
/// Snackbar first so rapid-failure sequences don't queue four-deep
/// ambiguous toasts (epic UX Risk — "Snackbar width at 320px").
void showMutationFailureSnackbar(
  BuildContext context,
  MutationType type,
  VoidCallback retry, {
  VoidCallback? rollback,
  String? suffix,
  Duration visibleFor = const Duration(seconds: 5),
}) {
  // Fire the rollback synchronously — callers rely on it running before
  // the messenger lookup so the UI has already snapped back by the time
  // the Snackbar paints on the next frame.
  if (rollback != null) rollback();

  final copy = mutationFailureCopy[type];
  final title = copy?.title ?? "Couldn't complete that action";
  final message = suffix == null ? title : '$title$suffix';

  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;

  messenger.removeCurrentSnackBar();
  messenger.showSnackBar(
    SnackBar(
      content: Text(message),
      duration: visibleFor,
      behavior: SnackBarBehavior.floating,
      action: SnackBarAction(
        label: 'Retry',
        onPressed: retry,
      ),
    ),
  );
}
