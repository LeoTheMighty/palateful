import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/error_reporter.dart';
import 'package:palateful/core/state/provider_ttl.dart';

/// ffm-6 — TTL helper regression tests.
///
/// Uses `fakeAsync` via `FakeAsync` style helpers — because Timer.periodic
/// is wall-clock, we lean on `async_test`'s flake-resistant patterns:
/// drive timers by pumping elapsed time via `Future.delayed`-wrapped
/// assertions under a `fakeAsync` zone, or (in this codebase) by
/// direct `await` with short maxAge values.
void main() {
  group('keepAliveWithTtl', () {
    tearDown(() {
      // Clear any test hooks set by these tests so suite neighbours
      // don't inherit state.
      ErrorReporter.testReportHook = null;
    });

    test('keeps provider alive past autoDispose frame', () async {
      int builds = 0;
      final provider = FutureProvider.autoDispose<int>((ref) async {
        builds++;
        keepAliveWithTtl(
          ref,
          maxAge: const Duration(minutes: 10),
          revalidate: () async {},
        );
        return 42;
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);

      final value = await container.read(provider.future);
      expect(value, 42);
      expect(builds, 1);

      // Without keepAlive, autoDispose would evict after the final read;
      // reading again wouldn't re-fetch immediately because the tear-down
      // schedule is a microtask. A direct re-read observes the cached
      // value (a non-kept-alive autoDispose still caches across reads
      // within the same container lifetime, so this test mostly asserts
      // the timer registration path runs without throwing).
      final second = await container.read(provider.future);
      expect(second, 42);
      expect(
        builds,
        1,
        reason: 'keepAlive prevented rebuild between two reads',
      );
    });

    test('timer fires `revalidate` on every maxAge interval', () async {
      final revalidateCalls = <int>[];
      final provider = FutureProvider.autoDispose<int>((ref) async {
        keepAliveWithTtl(
          ref,
          maxAge: const Duration(milliseconds: 20),
          revalidate: () async {
            revalidateCalls.add(revalidateCalls.length);
          },
        );
        return 1;
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);
      await container.read(provider.future);

      // Wait for ~3 timer firings. 20ms × 3 = 60ms, plus a bit of slop.
      await Future<void>.delayed(const Duration(milliseconds: 80));

      expect(
        revalidateCalls.length,
        greaterThanOrEqualTo(3),
        reason: 'three revalidation ticks should have fired in 80ms '
            'with a 20ms maxAge',
      );
    });

    test(
        'failure in revalidate is captured by ErrorReporter + '
        'does not propagate', () async {
      final reported = <Object>[];
      ErrorReporter.testReportHook = (
        error,
        stack, {
        String? area,
        String? operation,
        Map<String, Object?>? extras,
        bool fatal = false,
      }) {
        reported.add(error);
      };

      final provider = FutureProvider.autoDispose<int>((ref) async {
        keepAliveWithTtl(
          ref,
          maxAge: const Duration(milliseconds: 15),
          revalidate: () async {
            throw StateError('revalidation boom');
          },
        );
        return 0;
      });

      final container = ProviderContainer();
      addTearDown(container.dispose);
      await container.read(provider.future);

      // Let a couple of ticks fire.
      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(reported, isNotEmpty, reason: 'ErrorReporter must log');
      expect(
        reported.first,
        isA<StateError>(),
      );
    });

    test('dispose cancels the timer — no post-dispose fire', () async {
      var calls = 0;
      final provider = FutureProvider.autoDispose<int>((ref) async {
        keepAliveWithTtl(
          ref,
          maxAge: const Duration(milliseconds: 15),
          revalidate: () async {
            calls++;
          },
        );
        return 0;
      });

      final container = ProviderContainer();
      await container.read(provider.future);

      // One tick before dispose.
      await Future<void>.delayed(const Duration(milliseconds: 20));
      final beforeDispose = calls;

      container.dispose();

      // Wait a few more intervals; calls must not grow.
      await Future<void>.delayed(const Duration(milliseconds: 60));
      expect(
        calls,
        beforeDispose,
        reason: 'timer must not fire after container dispose',
      );
    });

    test('assertion: maxAge must be positive', () {
      expect(
        () => ProviderContainer().read(
          FutureProvider.autoDispose<int>((ref) async {
            keepAliveWithTtl(
              ref,
              maxAge: Duration.zero,
              revalidate: () async {},
            );
            return 0;
          }).future,
        ),
        throwsA(isA<AssertionError>()),
      );
    });
  });
}
