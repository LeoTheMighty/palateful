---
hash: copydrift1
type: debug
created: 2026-09-23T03:30:00-06:00
title: three guards, one trap, two halves — allowlists keyed by file:lineno rot, and their parsers split on the first colon
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

## The pattern, which is the point

This is not one file's bug. **Three guards reached for the same fragile
shape — `file:lineno:rationale`, parsed by splitting on colons — and it
failed in two different halves on the same night:**

| guard | half that bit | state |
|---|---|---|
| `tools/copy-grep-guard.sh` + its allowlist | **line-number rot** — an edit above an entry moves the string | **live**; cost a CI cycle on acttab1 tonight |
| `tools/silent-catch-allowlist.txt` | same shape, same rot | **latent** — its paths are colon-free and nobody has edited above its entries lately |
| `tools/stale-pointer-check.py` (PR #47) | **colon-split** — a rationale citing `ci.yml:748` swallows the path | hit by palateful-4f, fixed there |

The only one built to resist both is the core baseline added in PR #56
(`tools/silent-catch-core-baseline.txt`: per-file counts, whole-file
format validation, duplicate-row rejection, self-tested in all three
failure directions).

**And it resists them because of a message, not a rule.** I was about to
ship the identical `file:lineno` shape in that baseline; palateful-4f
warned me mid-work, having just hit the colon half in #47, and then
corrected its own first suggestion (last-colon anchoring) when 0a found
the case that breaks it too. Three independent authors reached for the
same shape; the one that survived did so because someone happened to be
looking at the right moment. That is not a repeatable defence, which is
the argument for writing the pattern down here rather than fixing one
file quietly.

## Technical notes
- `tools/silent-catch-allowlist.txt` should get the same treatment; it is
  filed separately as part of `scanmig1`, which already owns migrating the
  feature-services section onto the brace-matched scanner.
- Lower priority than a user-facing bug, higher than it looks: the cost is
  paid by an unrelated PR at a random future moment, which is the most
  expensive time to pay it.

## Status log
- 2026-09-23T03:30 — filed from acttab1, where it turned that PR's first CI run red. Evidence is the run's own log, quoted above. Blocked-by: —.
- 2026-09-23T16:10 — recorded here because it is tonight's other zero-that-reads-as-fine, and it now has a mechanism rather than an isolation: **GitHub check runs are keyed to the commit SHA, not the branch or the PR.** A SHA whose workflow dispatch is lost stays lost, and every branch and PR pointing at it inherits the silence.

  Evidence, both directions [M]: the acttab1 commits produced **zero** runs across `feat/dev-acttab1` (PRs #68, #72), a close/reopen, an empty commit, and a differently-named branch `feat/acttab1-retry` (#73) — while an unrelated PR (#71) opened minutes later on the same account ran normally. Then **the same code cherry-picked to new SHAs (#74) got 7 check runs in ~20s, and the same docs commits cherry-picked to new SHAs (#75) also got 7 in ~20s.** So the content was innocent in both directions; the SHAs were stuck.

  **Recovery is new SHAs — rebase, cherry-pick or amend. Retrying the same SHA in any form cannot work**, which is why reopening the PR, pushing an empty commit on top, and creating a fresh branch all failed: each kept the stuck SHAs in the PR's range.

  What makes it dangerous is the phrasing: `gh pr checks` answers *"no checks reported on the branch"*. **A PR whose SHAs are stuck is indistinguishable from a repo that has no CI configured** — and the natural reflex, retrying that SHA, is the one thing that cannot help. Cost before the mechanism was found: three PRs and about an hour.
