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
# USAGE
#   tool/time_travel_check.sh                 # default +400 days
#   tool/time_travel_check.sh --days 120      # +120 days
#   tool/time_travel_check.sh --days 800 test/features/activity
#
# Exit code is `flutter test`'s own: 0 green, non-zero red.
set -euo pipefail

DAYS=400
TEST_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="$2"; shift 2 ;;
    --days=*) DAYS="${1#*=}"; shift ;;
    -h|--help) sed -n '1,45p' "$0"; exit 0 ;;
    *) TEST_ARGS+=("$1"); shift ;;
  esac
done

if [[ ! -d test ]]; then
  echo "error: run from app/ (no ./test directory here)" >&2
  exit 2
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/fxfuse-timetravel.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

echo "==> staging a copy of app/ in $WORK"
# Only what `flutter test` needs: Dart sources, assets, pubspec.
# `ios/` and `android/` are needed too: a few tests read Info.plist /
# AndroidManifest.xml straight off disk and fail as "missing file"
# otherwise — a harness artifact that looks exactly like a fuse.
for entry in lib test ios android pubspec.yaml pubspec.lock analysis_options.yaml assets l10n.yaml; do
  if [[ -e "$entry" ]]; then cp -R "$entry" "$WORK/"; fi
done

echo "==> shifting every YYYY-MM-DD under test/ back by $DAYS days"
python3 - "$WORK/test" "$DAYS" <<'PY'
import datetime, pathlib, re, sys

root, days = pathlib.Path(sys.argv[1]), int(sys.argv[2])
date_re = re.compile(r'(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)')
# Lines whose assertion is about the absolute date, not its age.
SKIP = '// no-time-travel'
shifted = files = skipped = 0

def back(m):
    global shifted
    try:
        d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return m.group(0)  # not a real date (e.g. a 0000-00-00 sentinel)
    shifted += 1
    return (d - datetime.timedelta(days=days)).isoformat()

for path in sorted(root.rglob('*.dart')):
    src = path.read_text()
    lines = src.splitlines(keepends=True)
    out_lines = []
    for line in lines:
        if SKIP in line:
            skipped += 1
            out_lines.append(line)
        else:
            out_lines.append(date_re.sub(back, line))
    out = ''.join(out_lines)
    if out != src:
        path.write_text(out)
        files += 1

print(f"    {shifted} date literals rewritten across {files} files "
      f"({skipped} lines held back by {SKIP})")
if shifted == 0:
    print("    (nothing to shift — every fixture is already now-relative)")
PY

cd "$WORK"
echo "==> flutter pub get"
flutter pub get >/dev/null
echo "==> flutter test ${TEST_ARGS[*]:-(all)}"
flutter test ${TEST_ARGS[@]+"${TEST_ARGS[@]}"}
