#!/usr/bin/env bash
# pos-6a — CI guard against paywall language in user-facing copy.
#
# Rationale: Palateful is committed to "free forever" — no premium tier,
# no paywall, no in-app purchases. This guard catches accidental
# regressions when a future story (human-or-agent-authored) introduces
# paywall-shaped vocabulary in a user-visible surface.
#
# We scan user-facing surfaces only. The forbidden-strings list is
# deliberately narrow: false positives in technical contexts (e.g. a
# Dart `subscription` to a Stream, or `upgrade` referring to a Flutter
# SDK upgrade in a comment) would force the allowlist to bloat past
# usefulness, so we limit the regex to words that almost-always mean
# paywall in copy.
#
# Patterns:
#   - \b(premium|paywall)\b   — case-insensitive. Almost never used
#     outside paywall context in copy or markup.
#   - \bPro\b                 — case-sensitive, standalone. Catches
#     "Pro plan", "Recime Pro", "Pro Tier"; ignores Profile, Provider,
#     Process, etc.
#   - v1[ \-_]+purchases      — the "v1 — Palateful is free, no in-app
#     purchases" hedge phrasing the epic rejected.
#
# Notes intentionally NOT in the regex:
#   - subscription / upgrade / unlock — collide with technical Dart code
#     (Stream subscription, SDK upgrade, file unlock) too often. If a
#     future regression slips them into copy, the broader phrasing will
#     also pull in `premium` or `paywall` (because they cluster together
#     in marketing copy) and the guard will catch the broader intent.
#
# Scanned surfaces (USER-FACING ONLY):
#   - app/lib/**/*.dart       — Flutter source.
#   - app/web/                — current Flutter web shell + privacy.
#   - app/web-landing/        — pos-3 static landing.
#   - ANDROID.md, README.md   — operator-facing docs that double as
#                               positioning surfaces.
#
# Deliberately NOT scanned:
#   - _bmad-output/**         — PRDs, investigations, UX specs, and
#     every other planning artifact freely discuss competitor pricing,
#     paywall analysis, "Pro" tier comparisons, etc. — that's the work,
#     not a regression. Allowlisting 50+ legitimate planning mentions
#     would bury actual regressions. The guard's purpose is catching
#     USER-FACING regressions (because user-facing copy is what the
#     "free forever" commitment is *about*), and planning docs don't
#     ship to users. If a future positioning epic touches user-facing
#     copy with paywall language, the user-facing scan paths above will
#     catch it.
#   - tools/copy-grep-guard.sh, tools/copy-grep-allowlist.txt — the
#     guard and its allowlist necessarily contain forbidden tokens.
#
# Allowlist: tools/copy-grep-allowlist.txt (file:lineno:rationale).
# Reviewer sign-off required for new entries (per the same convention
# as tools/silent-catch-allowlist.txt).
#
# Portable: bash 3.x compatible (macOS default), no ripgrep, no
# associative arrays.
#
# Exit codes:
#   0 — clean
#   1 — at least one violation outside the allowlist
#   2 — tooling error (missing allowlist file)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALLOWLIST="$ROOT/tools/copy-grep-allowlist.txt"

if [ ! -f "$ALLOWLIST" ]; then
  echo "copy-grep-guard: allowlist $ALLOWLIST not found" >&2
  exit 2
fi

# Materialize the allowlist as `file:lineno` per line. Same convention
# as tools/no-silent-catch-check.sh: paths are relative to repo root,
# normalized to absolute against $ROOT for the grep -Fxq match below.
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

# Files we never scan (the guard + the allowlist).
SKIP_REL_PATHS="
tools/copy-grep-guard.sh
tools/copy-grep-allowlist.txt
"

is_skipped() {
  local rel="$1"
  for skip in $SKIP_REL_PATHS; do
    if [ "$rel" = "$skip" ]; then return 0; fi
  done
  return 1
}

scan_file() {
  local file="$1"
  local rel="${file#$ROOT/}"
  if is_skipped "$rel"; then return 0; fi

  # Pattern 1: case-insensitive premium|paywall.
  while IFS=: read -r lineno _match; do
    [ -z "$lineno" ] && continue
    if grep -Fxq "$file:$lineno" "$ALLOW_SET"; then continue; fi
    violations="${violations}${file}:${lineno}: premium|paywall"$'\n'
  done < <(grep -niE '\b(premium|paywall)\b' "$file" 2>/dev/null || true)

  # Pattern 2: case-sensitive standalone Pro.
  while IFS=: read -r lineno _match; do
    [ -z "$lineno" ] && continue
    if grep -Fxq "$file:$lineno" "$ALLOW_SET"; then continue; fi
    violations="${violations}${file}:${lineno}: \\bPro\\b"$'\n'
  done < <(grep -nE '\bPro\b' "$file" 2>/dev/null || true)

  # Pattern 3: "v1 — purchases" / "v1-purchases" hedge phrasing.
  while IFS=: read -r lineno _match; do
    [ -z "$lineno" ] && continue
    if grep -Fxq "$file:$lineno" "$ALLOW_SET"; then continue; fi
    violations="${violations}${file}:${lineno}: v1.*purchases"$'\n'
  done < <(grep -niE 'v1[ _-]+(.*)?purchases' "$file" 2>/dev/null || true)
}

violations=""
scanned=0

# 1. Dart sources under app/lib/.
while IFS= read -r -d '' file; do
  scanned=$((scanned + 1))
  scan_file "$file"
done < <(find "$ROOT/app/lib" -type f -name '*.dart' -print0 2>/dev/null)

# 2. Web sources.
for dir in "$ROOT/app/web" "$ROOT/app/web-landing"; do
  if [ ! -d "$dir" ]; then continue; fi
  while IFS= read -r -d '' file; do
    scanned=$((scanned + 1))
    scan_file "$file"
  done < <(find "$dir" -type f \( -name '*.html' -o -name '*.css' -o -name '*.js' \) -print0 2>/dev/null)
done

# 3. Top-level operator docs.
for doc in "$ROOT/ANDROID.md" "$ROOT/README.md"; do
  if [ -f "$doc" ]; then
    scanned=$((scanned + 1))
    scan_file "$doc"
  fi
done

if [ -n "$violations" ]; then
  count=$(printf '%s' "$violations" | grep -c '^' || true)
  echo "copy-grep-guard: $count paywall-language violation(s) found:" >&2
  printf '%s' "$violations" | sed 's/^/  /' >&2
  echo >&2
  echo "Each match must either:" >&2
  echo "  - Be removed (Palateful is free forever; no premium tier ever), OR" >&2
  echo "  - Appear in tools/copy-grep-allowlist.txt with reviewer sign-off." >&2
  exit 1
fi

echo "copy-grep-guard: OK (scanned $scanned file(s))"
exit 0
