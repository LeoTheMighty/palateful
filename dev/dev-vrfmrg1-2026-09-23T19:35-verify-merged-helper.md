---
hash: vrfmrg1
type: dev
created: 2026-09-23T19:35:00-06:00
title: A verify-merged helper, because the guidance that has to be recalled at the moment of use is the guidance that isn't
from: LESSONS.md (the verdict-silence umbrella + the squash-merge entry)
status: ready
owner: null
branch: null
---

## Goal

`tools/verify-merged.sh <path> <fragment>` — answer "did this actually land on
`origin/main`?" by content, in a way that a line wrap cannot defeat.

The recipe already exists in LESSONS.md: grep `origin/main` for something the
branch added, because `git cherry` and `git diff origin/main` both lie about
squash-merged branches. **The recipe is correct and it still fails in use.**

## Why this is a tool and not another paragraph

Two instances on 2026-09-23, four minutes apart:

1. Verifying #69 had merged, a grep for a sentence from the merged text
   returned **0** against a `main` that contained it. The sentence had been
   re-wrapped; the pattern straddled a line break. The technique that guards
   against a false "merged" produced a false "not merged".
2. That finding was written up as #81, adding the caveat "verify-by-content
   needs a fragment that **cannot cross a wrap**". Verifying **#81** had
   merged, a grep for `"cannot cross a wrap"` returned **0** — because in the
   merged text that phrase is broken as `cannot\n  cross a wrap`.

**The caveat warning against sentence-length greps was itself un-greppable by
a sentence-length grep, in the commit that added it.** The author of the
sentence reached for a sentence four minutes after writing it.

So the rationale is not "prose is bad". The prose is accurate and it stays.
It is that **guidance which must be remembered at the moment of use wants to
be a command someone copies, not a paragraph someone read.** The tool does
not replace the lesson; it removes the need to recall it under time pressure,
which is the only time it matters.

## Acceptance criteria

- [ ] `tools/verify-merged.sh <path> <fragment>` reads the file from
      `origin/main` (not the worktree) and reports found / not-found with the
      fragment echoed back, so a typo in the fragment is visible in the output
      rather than indistinguishable from a real miss.
- [ ] **Whitespace is normalised on both sides before matching** — collapse
      runs of whitespace (including newlines) to single spaces. This is the
      whole point of the tool; a helper that greps raw has exactly the bug it
      exists to prevent.
- [ ] **A negative control ships with it**: a fragment known to be absent must
      report not-found, asserted in the same run. Otherwise a helper that
      always says "found" passes every test anyone would think to write.
- [ ] **Proven against both of tonight's instances** — the two fragments that
      returned 0 by raw grep must report found. These are the regression
      cases; they are why it exists.
- [ ] Exit codes: `0` found, `1` not found, `2` usage / unreadable path. A
      caller must be able to branch on it without parsing prose.
- [ ] Fetches or requires a fresh `origin/main` and says which commit it
      checked against, so a stale answer is visible as a stale commit rather
      than silently wrong.
- [ ] LESSONS.md's squash-merge entry points at the command. The prose stays;
      it gains a copyable line.

## Technical notes

- Scope is deliberately one file, one fragment, one answer. Not a merge
  checker, not a PR tool — `gh pr view --json state` remains the merge
  authority, per the existing entry. This answers the different question of
  whether specific *content* is present.
- Multi-line fragments should work as a consequence of normalisation, not as
  a separate mode.
- Worth considering, not blocking: a `--all` that takes several fragments and
  reports each, since verifying a merged doc usually means checking three or
  four things and the per-call overhead is what pushes people back to grep.

## Status log
- 2026-09-23T19:35 — filed at palateful-41's request, unclaimed. Arose from
  the #69 and #81 verification misses recorded above; 41's framing of the
  rationale ("a command someone copies, not a paragraph someone read") is
  carried into the spec deliberately, as is the requirement that whitespace
  normalisation is the point rather than an implementation detail.
