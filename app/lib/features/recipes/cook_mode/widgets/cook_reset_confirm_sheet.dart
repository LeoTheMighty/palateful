import 'package:flutter/material.dart';

import '../../../../core/theme/theme.dart';

/// Confirmation sheet for the in-cook "Reset cook" affordance. Returns
/// true when the user confirms, false (or null on outside-tap) when they
/// cancel. Destructive action sits on the right per iOS/Android
/// convention.
Future<bool> showCookResetConfirmSheet(BuildContext context) async {
  final result = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Theme.of(context).extension<CookModeTheme>()?.cookSurface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (sheetContext) => const CookResetConfirmSheet(),
  );
  return result ?? false;
}

class CookResetConfirmSheet extends StatelessWidget {
  const CookResetConfirmSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Align(
              alignment: Alignment.center,
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: cook.cookOnSurface.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Reset this cook session? Step progress, checked ingredients, '
              'and active timers will be cleared.',
              style: TextStyle(
                fontSize: 15,
                color: cook.cookOnSurface,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: TextButton(
                    onPressed: () => Navigator.of(context).pop(false),
                    style: TextButton.styleFrom(
                      foregroundColor: cook.cookOnSurface,
                      minimumSize: const Size.fromHeight(48),
                    ),
                    child: const Text('Cancel'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: () => Navigator.of(context).pop(true),
                    style: FilledButton.styleFrom(
                      backgroundColor: cook.cookError,
                      foregroundColor: cook.cookOnAccent,
                      minimumSize: const Size.fromHeight(48),
                    ),
                    child: const Text('Reset'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
