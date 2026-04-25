import 'package:flutter/material.dart';

/// Show a SnackBar after a bulk move with a 5-second Undo affordance.
///
/// Caller owns the inverse-move closure ([onUndo]) — the toast just
/// surfaces the affordance and returns immediately. If the user does not
/// tap Undo within the window, the SnackBar dismisses itself and nothing
/// happens.
///
/// [breakdown] is non-null for multi-source `Move to…` flows
/// (recipe-bulk-org-3) — e.g. "3 from Mom's, 2 from Trying Out". When
/// supplied, the toast shows two lines: `<breakdown> → <destinationName>`
/// over `Undo`. Single-source flows pass `null`.
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
  String? breakdown,
}) {
  final messenger = ScaffoldMessenger.of(context);
  // Hide any pending toast so the new one isn't queued behind a stale
  // "Selection cleared" or partial-failure snack.
  messenger.hideCurrentSnackBar();
  final message = breakdown != null
      ? 'Moved $breakdown → $destinationName'
      : 'Moved $movedCount ${movedCount == 1 ? 'recipe' : 'recipes'} '
          'to $destinationName';
  return messenger.showSnackBar(
    SnackBar(
      content: Text(message),
      duration: const Duration(seconds: 5),
      action: SnackBarAction(
        label: 'Undo',
        onPressed: onUndo,
      ),
    ),
  );
}
