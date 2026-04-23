#!/usr/bin/env bash
# ptd-4.5 — CI guard against silently raising a perf-audit budget.
#
# Rationale: every endpoint in `tools/perf-budgets.yaml` with a count
# > 1 must have a matching waiver line in
# `tools/perf-budget-waivers.txt`, format:
#
#     screen:endpoint:rationale
#
# The invariant is "each logical endpoint should fire at most once per
# cold-start." When a screen legitimately needs a duplicate fetch,
# the raise is recorded as (a) a bump in the budget yaml and (b) a
# waiver line pinning the rationale. Code review can spot both in one
# diff.
#
# Mirrors the shape of `tools/no-silent-catch-check.sh` +
# `tools/silent-catch-allowlist.txt`: flat text allowlist, bash-
# driven check, one entry per line.
#
# Exit codes:
#   0 — clean
#   1 — offending budget entry without matching waiver (listed on stderr)
#   2 — tooling error (missing files, malformed yaml)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUDGET="$ROOT/tools/perf-budgets.yaml"
WAIVERS="$ROOT/tools/perf-budget-waivers.txt"

if [ ! -f "$BUDGET" ]; then
  echo "no-perf-budget-waiver-check: $BUDGET not found" >&2
  exit 2
fi
if [ ! -f "$WAIVERS" ]; then
  echo "no-perf-budget-waiver-check: $WAIVERS not found" >&2
  exit 2
fi

# Extract (screen, endpoint, count) triples from the budget yaml.
# The yaml is emitted by `perf-audit-diff.py`'s safe_dump so its
# shape is predictable:
#
#     screens:
#       home:
#         total: 5
#         endpoints:
#           GET /v1/cooking-logs: 1
#           ...
#
# Awk tracks the currently-open screen via 2-space indentation and
# emits any 6-space-indented `METHOD /path: N` line under `endpoints:`.
triples="$(mktemp -t perf-budget-triples.XXXXXX)"
trap 'rm -f "$triples"' EXIT

awk '
  # Screen header: "  <screen>:"
  /^  [a-z][a-z0-9_-]*:$/ {
    line = $0
    sub(/^ +/, "", line)
    sub(/:$/, "", line)
    screen = line
    in_endpoints = 0
    next
  }
  # Endpoints map header: "    endpoints:"
  /^    endpoints:$/ { in_endpoints = 1; next }
  /^    total:/      { in_endpoints = 0; next }
  # Endpoint row: "      METHOD /path: N". `/path` may contain `:` in
  # route-redacted segments (e.g. `/v1/recipes/:id`), so we anchor on
  # the trailing `: <int>` and take everything before as the endpoint.
  in_endpoints && /^      [A-Z]+ \/.+: [0-9]+$/ {
    body = substr($0, 7)  # strip 6 leading spaces
    pos = match(body, /: [0-9]+$/)
    if (pos == 0) next
    endpoint = substr(body, 1, pos - 1)
    count = substr(body, pos + 2)
    print screen "\t" endpoint "\t" count
  }
' "$BUDGET" > "$triples"

if [ ! -s "$triples" ]; then
  echo "no-perf-budget-waiver-check: failed to parse any budget entries" \
       "from $BUDGET" >&2
  exit 2
fi

violations=""
scanned=0
waived=0

while IFS=$'\t' read -r screen endpoint count; do
  scanned=$((scanned + 1))
  [ "$count" -le 1 ] && continue

  # Waiver match: exact `screen:endpoint:` prefix in waivers file.
  if grep -Eq "^${screen}:${endpoint}:" "$WAIVERS" 2>/dev/null; then
    waived=$((waived + 1))
    continue
  fi
  violations="${violations}${screen}:${endpoint} = ${count}"$'\n'
done < "$triples"

if [ -n "$violations" ]; then
  count=$(printf '%s' "$violations" | grep -c '^' || true)
  echo "no-perf-budget-waiver-check: $count budget entry/entries > 1 without matching waiver:" >&2
  printf '%s' "$violations" | sed 's/^/  /' >&2
  echo >&2
  echo "Add a matching line to tools/perf-budget-waivers.txt in the format:" >&2
  echo "    screen:endpoint:rationale" >&2
  exit 1
fi

echo "no-perf-budget-waiver-check: OK (scanned $scanned entries, $waived waived)"
exit 0
