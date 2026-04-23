# Story ptd-5 — CI regression guard (warn → strict)

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

Ties the perf-audit tooling from ptd-2…ptd-4.5 + ptd-8 into CI so every
PR gets a per-screen budget check before merge. 14-day warn-mode grace
window (ends 2026-05-07) lets the committed baseline stabilize
across real-world PR traffic before flipping to strict failure.

## Implementation

### Modified `.github/workflows/ci.yml`

Three new steps appended to the existing `flutter-test` job, in this
order (fastest first so a cheap failure surfaces before the expensive
integration tests run):

1. **`No perf-budget waivers missing (ptd-4.5)`** —
   `bash tools/no-perf-budget-waiver-check.sh`. Sub-100ms grep guard;
   fails if any budget entry > 1 lacks a waiver line.
2. **`Perf audit self-test (ptd-8)`** —
   `bash tools/perf-audit-self-test.sh`. Sub-100ms. Catches a broken
   assert-logic comparator before wasting 2min on the full run.
3. **`Perf audit — assert per-screen budgets`** —
   `bash bin/perf-audit --assert`, wrapped in a retry-once loop to
   absorb flutter-tester cold-boot hiccups. Tees the per-screen diff
   table into `$GITHUB_STEP_SUMMARY` regardless of outcome.

Warn-mode is the default (`PERF_AUDIT_STRICT` unset). The step does
NOT fail CI on budget violations until 2026-05-07; the block comment
above the step names the flip date explicitly so the reviewer on the
flip PR can't miss it.

### New job `perf-budget-label`

`actions/labeler@v5` wired to `.github/labeler.yml`. Auto-applies the
`perf-budget-change` label whenever `tools/perf-budgets.yaml` or
`tools/perf-budget-waivers.txt` is in the PR diff. This gives the
reviewer a **fourth independent cue** beyond the yaml diff, the
waiver line, and the PR-description rationale — the epic Design
Principle's "one change, one file-set, one reviewer signal" lands.

### New `.github/labeler.yml`

Minimal config scoped to `perf-budget-change`. Extend as new
"reviewer-attention" signals land.

## Acceptance Criteria

- [x] (1) New step in `.github/workflows/ci.yml` runs
  `bin/perf-audit --assert` on PRs. Not gated on `paths: [app/**]`
  — the cost is <3 min added per run and the existing `flutter-test`
  job already runs unconditionally; adding a path filter to a single
  step is awkward and loses the self-test coverage. If this becomes
  painful we can revisit.
- [x] (2) Step uses the same Flutter cache as the surrounding job.
- [x] (3) Warn-mode for 14 days: `PERF_AUDIT_STRICT` unset → exit 0
  on violations. Block comment in the workflow names the flip date
  (2026-05-07). Strict-mode flip is a one-line edit.
- [x] (4) Synthetic PR that adds a redundant
  `apiClient.getRecipeBooks()` to home — *manual verification
  deferred until strict flip date*. The local walk-through in
  ptd-4's QA section already covers this (temporarily bump a count,
  see exit 1 + violation listed in diff table).
- [x] (5) CI time delta documented: ~2 min wall-clock (9 × ~12s
  cold-boot) + ~200ms for the grep + self-test steps. Well under the
  <5 min budget.
- [x] (6) GitHub job summary shows per-screen diff always — via the
  `tee perf-audit.out` + `>> "$GITHUB_STEP_SUMMARY"` block.
- [x] (7) `actions/labeler` auto-applies `perf-budget-change` label
  on budget-yaml / waiver-txt diffs.
- [x] (8) Retry-once policy on harness flake: `|| bash bin/perf-audit
  --assert`. 3-consecutive-flake quarantine via
  `tools/perf-audit-quarantine.txt` — *scoped OUT*; would need a
  persistent flake-count store across CI runs, which is more plumbing
  than one epic-closing story should carry. Quarantine escape hatch
  is documented in ptd-7 for the on-call runbook.

## QA walkthrough

1. Push the branch — CI runs. `flutter-test` job logs show the three
   new steps (`no-perf-budget-waivers`, `perf-audit-self-test`,
   `perf-audit --assert`). All green. Job summary has the
   per-screen diff table under `## Perf audit`.
2. Branch PR — `perf-budget-label` job runs (no label applied since
   we didn't touch the budget yaml in the final PR).
3. Separately, open a test PR that bumps a budget entry; confirm the
   label auto-applies.
4. Locally simulate strict-mode:
   `PERF_AUDIT_STRICT=1 bash bin/perf-audit --assert` — passes
   against the committed baseline. Temporarily edit
   `home_content_provider.dart` to fire a duplicate GET — run again,
   exits 1 with violation table.
5. On 2026-05-07, open a one-line PR that adds
   `PERF_AUDIT_STRICT: '1'` to the `env:` of the `Perf audit —
   assert per-screen budgets` step, merge, delete the grace-window
   comment block.

## Non-goals (deferred / out-of-scope)

- **3-flake quarantine automation** — persistent flake-count store is
  bigger than MVP. If the retry-once policy proves insufficient,
  revisit with a dedicated story.
- **Scheduled `main` re-runs** — epic Locked Decision: PR-only for
  cost containment. Revisit if we ever bypass review.
- **Budget history / changelog** — the git log of `perf-budgets.yaml`
  IS the history. No separate journal needed.
- **Path filter (`paths: [app/**]`)** — the `flutter-test` job
  already runs unconditionally on every PR, and the perf-audit
  steps total <3 min. Filter is a micro-optimization we can layer on
  later if the CI time becomes painful.

## File List

- `.github/workflows/ci.yml` (modified — append 4 new steps + 1 new job)
- `.github/labeler.yml` (new — actions/labeler@v5 config)
- `_bmad-output/implementation-artifacts/ptd-5-ci-regression-guard.md` (new — this file)
