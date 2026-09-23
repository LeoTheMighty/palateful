---
hash: copydrift1
type: debug
created: 2026-09-23T03:30:00-06:00
title: copy-grep-guard's allowlist pins line numbers, so any edit above an entry turns approved copy into a CI failure
from: dev/dev-acttab1-2026-09-22T22:05-explicit-activity-tab-wins.md
status: ready
owner: null
branch: null
---

## Goal

`tools/copy-grep-allowlist.txt` pins each approved match as
`file:lineno:rationale`. Line numbers rot: **any edit above an entry
moves the approved string and the guard reports it as a new violation**,
on a PR that never touched the copy.

Measured tonight, not hypothetical. On `acttab1` I added seven lines to
`app/lib/features/profile/profile_screen.dart` (a provider reset in the
logout path). That pushed the allowlisted "no premium tier — ever" string
from **865 to 872**, and CI failed with:

```
copy-grep-guard: 1 paywall-language violation(s) found:
  app/lib/features/profile/profile_screen.dart:872: premium|paywall
```

Cost: one full CI cycle (~10 min) and a debugging detour on a PR about
Activity tab selection. It will do the same to whoever next edits above
line 872 in that file.

## Acceptance criteria

- [ ] An edit above an allowlisted entry does not fail the guard. The fix
      that is already proven in this repo: **count approved matches per
      file** (`path:count`) instead of pinning `file:lineno` — see
      `tools/silent-catch-core-baseline.txt` and the ratchet in
      `tools/no-silent-catch-check.sh`, which were built this way for
      exactly this reason and have a self-test covering it.
- [ ] Whatever replaces it still catches a genuinely NEW match in an
      already-allowlisted file. A per-file count does: one approved match
      plus one new one is 2 against a baseline of 1. Pin that with a test.
- [ ] The parser stops splitting on the first colon
      (`copy-grep-guard.sh:81`, `while IFS=: read -r alist_file alist_line
      _rest`). Paths in this repo can contain colons — spec filenames carry
      `2026-09-22T18:00` — and a rationale that cites a line number breaks
      last-colon anchoring too. The strict form that resists both is
      `^[^:]+:[0-9]+$` validated up front, as the core baseline does.
- [ ] Re-point the 22 existing entries to whatever format wins, in one
      commit, with the guard green before and after.

## Technical notes

- Same trap, same night, three guards: this one, the older
  `tools/silent-catch-allowlist.txt` (still `file:lineno`, latent because
  its paths are colon-free and edits above its entries have been rare),
  and `tools/stale-pointer-check.py` in PR #47, where palateful-4f hit the
  colon-split half of it. The core baseline added in PR #56 is the only
  one built to resist both.
- `tools/silent-catch-allowlist.txt` should get the same treatment; it is
  filed separately as part of `scanmig1`, which already owns migrating the
  feature-services section onto the brace-matched scanner.
- Lower priority than a user-facing bug, higher than it looks: the cost is
  paid by an unrelated PR at a random future moment, which is the most
  expensive time to pay it.

## Status log
- 2026-09-23T03:30 — filed from acttab1, where it turned that PR's first CI run red. Evidence is the run's own log, quoted above. Blocked-by: —.
