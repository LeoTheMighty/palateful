---
hash: arci1
type: debug
created: 2026-07-27T23:10:00-06:00
title: await-remote-ci reports success while a sibling workflow is red
from: dev/dev-rsh101-2026-07-27T12:30-unblock-deploy-path.md
status: done
owner: /devx-loop-2026-07-27T21-15-34-312-36147
branch: null
---

## Goal

`devx devx-helper await-remote-ci <branch>` should not report a terminal
`success` for a branch that has a failing workflow run on the same commit.
Today it reports the newest run only, so `/devx` Phase 7 concludes "CI
green, proceed to merge" while `devx merge-gate` — which aggregates every
check — correctly says `merge:false`. The two helpers disagree about the
same commit, and the disagreement is silent.

Repo state matters here: this repo runs **two** workflows on every PR,
`CI & Deploy` (`ci.yml`) and `devx-ci` (`devx-ci.yml`). Any branch where
they disagree hits this.

## Acceptance criteria

- [ ] `await-remote-ci` returns a non-success terminal state when *any*
      workflow run at the branch's `headSha` concluded non-success.
- [ ] The returned JSON names which workflow failed, so the Phase 7 status
      log line is actionable without a second `gh` call.
- [ ] A branch with one green and one red workflow is covered by a test —
      this is the exact case that produced the false green.
- [ ] `in-progress` still wins over a completed sibling: if one workflow is
      done and another is still running, the state stays `in-progress`
      rather than resolving early on a partial view.
- [ ] The skill's Phase 7 dispatch table in `.claude/commands/devx.md` still
      describes the states accurately after the change.

## Technical notes

- Observed on 2026-07-27 during rsh101 Phase 8, commit `408aeaf`:
  - `await-remote-ci feat/dev-rsh101 --once` →
    `{"state":"completed","conclusion":"success","runId":30296754787}`
    (that is `CI & Deploy`, which genuinely passed).
  - `devx merge-gate rsh101` →
    `{"merge":false,"reason":"CI not green (conclusion=failure)"}`.
  - `gh run list --branch feat/dev-rsh101` showed both runs at the same
    `headSha`: `30296754787 CI & Deploy … success` and
    `30296754128 devx-ci … failure`.
- The merge gate caught it, so nothing bad shipped — **this is a
  defense-in-depth failure, not an incident**. The risk is that Phase 7 is
  documented as the place that waits for CI, and a future change that
  trusts its verdict without a merge-gate re-check would merge red.
- Likely fix shape: `gh run list` already returns every run; take the set at
  `headSha` rather than `[0]`, and fold: any `failure`/`cancelled`/
  `timed_out` → that conclusion; any still running → `in-progress`; all
  success → `success`.
- Adjacent smell, worth deciding rather than inheriting: `debug-dvxci1`
  left an open question about whether a TS/JS `devx-ci` should exist at all
  in a Python/Flutter repo where `ci.yml` already runs the real suites. If
  that workflow is deleted, this bug stops biting *this* repo — but the
  helper is still wrong for any repo with two workflows.

## Status log

- 2026-07-27T23:10 — filed from rsh101 Phase 8. Found because `merge-gate`
  and `await-remote-ci` disagreed on commit `408aeaf`; investigating the
  disagreement is also what surfaced the imptab1 collision, so the false
  green cost nothing this time and saved something.
- 2026-07-27T17:20:14-06:00 — claimed by /devx in session /devx-loop-2026-07-27T21-15-34-312-36147
- 2026-07-27T23:49:11.480Z — loop iteration 1: Fixed the await-remote-ci single-workflow blind spot in the devx CLI — the probe now folds every workflow run at the branch's headSha instead of trusting the newest one — with 21 new tests, a full green suite, and live verification against the exact commit from the spec.
  - Change: probeRemoteCi now requests 30 runs (configurable via a new runLimit opt), filters to the pinned headSha, and delegates to a new exported pure foldRunsAtSha; sha-mismatch now means 'no run at this commit' and cites the newest run's sha.
  - Change: foldRunsAtSha precedence: any non-completed run wins as in-progress (dominant even over an already-failed sibling, per AC #4); else the first conclusion != 'success' wins with that run as representative; else success. Matches the skill body's existing conclusion=='success' dispatch, so skipped/neutral fold as red exactly as a lone such run always did.
  - Change: ProbeState/AwaitState in-progress and completed variants gained runs: RunSummary[] listing every workflow at the commit, so the Phase 7 status-log line names the red workflow without a second gh call (AC #2).
  - Change: 21 new tests across four levels: foldRunsAtSha unit cases, probeRemoteCi sibling cases (incl. ignoring an older commit's red run), awaitRemoteCi poll-past-green-to-red, and CLI-level JSON assertions. Updated 11 existing --limit 1 fixtures to --limit 30.
  - Change: AC #5: Phase 7 dispatch table in .claude/commands/devx.md updated in both the devx repo (source of truth) and this worktree's synced copy; stale MED-5 comment in src/lib/loop/tail.ts corrected.
  - Change: Filed a MANUAL.md entry in this repo documenting the cross-repo commit that the loop cannot perform, including the dist/-already-rebuilt caveat.
  - Learning: The fix does not live in this repo at all — `devx` resolves to ~/personal/devx/dist/cli.js. arci1 is filed in palateful's debug/ backlog but only its .claude/commands/devx.md half can be committed by this loop; the devx repo has its own debug/ + DEBUG.md backlog where this spec arguably belonged.
  - Learning: src/lib/loop/tail.ts ALREADY implemented this exact aggregation (limit 20, filter by headSha, in-progress-dominant, then any-non-success) as review finding MED-5, and its header comment explicitly called out probeRemoteCi's single-run shape as the weaker sibling. The bug was a known-and-fixed-in-one-place issue that never propagated to the other. Independently arriving at the same precedence order validates the AC #4 reading over the spec's hedged 'likely fix shape' technical note, which had failure winning over in-progress.
  - Learning: skills/devx.md is a GENERATED mirror — scripts/sync-skills.mjs copies .claude/commands/ -> skills/, and test/skills-sync.test.ts is a byte-identical drift guard. Editing skills/devx.md gets silently reverted by the next sync and fails two tests; always edit .claude/commands/devx.md then run `npm run sync:skills`.
  - Learning: `npm test` in the devx repo runs `npm run build`, which rewrites dist/ — the globally-linked devx binary. Running the suite there is not side-effect-free: it ships uncommitted source changes to the live CLI immediately.
  - Learning: The full devx suite takes ~8.5 minutes, dominated by one loop-integration file; targeted vitest runs are ~0.4s. Piping `npm test` to `tail` buffers all output until exit, which makes progress invisible — redirect to a file instead.
- 2026-07-28T00:00:55.097Z — loop iteration 2: Ran the arci1 fix to completion-verification: full devx suite green (120 files / 2350 tests, incl. build + typecheck), all five acceptance criteria audited and confirmed, and the live probe re-verified against the spec's exact commit through the shipped binary.
  - Change: Verified the full devx test suite end-to-end — 120 files / 2350 tests passed, exit 0, which also covers `npm run build` and `tsc --noEmit`; no failures or type errors.
  - Change: Audited all five acceptance criteria against the implemented code rather than iteration 1's claims: confirmed foldRunsAtSha precedence, the `runs[]`/`workflowName` fields reaching the CLI's JSON output verbatim, dedicated tests at four levels for the green+red and in-progress-dominant cases, and the Phase 7 dispatch table's accuracy.
  - Change: Confirmed the doc half is genuinely in sync: palateful's `.claude/commands/devx.md` is byte-identical to devx's source-of-truth copy modulo its `<!-- devx-skill -->` banner line.
  - Change: Re-ran the live end-to-end check against the shipped `dist/`: `408aeaf` now yields `{conclusion:"failure", workflowName:"devx-ci", runs:[CI & Deploy=success, devx-ci=failure]}` (previously a false `success`), while the all-green sibling `f7a8ab4` still yields `success`.
  - Change: Repaired the now-stale reproduction recipe in MANUAL.md's cross-repo handoff entry, replacing the broken CLI invocation with a working read-only sha-pinned library call, and recorded the final suite numbers there.
  - Learning: The CLI-level live check from iteration 1 is no longer reproducible as written: `feat/dev-rsh101` was deleted locally after the rsh101 merge, so `await-remote-ci feat/dev-rsh101 --once` exits 2 at stage `git-rev-parse`. The remote runs still exist, so verification must bypass the branch ref by passing `headSha` directly to `probeRemoteCi` — worth remembering for any future spec that cites a since-merged branch as its evidence.
  - Learning: That deleted-branch failure is itself a small confirmation of the design: a vanished local ref degrades to an operator-actionable exit 2, not to a silent green — the same failure-safe direction the sha-mismatch state takes.
  - Learning: The tail.ts dedup that iteration 1 flagged as a 'live candidate' is not worth taking under this spec: tail.ts's inlined fold already has precedence identical to foldRunsAtSha, so the two cannot disagree today, and collapsing them would touch the 15s loop-integration test that dominates the suite's ~8.5min runtime for no behavioural gain.
  - Learning: `npm test` in devx is a single command covering build, typecheck, and vitest — there is no separate lint script, so one green `npm test` is the complete verification gate for that repo.
- 2026-07-28T00:09:56.338Z — phase 4: loop-shipped — per-iteration verification (see iteration lines above) stood in for the interactive self-review pass; line appended by the loop merge tail per dvx103
- 2026-07-28T00:09:56.339Z — merged via devx loop — PR https://github.com/LeoTheMighty/palateful/pull/10
