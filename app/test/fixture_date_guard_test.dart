// rsh101 — grep guard against hardcoded fixture dates.
//
// `imports_tab.dart:165-168` cuts the Auto-Imported and Skipped buckets
// off at 30 days, measured against `DateTime.now()`. A test fixture
// frozen at a literal date is therefore a time bomb: it passes until the
// wall clock drifts past the cutoff, then fails — reddening
// `flutter-test`, which is the root job both `deploy-web` (`ci.yml:462`)
// and `detect-changes` (`ci.yml:521`) hang off. That is precisely how
// prod stayed frozen on image `c85e350` from 2026-04-26 to 2026-07-27.
//
// This guard fails on any *new* hardcoded `'created_at': '<year>-…'`
// literal under `app/test/`. Two escapes, both deliberate:
//
//   1. Append `// age-independent` to the line, when the fixture feeds a
//      bucket the widget shows regardless of age (Needs Review, Failed).
//   2. Add the file to `test/fixture_date_guard_baseline.txt` with a
//      count. That file is GONE as of fxfuse — the 29 files / 66
//      literals it grandfathered were drained (anchored to `now` where
//      they reach a cutoff, marked `// age-independent` where they
//      provably don't), and the guard treats an absent baseline as an
//      empty one. Re-creating it grandfathers a live fuse, so it needs
//      reviewer sign-off and a rationale naming the specific surface.
//
// The counts ratchet in both directions: cleaning a file up without
// lowering its count fails too, so the baseline can only shrink.
//
// Escape 1 is a claim, not a comment: `// age-independent` asserts the
// literal never reaches a `DateTime.now()`-relative comparison. Prove it
// the way fxfuse did — `app/tool/time_travel_check.sh` re-runs the suite
// with every fixture date shifted into the past, which is arithmetically
// the same as advancing the clock, so a mis-marked literal fails there
// instead of on a random morning months from now.

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Matches a `created_at` map entry whose value is a hardcoded date
/// literal — a quoted value opening with four digits and a dash.
/// Deliberately narrow: a computed value (`_at(...)`,
/// `DateTime.now()…`) has no opening quote followed by a year, so it
/// never matches. Both quote styles count; `notifications_tab_test.dart`
/// and `rf2_response_parsing_test.dart` use `"` where the rest use `'`.
///
/// Note this file scans itself — the fixtures in the `detection` group
/// below are assembled at runtime precisely so the guard is not forced
/// to carve out an exemption for its own source.
final _hardcodedCreatedAt =
    RegExp(r'''["']created_at["']\s*:\s*["']\d{4}-''');

/// Matches a `created_at` key whose value got wrapped onto the next line
/// (dartfmt does this once the entry runs long). Without folding those
/// back together the regex above sees only the key and the literal slips
/// through — silent under-detection, the one failure mode a guard must
/// not have.
///
/// A trailing `// comment` after the colon still counts as dangling: the
/// comment is stripped before this is applied, because otherwise one
/// explanatory comment on the key line silently disables detection for
/// the value beneath it (fxfuse review finding).
final _danglingCreatedAtKey =
    RegExp(r'''["']created_at["']\s*:\s*$''');

/// A `//` comment's text, for stripping before the dangling-key check and
/// for locating the opt-out marker.
final _lineComment = RegExp(r'//.*$');

/// A line that is nothing but a comment — folding skips over these so a
/// comment between a key and its wrapped value cannot hide the value.
final _commentOnlyLine = RegExp(r'^\s*//');

/// Opt-out marker for fixtures in age-independent buckets.
const _marker = 'age-independent';

/// The marker as an actual opt-out: it must appear in a `//` comment, and
/// it must not be negated. `contains('age-independent')` was too loose —
/// prose *about* the marker, and even `// NOT age-independent — live
/// fuse`, silently exempted the line.
final _markerClaim = RegExp(r'//[^\n]*?(?<![a-z])age-independent\b');
final _negatedMarker = RegExp(
  r"(\bnot\b|\bn't\b|\bnever\b)[^\n]{0,20}age-independent",
  caseSensitive: false,
);

const _baselineFile = 'test/fixture_date_guard_baseline.txt';

/// One entry per physical line, with a wrapped `created_at` value folded
/// into the line that carries its key. [line] is the 1-indexed number of
/// the key's line, which is where a human should look.
///
/// A folded continuation line is still emitted on its own, but it is a
/// bare literal with no `created_at` key, so it cannot double-count.
List<({int line, String text})> foldWrappedValues(List<String> lines) {
  final out = <({int line, String text})>[];
  for (var i = 0; i < lines.length; i++) {
    final withoutComment = lines[i].replaceAll(_lineComment, '').trimRight();
    if (!_danglingCreatedAtKey.hasMatch(withoutComment)) {
      out.add((line: i + 1, text: lines[i]));
      continue;
    }
    // Fold in the next line that carries something other than a comment,
    // keeping the key line's own comment so a marker on it still counts.
    var j = i + 1;
    while (j < lines.length && _commentOnlyLine.hasMatch(lines[j])) {
      j++;
    }
    // Rebuild as `key value  // key's own comment` so the value sits
    // directly after the colon (where the literal regex expects it) while
    // any marker written on the key line still counts as an opt-out.
    final keyComment = _lineComment.stringMatch(lines[i]) ?? '';
    out.add((
      line: i + 1,
      text: j < lines.length
          ? '$withoutComment ${lines[j].trim()}  $keyComment'
          : lines[i],
    ));
  }
  return out;
}

/// Whether [text] carries a usable `// age-independent` opt-out.
bool hasAgeIndependentMarker(String text) =>
    _markerClaim.hasMatch(text) && !_negatedMarker.hasMatch(text);

/// Whether [text] is a hardcoded fixture date the guard should report.
bool isUnmarkedHardcodedDate(String text) =>
    _hardcodedCreatedAt.hasMatch(text) && !hasAgeIndependentMarker(text);

/// Parsed `path -> allowed unmarked count` from the baseline file.
Map<String, int> parseBaseline(String contents) {
  final out = <String, int>{};
  for (final raw in const LineSplitter().convert(contents)) {
    final line = raw.trim();
    if (line.isEmpty || line.startsWith('#')) continue;
    final parts = line.split(':');
    if (parts.length < 2) {
      throw FormatException('malformed baseline entry (want path:count:rationale): $raw');
    }
    final count = int.tryParse(parts[1].trim());
    if (count == null) {
      throw FormatException('baseline count is not an integer: $raw');
    }
    out[parts[0].trim()] = count;
  }
  return out;
}

/// Number of unmarked hardcoded `created_at` literals per `.dart` file
/// under [root], keyed by path relative to [root]'s parent (i.e. the
/// same shape the baseline file uses: `test/…`).
Map<String, int> scanUnmarked(Directory root) {
  final counts = <String, int>{};
  final entries = root.listSync(recursive: true).whereType<File>().toList()
    ..sort((a, b) => a.path.compareTo(b.path));
  for (final file in entries) {
    if (!file.path.endsWith('.dart')) continue;
    var unmarked = 0;
    for (final entry in foldWrappedValues(file.readAsLinesSync())) {
      if (isUnmarkedHardcodedDate(entry.text)) unmarked++;
    }
    if (unmarked > 0) {
      counts[file.path.replaceAll(r'\', '/')] = unmarked;
    }
  }
  return counts;
}

/// Every line that would be reported, as `path:line: text`, for the
/// human-readable failure message. [relPath] is cwd-relative, matching
/// the keys [scanUnmarked] returns.
List<String> offendingLines(String relPath) {
  final out = <String>[];
  for (final entry in foldWrappedValues(File(relPath).readAsLinesSync())) {
    if (!isUnmarkedHardcodedDate(entry.text)) continue;
    out.add('  $relPath:${entry.line}: ${entry.text.trim()}');
  }
  return out;
}

/// The baseline as the guard sees it. An absent file is an empty
/// baseline, not an error.
Map<String, int> loadBaseline(File file) =>
    file.existsSync() ? parseBaseline(file.readAsStringSync()) : <String, int>{};

/// The three ways the scan can disagree with the baseline. Extracted so
/// the ratchet is testable: with the baseline file deleted, `raised` and
/// `stale` are unreachable from the real scan, and an inverted comparison
/// here would otherwise ship green and only surface the next time someone
/// grandfathers a live fuse (fxfuse review finding).
///
/// [offendersFor] supplies the human-readable offending lines for a path;
/// the real guard reads the file, the tests pass a stub.
({List<String> added, List<String> raised, List<String> stale})
    compareToBaseline(
  Map<String, int> actual,
  Map<String, int> baseline, {
  required List<String> Function(String path) offendersFor,
}) {
  final added = <String>[];
  final raised = <String>[];
  for (final entry in actual.entries) {
    final allowed = baseline[entry.key];
    if (allowed == null) {
      added.addAll(offendersFor(entry.key));
    } else if (entry.value > allowed) {
      raised.add(
        '  ${entry.key}: ${entry.value} unmarked, baseline allows $allowed\n'
        '${offendersFor(entry.key).join('\n')}',
      );
    }
  }

  final stale = <String>[];
  for (final entry in baseline.entries) {
    final now = actual[entry.key] ?? 0;
    if (now < entry.value) {
      stale.add(
          '  ${entry.key}: now $now unmarked, baseline still says ${entry.value}');
    }
  }
  return (added: added, raised: raised, stale: stale);
}

void main() {
  test('no new hardcoded created_at fixture dates under app/test/', () {
    final root = Directory('test');
    expect(
      root.existsSync(),
      isTrue,
      reason: 'guard expects cwd == app/ (as `flutter test` and '
          "ci.yml's flutter-test job both provide)",
    );

    // The baseline is optional by design: fxfuse drained it to zero and
    // deleted it, and an absent file is the healthy steady state — every
    // literal under `test/` is now either now-relative or explicitly
    // marked `// age-independent`. Re-adding the file to grandfather a
    // new fuse needs reviewer sign-off (and a rationale that says more
    // than "pre-existing").
    final baseline = loadBaseline(File(_baselineFile));
    final actual = scanUnmarked(root);
    final (:added, :raised, :stale) =
        compareToBaseline(actual, baseline, offendersFor: offendingLines);

    expect(
      added,
      isEmpty,
      reason: 'Hardcoded fixture dates in files the guard protects. These '
          'pass today and fail once the wall clock drifts past the 30-day '
          'cutoff in imports_tab.dart:168 — which reds flutter-test and '
          'skips every deploy job.\n${added.join('\n')}\n\n'
          'Fix: mint the timestamp relative to DateTime.now() (see '
          '_at() in test/features/activity/imports_tab_test.dart), or '
          'append `// $_marker` if the fixture feeds Needs Review / Failed '
          '(shown regardless of age).',
    );

    expect(
      raised,
      isEmpty,
      reason: 'Baselined files grew new hardcoded fixture dates. Fix them '
          'rather than raising the count; raising it needs reviewer '
          'sign-off on the PR.\n${raised.join('\n')}',
    );

    expect(
      stale,
      isEmpty,
      reason: 'Baseline counts are stale — the fuse shrank but '
          '$_baselineFile was not ratcheted down. Lower these counts (or '
          'delete the entry at 0) so the baseline can only shrink.\n'
          '${stale.join('\n')}',
    );
  });

  // Demonstrates the guard actually fires. Without this, a regex typo
  // would make the guard above vacuously green forever — the exact
  // failure mode a guard is supposed to prevent.
  group('detection', () {
    late Directory sandbox;

    setUp(() => sandbox = Directory.systemTemp.createTempSync('fixture-date-guard'));
    tearDown(() => sandbox.deleteSync(recursive: true));

    File write(String name, String body) =>
        File('${sandbox.path}/$name')..writeAsStringSync(body);

    // Assembled at runtime so this source file carries no literal the
    // guard would flag when it scans itself: `year` is interpolated, so
    // no four digits ever sit next to a dash inside a quoted value here.
    const sq = "'";
    const dq = '"';
    const year = 2026;
    String hardcoded({String q = sq, String time = '10:35:00Z'}) =>
        '${q}created_at$q: $q$year-04-18T$time$q';

    test('flags a reintroduced hardcoded literal', () {
      write('bad_test.dart', 'final fixture = {${hardcoded()}};\n');
      expect(scanUnmarked(sandbox).values.single, 1);
    });

    test('flags one written with double quotes', () {
      write('bad_dq_test.dart', 'final fixture = {${hardcoded(q: dq)}};\n');
      expect(scanUnmarked(sandbox).values.single, 1);
    });

    test('flags one whose value dartfmt wrapped onto the next line', () {
      write('wrapped_test.dart', "final fixture = {\n"
          "  ${sq}created_at$sq:\n"
          "      $sq$year-04-18T10:35:00Z$sq,\n"
          "};\n");
      expect(scanUnmarked(sandbox).values.single, 1);
    });

    test('a wrapped value marked on its continuation line is accepted', () {
      write('wrapped_marked_test.dart', "final fixture = {\n"
          "  ${sq}created_at$sq:\n"
          "      $sq$year-04-18T10:35:00Z$sq,  // $_marker\n"
          "};\n");
      expect(scanUnmarked(sandbox), isEmpty);
    });

    test('accepts a DateTime.now()-relative value', () {
      write('good_test.dart', """
        final fixture = {'created_at': _at(35)};
      """);
      expect(scanUnmarked(sandbox), isEmpty);
    });

    test('accepts a marked age-independent literal', () {
      write('marked_test.dart', 'final f = {${hardcoded()}};  // $_marker\n');
      expect(scanUnmarked(sandbox), isEmpty);
    });

    test('counts every unmarked literal in a file, not just the first', () {
      write(
        'many_test.dart',
        'final a = {${hardcoded(time: '10:00:00Z')}};\n'
            'final b = {${hardcoded(time: '10:10:00Z')}};  // $_marker\n'
            'final c = {${hardcoded(q: dq, time: '10:20:00Z')}};\n',
      );
      expect(scanUnmarked(sandbox).values.single, 2);
    });

    // Review finding: one explanatory comment on the key line stopped the
    // fold, so the wrapped value underneath was never scanned. A comment
    // BETWEEN key and value did the same. Both are the silent
    // under-detection this guard's header calls the one unacceptable
    // failure mode.
    test('flags a wrapped value whose key line carries a comment', () {
      write('wrapped_commented_key_test.dart', "final fixture = {\n"
          "  ${sq}created_at$sq:  // why this date\n"
          "      $sq$year-04-18T10:35:00Z$sq,\n"
          "};\n");
      expect(scanUnmarked(sandbox).values.single, 1);
    });

    test('flags a wrapped value with a comment line between key and value',
        () {
      write('wrapped_comment_between_test.dart', "final fixture = {\n"
          "  ${sq}created_at$sq:\n"
          "      // explanation\n"
          "      $sq$year-04-18T10:35:00Z$sq,\n"
          "};\n");
      expect(scanUnmarked(sandbox).values.single, 1);
    });

    // Review finding: the marker used to be a bare `contains`, so a line
    // DENYING the claim exempted itself, as did prose that merely named
    // the marker while a date sat elsewhere on the line.
    test('a negated marker is not an opt-out', () {
      write('negated_test.dart',
          'final f = {${hardcoded()}};  // NOT $_marker — live fuse\n');
      expect(scanUnmarked(sandbox).values.single, 1);
    });

    test('a marker outside a comment is not an opt-out', () {
      write('prose_marker_test.dart',
          "final reason = 'this fixture is $_marker'; final f = {${hardcoded()}};\n");
      expect(scanUnmarked(sandbox).values.single, 1);
    });

    test('ignores non-dart files', () {
      write('notes.txt', 'final fixture = {${hardcoded()}};\n');
      expect(scanUnmarked(sandbox), isEmpty);
    });
  });

  group('baseline parsing', () {
    test('skips comments and blanks, keeps path -> count', () {
      final parsed = parseBaseline('''
# a comment

test/a_test.dart:3:pre-existing date fuse
test/b_test.dart:1:pre-existing date fuse
''');
      expect(parsed, {'test/a_test.dart': 3, 'test/b_test.dart': 1});
    });

    test('rejects a non-integer count', () {
      expect(
        () => parseBaseline('test/a_test.dart:many:oops\n'),
        throwsFormatException,
      );
    });

    test('rejects a countless entry', () {
      expect(
        () => parseBaseline('test/a_test.dart\n'),
        throwsFormatException,
      );
    });

    // fxfuse drained the baseline to zero and deleted the file. An absent
    // baseline must read as "nothing is grandfathered" — if it threw, the
    // guard would be red for everyone the moment the fuse list hit zero,
    // which is the one outcome that would push someone to re-add it.
    late Directory tmp;
    setUp(() => tmp = Directory.systemTemp.createTempSync('baseline-load'));
    tearDown(() => tmp.deleteSync(recursive: true));

    test('an absent baseline file is an empty baseline', () {
      final missing = File('${tmp.path}/definitely_not_here.txt');
      expect(missing.existsSync(), isFalse);
      expect(loadBaseline(missing), isEmpty);
    });

    test('a present baseline file is still read', () {
      final present = File('${tmp.path}/baseline.txt')
        ..writeAsStringSync('test/a_test.dart:2:some rationale\n');
      expect(loadBaseline(present), {'test/a_test.dart': 2});
    });
  });

  group('baseline ratchet', () {
    List<String> noOffenders(String path) => const [];

    test('an unlisted file with literals is reported as added', () {
      final r = compareToBaseline(
        {'test/new_test.dart': 2},
        const {},
        offendersFor: (p) => ['  $p:1: literal'],
      );
      expect(r.added, ['  test/new_test.dart:1: literal']);
      expect(r.raised, isEmpty);
      expect(r.stale, isEmpty);
    });

    test('a listed file that grew is reported as raised, not added', () {
      final r = compareToBaseline(
        {'test/a_test.dart': 3},
        const {'test/a_test.dart': 2},
        offendersFor: noOffenders,
      );
      expect(r.added, isEmpty);
      expect(r.raised.single, contains('3 unmarked, baseline allows 2'));
      expect(r.stale, isEmpty);
    });

    test('a count that matches the baseline exactly is not raised', () {
      final r = compareToBaseline(
        {'test/a_test.dart': 2},
        const {'test/a_test.dart': 2},
        offendersFor: noOffenders,
      );
      expect(r.added, isEmpty);
      expect(r.raised, isEmpty);
      expect(r.stale, isEmpty);
    });

    // The ratchet has to bite in BOTH directions: cleaning a file without
    // lowering its count leaves a stale entry that hides the next fuse.
    test('a file cleaned below its baseline is reported as stale', () {
      final r = compareToBaseline(
        {'test/a_test.dart': 1},
        const {'test/a_test.dart': 2},
        offendersFor: noOffenders,
      );
      expect(r.stale.single, contains('now 1 unmarked, baseline still says 2'));
    });

    test('a file cleaned to zero and dropped from the scan is stale', () {
      final r = compareToBaseline(
        const {},
        const {'test/a_test.dart': 2},
        offendersFor: noOffenders,
      );
      expect(r.stale.single, contains('now 0 unmarked, baseline still says 2'));
    });
  });
}
