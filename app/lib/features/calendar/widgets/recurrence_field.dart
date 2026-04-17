import 'package:flutter/material.dart';

import '../models/meal_event.dart';

const _weekdays = [
  ('mon', 'Mon'),
  ('tue', 'Tue'),
  ('wed', 'Wed'),
  ('thu', 'Thu'),
  ('fri', 'Fri'),
  ('sat', 'Sat'),
  ('sun', 'Sun'),
];

/// Collapsed "Repeats: Never ▾" row + tap-to-open bottom sheet for picking
/// the full RecurrenceValue. Null = non-recurring.
class RecurrenceField extends StatelessWidget {
  final RecurrenceValue? value;
  final DateTime anchorDate;
  final ValueChanged<RecurrenceValue?> onChanged;

  const RecurrenceField({
    super.key,
    required this.value,
    required this.anchorDate,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return GestureDetector(
      onTap: () => _openPicker(context),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(
              Icons.repeat,
              size: 18,
              color: colorScheme.primary,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                _summary(),
                style: TextStyle(
                  fontSize: 15,
                  color: colorScheme.onSurface,
                ),
              ),
            ),
            Icon(
              Icons.chevron_right,
              color: colorScheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }

  String _summary() {
    final v = value;
    if (v == null) return 'Repeats: Never';
    return 'Repeats: ${describeRecurrence(v)}';
  }

  Future<void> _openPicker(BuildContext context) async {
    final result = await showModalBottomSheet<_PickerResult>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _RecurrencePickerSheet(
        initial: value,
        anchorDate: anchorDate,
      ),
    );
    if (result != null) {
      onChanged(result.value);
    }
  }
}

/// Public helper for rendering a rule summary line.
String describeRecurrence(RecurrenceValue v) {
  final intervalLabel = switch (v.interval) {
    'weekly' => 'Weekly',
    'biweekly' => 'Every other week',
    'monthly' => 'Monthly (${v.monthlyNth ?? 'first'} ${_weekdayLabel(v.weekdays.firstOrNull)})',
    _ => v.interval,
  };
  if (v.interval == 'monthly') return intervalLabel;
  final days = v.weekdays.map(_weekdayLabel).join(', ');
  return '$intervalLabel · $days';
}

String _weekdayLabel(String? code) {
  if (code == null) return '';
  final match = _weekdays.firstWhere(
    (w) => w.$1 == code,
    orElse: () => (code, code),
  );
  return match.$2;
}

class _PickerResult {
  final RecurrenceValue? value;
  const _PickerResult(this.value);
}

class _RecurrencePickerSheet extends StatefulWidget {
  final RecurrenceValue? initial;
  final DateTime anchorDate;

  const _RecurrencePickerSheet({
    required this.initial,
    required this.anchorDate,
  });

  @override
  State<_RecurrencePickerSheet> createState() => _RecurrencePickerSheetState();
}

class _RecurrencePickerSheetState extends State<_RecurrencePickerSheet> {
  late String _interval; // "never" | "weekly" | "biweekly" | "monthly"
  late Set<String> _selectedDays;
  DateTime? _endDate;
  String _monthlyNth = 'first';

  @override
  void initState() {
    super.initState();
    final v = widget.initial;
    if (v == null) {
      _interval = 'never';
      _selectedDays = {_codeFor(widget.anchorDate.weekday)};
    } else {
      _interval = v.interval;
      _selectedDays = v.weekdays.toSet();
      _endDate = v.endDate;
      _monthlyNth = v.monthlyNth ?? 'first';
    }
  }

  String _codeFor(int weekday) {
    // Flutter weekday: 1=Mon ... 7=Sun. Matches _weekdays order.
    return _weekdays[weekday - 1].$1;
  }

  bool get _canSave {
    if (_interval == 'never') return true;
    if (_interval == 'monthly') return _selectedDays.length == 1;
    return _selectedDays.isNotEmpty;
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 24,
        bottom: 24 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Repeats',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.pop(context),
                color: colorScheme.onSurfaceVariant,
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Interval chips
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _intervalChip('never', 'Never'),
              _intervalChip('weekly', 'Weekly'),
              _intervalChip('biweekly', 'Every other week'),
              _intervalChip('monthly', 'Monthly'),
            ],
          ),

          if (_interval == 'monthly') ...[
            const SizedBox(height: 20),
            Text(
              'Which occurrence?',
              style: TextStyle(
                fontSize: 13,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                for (final n in const ['first', 'second', 'third', 'fourth', 'last'])
                  _nthChip(n),
              ],
            ),
          ],

          if (_interval != 'never') ...[
            const SizedBox(height: 20),
            Text(
              _interval == 'monthly' ? 'Weekday' : 'On which days?',
              style: TextStyle(
                fontSize: 13,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                for (final w in _weekdays) _dayChip(w.$1, w.$2),
              ],
            ),
            if (_interval != 'monthly') ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  _presetChip('Weekdays', ['mon', 'tue', 'wed', 'thu', 'fri']),
                  _presetChip('Weekends', ['sat', 'sun']),
                ],
              ),
            ],
            const SizedBox(height: 20),

            // End-date picker
            Text(
              'Ends on',
              style: TextStyle(
                fontSize: 13,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: GestureDetector(
                    onTap: _pickEndDate,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 14,
                      ),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _endDate == null
                            ? 'Forever'
                            : _formatDate(_endDate!),
                      ),
                    ),
                  ),
                ),
                if (_endDate != null)
                  IconButton(
                    icon: const Icon(Icons.clear),
                    onPressed: () => setState(() => _endDate = null),
                  ),
              ],
            ),
          ],

          const SizedBox(height: 28),

          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _canSave ? _done : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: colorScheme.primary,
                foregroundColor: colorScheme.onPrimary,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text(
                'Done',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _intervalChip(String value, String label) {
    final selected = _interval == value;
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => setState(() {
        _interval = value;
        if (value == 'monthly' && _selectedDays.length > 1) {
          _selectedDays = {_selectedDays.first};
        }
      }),
    );
  }

  Widget _nthChip(String value) {
    final selected = _monthlyNth == value;
    return ChoiceChip(
      label: Text(value[0].toUpperCase() + value.substring(1)),
      selected: selected,
      onSelected: (_) => setState(() => _monthlyNth = value),
    );
  }

  Widget _dayChip(String code, String label) {
    final selected = _selectedDays.contains(code);
    return FilterChip(
      label: Text(label),
      selected: selected,
      onSelected: (v) => setState(() {
        if (_interval == 'monthly') {
          _selectedDays = {code};
          return;
        }
        if (v) {
          _selectedDays.add(code);
        } else {
          _selectedDays.remove(code);
        }
      }),
    );
  }

  Widget _presetChip(String label, List<String> days) {
    return ActionChip(
      label: Text(label),
      onPressed: () => setState(() {
        _selectedDays = days.toSet();
      }),
    );
  }

  Future<void> _pickEndDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _endDate ?? widget.anchorDate.add(const Duration(days: 30)),
      firstDate: widget.anchorDate,
      lastDate: widget.anchorDate.add(const Duration(days: 365 * 2)),
    );
    if (picked != null) {
      setState(() => _endDate = picked);
    }
  }

  void _done() {
    if (_interval == 'never') {
      Navigator.pop(context, const _PickerResult(null));
      return;
    }
    final ordered = _weekdays
        .map((w) => w.$1)
        .where(_selectedDays.contains)
        .toList();
    Navigator.pop(
      context,
      _PickerResult(
        RecurrenceValue(
          interval: _interval,
          weekdays: ordered,
          endDate: _endDate,
          monthlyNth: _interval == 'monthly' ? _monthlyNth : null,
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${months[date.month - 1]} ${date.day}, ${date.year}';
  }
}
