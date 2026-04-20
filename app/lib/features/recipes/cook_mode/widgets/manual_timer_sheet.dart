/// cmt-5 — `ManualTimerSheet` is a bottom sheet that lets the user
/// enter an arbitrary minute count and optional label when neither the
/// extractor nor the regex surfaced a timer for the current step.
///
/// Returns `(int minutes, String label)` on Start; returns `null` when
/// the sheet is dismissed.

library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../util/cook_timer_token.dart';

const int kManualTimerMinMinutes = 1;
const int kManualTimerMaxMinutes = 360;
const int kManualTimerMaxLabelLen = 40;
const String kManualTimerDefaultLabel = 'Timer';

class ManualTimerSheet extends StatefulWidget {
  const ManualTimerSheet({super.key});

  @override
  State<ManualTimerSheet> createState() => _ManualTimerSheetState();
}

class _ManualTimerSheetState extends State<ManualTimerSheet> {
  final _minutesController = TextEditingController();
  final _labelController = TextEditingController(
    text: kManualTimerDefaultLabel,
  );
  int? _minutes;

  @override
  void dispose() {
    _minutesController.dispose();
    _labelController.dispose();
    super.dispose();
  }

  bool get _isValid {
    final m = _minutes;
    return m != null && m >= kManualTimerMinMinutes && m <= kManualTimerMaxMinutes;
  }

  void _onMinutesChanged(String raw) {
    setState(() {
      _minutes = int.tryParse(raw);
    });
  }

  void _submit() {
    if (!_isValid) return;
    var label = _labelController.text.trim();
    if (label.isEmpty) label = kManualTimerDefaultLabel;
    if (label.length > kManualTimerMaxLabelLen) {
      label = label.substring(0, kManualTimerMaxLabelLen);
    }
    Navigator.of(context).pop<(int, String)>((_minutes!, label));
  }

  @override
  Widget build(BuildContext context) {
    final accent = resolveCookTimer(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        24,
        20,
        24,
        MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.timer_outlined, color: accent),
              const SizedBox(width: 8),
              Text(
                'Add a timer',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ],
          ),
          const SizedBox(height: 16),
          TextField(
            key: const Key('manual_timer_minutes'),
            controller: _minutesController,
            autofocus: true,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            onChanged: _onMinutesChanged,
            onSubmitted: (_) => _submit(),
            decoration: InputDecoration(
              labelText: 'Minutes',
              suffixText: 'min',
              border: const OutlineInputBorder(),
              helperText:
                  '$kManualTimerMinMinutes–$kManualTimerMaxMinutes min',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('manual_timer_label'),
            controller: _labelController,
            maxLength: kManualTimerMaxLabelLen,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _submit(),
            decoration: const InputDecoration(
              labelText: 'Label',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(
            key: const Key('manual_timer_start'),
            onPressed: _isValid ? _submit : null,
            style: FilledButton.styleFrom(
              backgroundColor: accent,
              foregroundColor: Colors.white,
              minimumSize: const Size.fromHeight(48),
            ),
            child: const Text('Start'),
          ),
        ],
      ),
    );
  }
}

/// Given a [requested] label, return a unique variant by appending
/// " 2", " 3", ... when [existingLabels] already contains an exact
/// match. Keeps chip display disambiguable when the user adds
/// multiple default-labelled timers.
String disambiguateTimerLabel(
  String requested,
  Iterable<String> existingLabels,
) {
  final set = existingLabels.toSet();
  if (!set.contains(requested)) return requested;
  var n = 2;
  while (set.contains('$requested $n')) {
    n++;
  }
  return '$requested $n';
}
