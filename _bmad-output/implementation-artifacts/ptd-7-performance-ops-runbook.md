# Story ptd-7 — `docs/PERFORMANCE_OPS.md` ops runbook

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

Last story in the epic — documents every tool the epic shipped:
overlay (ptd-1), harness + fixtures (ptd-2.5 / ptd-2 / ptd-3),
`bin/perf-audit` + budget yaml (ptd-4), waivers + grep guard (ptd-4.5),
CI regression guard (ptd-5), self-test (ptd-8). The `analyze_latency.py`
+ `--section client` sections from ptd-6 were already in
`docs/PERFORMANCE_OPS.md` when this story started.

Write-docs-last per the epic: the runbook can now describe tools as
they actually ship, rather than as they were drafted.

## Implementation

Append six new sections to `docs/PERFORMANCE_OPS.md` (order reflects
the epic story order — overlay first, regression guard last):

1. **Debug perf overlay (ptd-1)** — how to invoke in the simulator,
   why the hit-zone is top-right, zero-cost-in-release note.
2. **Perf audit harness (ptd-2.5 / ptd-2 / ptd-3)** — how to run a
   single test, why provider-level instead of widget pump, where
   fixtures live, how to refresh a drifted fixture.
3. **`bin/perf-audit` (ptd-4)** — capture vs assert modes, strict
   env var, custom budget file, exit codes, CI time cost.
4. **Raising a perf budget (ptd-4.5)** — the four-cue workflow
   (yaml bump + waiver line + PR description + auto-label) + waiver
   file hygiene.
5. **Self-test (ptd-8)** — what it proves, the two-branch assertion
   matrix.
6. **CI regression guard (ptd-5)** — step order, warn-mode grace
   window end date (2026-05-07), how to flip to strict, flake /
   quarantine guidance.

## Acceptance Criteria

- [x] (1) Doc covers how to run `bin/perf-audit` locally, how to
  update budgets + add a waiver line, how to read
  `analyze_latency.py` output (server + client + `--regression-hunt`
  — already in the file from ptd-6), how the debug overlay works,
  where client analytics live (`client_latencies` table, admin
  `Client` tab — already in the file from ptd-6), how to refresh
  `tools/perf-audit-fixtures/`, how to quarantine a flaky harness
  test.
- [x] (2) Links to `cla-*` / `ffm-*` stories for cross-reference —
  the existing file references these throughout; new sections
  cross-link to the perf-audit-fixtures README and the ptd-N story
  files via file-path mentions.
- [x] (3) Reviewer-sanity-checked by a round-trip read — each new
  section starts from "what's this for" and walks an operator
  through a concrete command. No assumed context beyond the pointer
  to the relevant tool file.

## QA walkthrough

1. `cat docs/PERFORMANCE_OPS.md | less` — scroll from top to bottom,
   every new section has a command block that copy-pastes cleanly.
2. Grep the file for every story key mentioned in the epic:
   `grep -E 'ptd-[0-9]' docs/PERFORMANCE_OPS.md` — at least one
   reference for ptd-1, ptd-2, ptd-2.5, ptd-3, ptd-4, ptd-4.5,
   ptd-5, ptd-6, ptd-7, ptd-8.
3. Follow the "raising a perf budget" flow end-to-end in a scratch
   branch: bump an entry, add a waiver, run the grep guard, confirm
   CI would pass.

## Non-goals (deferred)

- **Screenshot of the overlay** — doc is text-only. If the screen
  is non-obvious enough to need one, the section is over-
  abstracted.
- **Playbook for each individual regression case** — the runbook
  describes the tools; case-specific playbooks belong in PR
  descriptions / git log.

## File List

- `docs/PERFORMANCE_OPS.md` (modified — append 6 new sections)
- `_bmad-output/implementation-artifacts/ptd-7-performance-ops-runbook.md` (new — this file)
