import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palateful/features/recipes/add_recipe/models/import_batch.dart';

/// impstat1 — the client's "this import is unattended" threshold duplicates
/// a server constant, and this test is the thing that keeps them in step.
///
/// `ImportBatch.watcherBudget` must equal
/// `MAX_POLL_ATTEMPTS × POLL_INTERVAL_SECONDS` from
/// `watch_parser_batch_task.py`. Past that the watcher stops polling and
/// nothing is looking at the batch any more — which is precisely what the
/// UI claims when it says the import stopped responding.
///
/// **A UI that says "stuck" at the wrong threshold is its own false
/// verdict**: too early and it libels a healthy import, too late and it
/// leaves the user watching a counter climb while nothing is watching back.
/// Reading the server file rather than restating its numbers means a change
/// there fails here, instead of drifting silently the way the two
/// `processed_items` definitions did.
void main() {
  test('the client budget equals the server watcher budget', () {
    final source = _watcherSource();

    final interval = _intConstant(source, 'POLL_INTERVAL_SECONDS');
    final attempts = _intConstant(source, 'MAX_POLL_ATTEMPTS');
    final serverBudget = Duration(seconds: interval * attempts);

    expect(
      ImportBatch.watcherBudget,
      serverBudget,
      reason:
          'watch_parser_batch_task.py polls every ${interval}s × $attempts '
          '= ${serverBudget.inMinutes} min, but the client treats '
          '${ImportBatch.watcherBudget.inMinutes} min as the point where '
          'nothing is watching. Change both or neither.',
    );
  });

  test('the server file still holds both constants', () {
    // If either name disappears the parity test above would pass vacuously
    // on a default — so fail loudly here instead.
    final source = _watcherSource();
    expect(source, contains('POLL_INTERVAL_SECONDS'));
    expect(source, contains('MAX_POLL_ATTEMPTS'));
  });
}

String _watcherSource() {
  final file = File(
    '../libraries/utils/utils/tasks/import_tasks/watch_parser_batch_task.py',
  );
  expect(
    file.existsSync(),
    isTrue,
    reason: 'watcher task moved — update this test to follow it, do not '
        'delete it: the client threshold would then be unpinned',
  );
  return file.readAsStringSync();
}

int _intConstant(String source, String name) {
  final match =
      RegExp('^$name\\s*=\\s*(\\d+)', multiLine: true).firstMatch(source);
  expect(match, isNotNull, reason: '$name not found in the watcher task');
  return int.parse(match!.group(1)!);
}
