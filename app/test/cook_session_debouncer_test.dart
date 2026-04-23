import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/cook_mode/services/cook_session_debouncer.dart';
import 'package:palateful/features/recipes/cook_mode/services/cook_session_persister.dart';
import 'package:shared_preferences/shared_preferences.dart';

CookSessionState _sample({int currentStep = 0, int updatedAtMs = 100}) {
  return CookSessionState(
    targetKind: CookTargetKind.recipe,
    targetId: 'r1',
    startedAtMs: 0,
    cumulativeElapsedMs: 0,
    activeRecipeId: null,
    currentStepByRecipe: {'r1': currentStep},
    completedStepsByRecipe: const {'r1': <int>{}},
    checkedIngredients: const [],
    activeTimers: const [],
    updatedAtMs: updatedAtMs,
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('coalesces a burst of markDirty calls into a single save', () {
    fakeAsync((async) {
      final persister = _RecordingPersister();
      final debouncer = CookSessionDebouncer(persister);
      final key = CookSessionKey.forRecipe('r1');
      for (var step = 0; step < 5; step++) {
        debouncer.markDirty(key, () => _sample(currentStep: step));
        async.elapse(const Duration(milliseconds: 20));
      }
      // Burst window complete but under the 250ms debounce threshold.
      expect(persister.saves, isEmpty);
      // Flush the debounce window.
      async.elapse(const Duration(milliseconds: 250));
      expect(persister.saves.length, 1);
      expect(persister.saves.single.state.currentStepByRecipe['r1'], 4,
          reason: 'latest snapshot wins');
    });
  });

  test('flushNow writes immediately and cancels the debounce window', () async {
    final persister = _RecordingPersister();
    final debouncer = CookSessionDebouncer(persister);
    final key = CookSessionKey.forRecipe('r1');
    debouncer.markDirty(key, () => _sample(currentStep: 3));
    await debouncer.flushNow();
    expect(persister.saves.length, 1);
    expect(persister.saves.single.state.currentStepByRecipe['r1'], 3);
    // Wait well past the debounce window; no additional save should fire.
    await Future<void>.delayed(const Duration(milliseconds: 400));
    expect(persister.saves.length, 1);
  });

  test('flushNow is a no-op when nothing pending', () async {
    final persister = _RecordingPersister();
    final debouncer = CookSessionDebouncer(persister);
    await debouncer.flushNow();
    expect(persister.saves, isEmpty);
  });

  test('discardPending drops the queued save', () {
    fakeAsync((async) {
      final persister = _RecordingPersister();
      final debouncer = CookSessionDebouncer(persister);
      debouncer.markDirty(
        CookSessionKey.forRecipe('r1'),
        () => _sample(currentStep: 7),
      );
      debouncer.discardPending();
      async.elapse(const Duration(milliseconds: 500));
      expect(persister.saves, isEmpty);
    });
  });
}

class _SaveCall {
  final String key;
  final CookSessionState state;
  _SaveCall(this.key, this.state);
}

class _RecordingPersister extends CookSessionPersister {
  final List<_SaveCall> saves = [];

  @override
  Future<void> save(String key, CookSessionState state) async {
    saves.add(_SaveCall(key, state));
  }
}
