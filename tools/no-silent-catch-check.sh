#!/usr/bin/env bash
# rp-5 — CI guard against silent catch blocks.
#
# Two sections:
#   1. feature services (`app/lib/features/**/services/*.dart`) — the
#      original rp-5 allowlist guard, unchanged.
#   2. `app/lib/core/**` (G12, authrep1) — a shrink-only ratchet against
#      tools/silent-catch-core-baseline.txt. Core is where the auth path
#      lives, so the guard could not see the file that swallowed most.
#
# Rationale: every catch-block in a `*Service.dart` file under
# `app/lib/features/**/services/*.dart` must either
#   - rethrow / throw — surface the failure to the UI, OR
#   - call `showMutationFailureSnackbar(` — centralize the user-facing
#     copy (epic Design Principle #6), OR
#   - call `emitMutation(` — we're mid-lowering a transport frame,
#     failure is informational, OR
#   - call `ErrorReporter.report(` / `ErrorReporter.reportPreAuth(` —
#     logged to Crashlytics (and, for report, the server mirror), OR
#   - appear in `tools/silent-catch-allowlist.txt` (file:lineno:rationale).
#
# Shell-script v1 (vs. custom_lint): <2h to set up, easy to debug on CI
# failures, runs in <1s across ~50 service files. Revisit if the
# allowlist grows past ~20 entries.
#
# Portable: uses plain POSIX-ish shell; no ripgrep, no bash-4 associative
# arrays (macOS default bash is 3.x).
#
# Exit codes:
#   0 — clean
#   1 — offending catch-block found, or a core file off its baseline
#       (full list printed to stderr)
#   2 — tooling error (missing allowlist / baseline / scanner)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_LIB="$ROOT/app/lib/features"
ALLOWLIST="$ROOT/tools/silent-catch-allowlist.txt"

if [ ! -f "$ALLOWLIST" ]; then
  echo "no-silent-catch-check: allowlist $ALLOWLIST not found" >&2
  exit 2
fi

# Token pattern: the union of acceptable recovery paths.
SAFE_TOKENS='(rethrow|[^a-zA-Z_]throw |showMutationFailureSnackbar\(|emitMutation\(|ErrorReporter\.report\(|ErrorReporter\.reportPreAuth\()'

# Materialize the allowlist as a plain `file:lineno` set, one per line.
# We compare full paths in the `is-allowed` check below.
ALLOW_SET="$(mktemp)"
trap 'rm -f "$ALLOW_SET"' EXIT

while IFS=: read -r alist_file alist_line _rest; do
  case "$alist_file" in
    ''|'#'*) continue ;;
  esac
  case "$alist_file" in
    /*) printf '%s:%s\n' "$alist_file" "$alist_line" >> "$ALLOW_SET" ;;
     *) printf '%s:%s\n' "$ROOT/$alist_file" "$alist_line" >> "$ALLOW_SET" ;;
  esac
done < "$ALLOWLIST"

violations=""
scanned=0

# Iterate service files. `find … -print0 | while read -d ''` is
# portable across macOS and GNU find.
while IFS= read -r -d '' file; do
  scanned=$((scanned + 1))

  # Find every catch-block header. Bash 3 doesn't support associative
  # arrays, so we iterate line-by-line.
  while IFS=: read -r lineno _match; do
    [ -z "$lineno" ] && continue

    # Pull 40 lines starting at this catch-block header.
    end=$((lineno + 40))
    window="$(sed -n "${lineno},${end}p" "$file")"
    if echo "$window" | grep -E -q "$SAFE_TOKENS"; then
      continue
    fi

    # Allowlisted?
    if grep -Fxq "$file:$lineno" "$ALLOW_SET"; then
      continue
    fi

    violations="${violations}${file}:${lineno}"$'\n'
  done < <(grep -nE '^[[:space:]]*\}[[:space:]]*(on[[:space:]]+[A-Z][A-Za-z0-9_]*[[:space:]]+)?catch[[:space:]]*\(' "$file" 2>/dev/null || true)
done < <(find "$APP_LIB" -type f -name '*.dart' -path '*/services/*' -print0)

# ---------------------------------------------------------------------
# Section 2 — app/lib/core/** + auth screens + main.dart ratchet (G12).
#
# Uses tools/silent_catch_scan.py, which matches the catch block's own
# braces instead of taking a fixed line window. The window in section 1
# accepts a safe token from a *neighbouring* function: measured on
# app/lib/features/shopping_cart/services/shopping_cart_service.dart:358,
# a pure debugPrint swallow that passes on an ErrorReporter.report( 30
# lines below it, inside _handleError. Section 1 keeps the window for now
# (tightening it turns existing passes into failures, which is its own
# item — see TEST.md); core starts strict.
# ---------------------------------------------------------------------
# Overridable so the self-test can drive the guard against a fixture
# baseline instead of copying over the tracked file (which a Ctrl-C or a CI
# timeout mid-run would leave perturbed).
CORE_BASELINE="${SILENT_CATCH_CORE_BASELINE:-$ROOT/tools/silent-catch-core-baseline.txt}"
SCANNER="$ROOT/tools/silent_catch_scan.py"

if [ ! -f "$CORE_BASELINE" ]; then
  echo "no-silent-catch-check: core baseline $CORE_BASELINE not found" >&2
  exit 2
fi
if [ ! -f "$SCANNER" ]; then
  echo "no-silent-catch-check: scanner $SCANNER not found" >&2
  exit 2
fi

CORE_ACTUAL="$(mktemp)"
trap 'rm -f "$ALLOW_SET" "$CORE_ACTUAL"' EXIT

# --min-files: a scan that silently sees nothing passes exactly as loudly
# as one that sees everything. app/lib/core holds 53 .dart files today; 40
# is a floor that catches a wrong root or a moved tree without tripping on
# ordinary deletions.
# The surface: all of app/lib/core, the auth feature screens (login_screen
# holds three of the auth path's catches and sits in no service directory),
# and main.dart, whose cold-start block logs the user out on a failed /me —
# an entrypoint file that belongs to no scanned directory at all.
if ! python3 "$SCANNER" --root "$ROOT" \
     --dir app/lib/core \
     --dir app/lib/features/auth \
     --file app/lib/main.dart \
     --count-by-file --min-files 40 > "$CORE_ACTUAL"; then
  echo "no-silent-catch-check: core scanner failed" >&2
  exit 2
fi

# Baseline lookup, colon-safe: match the row whose path (everything before
# the final colon) equals the file we are asking about.
baseline_count_for() {
  awk -v f="$1" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      idx = match($0, /:[0-9]+[[:space:]]*$/)
      if (idx == 0) next
      path = substr($0, 1, idx - 1)
      # `read` strips leading whitespace from the row it looks up, so an
      # indented baseline row would never match and read as "baseline 0".
      gsub(/^[[:space:]]+/, "", path)
      count = substr($0, idx + 1)
      gsub(/[[:space:]]/, "", count)
      # `exit` after the first hit: without it a duplicated row printed two
      # numbers, and `[ "$n" -gt "2\n2" ]` errors out inside an `if`, which
      # `set -e` does not catch — the file was silently exempted. Duplicates
      # are rejected up front too; this makes the lookup safe regardless.
      # (awk runs END even on `exit`, hence the found flag.)
      if (path == f) { print count; found = 1; exit }
    }
    END { if (!found) print 0 }
  ' "$CORE_BASELINE"
}

# Format validation, whole-file, BEFORE any comparison. Every non-comment
# row must be exactly `path:count`. Without this, a row someone hand-adds
# with a trailing rationale — `x.dart:3:kept for now, see ci.yml:748` —
# parses under last-colon anchoring as count `748` and silently keys to a
# file that does not exist. Making the format unextendable-by-accident is
# stronger than making each mis-split loud at the point of use.
# (Credit: palateful-4f, from the same bug in tools/stale-pointer-check.py.)
# A row is valid only as `path:count` with NO colon in the path — the
# strictest form, and the one that cannot be mis-split. Note a `case` glob
# like `*:[0-9][0-9][0-9]` does NOT work here: it happily matches the very
# row this rejects (`x.dart:3:see ci.yml:748` ends in `:748`).
malformed="$(grep -vE '^[[:space:]]*(#|$)' "$CORE_BASELINE" \
             | grep -vE '^[^:]+:[0-9]+$' || true)"

# Duplicate paths are the other way this file can fail OPEN: two rows for
# one path made the awk lookup print two numbers, `[ "$n" -gt "$allowed" ]`
# die with "integer expression expected" — which inside an `if` is exempt
# from `set -e` — and the file was silently exempted with the guard still
# exiting 0. A bad merge on this file is the obvious way in.
dupes="$(grep -vE '^[[:space:]]*(#|$)' "$CORE_BASELINE" \
         | sed 's/:[0-9]*$//' | sort | uniq -d || true)"
if [ -n "$dupes" ]; then
  echo "no-silent-catch-check: duplicate path(s) in $CORE_BASELINE:" >&2
  printf '%s\n' "$dupes" | sed 's/^/  /' >&2
  echo "One row per file. Two rows silently disable the ratchet for it." >&2
  exit 2
fi

if [ -n "$malformed" ]; then
  echo "no-silent-catch-check: malformed row(s) in $CORE_BASELINE:" >&2
  printf '%s\n' "$malformed" | sed 's/^/  /' >&2
  echo "Every row must be exactly 'path:count' — no rationale field," >&2
  echo "and no colon in the path." >&2
  exit 2
fi

core_problems=""

# Over / under baseline, per file that currently has offenders.
#
# Parsing note: split on the LAST colon, never `IFS=:`. Paths in this repo
# can contain colons (spec filenames carry `...2026-09-22T18:00-...`), and a
# first-colon split turns the path into a prefix and the count into garbage.
# The `file:lineno` allowlist above has the same latent bug; it survives only
# because its paths happen to be colon-free. Fixed here, not there, to keep
# this change to core (see TEST.md).
while read -r core_row || [ -n "$core_row" ]; do
  [ -z "$core_row" ] && continue
  core_count="${core_row##*:}"
  core_file="${core_row%:*}"
  case "$core_count" in
    ''|*[!0-9]*)
      echo "no-silent-catch-check: malformed scanner row: $core_row" >&2
      exit 2 ;;
  esac
  allowed="$(baseline_count_for "$core_file")"
  if [ "$core_count" -gt "$allowed" ]; then
    core_problems="${core_problems}  ${core_file}: ${core_count} silent catch(es), baseline ${allowed} — report it or surface it"$'\n'
  elif [ "$core_count" -lt "$allowed" ]; then
    core_problems="${core_problems}  ${core_file}: ${core_count} silent catch(es), baseline ${allowed} — lower the baseline to ${core_count} in this commit"$'\n'
  fi
done < "$CORE_ACTUAL"

# Baseline rows whose file is now clean, gone, or renamed.
# `|| [ -n … ]`: a hand-edited baseline saved without a trailing newline
# otherwise loses its last row from this check while the loop above still
# enforces it — half-enforced is worse than either extreme.
while read -r base_row || [ -n "$base_row" ]; do
  case "$base_row" in ''|'#'*) continue ;; esac
  base_count="${base_row##*:}"
  base_file="${base_row%:*}"
  case "$base_count" in
    ''|*[!0-9]*)
      echo "no-silent-catch-check: malformed baseline row: $base_row" >&2
      exit 2 ;;
  esac
  if [ ! -f "$ROOT/$base_file" ]; then
    core_problems="${core_problems}  ${base_file}: file no longer exists — drop its baseline row"$'\n'
    continue
  fi
  # Anchored both ends: an unanchored match would let
  # `x/foo.dart` be satisfied by a row for `x/foo.dart.bak` or
  # `other/x/foo.dart`.
  if ! grep -q "^$(printf '%s' "$base_file" | sed 's/[][\.*^$/]/\\&/g'):[0-9][0-9]*$" \
       "$CORE_ACTUAL"; then
    core_problems="${core_problems}  ${base_file}: 0 silent catch(es), baseline ${base_count} — drop its baseline row in this commit"$'\n'
  fi
done < "$CORE_BASELINE"

# Both sections report together. Exiting here on core problems meant a PR
# that regressed both got only the core list, fixed it, re-ran, and met a
# second, different failure it could have seen the first time.

failed=0

if [ -n "$violations" ]; then
  failed=1
  count=$(printf '%s' "$violations" | grep -c '^' || true)
  echo "no-silent-catch-check: $count offending catch block(s) found:" >&2
  printf '%s' "$violations" | sed 's/^/  /' >&2
  echo >&2
  echo "Each catch-block in a feature service must rethrow, showMutationFailureSnackbar," >&2
  echo "emitMutation, ErrorReporter.report, or be listed in tools/silent-catch-allowlist.txt" >&2
  echo >&2
fi

if [ -n "$core_problems" ]; then
  failed=1
  echo "no-silent-catch-check: app/lib/core is off its baseline:" >&2
  printf '%s' "$core_problems" >&2
  echo >&2
  echo "tools/silent-catch-core-baseline.txt is a shrink-only debt register." >&2
  echo "Regenerate the counts with:" >&2
  echo "  python3 tools/silent_catch_scan.py --root . --dir app/lib/core \\" >&2
  echo "    --dir app/lib/features/auth --file app/lib/main.dart --count-by-file" >&2
  echo >&2
fi

if [ "$failed" -ne 0 ]; then
  exit 1
fi

core_files=$(grep -c '^' "$CORE_ACTUAL" || true)
echo "no-silent-catch-check: OK (scanned $scanned feature service files;" \
     "app/lib/core on baseline across $core_files file(s) with known debt)"
exit 0
