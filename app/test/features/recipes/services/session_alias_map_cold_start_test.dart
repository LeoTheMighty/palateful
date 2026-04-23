// eri-4b: cold-start cache-refresh verification for SessionAliasMap.
//
// The 15 plural→singular aliases seeded by migration `erifraliases01`
// (stalks→stalk, cans→can, etc.) must be picked up by already-logged-in
// users without an app reinstall. The cold-start path runs once per
// DI construction: `SessionAliasMap(apiClient)..init()` fires the live
// fetch; `init()` is idempotent (guarded by `_initialized`) so repeated
// calls in the same session are no-ops, but a process restart re-runs
// DI and picks up fresh aliases.
//
// These tests drive that path directly via the `withFetcher` test seam.

import 'package:flutter_test/flutter_test.dart';

import 'package:palateful/features/recipes/services/session_alias_map.dart';

void main() {
  group('SessionAliasMap cold-start refresh', () {
    test(
      'init() picks up the eri-4b freeform aliases from a live fetch',
      () async {
        final fetcher = () async => <String, dynamic>{
              'aliases': <String, String>{
                'stalks': 'stalk',
                'bunches': 'bunch',
                'cans': 'can',
                'heads': 'head',
                'pieces': 'piece',
                'drops': 'drop',
              },
              'canonical': <String>[
                'cup',
                'tbsp',
                'stalk',
                'bunch',
                'can',
                'head',
                'piece',
                'drop',
              ],
            };
        final map = SessionAliasMap.withFetcher(fetcher);
        expect(map.isInitialized, isFalse);

        await map.init();

        expect(map.isInitialized, isTrue);
        expect(map.coerce('stalks'), 'stalk');
        expect(map.coerce('bunches'), 'bunch');
        expect(map.coerce('cans'), 'can');
        expect(map.coerce('heads'), 'head');
        expect(map.coerce('pieces'), 'piece');
        expect(map.coerce('drops'), 'drop');
      },
    );

    test(
      'canonical words from eri-4a pass through without alias lookup',
      () async {
        final fetcher = () async => <String, dynamic>{
              'aliases': <String, String>{},
              'canonical': <String>[
                'stalk',
                'bunch',
                'can',
                'head',
                'piece',
              ],
            };
        final map = SessionAliasMap.withFetcher(fetcher);
        await map.init();
        // Canonical hit returns the input unchanged.
        expect(map.coerce('stalk'), 'stalk');
        expect(map.coerce('piece'), 'piece');
      },
    );

    test(
      'init() is idempotent within a session — second call is a no-op',
      () async {
        var callCount = 0;
        final fetcher = () async {
          callCount += 1;
          return <String, dynamic>{
            'aliases': <String, String>{'stalks': 'stalk'},
            'canonical': <String>['stalk'],
          };
        };
        final map = SessionAliasMap.withFetcher(fetcher);
        await map.init();
        await map.init();
        expect(callCount, 1, reason: 'second init() must not re-fetch');
        expect(map.coerce('stalks'), 'stalk');
      },
    );

    test(
      'pre-init coerce still works via the hardcoded fallback — '
      'no window where the user gets unnormalized output',
      () {
        // Fetcher returns null so init() leaves the map on the fallback seed.
        final map = SessionAliasMap.withFetcher(() async => null);
        // Fallback map includes tablespoon→tbsp from riip-5.
        expect(map.coerce('tablespoon'), 'tbsp');
        // New aliases aren't in the fallback — that's OK, the normalized
        // (lowercased/trimmed) input flows through to the server where
        // `normalize_unit_display` resolves against the fresh seed.
        expect(map.coerce('stalks'), 'stalks');
      },
    );

    test(
      'failed live fetch leaves the fallback intact — no crash, no data loss',
      () async {
        final map = SessionAliasMap.withFetcher(
          () async => throw Exception('network down'),
        );
        await map.init();
        expect(map.isInitialized, isFalse);
        // Fallback still answers.
        expect(map.coerce('tablespoon'), 'tbsp');
      },
    );
  });
}
