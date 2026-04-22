import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/services/error_reporter.dart';
import 'package:palateful/features/recipes/cook_mode/services/cook_session_persister.dart';
import 'package:shared_preferences/shared_preferences.dart';

CookSessionState _sample({
  String id = 'recipe-1',
  int currentStep = 2,
  int elapsedMs = 120000,
  int updatedAtMs = 1700000000000,
  List<SavedTimerState>? timers,
}) {
  return CookSessionState(
    targetKind: CookTargetKind.recipe,
    targetId: id,
    startedAtMs: updatedAtMs - elapsedMs,
    cumulativeElapsedMs: elapsedMs,
    currentStep: currentStep,
    completedSteps: const [0, 1],
    checkedIngredients: const ['0', '2'],
    activeTimers: timers ??
        const [
          SavedTimerState(
            label: 'simmer',
            deadlineMs: 1700000600000,
            totalDurationSeconds: 600,
            source: 'extracted',
          ),
        ],
    updatedAtMs: updatedAtMs,
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    ErrorReporter.testLogHook = null;
  });

  tearDown(() {
    ErrorReporter.testLogHook = null;
  });

  group('CookSessionKey', () {
    test('forRecipe uses cook_session_recipe_<id>', () {
      expect(CookSessionKey.forRecipe('abc'), 'cook_session_recipe_abc');
    });

    test('forMeal uses cook_session_meal_<id>', () {
      expect(CookSessionKey.forMeal('xyz'), 'cook_session_meal_xyz');
    });
  });

  group('CookSessionState serialization', () {
    test('round-trips through JSON losslessly', () {
      final original = _sample();
      final encoded = jsonEncode(original.toJson());
      final decoded = CookSessionState.fromJson(jsonDecode(encoded));
      expect(decoded, isNotNull);
      expect(decoded!.targetKind, CookTargetKind.recipe);
      expect(decoded.targetId, original.targetId);
      expect(decoded.startedAtMs, original.startedAtMs);
      expect(decoded.cumulativeElapsedMs, original.cumulativeElapsedMs);
      expect(decoded.currentStep, original.currentStep);
      expect(decoded.completedSteps, original.completedSteps);
      expect(decoded.checkedIngredients, original.checkedIngredients);
      expect(decoded.activeTimers, original.activeTimers);
      expect(decoded.updatedAtMs, original.updatedAtMs);
    });

    test('writes schema_version=1 on toJson', () {
      final json = _sample().toJson();
      expect(json['schema_version'], 1);
    });

    test('fromJson returns null for unknown schema_version', () {
      final stale = {..._sample().toJson(), 'schema_version': 999};
      expect(CookSessionState.fromJson(stale), isNull);
    });

    test('fromJson returns null for missing required fields', () {
      final broken = {..._sample().toJson()};
      broken.remove('target_id');
      expect(CookSessionState.fromJson(broken), isNull);
    });

    test('fromJson drops malformed timers but keeps valid ones', () {
      final json = _sample().toJson();
      json['active_timers'] = [
        {'label': 'ok', 'deadline_ms': 10, 'total_duration_s': 60, 'source': 'manual'},
        {'label': 'bad'},
      ];
      final decoded = CookSessionState.fromJson(json);
      expect(decoded, isNotNull);
      expect(decoded!.activeTimers.length, 1);
      expect(decoded.activeTimers.first.label, 'ok');
    });
  });

  group('CookSessionPersister.load', () {
    test('returns null when key absent', () async {
      final persister = CookSessionPersister();
      expect(await persister.load('cook_session_recipe_missing'), isNull);
    });

    test('returns parsed state when payload is valid', () async {
      final persister = CookSessionPersister();
      final key = CookSessionKey.forRecipe('r1');
      await persister.save(key, _sample(id: 'r1'));
      final loaded = await persister.load(key);
      expect(loaded, isNotNull);
      expect(loaded!.currentStep, 2);
    });

    test('returns null and keeps value when schema_version unknown', () async {
      final prefs = await SharedPreferences.getInstance();
      final key = CookSessionKey.forRecipe('r2');
      final payload = _sample(id: 'r2').toJson();
      payload['schema_version'] = 99;
      await prefs.setString(key, jsonEncode(payload));
      final persister = CookSessionPersister();
      expect(await persister.load(key), isNull);
      // Don't drop future-schema data — newer build may still want it.
      expect(prefs.getString(key), isNotNull);
    });

    test('malformed JSON clears the key and logs a warning', () async {
      final prefs = await SharedPreferences.getInstance();
      final key = CookSessionKey.forRecipe('r3');
      await prefs.setString(key, '{not-valid-json');
      final logged = <String>[];
      ErrorReporter.testLogHook = logged.add;
      final persister = CookSessionPersister();
      expect(await persister.load(key), isNull);
      expect(prefs.getString(key), isNull);
      expect(logged, isNotEmpty);
      expect(logged.first, contains('malformed'));
    });
  });

  group('CookSessionPersister.save', () {
    test('writes encoded JSON under the key', () async {
      final persister = CookSessionPersister();
      final key = CookSessionKey.forRecipe('r4');
      await persister.save(key, _sample(id: 'r4'));
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(key);
      expect(raw, isNotNull);
      final decoded = jsonDecode(raw!) as Map<String, dynamic>;
      expect(decoded['target_id'], 'r4');
      expect(decoded['schema_version'], 1);
    });

    test('skips writes exceeding the 50 KB cap and preserves prior value',
        () async {
      final persister = CookSessionPersister();
      final key = CookSessionKey.forRecipe('r5');
      await persister.save(key, _sample(id: 'r5', currentStep: 1));
      final oversized = _sample(
        id: 'r5',
        currentStep: 99,
        timers: List<SavedTimerState>.generate(
          1000,
          (i) => SavedTimerState(
            label: 'a' * 80,
            deadlineMs: 1700000000000 + i,
            totalDurationSeconds: 600,
            source: 'manual',
          ),
        ),
      );
      final logged = <String>[];
      ErrorReporter.testLogHook = logged.add;
      await persister.save(key, oversized);
      final loaded = await persister.load(key);
      expect(loaded, isNotNull);
      expect(loaded!.currentStep, 1, reason: 'prior value preserved');
      expect(logged.any((m) => m.contains('exceeds')), isTrue);
    });
  });

  group('CookSessionPersister.clear', () {
    test('removes the key', () async {
      final persister = CookSessionPersister();
      final key = CookSessionKey.forRecipe('r6');
      await persister.save(key, _sample(id: 'r6'));
      await persister.clear(key);
      expect(await persister.load(key), isNull);
    });

    test('is idempotent on an already-empty key', () async {
      final persister = CookSessionPersister();
      await persister.clear('cook_session_recipe_none');
      // no throw.
    });
  });

  group('CookSessionPersister.listKeys', () {
    test('filters to cook-session keys by default', () async {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('unrelated_key', 'x');
      final persister = CookSessionPersister();
      await persister.save(CookSessionKey.forRecipe('a'), _sample(id: 'a'));
      await persister.save(CookSessionKey.forMeal('b'), _sample(id: 'b'));
      final keys = await persister.listKeys();
      expect(keys, containsAll([
        CookSessionKey.forRecipe('a'),
        CookSessionKey.forMeal('b'),
      ]));
      expect(keys.contains('unrelated_key'), isFalse);
    });

    test('prefix override returns only matching keys', () async {
      final persister = CookSessionPersister();
      await persister.save(CookSessionKey.forRecipe('a'), _sample(id: 'a'));
      await persister.save(CookSessionKey.forMeal('b'), _sample(id: 'b'));
      final recipeOnly =
          await persister.listKeys(prefix: CookSessionKey.recipePrefix);
      expect(recipeOnly, [CookSessionKey.forRecipe('a')]);
    });
  });

  group('CookSessionPersister.pruneStaleOlderThan', () {
    test('deletes entries whose updated_at_ms is older than the window',
        () async {
      final persister = CookSessionPersister();
      final now = DateTime.now().millisecondsSinceEpoch;
      final fresh = _sample(id: 'fresh', updatedAtMs: now);
      final stale = _sample(
        id: 'stale',
        updatedAtMs: now - const Duration(days: 31).inMilliseconds,
      );
      await persister.save(CookSessionKey.forRecipe('fresh'), fresh);
      await persister.save(CookSessionKey.forRecipe('stale'), stale);
      final cleared =
          await persister.pruneStaleOlderThan(const Duration(days: 30));
      expect(cleared, 1);
      expect(await persister.load(CookSessionKey.forRecipe('fresh')), isNotNull);
      expect(await persister.load(CookSessionKey.forRecipe('stale')), isNull);
    });

    test('treats malformed entries as stale', () async {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(CookSessionKey.forRecipe('broken'), '{not-json');
      final persister = CookSessionPersister();
      final cleared =
          await persister.pruneStaleOlderThan(const Duration(days: 30));
      expect(cleared, 1);
      expect(prefs.getString(CookSessionKey.forRecipe('broken')), isNull);
    });

    test('ignores keys outside the cook-session namespace', () async {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('palateful_recipe_other', 'keep me');
      final persister = CookSessionPersister();
      await persister.pruneStaleOlderThan(const Duration(days: 30));
      expect(prefs.getString('palateful_recipe_other'), 'keep me');
    });
  });
}
