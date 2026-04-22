#!/usr/bin/env bash
# rp-5 — CI guard against silent catch blocks in feature services.
#
# Rationale: every catch-block in a `*Service.dart` file under
# `app/lib/features/**/services/*.dart` must either
#   - rethrow / throw — surface the failure to the UI, OR
#   - call `showMutationFailureSnackbar(` — centralize the user-facing
#     copy (epic Design Principle #6), OR
#   - call `emitMutation(` — we're mid-lowering a transport frame,
#     failure is informational, OR
#   - call `ErrorReporter.report(` — logged to Crashlytics / server, OR
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
#   1 — offending catch-block found (full list printed to stderr)
#   2 — tooling error (missing allowlist file)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_LIB="$ROOT/app/lib/features"
ALLOWLIST="$ROOT/tools/silent-catch-allowlist.txt"

if [ ! -f "$ALLOWLIST" ]; then
  echo "no-silent-catch-check: allowlist $ALLOWLIST not found" >&2
  exit 2
fi

# Token pattern: the union of acceptable recovery paths.
SAFE_TOKENS='(rethrow|[^a-zA-Z_]throw |showMutationFailureSnackbar\(|emitMutation\(|ErrorReporter\.report\()'

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

if [ -n "$violations" ]; then
  count=$(printf '%s' "$violations" | grep -c '^' || true)
  echo "no-silent-catch-check: $count offending catch block(s) found:" >&2
  printf '%s' "$violations" | sed 's/^/  /' >&2
  echo >&2
  echo "Each catch-block in a feature service must rethrow, showMutationFailureSnackbar," >&2
  echo "emitMutation, ErrorReporter.report, or be listed in tools/silent-catch-allowlist.txt" >&2
  exit 1
fi

echo "no-silent-catch-check: OK (scanned $scanned service files)"
exit 0
