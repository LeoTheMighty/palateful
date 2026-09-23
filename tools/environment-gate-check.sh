#!/usr/bin/env bash
# envspell1 — CI guard against bare `ENVIRONMENT` comparisons.
#
# Rationale: `ENVIRONMENT` is compared in gates that fail in OPPOSITE
# directions. `utils.api.endpoint` records 4xx audit rows only in production,
# so an unrecognised spelling silently disables a recorder. `dependencies.py`
# skips Auth0 for local environments, so an unrecognised spelling must DENY —
# loosening it moves an authentication bypass toward armed.
#
# Both decisions therefore live in `utils/environment.py`, as two predicates
# with deliberately opposite defaults (`is_production` unknown -> True,
# `is_local_bypass_allowed` unknown -> False). A bare `== "prod"` written
# later re-creates the bug this story fixed, and reads as obviously correct
# in review — which is exactly why it needs a machine to object.
#
# Escape hatch: `tools/environment-gate-allowlist.txt`
# (format: `file:lineno:rationale`, reviewer sign-off required).
#
# WHAT THIS GUARD DOES NOT CATCH — stated plainly, because a guard whose
# limits are unknown gets trusted past them:
#   * an alias: `env = settings.environment` ... `if env == "prod"`.
#   * a match/case on the value, or a dict lookup keyed by it.
#   * `.startswith("prod")`, or a comparison built by f-string.
#   * a normalising call before the compare: `ENVIRONMENT.lower() == "prod"`.
#   * anything outside `libraries/` and `services/` (Dart, shell, Terraform).
# It DOES catch: `==` / `!=` in either operand order, `in` against a tuple,
# list or set literal, and a direct `os.environ["ENVIRONMENT"]` /
# `os.environ.get("ENVIRONMENT")` read — the shape `utils/constants.py`
# itself uses, and so the likeliest way the bug returns.
# It catches the shape that has actually appeared in this repo six times:
# a direct `==` / `!=` / `in (...)` against `ENVIRONMENT` or `.environment`.
# That is a trip-wire for the common case, not a proof of absence.
#
# Portable: POSIX-ish shell, no ripgrep, no bash-4 features (macOS ships 3.x).

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALLOWLIST="$ROOT/tools/environment-gate-allowlist.txt"

# Comparisons against either source of the value: `ENVIRONMENT` (os.environ,
# via utils.constants) and `.environment` (the pydantic Settings field).
PATTERN='(ENVIRONMENT|\.environment)[[:space:]]*(==|!=)|(ENVIRONMENT|\.environment)[[:space:]]+in[[:space:]]*[({[]|(==|!=)[[:space:]]*(ENVIRONMENT|settings\.environment)|environ(\.get\(|\[)[\"'"'"']ENVIRONMENT'

status=0
found=""

# The predicates' own definition is the one place these literals belong.
# Tests are excluded: pinning the predicates requires naming the spellings.
while IFS= read -r hit; do
  [ -n "$hit" ] || continue   # empty grep output still yields one blank line
  file="${hit%%:*}"
  rest="${hit#*:}"
  lineno="${rest%%:*}"

  case "$file" in
    */utils/environment.py) continue ;;
    # Anchored: `*test_*.py` would also exempt real sources such as
    # `admin/send_test_push.py` and everything under `test-helper/`.
    */test/*|*/tests/*|*/test_*.py|*_test.py) continue ;;
  esac

  # Comment lines describe the old gate (e.g. "was `ENVIRONMENT != prod`");
  # they are not gates. ONLY a line whose first non-space character is `#`
  # is skipped — a real comparison with a trailing comment still counts.
  #
  # Written as "strip leading blanks, test first char" rather than a glob:
  # `[[:space:]]*\#*` looks like it means "spaces then #", but `*` is a
  # wildcard, so it matches "spaces, ANYTHING, #" — i.e. every line with a
  # trailing comment. That glob shipped in this script's first draft and its
  # mutation test caught it.
  text="${rest#*:}"
  stripped="$(printf '%s' "$text" | sed 's/^[[:space:]]*//')"
  case "$stripped" in
    \#*) continue ;;
  esac

  # Allowlisted only if the recorded FINGERPRINT still matches the line's
  # text. A bare file:lineno exemption drifts silently onto whatever code
  # later occupies that line — which for a security-relevant gate is an
  # exemption nobody reviewed (envspell1 review, F4).
  if [ -f "$ALLOWLIST" ]; then
    entry="$(grep "^${file}:${lineno}:" "$ALLOWLIST" 2>/dev/null | head -1)"
    if [ -n "$entry" ]; then
      fingerprint="$(printf '%s' "$entry" | cut -d: -f3)"
      line_text="${rest#*:}"
      case "$line_text" in
        *"$fingerprint"*) continue ;;
        *)
          echo "envspell1: allowlist entry is stale — ${file}:${lineno}"
          echo "  recorded fingerprint: ${fingerprint}"
          echo "  line now reads:       $(printf '%s' "$line_text" | sed 's/^[[:space:]]*//')"
          echo "  Re-verify it is still naming-not-gating, then update the entry."
          status=1
          continue
          ;;
      esac
    fi
  fi

  found="${found}${hit}\n"
  status=1
done <<EOF
$(cd "$ROOT" && grep -rnE "$PATTERN" \
    --include='*.py' libraries services 2>/dev/null)
EOF

if [ "$status" -ne 0 ]; then
  echo "envspell1: bare ENVIRONMENT comparison(s) found."
  echo ""
  printf "%b" "$found"
  echo ""
  echo "Use utils.environment instead:"
  echo "  is_recording_environment(v)     — gating a RECORDER; unknown -> True"
  echo "  is_local_bypass_allowed(v)      — gating a PRIVILEGE; unknown -> False"
  echo "                                    (exact match; never normalised)"
  echo ""
  echo "They are not inverses. Pick by what the wrong answer costs:"
  echo "a recorder that goes quiet, or a bypass that gets armed."
  echo ""
  echo "If a comparison is genuinely naming rather than gating (e.g. deriving"
  echo "a log-group or bucket name), add it to:"
  echo "  tools/environment-gate-allowlist.txt   (file:lineno:fingerprint:rationale)"
  exit 1
fi

echo "envspell1: no bare ENVIRONMENT comparisons outside utils/environment.py"
exit 0
