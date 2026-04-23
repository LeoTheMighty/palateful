import 'package:flutter/material.dart';

import '../../../../core/theme/theme.dart';
import '../services/cook_session_persister.dart';
import '../util/relative_time.dart';

/// Result of the Resume / Start Over gate.
enum CookResumeChoice {
  resume,
  startOver,
}

/// Shows the non-dismissible Resume / Start Over gate sheet. The caller
/// MUST act on the returned choice before continuing — the screen's
/// initial stopwatch baseline depends on which path the user took.
///
/// [targetName] is the user-facing title (recipe name or meal name).
/// [totalSteps] is optional — when null, the summary line drops the
/// "of M" suffix.
/// [stepSummaryOverride], when non-null, replaces the default
/// "step N [of M]" phrase with caller-supplied section-aware copy
/// (e.g. meal cook's "Salad · step 2 of 4").
Future<CookResumeChoice?> showCookResumeGate(
  BuildContext context, {
  required CookSessionState state,
  required String targetName,
  int? totalSteps,
  DateTime? now,
  String? stepSummaryOverride,
}) {
  return showModalBottomSheet<CookResumeChoice>(
    context: context,
    isDismissible: false,
    enableDrag: false,
    isScrollControlled: true,
    backgroundColor: Theme.of(context).extension<CookModeTheme>()?.cookSurface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (sheetContext) => CookResumeGateSheet(
      state: state,
      targetName: targetName,
      totalSteps: totalSteps,
      now: now,
      stepSummaryOverride: stepSummaryOverride,
    ),
  );
}

/// Non-dismissible sheet offering Resume or Start Over for a persisted
/// cook session. Back-button is swallowed by a [PopScope] — the user
/// must tap one of the two buttons.
class CookResumeGateSheet extends StatelessWidget {
  final CookSessionState state;
  final String targetName;
  final int? totalSteps;
  final DateTime? now;
  final String? stepSummaryOverride;

  const CookResumeGateSheet({
    super.key,
    required this.state,
    required this.targetName,
    this.totalSteps,
    this.now,
    this.stepSummaryOverride,
  });

  @override
  Widget build(BuildContext context) {
    final cook = context.cookModeTheme;
    final reference = now ?? DateTime.now();
    final started =
        DateTime.fromMillisecondsSinceEpoch(state.startedAtMs);
    final startedRelative = relativeTime(started, now: reference);

    final stepSummary = stepSummaryOverride ??
        (totalSteps != null
            ? 'step ${state.currentStep + 1} of $totalSteps'
            : 'step ${state.currentStep + 1}');
    final checkedCount = state.checkedIngredients.length;
    final totalTimers = state.activeTimers.length;
    final expiredTimers = state.activeTimers
        .where((t) => t.deadlineMs <= reference.millisecondsSinceEpoch)
        .length;
    final timerPhrase = _timerPhrase(totalTimers, expiredTimers);

    final summary = StringBuffer()
      ..write('Picked up from ')
      ..write(stepSummary)
      ..write(' · started ')
      ..write(startedRelative)
      ..write(' · ')
      ..write(_ingredientPhrase(checkedCount));
    if (timerPhrase != null) {
      summary..write(' · ')..write(timerPhrase);
    }

    return PopScope(
      canPop: false,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Drag handle (decorative — sheet is non-dismissible).
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
                targetName,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                  color: cook.cookOnSurface,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                summary.toString(),
                style: TextStyle(
                  fontSize: 14,
                  color: cook.cookOnSurface.withValues(alpha: 0.8),
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: FilledButton(
                      onPressed: () => Navigator.of(context)
                          .pop(CookResumeChoice.resume),
                      style: FilledButton.styleFrom(
                        backgroundColor: cook.cookAccent,
                        foregroundColor: cook.cookOnAccent,
                        minimumSize: const Size.fromHeight(48),
                      ),
                      child: const Text('Resume'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextButton(
                      onPressed: () => Navigator.of(context)
                          .pop(CookResumeChoice.startOver),
                      style: TextButton.styleFrom(
                        foregroundColor: cook.cookError,
                        minimumSize: const Size.fromHeight(48),
                      ),
                      child: const Text('Start Over'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _ingredientPhrase(int n) {
    if (n == 0) return 'no ingredients checked';
    if (n == 1) return '1 ingredient checked';
    return '$n ingredients checked';
  }

  String? _timerPhrase(int total, int expired) {
    if (total == 0) return null;
    final base = total == 1 ? '1 timer' : '$total timers';
    if (expired == 0) return base;
    return '$base (done while away)';
  }
}
