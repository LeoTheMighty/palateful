import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/injection.dart';
import '../providers/active_calendar_provider.dart';
import '../services/calendar_service.dart';

/// Modal dialog for creating a new calendar.
///
/// Name is required (128 char max, autofocus). Description is optional
/// multi-line. On success, the new calendar becomes the active one via
/// [activeCalendarProvider]. Caller is responsible for dismissing the
/// switcher sheet + reloading the calendar grid.
class CalendarCreateDialog extends ConsumerStatefulWidget {
  const CalendarCreateDialog({super.key});

  @override
  ConsumerState<CalendarCreateDialog> createState() =>
      _CalendarCreateDialogState();
}

class _CalendarCreateDialogState extends ConsumerState<CalendarCreateDialog> {
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final svc = getIt<CalendarService>();
      final cal = await svc.createCalendar(
        name,
        description: _descCtrl.text.trim(),
      );
      // Refresh the list cache so the new calendar is visible in the
      // switcher, then set it active.
      ref.invalidate(calendarsListProvider);
      await ref.read(activeCalendarProvider.notifier).setActive(cal.id);
      if (mounted) Navigator.of(context).pop(cal);
    } catch (e) {
      if (mounted) {
        setState(() {
          _submitting = false;
          _error = 'Failed to create calendar';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final nameLen = _nameCtrl.text.trim().length;
    return AlertDialog(
      title: const Text('New Calendar'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _nameCtrl,
            autofocus: true,
            maxLength: 128,
            decoration: const InputDecoration(
              labelText: 'Name',
              hintText: 'e.g. Meal Prep',
            ),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _descCtrl,
            minLines: 1,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Description (optional)',
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: _submitting ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: (nameLen == 0 || _submitting) ? null : _submit,
          child: _submitting
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Create'),
        ),
      ],
    );
  }
}
