#!/usr/bin/env bash
# fxfuse — time-travel check for hardcoded fixture dates.
#
# WHAT THIS PROVES
# ----------------
# Tests rot when a frozen fixture date drifts out of a
# `DateTime.now()`-relative window in lib/ (the 30-day cutoff in
# `imports_tab.dart:168`, the date-picker range in
# `plan_meal_sheet.dart:179`, `profile_screen.dart:417`, or any of the
# relative-time formatters whose output string changes with age). The
# failure lands months after the commit that "caused" it and reads as a
# broken feature, not a moved clock — that is how prod stayed frozen on
# image `c85e350` from 2026-04-26 to 2026-07-27.
#
# The only honest way to tell "drained" from "the bombs just haven't gone
# off yet" is to move the clock and re-run. This script does that by
# shifting the *fixtures* rather than the *clock*: every literal
# `YYYY-MM-DD` under `test/` is rewritten N days earlier, which is
# arithmetically identical to running the suite N days in the future for
# any comparison of the form `DateTime.now() - fixture`.
#
# WHY NOT `faketime`
# ------------------
# libfaketime (0.9.10 and 0.9.12, macOS arm64 and Linux arm64) crashes
# the Dart VM: `OS::GetCurrentTimeMillis` hits `unreachable code` in
# `os_linux.cc:474` / `os_macos.cc:67` during `Dart_CreateIsolateGroup`,
# and preloading it around the whole `flutter test` invocation makes the
# tool SIGTERM the tester shell before any test runs. Faking the clock
# under the Dart VM is not currently a working option on either host, so
# the equivalent fixture-side transform is what we run instead.
#
# KNOWN BLIND SPOT
# ----------------
# Shifting fixtures is equivalent to advancing the clock for
# `now - fixture` arithmetic, but NOT for an assertion on the absolute
# date itself (`expect(list.updatedAt.month, 3)`, or a test expecting the
# literal text "Apr 18, 2026"): those fail here while a real clock
# advance leaves them alone. That is a false positive of the harness, not
# a fuse. Tag such a line with `// no-time-travel` and this script leaves
# it untouched — but read the assertion first, because the tag also
# excludes the line from the only check that would catch a real fuse
# there.
#
# Second false-positive class, found the same way: a test that INJECTS
# its own `now` (`fuzzyExpiry(expiry, now: now)`) can never rot, but
# shifting both sides is still not a no-op — a shift that lands the
# interval across a DST transition changes the delta by an hour and can
# drop an `inDays` boundary by one. `fuzzy_expiry_text_test.dart` is the
# worked example. A multiple-of-7 `--days` preserves weekdays but not DST
# offsets, so this class needs the tag rather than a cleverer default.
#
# WHAT THIS STILL CANNOT SEE
# --------------------------
# Under-detection is the failure mode a check like this must not have, so
# state the gaps rather than let a green run imply completeness. Shifted:
# ISO dates (`'2026-04-18T10:00:00Z'`, which covers `DateTime.parse('…')`)
# and constructor dates (`DateTime(2026, 4, 18)` / `DateTime.utc(…)`). NOT
# shifted, and therefore invisible here:
#
#   * epoch forms — `DateTime.fromMillisecondsSinceEpoch(1776…)`.
#   * a date assembled from parts — `DateTime(y, m, d)` where any of the
#     three is a variable or an arithmetic expression.
#   * a date that reaches the fixture from outside `test/` — a golden file,
#     a seeded database, an asset JSON.
#   * a date only written as a component — `..month = 4`.
#
# Measured at fxfuse (2026-09-22): the epoch form has 3 occurrences, all in
# `test/core/services/shared_state_service_test.dart`, and all three only
# round-trip the value back out through `share_auth_jwt_expires_at` — no
# `now` comparison anywhere in `shared_state_service.dart` — so they are
# invisible here but are not fuses. Re-check that claim rather than
# inheriting it whenever a new fixture style shows up.
# The repo's `fixture_date_guard_test.dart` is narrower still — it
# matches only an inline `'created_at': '<literal>'` — so the two checks
# fail differently on purpose, and `test/test-fxguard2-…md` tracks closing
# the guard's half.
#
# PROVING THE HARNESS STILL BITES
# --------------------------------
# A green run only means something if the same run would go red on a real
# fuse. Negative control, re-runnable in two minutes:
#
#   1. In `test/features/activity/imports_tab_test.dart`, replace
#      `_fixtureBase`'s `DateTime.now()…` with a literal
#      `DateTime.parse('<today>T10:00:00Z')`.
#   2. `flutter test test/features/activity/imports_tab_test.dart` → green
#      (the fixture is zero days old).
#   3. `tool/time_travel_check.sh --days 400 \
#        test/features/activity/imports_tab_test.dart` → 3 failures, as the
#      Auto-Imported and Skipped rows fall out of the 30-day window and the
#      assertions find zero widgets. That is the imptab1 signature.
#   4. Revert step 1.
#
# Run at fxfuse (2026-09-22): steps 2 and 3 behaved exactly as above.
#
# USAGE
#   tool/time_travel_check.sh                 # default +400 days
#   tool/time_travel_check.sh --days 120      # +120 days
#   tool/time_travel_check.sh --days 800 test/features/activity
#
# Exit code is `flutter test`'s own: 0 green, non-zero red.
set -euo pipefail

# 406 = 58 whole weeks. A shift that is a multiple of 7 keeps every
# fixture's weekday, which matters because weekday-consuming surfaces
# exist (`recurrence_field.dart:141` seeds the repeat-days chip from
# `anchorDate.weekday`). The old default of 400 rotated every fixture by
# one day and turned that into a whole class of failures the operator
# would have to triage as false positives. Stay above 365 so the
# year-boundary in the relative-time formatters is still crossed.
DAYS=406
TEST_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      if [[ $# -lt 2 ]]; then
        echo "error: --days needs a value (e.g. --days 406)" >&2
        exit 2
      fi
      DAYS="$2"; shift 2 ;;
    --days=*) DAYS="${1#*=}"; shift ;;
    -h|--help) sed -n '/^# USAGE/,/^set -euo/p' "$0"; exit 0 ;;
    -*)
      echo "error: unknown flag $1 (see --help)" >&2
      exit 2 ;;
    *) TEST_ARGS+=("$1"); shift ;;
  esac
done

# A non-numeric value used to surface as a raw Python traceback, and a
# NEGATIVE one was accepted silently — shifting fixtures into the future,
# where every now-relative surface degenerates ('just now', '—', cutoffs
# trivially satisfied) and the run comes back green having proved the
# opposite of what was asked.
if [[ ! "$DAYS" =~ ^[0-9]+$ ]]; then
  echo "error: --days must be a non-negative whole number of days, got '$DAYS'" >&2
  echo "       (to simulate the clock moving FORWARD, pass a positive value;" >&2
  echo "        this script shifts fixtures backwards to achieve that)" >&2
  exit 2
fi
if (( DAYS == 0 )); then
  echo "error: --days 0 shifts nothing and would report a vacuous pass" >&2
  exit 2
fi

if [[ ! -d test ]]; then
  echo "error: run from app/ (no ./test directory here)" >&2
  exit 2
fi

# A target path that escapes the staged copy runs the REAL, unshifted tree
# and reports success having tested nothing. Absolute paths are what shell
# completion and editor "copy path" produce, so this is the likely slip.
for arg in ${TEST_ARGS[@]+"${TEST_ARGS[@]}"}; do
  case "$arg" in
    /*|../*|*/../*)
      echo "error: target '$arg' points outside the staged copy, so it would" >&2
      echo "       run the real unshifted tree and prove nothing." >&2
      echo "       Pass a path relative to app/, e.g. test/features/activity" >&2
      exit 2 ;;
  esac
done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/fxfuse-timetravel.XXXXXX")"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT INT TERM

echo "==> staging a copy of app/ in $WORK"
# Only what `flutter test` needs: Dart sources, assets, pubspec.
# `ios/` and `android/` are needed too: a few tests read Info.plist /
# AndroidManifest.xml straight off disk and fail as "missing file"
# otherwise — a harness artifact that looks exactly like a fuse.
for entry in lib test ios android pubspec.yaml pubspec.lock analysis_options.yaml assets l10n.yaml; do
  if [[ -e "$entry" ]]; then cp -R "$entry" "$WORK/"; fi
done

echo "==> shifting fixture dates under test/ back by $DAYS days"
python3 - "$WORK/test" "$DAYS" <<'PY'
import datetime, pathlib, re, sys

root, days = pathlib.Path(sys.argv[1]), int(sys.argv[2])

# Two fixture-date forms, both of which reach now-relative lib code:
#   1. an ISO string   — 'created_at': '2026-04-18T10:00:00Z'
#                        (also covers DateTime.parse('2026-04-18…'))
#   2. a constructor   — DateTime(2026, 4, 18) / DateTime.utc(2026, 4)
#                        / DateTime(2026), all with optional time args
# Form 2 is invisible to the repo's grep guard, which scans only form 1,
# so it is exactly the shape a fuse hides in. Both are shifted.
iso_re = re.compile(r'(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)')
# Whitespace-tolerant across newlines so a dartfmt-wrapped constructor is
# not silently skipped.
ctor_re = re.compile(
    r'DateTime(\.utc)?\(\s*(\d{4})\s*(?:,\s*(\d{1,2})\s*(?:,\s*(\d{1,2})\s*)?)?'
    r'(?=[,)])')

# Lines whose assertion is about the absolute date, not its age. The
# marker only counts inside a `//` comment: a bare substring test let
# prose *about* the marker exempt a real fixture on the same line.
skip_re = re.compile(r'//[^\n]*\bno-time-travel\b')

shifted = ctor_shifted = files = held = 0


def shift(y, m, d):
    return datetime.date(y, m, d) - datetime.timedelta(days=days)


def back(m):
    global shifted
    try:
        d = shift(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return m.group(0)  # not a real date (e.g. a 0000-00-00 sentinel)
    shifted += 1
    return d.isoformat()


def back_ctor(m):
    global ctor_shifted
    utc, y, mo, day = m.group(1) or '', m.group(2), m.group(3), m.group(4)
    try:
        # `DateTime(2026)` is Jan 1st and `DateTime(2026, 4)` is April 1st;
        # emit an explicit day so a shifted value cannot silently land on
        # some other month's 1st.
        d = shift(int(y), int(mo) if mo else 1, int(day) if day else 1)
    except ValueError:
        return m.group(0)
    ctor_shifted += 1
    # No trailing separator: whatever followed (`, 12, 30)` for a
    # time-bearing constructor, or just `)`) is left untouched.
    return f'DateTime{utc}({d.year}, {d.month}, {d.day}'


def skipped_line_numbers(text):
    """1-indexed lines carrying the marker, plus the line below a marker
    that sits on a wrapped entry's key line — dartfmt splits long entries,
    and the repo's guard folds them for exactly this reason."""
    out = set()
    for i, line in enumerate(text.splitlines(), start=1):
        if skip_re.search(line):
            out.add(i)
            if line.rstrip().rstrip(',').rstrip().endswith(':'):
                out.add(i + 1)
            # `'created_at':  // no-time-travel` — value is on the next line
            if re.search(r':\s*//[^\n]*\bno-time-travel\b', line):
                out.add(i + 1)
    return out


def make_guard(src, skip_lines):
    """Wrap a substitution so matches on a tagged line are left alone.
    `held` then counts dates actually suppressed, not comment lines — the
    only number an operator can audit exemptions with."""
    starts = [0] + [i + 1 for i, ch in enumerate(src) if ch == '\n']

    def line_of(pos):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    def guard(fn):
        def wrapper(m):
            global held
            if line_of(m.start()) in skip_lines:
                held += 1
                return m.group(0)
            return fn(m)
        return wrapper

    return guard


for path in sorted(root.rglob('*.dart')):
    src = path.read_text()
    # One guard per pass, each built from the exact string that pass
    # scans: `re.sub` reports match offsets into its own input, and the
    # constructor pass can collapse a wrapped `DateTime(\n …)` onto one
    # line, so offsets from the original text would drift and start
    # mapping matches to the wrong line.
    after_iso = iso_re.sub(
        make_guard(src, skipped_line_numbers(src))(back), src)
    out = ctor_re.sub(
        make_guard(after_iso, skipped_line_numbers(after_iso))(back_ctor),
        after_iso)
    if out != src:
        path.write_text(out)
        files += 1

print(f"    {shifted} ISO literals + {ctor_shifted} DateTime(...) constructors "
      f"rewritten across {files} files "
      f"({held} dates held back by no-time-travel)")
if shifted + ctor_shifted == 0:
    # A no-op run that reports success is worse than a failure: it looks
    # exactly like "the fixtures are drained".
    print("    error: nothing was shifted — this run would prove nothing.")
    print("    Either every fixture is already now-relative (check by hand),")
    print("    or the tests moved out of test/ and this tool is now blind.")
    sys.exit(3)
PY

cd "$WORK"
echo "==> flutter pub get"
flutter pub get >/dev/null
echo "==> flutter test ${TEST_ARGS[*]:-(all)}"
flutter test ${TEST_ARGS[@]+"${TEST_ARGS[@]}"}
