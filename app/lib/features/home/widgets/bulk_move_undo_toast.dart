import 'package:flutter/material.dart';

/// Show a SnackBar after a bulk move with a 5-second Undo affordance.
///
/// Caller owns the inverse-move closure ([onUndo]) — the toast just
/// surfaces the affordance and returns immediately. If the user does not
/// tap Undo within the window, the SnackBar dismisses itself and nothing
/// happens.
///
/// Returns the controller so callers can cancel the toast eagerly (e.g.
/// when a follow-up bulk action would shadow it). Most callers ignore
/// the return value.
ScaffoldFeatureController<SnackBar, SnackBarClosedReason>
    showBulkMoveUndoToast(
  BuildContext context, {
  required int movedCount,
  required String destinationName,
  required VoidCallback onUndo,
}) {
  final messenger = ScaffoldMessenger.of(context);
  // Hide any pending toast so the new one isn't queued behind a stale
  // "Selection cleared" or partial-failure snack.
  messenger.hideCurrentSnackBar();
  return messenger.showSnackBar(
    SnackBar(
      content: Text(
        'Moved $movedCount ${movedCount == 1 ? 'recipe' : 'recipes'} '
        'to $destinationName',
      ),
      duration: const Duration(seconds: 5),
      action: SnackBarAction(
        label: 'Undo',
        onPressed: onUndo,
      ),
    ),
  );
}
