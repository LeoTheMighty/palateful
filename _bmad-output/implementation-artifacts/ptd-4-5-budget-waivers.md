# Story ptd-4.5 — Budget waiver file + grep guard

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

ptd-4 landed `tools/perf-budgets.yaml` + `bin/perf-audit`. ptd-4.5
adds the reviewer-sign-off channel: every endpoint whose budget count
exceeds 1 needs a matching waiver line in
`tools/perf-budget-waivers.txt`. A budget raise is therefore
**three diff lines**, all visible to the PR reviewer:

1. Bump the count in `tools/perf-budgets.yaml`.
2. Add `screen:endpoint:rationale` to `tools/perf-budget-waivers.txt`.
3. Rationale in the PR description.

Mirrors the shape of `tools/no-silent-catch-check.sh` +
`tools/silent-catch-allowlist.txt` (flat text allowlist, shell-
runnable grep-guard) per the epic Design Principles:
> Silent-catch allowlist shape, `helpers.dart` test primitives,
> `analyze_latency.py` flag structure — new tooling echoes existing
> tooling so ops muscle memory transfers.

## Implementation

### New files

- **`tools/perf-budget-waivers.txt`** — committed allowlist, header
  documents format + shape + example lines. Currently empty of
  active waivers — the ptd-4 baseline has every endpoint at count 1.
- **`tools/no-perf-budget-waiver-check.sh`** — CI guard.
  - `awk`-parses the budget yaml (predictable shape from PyYAML's
    `safe_dump`) to extract `screen → endpoint → count` triples.
  - For every triple with `count > 1`, grep for
    `^screen:endpoint:` in the waivers file.
  - Exits 1 with a stderr-listed violation set if any entry exceeds
    without a matching waiver. Exits 0 clean.
  - Exit code 2 on tooling error (missing files / malformed yaml).

### awk parsing notes

The awk script tolerates path segments that contain `:` — e.g.,
`GET /v1/recipes/:id` (route-redacted). It anchors the trailing
`: <int>` counter rather than splitting on the first `:`.

## Acceptance Criteria

- [x] (1) `tools/perf-budget-waivers.txt` committed with format
  `screen:endpoint:rationale` (one per line).
- [x] (2) `tools/no-perf-budget-waiver-check.sh` fails if any
  `tools/perf-budgets.yaml` entry exceeds count 1 without a matching
  waiver line.
- [x] (3) Grep guard wired into CI — **deferred to ptd-5** which
  owns the `.github/workflows/ci.yml` edit. The script is usable
  from any context today (`bash tools/no-perf-budget-waiver-check.sh`).
- [x] (4) Reviewer sign-off required in PR description (convention;
  not automated) — documented in the waiver file header.

## QA walkthrough

```bash
# Clean baseline: 14 entries scanned, 0 waived, exit 0.
tools/no-perf-budget-waiver-check.sh

# Simulate a violation: bump favorites to 2 in the budget yaml.
sed -i.bak 's/GET \/v1\/favorites: 1/GET \/v1\/favorites: 2/' tools/perf-budgets.yaml
tools/no-perf-budget-waiver-check.sh     # exit 1, prints the offender
git checkout tools/perf-budgets.yaml
rm tools/perf-budgets.yaml.bak

# Simulate a waived violation: bump + add waiver line.
sed -i.bak 's/GET \/v1\/favorites: 1/GET \/v1\/favorites: 2/' tools/perf-budgets.yaml
printf 'home:GET /v1/favorites:demo waiver\n' >> tools/perf-budget-waivers.txt
tools/no-perf-budget-waiver-check.sh     # exit 0, "1 waived"
git checkout tools/perf-budgets.yaml tools/perf-budget-waivers.txt
rm tools/perf-budgets.yaml.bak
```

## Non-goals (deferred)

- **CI wiring** — lives in ptd-5 so all the CI steps land together.
- **Automated PR-description rationale enforcement** — convention
  + code-review checklist; the point of the waiver file is that the
  rationale is *in* the diff.
- **Waivers that expire** — if the waiver pool grows unruly, we can
  add a date column later. Out of scope for MVP.

## File List

- `tools/perf-budget-waivers.txt` (new)
- `tools/no-perf-budget-waiver-check.sh` (new)
- `_bmad-output/implementation-artifacts/ptd-4-5-budget-waivers.md` (new — this file)
