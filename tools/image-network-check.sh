#!/usr/bin/env bash
# ffm-11 — CI guard against direct `Image.network(` calls under
# `app/lib/features/**`.
#
# Rationale: every network-loaded image should flow through
# `CachedNetworkImage` so scrolling past the same URL doesn't trigger
# a re-download on every frame. Public-share pages and intentional
# bypasses live in `tools/image-network-allowlist.txt`
# (`file:lineno:rationale`, reviewer sign-off required).
#
# Mirrors `tools/no-silent-catch-check.sh`: bash-3 portable (macOS
# default), same allowlist format, no ripgrep dependency.
#
# To add an allowlist entry:
#   1. Add `<file>:<lineno>:<one-line rationale>` to
#      tools/image-network-allowlist.txt.
#   2. Document in the PR description why this site skips the cache
#      (e.g. one-shot public-share visitor, no cache benefit).
#
# Exit codes:
#   0 — clean
#   1 — direct Image.network(...) site found outside the allowlist
#   2 — tooling error (missing allowlist file)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_LIB="$ROOT/app/lib/features"
ALLOWLIST="$ROOT/tools/image-network-allowlist.txt"

if [ ! -d "$APP_LIB" ]; then
  echo "image-network-check: features dir not found at $APP_LIB" >&2
  exit 2
fi

if [ ! -f "$ALLOWLIST" ]; then
  echo "image-network-check: allowlist $ALLOWLIST not found" >&2
  exit 2
fi

# Materialize the allowlist as a plain `file:lineno` set.
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

while IFS= read -r -d '' file; do
  scanned=$((scanned + 1))

  # Grep for `Image.network(` occurrences. Ignore comment-only lines
  # (// prefix) so code-adjacent references in doc comments don't trip
  # the guard.
  while IFS=: read -r lineno match; do
    [ -z "$lineno" ] && continue
    # Strip leading whitespace, then skip lines that start with `//`.
    trimmed="$(printf '%s' "$match" | sed 's/^[[:space:]]*//')"
    case "$trimmed" in
      '//'*) continue ;;
    esac

    # Allowlisted?
    if grep -Fxq "$file:$lineno" "$ALLOW_SET"; then
      continue
    fi

    violations="${violations}${file}:${lineno}:${match}"$'\n'
  done < <(grep -nF 'Image.network(' "$file" 2>/dev/null || true)
done < <(find "$APP_LIB" -type f -name '*.dart' -print0)

if [ -n "$violations" ]; then
  count=$(printf '%s' "$violations" | grep -c '^' || true)
  echo "image-network-check: $count direct Image.network() call(s) found:" >&2
  printf '%s' "$violations" | sed 's/^/  /' >&2
  echo >&2
  echo "Every network image under app/lib/features/ must use CachedNetworkImage." >&2
  echo "Allowlist intentional bypasses in tools/image-network-allowlist.txt" >&2
  echo "(format: file:lineno:rationale)." >&2
  exit 1
fi

echo "image-network-check: OK (scanned $scanned files)"
exit 0
