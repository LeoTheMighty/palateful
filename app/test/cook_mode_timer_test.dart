import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/theme/app_colors.dart';

// ---------------------------------------------------------------------------
// Helpers that replicate the timer-related widgets in isolation (no DI needed)
// ---------------------------------------------------------------------------

String _formatDuration(Duration d) {
  final minutes = d.inMinutes;
  final seconds = d.inSeconds % 60;
  return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
}

/// Minimal timer-chip widget for unit testing chip rendering.
Widget _buildTimerChip({
  required String label,
  required Duration remaining,
  required Duration total,
  required VoidCallback onClose,
  required VoidCallback onTap,
}) {
  final progress = total.inSeconds > 0
      ? 1 - (remaining.inSeconds / total.inSeconds)
      : 1.0;
  return GestureDetector(
    onTap: onTap,
    child: Container(
      key: const Key('timer_chip'),
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: AppColors.withOpacity(AppColors.terracotta, 0.15),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppColors.terracotta),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              key: const Key('timer_progress'),
              value: progress,
              strokeWidth: 2,
              color: AppColors.terracotta,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            _formatDuration(remaining),
            key: const Key('timer_countdown'),
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppColors.terracotta,
              fontFeatures: [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: onClose,
            child: const Icon(Icons.close, size: 16, color: AppColors.terracotta),
          ),
        ],
      ),
    ),
  );
}

/// Minimal timer-detail sheet for unit testing.
Widget _buildTimerDetailSheet({
  required String label,
  required Duration remaining,
  required VoidCallback onCancel,
  required VoidCallback onRestart,
}) {
  return Padding(
    padding: const EdgeInsets.fromLTRB(24, 20, 24, 36),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppColors.warmIvory,
          ),
        ),
        const SizedBox(height: 16),
        Text(
          _formatDuration(remaining),
          key: const Key('sheet_countdown'),
          style: const TextStyle(
            fontSize: 72,
            fontWeight: FontWeight.w700,
            color: AppColors.terracotta,
            fontFeatures: [FontFeature.tabularFigures()],
          ),
        ),
        const SizedBox(height: 32),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: onCancel,
                icon: const Icon(Icons.close),
                label: const Text('Cancel Timer'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.warmIvory,
                  minimumSize: const Size.fromHeight(48),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton.icon(
                onPressed: onRestart,
                icon: const Icon(Icons.replay),
                label: const Text('Restart'),
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.terracotta,
                  minimumSize: const Size.fromHeight(48),
                ),
              ),
            ),
          ],
        ),
      ],
    ),
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('Timer chip', () {
    testWidgets('renders formatted countdown with MM:SS', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            backgroundColor: AppColors.chocolate,
            body: Center(
              child: _buildTimerChip(
                label: 'Step 1',
                remaining: const Duration(minutes: 4, seconds: 35),
                total: const Duration(minutes: 5),
                onClose: () {},
                onTap: () {},
              ),
            ),
          ),
        ),
      );

      expect(find.byKey(const Key('timer_countdown')), findsOneWidget);
      expect(find.text('04:35'), findsOneWidget);
    });

    testWidgets('close icon fires cancel callback', (tester) async {
      bool cancelled = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: _buildTimerChip(
                label: 'Step 2',
                remaining: const Duration(minutes: 2),
                total: const Duration(minutes: 5),
                onClose: () => cancelled = true,
                onTap: () {},
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.close));
      expect(cancelled, isTrue);
    });

    testWidgets('tapping chip fires onTap callback', (tester) async {
      bool tapped = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: _buildTimerChip(
                label: 'Step 3',
                remaining: const Duration(minutes: 1),
                total: const Duration(minutes: 3),
                onClose: () {},
                onTap: () => tapped = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('timer_chip')));
      expect(tapped, isTrue);
    });

    testWidgets('circular progress reflects elapsed fraction', (tester) async {
      // 90s remaining of 180s total → progress = 1 - 0.5 = 0.5
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: _buildTimerChip(
                label: 'Boil pasta',
                remaining: const Duration(seconds: 90),
                total: const Duration(seconds: 180),
                onClose: () {},
                onTap: () {},
              ),
            ),
          ),
        ),
      );

      final progress = tester.widget<CircularProgressIndicator>(
          find.byKey(const Key('timer_progress')));
      expect(progress.value, closeTo(0.5, 0.01));
    });
  });

  group('Timer detail sheet', () {
    testWidgets('renders label and 72px countdown', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            backgroundColor: AppColors.chocolateDark,
            body: _buildTimerDetailSheet(
              label: 'Simmer sauce',
              remaining: const Duration(minutes: 12, seconds: 5),
              onCancel: () {},
              onRestart: () {},
            ),
          ),
        ),
      );

      expect(find.text('Simmer sauce'), findsOneWidget);
      expect(find.byKey(const Key('sheet_countdown')), findsOneWidget);
      expect(find.text('12:05'), findsOneWidget);

      final countdownText = tester.widget<Text>(
          find.byKey(const Key('sheet_countdown')));
      expect(countdownText.style?.fontSize, 72);
    });

    testWidgets('Cancel Timer button fires cancel callback', (tester) async {
      bool cancelled = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: _buildTimerDetailSheet(
              label: 'Rest dough',
              remaining: const Duration(minutes: 3),
              onCancel: () => cancelled = true,
              onRestart: () {},
            ),
          ),
        ),
      );

      await tester.tap(find.text('Cancel Timer'));
      expect(cancelled, isTrue);
    });

    testWidgets('Restart button fires restart callback', (tester) async {
      bool restarted = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: _buildTimerDetailSheet(
              label: 'Chill butter',
              remaining: const Duration(minutes: 10),
              onCancel: () {},
              onRestart: () => restarted = true,
            ),
          ),
        ),
      );

      await tester.tap(find.text('Restart'));
      expect(restarted, isTrue);
    });
  });

  group('_formatDuration helper', () {
    test('zero duration formats as 00:00', () {
      expect(_formatDuration(Duration.zero), '00:00');
    });

    test('one minute thirty seconds formats as 01:30', () {
      expect(_formatDuration(const Duration(minutes: 1, seconds: 30)), '01:30');
    });

    test('hours spill into minutes field', () {
      // 65 minutes 5 seconds
      expect(_formatDuration(const Duration(hours: 1, minutes: 5, seconds: 5)),
          '65:05');
    });
  });
}
