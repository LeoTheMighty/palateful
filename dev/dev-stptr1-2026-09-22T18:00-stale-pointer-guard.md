---
hash: stptr1
type: dev
created: 2026-09-22T18:00:00-06:00
title: CI guard against stale pointers to migrated workstream artifacts
from: palateful-0a's finding on commit 64c8b7f5 (flat-era workstream migration)
status: ready
owner: null
branch: feat/dev-stptr1
---

## Goal

Stop a Markdown file from pointing at a workstream artifact that has moved.

`64c8b7f5` migrated the six flat-era artifacts to the folder-per-artifact
layout and rewrote the 16 live pointers that existed at the time. A sweep
can only cover files that exist when it runs, and two classes escape it:

1. **a file the sweep didn't cover**;
2. **a file written after the rename from an older template.** Because the
   file is new, git has nothing to conflict against, so the stale pointer
   merges silently.

Class 2 is the reason this exists, and it is not hypothetical.
palateful-0a's `rsh109b` spec (#46) was written from an older template and
carried a flat-era `plan.md` path. Its sibling `rsh109`, which already
existed, conflicted properly and forced a human to look. The new file
didn't. **A new file has no conflict to raise.**

## Acceptance criteria

- [x] `tools/stale-pointer-check.py` fails when a tracked `.md` references
      `_devx/workstreams/<slug>/<artifact>.md` while
      `_devx/workstreams/<slug>/<artifact>/agent.md` exists on disk.
- [x] Matches the bare `<slug>/<artifact>.md` prose form too, but only when
      `<slug>` is a real workstream directory.
- [x] **Exempts `## Status log` sections by section, not by an inline
      marker.** Those lines are append-only history of where an artifact
      was at the time. An inline escape comment would force an edit to the
      very lines the convention protects — the guard would be causing the
      write it exists to make unnecessary. (palateful-0a's design point.)
- [x] Exempts `evals/` paths: specs legitimately reference eval records a
      drill has yet to produce, e.g. `evals/E-drill-rotation.md`.
- [x] `tools/stale-pointer-allowlist.txt` (`file:lineno:rationale`) for
      anything else deliberate — a file rather than an inline comment, for
      the same reason.
- [x] **Asserts coverage**: prints files scanned and references resolved,
      and exits 2 on an implausible count rather than passing silently.
- [x] Proven by `tools/stale-pointer-check.suite.py`: 11 cases, all as
      expected, including 0a's real case.
- [x] Wired into CI's `lint` job, where `python3` is already set up.

## Technical notes

Current tree: 1366 Markdown files, 22 workstream references — 16 resolving
(the pointers `64c8b7f5` rewrote) and 6 status-log history lines, which
matches that migration exactly.

**Coverage counts the already-migrated form too.** Without it a clean run
could mean "nothing is stale" or "I matched almost nothing", and those must
not look alike. The first version of this guard reported 6 references and a
clean pass; it was only counting stale-*shaped* hits and could not see the
healthy population at all.

**Two bugs found while proving it**, both by cases rather than review:

1. The allowlist parse split on the first colon, which lands *inside* this
   repo's spec filenames (`…2026-09-22T18:00-…`). It now matches the last
   `:<digits>:`. `tools/silent-catch-allowlist.txt` never hit this because
   Dart paths have no colons — worth knowing if that allowlist ever needs
   to cover a spec path.
2. A coverage case that didn't test what it claimed: it renamed the path
   prefix, leaving the bare-form references intact, so the guard still saw
   them and the case "passed" for the wrong reason.

**Known limits.** It checks pointers to *workstream artifacts* only. A
stale pointer to a moved `dev/` or `docs/` file is not covered, and neither
is a reference built by string concatenation. It catches the migration
class, not every dead link.

## Status log

- 2026-09-22 — filed and implemented. Found by palateful-0a on `64c8b7f5`
  (#46's `rsh109b` carried a flat-era path); assigned here by the
  coordinator so it is built once rather than twice. Section-based
  exemption and the `evals/` carve-out are 0a's design points, adopted as
  given.
