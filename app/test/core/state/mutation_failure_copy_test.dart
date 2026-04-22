// rp-5 AC #1 — enumerate `MutationType.values` and assert every enum
// case has a `mutationFailureCopy` entry. Runtime enumeration is the
// right mechanism (Dart's const-time asserts don't fire at build
// time), and this test fails CI the moment a new enum case lands
// without copy.

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/core/state/mutation_failure_copy.dart';

void main() {
  group('mutationFailureCopy exhaustiveness', () {
    test('every MutationType has a copy entry', () {
      final missing = <MutationType>[];
      for (final type in MutationType.values) {
        if (!mutationFailureCopy.containsKey(type)) missing.add(type);
      }
      expect(
        missing,
        isEmpty,
        reason:
            'Every MutationType MUST have a mutationFailureCopy entry. '
            'Missing: $missing. Add a `(verb, noun)` pair in '
            'app/lib/core/state/mutation_failure_copy.dart.',
      );
    });

    test('every copy is 320px-safe (title + retry fits two lines)', () {
      // The Retry action label is the literal 'Retry' (5 chars). The
      // title is `"Couldn't <verb> <noun>"`. On iPhone SE 3rd-gen
      // (320px physical), two lines of body1 hold ~40 chars each —
      // so `title.length <= 40` is a sensible guard (the Retry action
      // renders to the right, not below, on floating Snackbars).
      for (final type in MutationType.values) {
        final copy = mutationFailureCopy[type]!;
        expect(
          copy.title.length,
          lessThanOrEqualTo(40),
          reason:
              '${type.name} copy "${copy.title}" is too long for 320px. '
              'Shorten the verb or noun.',
        );
      }
    });

    test('no duplicate (verb, noun) pairs point to confusingly-similar types',
        () {
      // Soft check: multiple types can legitimately share (verb, noun)
      // — e.g. updateNotificationPrefs and any future toggle-update
      // might both "update notifications". We just print a warning
      // via test output if the duplicate feels accidental.
      final seen = <String, MutationType>{};
      final duplicates = <String, List<MutationType>>{};
      for (final type in MutationType.values) {
        final copy = mutationFailureCopy[type]!;
        final key = '${copy.verb}|${copy.noun}';
        if (seen.containsKey(key)) {
          duplicates
              .putIfAbsent(key, () => [seen[key]!])
              .add(type);
        } else {
          seen[key] = type;
        }
      }
      // Not an assertion — just a helpful signal.
      if (duplicates.isNotEmpty) {
        // ignore: avoid_print
        print(
            'mutation_failure_copy — ${duplicates.length} duplicate copy pair(s):');
        duplicates.forEach((k, ts) => print('  $k → $ts'));
      }
    });
  });

  group('Title format contract', () {
    test('renders as "Couldn\'t <verb> <noun>"', () {
      const copy = MutationFailureCopy(verb: 'save', noun: 'recipe');
      expect(copy.title, "Couldn't save recipe");
    });
  });
}
