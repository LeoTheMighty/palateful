import 'package:flutter/material.dart';

enum EditScope { thisOccurrence, thisAndFollowing, all }

enum EditAction { reschedule, unschedule, recipeSwap }

/// Three-choice bottom sheet shown before any edit on a recurring
/// occurrence. The caller awaits the future — null means cancel.
Future<EditScope?> showEditScopePrompt(
  BuildContext context, {
  required EditAction action,
}) {
  return showModalBottomSheet<EditScope>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _EditScopePromptSheet(action: action),
  );
}

class _EditScopePromptSheet extends StatelessWidget {
  final EditAction action;

  const _EditScopePromptSheet({required this.action});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              _titleFor(action),
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
            const SizedBox(height: 16),
            _choice(
              context,
              scope: EditScope.thisOccurrence,
              label: 'This occurrence',
              subtitle: _subtitle(action, EditScope.thisOccurrence),
            ),
            const SizedBox(height: 8),
            _choice(
              context,
              scope: EditScope.thisAndFollowing,
              label: 'This and following',
              subtitle: _subtitle(action, EditScope.thisAndFollowing),
            ),
            const SizedBox(height: 8),
            _choice(
              context,
              scope: EditScope.all,
              label: 'All occurrences',
              subtitle: _subtitle(action, EditScope.all),
              destructiveTint: true,
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _choice(
    BuildContext context, {
    required EditScope scope,
    required String label,
    required String subtitle,
    bool destructiveTint = false,
  }) {
    final colorScheme = Theme.of(context).colorScheme;
    final borderColor = destructiveTint
        ? colorScheme.error.withValues(alpha: 0.35)
        : colorScheme.outlineVariant;
    return Semantics(
      button: true,
      label: '$label. $subtitle',
      child: InkWell(
        onTap: () => Navigator.pop(context, scope),
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            border: Border.all(color: borderColor),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: destructiveTint
                      ? colorScheme.error
                      : colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: TextStyle(color: colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _titleFor(EditAction action) {
    switch (action) {
      case EditAction.reschedule:
        return 'Reschedule recurring meal';
      case EditAction.unschedule:
        return 'Remove recurring meal';
      case EditAction.recipeSwap:
        return 'Change recurring meal';
    }
  }

  String _subtitle(EditAction action, EditScope scope) {
    switch (scope) {
      case EditScope.thisOccurrence:
        switch (action) {
          case EditAction.reschedule:
            return 'Only this occurrence moves. Past and future untouched.';
          case EditAction.unschedule:
            return 'Only this occurrence is removed. Series continues.';
          case EditAction.recipeSwap:
            return 'Only this occurrence changes. Series continues.';
        }
      case EditScope.thisAndFollowing:
        switch (action) {
          case EditAction.reschedule:
            return 'This and every future occurrence change. Past stays.';
          case EditAction.unschedule:
            return 'This and every future occurrence are removed. Past stays.';
          case EditAction.recipeSwap:
            return 'This and every future occurrence change. Past stays.';
        }
      case EditScope.all:
        switch (action) {
          case EditAction.reschedule:
            return 'Every future occurrence changes. Past stays.';
          case EditAction.unschedule:
            return 'Every future occurrence is removed. Past stays.';
          case EditAction.recipeSwap:
            return 'Every future occurrence changes. Past stays.';
        }
    }
  }
}
