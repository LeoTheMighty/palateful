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
//      count — reserved for the 29 files that were already on the fuse
//      when this landed. Raising a count needs reviewer sign-off.
//
// The counts ratchet in both directions: cleaning a file up without
// lowering its count fails too, so the baseline can only shrink.

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Matches a `created_at` map entry whose value is a hardcoded date
/// literal — a quoted value opening with four digits and a dash.
/// Deliberately narrow: a computed value (`_recent(...)`,
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
final _danglingCreatedAtKey =
    RegExp(r'''["']created_at["']\s*:\s*$''');

/// Opt-out marker for fixtures in age-independent buckets.
const _marker = 'age-independent';

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
    final text = i + 1 < lines.length &&
            _danglingCreatedAtKey.hasMatch(lines[i].trimRight())
        ? '${lines[i].trimRight()} ${lines[i + 1].trim()}'
        : lines[i];
    out.add((line: i + 1, text: text));
  }
  return out;
}

/// Whether [text] is a hardcoded fixture date the guard should report.
bool isUnmarkedHardcodedDate(String text) =>
    _hardcodedCreatedAt.hasMatch(text) && !text.contains(_marker);

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

void main() {
  test('no new hardcoded created_at fixture dates under app/test/', () {
    final root = Directory('test');
    expect(
      root.existsSync(),
      isTrue,
      reason: 'guard expects cwd == app/ (as `flutter test` and '
          "ci.yml's flutter-test job both provide)",
    );

    final baseline = parseBaseline(File(_baselineFile).readAsStringSync());
    final actual = scanUnmarked(root);

    final added = <String>[];
    final raised = <String>[];
    for (final entry in actual.entries) {
      final allowed = baseline[entry.key];
      if (allowed == null) {
        added.addAll(offendingLines(entry.key));
      } else if (entry.value > allowed) {
        raised.add(
          '  ${entry.key}: ${entry.value} unmarked, baseline allows $allowed\n'
          '${offendingLines(entry.key).join('\n')}',
        );
      }
    }

    final stale = <String>[];
    for (final entry in baseline.entries) {
      final now = actual[entry.key] ?? 0;
      if (now < entry.value) {
        stale.add('  ${entry.key}: now $now unmarked, baseline still says ${entry.value}');
      }
    }

    expect(
      added,
      isEmpty,
      reason: 'Hardcoded fixture dates in files the guard protects. These '
          'pass today and fail once the wall clock drifts past the 30-day '
          'cutoff in imports_tab.dart:168 — which reds flutter-test and '
          'skips every deploy job.\n${added.join('\n')}\n\n'
          'Fix: mint the timestamp relative to DateTime.now() (see '
          '_recent() in test/features/activity/imports_tab_test.dart), or '
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
        final fixture = {'created_at': _recent(const Duration(hours: 1))};
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
  });
}
