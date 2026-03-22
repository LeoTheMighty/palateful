/// Shared helpers for E2E integration tests.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Pump frames until the UI settles or [timeout] expires.
///
/// Unlike raw `pumpAndSettle`, this tolerates screens with perpetual
/// animations (shimmer loaders, streaming indicators, etc.).
Future<void> settle(
  WidgetTester tester, {
  Duration timeout = const Duration(seconds: 30),
}) async {
  final deadline = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(deadline)) {
    await tester.pump(const Duration(milliseconds: 500));
    try {
      await tester.pumpAndSettle(const Duration(milliseconds: 200));
      return; // settled
    } catch (_) {
      // still animating — keep pumping
    }
  }
  // Give up waiting for full settle — do one last pump so the test can proceed
  await tester.pump(const Duration(milliseconds: 500));
}

/// Wait until [finder] matches at least one widget, pumping every 300 ms.
///
/// This is the preferred way to wait for navigation or data-loading to
/// complete: ask for a specific widget that proves the screen is ready.
Future<void> waitFor(
  WidgetTester tester,
  Finder finder, {
  Duration timeout = const Duration(seconds: 15),
}) async {
  final deadline = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(deadline)) {
    await tester.pump(const Duration(milliseconds: 300));
    if (finder.evaluate().isNotEmpty) {
      // One extra pump to let follow-on frames land
      await tester.pump(const Duration(milliseconds: 100));
      return;
    }
  }
  // Final assertion — will give a clear error message on failure
  expect(finder, findsWidgets,
      reason: 'waitFor timed out looking for: $finder');
}

/// Tap a widget identified by visible text, then pump.
Future<void> tapText(WidgetTester tester, String text) async {
  final finder = find.text(text);
  expect(finder, findsWidgets, reason: 'tapText: "$text" not found');
  await tester.ensureVisible(finder.first);
  await tester.tap(finder.first);
  await tester.pump(const Duration(milliseconds: 300));
}

/// Tap a widget by its tooltip (used for icon buttons).
Future<void> tapTooltip(WidgetTester tester, String tooltip) async {
  final finder = find.byTooltip(tooltip);
  expect(finder, findsWidgets, reason: 'tapTooltip: "$tooltip" not found');
  await tester.ensureVisible(finder.first);
  await tester.tap(finder.first);
  await tester.pump(const Duration(milliseconds: 300));
}

/// Enter text into the first TextField whose decoration contains [hint].
Future<void> enterIn(WidgetTester tester, String hint, String text) async {
  final field = find.widgetWithText(TextField, hint);
  expect(field, findsWidgets, reason: 'enterIn: no TextField with "$hint"');
  await tester.tap(field.first);
  await tester.enterText(field.first, text);
  await tester.pump(const Duration(milliseconds: 300));
}

/// Assert that some widget containing [text] is visible.
void assertVisible(String text) {
  expect(find.textContaining(text), findsWidgets,
      reason: 'Expected "$text" to be visible on screen');
}

/// Assert that [text] is NOT visible on screen.
void assertNotVisible(String text) {
  expect(find.text(text), findsNothing,
      reason: 'Expected "$text" NOT to be visible');
}

/// Tap the first FloatingActionButton on screen.
Future<void> tapFab(WidgetTester tester) async {
  final fab = find.byType(FloatingActionButton);
  expect(fab, findsWidgets, reason: 'No FloatingActionButton found');
  await tester.ensureVisible(fab.first);
  await tester.tap(fab.first);
  await tester.pump(const Duration(milliseconds: 300));
}

/// Tap a widget found by [finder], then pump.
Future<void> tapFinder(WidgetTester tester, Finder finder) async {
  expect(finder, findsWidgets, reason: 'tapFinder: widget not found');
  await tester.ensureVisible(finder.first);
  await tester.tap(finder.first);
  await tester.pump(const Duration(milliseconds: 300));
}
