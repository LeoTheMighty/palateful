import 'package:flutter/material.dart';

import 'bulk_dispatcher.dart';

/// Shared partial / full-failure dialog for Add-to-Meal and Archive.
/// Shows one row per failed item with display name + user-facing reason.
/// Successful rows are skipped — callers surface the "X of Y" count via
/// the snackbar that opens this dialog.
class BulkPartialFailureDialog extends StatelessWidget {
  final BulkOperation operation;
  final List<BulkOperationResult> results;

  const BulkPartialFailureDialog({
    super.key,
    required this.operation,
    required this.results,
  });

  static Future<void> show(
    BuildContext context, {
    required BulkOperation operation,
    required List<BulkOperationResult> results,
  }) {
    return showDialog<void>(
      context: context,
      builder: (_) => BulkPartialFailureDialog(
        operation: operation,
        results: results,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final failures = results.where((r) => !r.success).toList();
    final title = switch (operation) {
      BulkOperation.addToMeal => 'Some recipes could not be added',
      BulkOperation.archive => 'Some items could not be archived',
    };
    return AlertDialog(
      title: Text(title),
      content: SizedBox(
        width: double.maxFinite,
        child: ListView.separated(
          shrinkWrap: true,
          itemCount: failures.length,
          separatorBuilder: (_, _) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final f = failures[i];
            return ListTile(
              key: ValueKey('bulk-failure-${f.targetName}'),
              title: Text(f.targetName),
              subtitle: Text(f.errorReason ?? 'Unknown error'),
              dense: true,
            );
          },
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).maybePop(),
          child: const Text('Dismiss'),
        ),
      ],
    );
  }
}
