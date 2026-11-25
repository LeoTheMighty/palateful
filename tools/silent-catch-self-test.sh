#!/usr/bin/env bash
# authrep1 (G12) — self-test for the silent-catch scanner + core ratchet.
#
# "Tests for the test." A guard that silently matches nothing passes exactly
# as loudly as one that matches everything, so the scanner is exercised
# against planted fixtures with known answers:
#
#   silent.dart    — 2 swallowing catches, 1 reporting, 1 rethrowing.
#   neighbour.dart — a swallowing catch whose *next function* reports. The
#                    40-line window in the feature-services section accepts
#                    this; brace-matching must not.
#   strings.dart   — braces inside strings, interpolation and comments.
#   reported.dart  — every catch reports; must be clean.
#   nested.dart    — an outer catch that swallows while a NESTED catch
#                    reports. The nested report handles the nested
#                    exception, not the outer one, so the outer block is
#                    still silent. `api_client.dart`'s 401 interceptor and
#                    `AuthService.logout()` are both this shape.
#
# Plus the ratchet's three failure directions, and the colon-in-path parse
# (spec filenames carry `2026-09-22T18:00`, and a first-colon split turns
# the path into a prefix — the bug PR #47 hit in tools/stale-pointer-check.py).
#
# Exit codes:
#   0 — every expectation held.
#   1 — an expectation failed.
#   2 — tooling error.

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCANNER="$ROOT/tools/silent_catch_scan.py"

if [ ! -f "$SCANNER" ]; then
  echo "silent-catch-self-test: scanner $SCANNER missing." >&2
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/app/lib/core/services"

failures=0

expect_eq() {
  # expect_eq <label> <expected> <actual>
  if [ "$2" = "$3" ]; then
    echo "  ok: $1"
  else
    echo "  FAIL: $1" >&2
    echo "    expected: $2" >&2
    echo "    actual:   $3" >&2
    failures=$((failures + 1))
  fi
}

cat > "$TMP/app/lib/core/services/silent.dart" <<'DART'
class Silent {
  void a() {
    try {
      risky();
    } catch (e) {
      debugPrint('swallowed: $e');
    }
  }

  void b() {
    try {
      risky();
    } catch (e, st) {
      ErrorReporter.report(e, st, area: 'x');
    }
  }

  void c() {
    try {
      risky();
    } on StateError catch (e) {
      debugPrint('also swallowed: $e');
    }
  }

  void d() {
    try {
      risky();
    } catch (e) {
      rethrow;
    }
  }
}
DART

cat > "$TMP/app/lib/core/services/neighbour.dart" <<'DART'
class Neighbour {
  void dispatch() {
    try {
      handle();
    } catch (e) {
      debugPrint('dropped frame: $e');
    }
  }

  void handleError(Object e, StackTrace st) {
    ErrorReporter.report(e, st, area: 'ws');
  }
}
DART

cat > "$TMP/app/lib/core/services/strings.dart" <<'DART'
class Strings {
  void a() {
    try {
      risky();
    } catch (e) {
      // A brace in a comment: }
      final s = 'literal } brace';
      final t = "interpolated ${map['k']} value";
      debugPrint('$s$t');
    }
  }

  void b() {
    try {
      risky();
    } catch (e, st) {
      final msg = 'failed } with ${e.runtimeType}';
      ErrorReporter.reportPreAuth(e, st, area: 'auth', operation: msg);
    }
  }
}
DART

cat > "$TMP/app/lib/core/services/nested.dart" <<'DART'
class Nested {
  void outerSwallows() {
    try {
      risky();
    } catch (e) {
      debugPrint('outer swallowed: $e');
      try {
        cleanup();
      } catch (e2, st2) {
        ErrorReporter.report(e2, st2, area: 'x');
      }
    }
  }

  void outerReports() {
    try {
      risky();
    } catch (e, st) {
      ErrorReporter.report(e, st, area: 'x');
      try {
        cleanup();
      } catch (_) {
        debugPrint('nested swallow is its own offender');
      }
    }
  }
}
DART

# Every fixture below is a bug that shipped in a draft of this scanner and
# was caught in review. Each one is here so it cannot come back quietly.
cat > "$TMP/app/lib/core/services/tricky.dart" <<'DART'
class Tricky {
  void interpolationThenBrace() {
    try {
      risky();
    } catch (e) {
      debugPrint('payload {"err": ${e}} done');
      rethrow;
    }
  }

  void interpolationThenOpenBrace() {
    try {
      risky();
    } catch (e) {
      debugPrint('brace after interp: ${e} {');
    }
  }

  void rescuedByComment() {
    try {
      risky();
    } catch (e) {
      // We could rethrow here, but we deliberately don't.
      debugPrint('swallowed: $e');
    }
  }

  void rescuedByString() {
    try {
      risky();
    } catch (e) {
      debugPrint('see ErrorReporter.report( for the real one');
    }
  }

  void rawStringBackslash() {
    try {
      risky();
    } catch (e) {
      debugPrint(r'windows path C:\');
    }
  }

  void commentedOutCatch() {
    /*
    } catch (e) {
      nothing();
    }
    */
    ok();
  }

  void inlineOneLiner() {
    try { risky(); } catch (e) { debugPrint('silent one-liner'); }
  }

  void catchOnItsOwnLine() {
    try {
      risky();
    }
    catch (e) {
      debugPrint('silent, unformatted');
    }
  }

  void onTypeWithoutBinding() {
    try {
      risky();
    } on TimeoutException {
      debugPrint('silent, no binding');
    }
  }

  void prefixedGenericType() {
    try {
      risky();
    } on http.ClientException catch (e) {
      debugPrint('silent prefixed');
    }
  }
}
DART

cat > "$TMP/app/lib/core/services/reported.dart" <<'DART'
class Reported {
  void a() {
    try {
      risky();
    } catch (e, st) {
      ErrorReporter.reportPreAuth(e, st, area: 'auth');
    }
  }
}
DART

echo "scanner:"

actual="$(python3 "$SCANNER" --root "$TMP" --dir app/lib/core --count-by-file)"
expected="app/lib/core/services/neighbour.dart:1
app/lib/core/services/nested.dart:2
app/lib/core/services/silent.dart:2
app/lib/core/services/strings.dart:1
app/lib/core/services/tricky.dart:8"
expect_eq "per-file counts across the fixtures" "$expected" "$actual"

actual="$(python3 "$SCANNER" --root "$TMP" --dir app/lib/core \
          --path-contains silent.dart)"
expected="app/lib/core/services/silent.dart:5
app/lib/core/services/silent.dart:21"
expect_eq "line numbers point at the catch headers" "$expected" "$actual"

actual="$(python3 "$SCANNER" --root "$TMP" --dir app/lib/core \
          --path-contains neighbour.dart)"
expected="app/lib/core/services/neighbour.dart:5"
expect_eq "a report in the NEXT function does not rescue the catch" \
  "$expected" "$actual"

actual="$(python3 "$SCANNER" --root "$TMP" --dir app/lib/core \
          --path-contains reported.dart || true)"
expect_eq "a fully-reporting file is clean" "" "$actual"

actual="$(python3 "$SCANNER" --root "$TMP" --dir app/lib/core \
          --path-contains nested.dart)"
expected="app/lib/core/services/nested.dart:5
app/lib/core/services/nested.dart:22"
expect_eq "a report in a NESTED catch does not rescue the enclosing one" \
  "$expected" "$actual"

actual="$(python3 "$SCANNER" --root "$TMP" \
          --file app/lib/core/services/silent.dart --count-by-file)"
expect_eq "--file scans an individual entrypoint (main.dart's case)" \
  "app/lib/core/services/silent.dart:2" "$actual"

# The seven shapes that a draft of this scanner got wrong. Line numbers are
# the catch headers in tricky.dart above.
actual="$(python3 "$SCANNER" --root "$TMP" --dir app/lib/core \
          --path-contains tricky.dart)"
# 14 brace-after-interpolation (silent) · 22 rescued-by-comment ·
# 31 rescued-by-string · 39 raw-string backslash · 54 inline one-liner ·
# 61 catch on its own line · 69 `on Foo {` with no binding ·
# 77 prefixed+generic type. Absent, and that is the point: the
# rethrow-after-a-JSON-log catch at :7 (a false positive in review) and the
# commented-out catch at :48 (a false positive too).
expected="app/lib/core/services/tricky.dart:14
app/lib/core/services/tricky.dart:22
app/lib/core/services/tricky.dart:31
app/lib/core/services/tricky.dart:39
app/lib/core/services/tricky.dart:54
app/lib/core/services/tricky.dart:61
app/lib/core/services/tricky.dart:69
app/lib/core/services/tricky.dart:77"
expect_eq "string/comment/layout shapes classify correctly" \
  "$expected" "$actual"

set +e
python3 "$SCANNER" --root "$TMP" --dir app/lib/core --min-files 999 \
  > /dev/null 2>&1
rc=$?
set -e
expect_eq "--min-files fails a scan that sees too little" "2" "$rc"

echo "colon-in-path parsing:"

# The parse under test, lifted verbatim from no-silent-catch-check.sh. A
# path with a colon in it must survive: `IFS=:` would yield file=`a/b-18`.
row="app/lib/core/services/spec-2026-09-22T18:00-thing.dart:4"
count="${row##*:}"
file="${row%:*}"
expect_eq "count from a colon-bearing row" "4" "$count"
expect_eq "path from a colon-bearing row" \
  "app/lib/core/services/spec-2026-09-22T18:00-thing.dart" "$file"

echo "ratchet:"

GUARD="$ROOT/tools/no-silent-catch-check.sh"
if [ ! -f "$GUARD" ]; then
  echo "silent-catch-self-test: guard $GUARD missing." >&2
  exit 2
fi

# The ratchet's three directions are exercised against the real repo by
# perturbing a copy of the baseline, so the test can never mutate the
# checked-in file.
BASELINE="$ROOT/tools/silent-catch-core-baseline.txt"
if [ ! -f "$BASELINE" ]; then
  echo "silent-catch-self-test: baseline $BASELINE missing." >&2
  exit 2
fi

run_guard_with_baseline() {
  # run_guard_with_baseline <baseline-file> -> prints exit code
  #
  # Drives the guard against a fixture baseline via the env override. The
  # tracked tools/silent-catch-core-baseline.txt is never written to, so a
  # Ctrl-C or CI timeout mid-run cannot leave it perturbed.
  set +e
  SILENT_CATCH_CORE_BASELINE="$1" bash "$GUARD" > /dev/null 2>&1
  local rc=$?
  set -e
  echo "$rc"
}

cp "$BASELINE" "$TMP/baseline.entry"

first_row="$(grep -v '^#' "$BASELINE" | grep -v '^$' | head -1)"
first_file="${first_row%:*}"
first_count="${first_row##*:}"

# Over baseline: pretend the file is allowed one fewer.
awk -v f="$first_row" -v r="${first_file}:$((first_count - 1))" \
  '{ if ($0 == f) print r; else print }' "$BASELINE" > "$TMP/over.txt"
expect_eq "a new silent catch fails the guard" "1" \
  "$(run_guard_with_baseline "$TMP/over.txt")"

# Under baseline: pretend the file is allowed one more.
awk -v f="$first_row" -v r="${first_file}:$((first_count + 1))" \
  '{ if ($0 == f) print r; else print }' "$BASELINE" > "$TMP/under.txt"
expect_eq "a fix without lowering the baseline fails the guard" "1" \
  "$(run_guard_with_baseline "$TMP/under.txt")"

# Stale row: a path that no longer exists.
{ cat "$BASELINE"; echo "app/lib/core/services/deleted_service.dart:2"; } \
  > "$TMP/stale.txt"
expect_eq "a baseline row for a deleted file fails the guard" "1" \
  "$(run_guard_with_baseline "$TMP/stale.txt")"

# Untouched baseline: the repo as committed must pass.
expect_eq "the committed baseline passes" "0" \
  "$(run_guard_with_baseline "$BASELINE")"

# A row whose rationale itself cites a line number. Under last-colon
# anchoring this parses as count `748` and silently keys to a file that does
# not exist, so the format check has to reject it outright.
# (palateful-4f, from the same bug in tools/stale-pointer-check.py.)
{ cat "$BASELINE"; echo "app/lib/main.dart:4:kept for now, see ci.yml:748"; } \
  > "$TMP/rationale.txt"
expect_eq "a row with a rationale field is rejected as malformed" "2" \
  "$(run_guard_with_baseline "$TMP/rationale.txt")"

# Two rows for one path made the awk lookup print two numbers, which made
# both `[ -gt ]` and `[ -lt ]` die with "integer expression expected" —
# exempt from `set -e` inside an `if` — silently exempting the file while
# the guard still exited 0. The one failure mode that fails OPEN.
{ cat "$BASELINE"; echo "app/lib/main.dart:4"; } > "$TMP/dupe.txt"
expect_eq "a duplicated baseline row is rejected, not silently honoured" "2" \
  "$(run_guard_with_baseline "$TMP/dupe.txt")"

# The tracked baseline must be byte-identical to what it was on entry —
# fixtures go through the env override, never in place.
if cmp -s "$BASELINE" "$TMP/baseline.entry"; then
  echo "  ok: the tracked baseline is untouched by this run"
else
  echo "  FAIL: the self-test modified the tracked baseline" >&2
  failures=$((failures + 1))
fi

if [ "$failures" -ne 0 ]; then
  echo "silent-catch-self-test: $failures expectation(s) failed." >&2
  exit 1
fi

echo "silent-catch-self-test: OK"
exit 0
