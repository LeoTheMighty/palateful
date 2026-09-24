---
hash: applygap1
type: dev
created: 2026-09-23T01:15:00-06:00
title: An apply that never ran is indistinguishable from one that ran and failed
from: dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
status: ready
owner: null
branch: null
---

## Goal

**An apply that never ran is not an apply that succeeded — and nothing says
which happened.**

Observed live on 2026-09-23. `#53` (the Batch `desired_vcpus` fix) merged as
`5dbb241e`. Its run failed in **`setup`**, on a transient PyPI timeout
(`Read timed out` / `Cannot install nvidia-nvjitlink-cu12`) that had nothing
to do with the change. Because every later job depends on `setup`,
`detect-changes`, `terraform-prod` and the deploy legs were all **skipped**.
The run shows as **a single red X**.

At a glance that is identical to a deploy that ran and failed. The readings
differ completely:

| What the X means | Prod state | What to do |
|---|---|---|
| Deploy **ran and failed** | possibly half-applied | investigate before re-running |
| Deploy **never ran** (this case) | untouched; **the merged change is not live** | just re-run |

The second is the more dangerous reading to get wrong, because "nothing
happened" is easy to hear as "nothing was needed". `#53` was merged
**specifically** to stop an apply resetting Batch capacity out from under a
queued job. After the merge, `main` said the fix had landed and prod still had
the old behaviour. **The gap between "merged" and "live" is exactly what
tfgate1 closed for Terraform, reopened here by a flaky unrelated job.**

This generalises beyond `setup`: **any** upstream failure skips the apply and
reports the same red X.

## Acceptance criteria

- [ ] A merge to `main` that was *supposed* to apply and **didn't** is
      distinguishable from one that applied and failed, without opening the
      run. Options, cheapest first:
      1. A job that runs on `always()` after the deploy legs and emits an
         explicit verdict — *applied* / *skipped* / *failed* — into the run
         summary.
      2. Publish that verdict to the alert topic (`alrt1`) so a skipped apply
         is noticed rather than looked up.
- [ ] **Re-runs count.** The verdict must reflect the *latest* attempt, or a
      re-run that fixes a flake leaves a stale "skipped" verdict behind.
- [ ] Proven by forcing an upstream failure on a Terraform-only change and
      confirming the verdict says *skipped, not applied*, then re-running and
      confirming it flips to *applied*.
- [ ] Doesn't fire for merges that legitimately apply nothing (docs-only). The
      distinction is **"was an apply expected?"**, i.e. `detect-changes.terraform`,
      **not** "did a job get skipped".

## Technical notes

- Related but not the same as **dfrcp1** (deploy-freshness gets a recipient).
  Deploy-freshness would eventually notice prod drifting stale, but only after
  its 7-day threshold, and it says nothing about a single merge that silently
  didn't apply.
- Cheap first version: since `detect-changes.terraform` already exists
  (tfgate1), the condition is
  `terraform == 'true' && terraform-prod.result != 'success'` → say so loudly.
- Worth considering the same verdict for the service-deploy legs, not just
  Terraform.

## Status log
- 2026-09-23T01:15 — filed from a live instance during #53's merge
  (palateful-41 caught it). The re-run is where the fix actually applies; the
  first run's red X meant "never attempted".
- 2026-09-23T02:00 — **prior instance of a misleading ref reading, recorded so
  a recurrence has something to point at.** After a `--force-with-lease` push
  to `feat/dev-harden`, `gh pr view --json headRefOid` reported head
  **`b8b103ed`**; moments later the same query returned **`7cd13e8d`**, the
  commit actually pushed. `b8b103ed` exists as a local object with a
  *different parent* and a tree carrying main's newer work — i.e. what a
  commit built on another base looks like — and it is **not** in the
  worktree's reflog, which shows a clean rebase followed by the real commit.
  Nothing was lost: local matched remote, the reflog was mine, and the diff
  against `main` was the intended docs-only 8 files. palateful-41 confirmed
  no other tab pushed to that branch. Most likely GitHub briefly serving a
  stale or intermediate ref view after a force-push.

  **Why it belongs in this spec:** the same class. A reading that looks
  authoritative — a head SHA from the API — can describe something other than
  what happened, and acting on it (force-pushing "back" over the unexpected
  SHA) would have destroyed real work. **The check that settled it was local
  evidence: reflog, parents, and the diff against `main`** — not a second
  query to the same source that produced the doubtful reading.
- 2026-09-24 — **a live instance, with the exact misreading this spec is about
  available on a merged PR right now.**

  `#96` (the Batch queue-order flip) merged as `55731990` at 19:46Z. Two
  further merges landed while its run was still in `flutter-test` —
  `e611e4ff` at 19:52:18Z and `6b4e23ab` at 19:52:26Z, eight seconds apart —
  and `cancel-in-progress` killed the run. Measured:

  ```
  run 36050394812 (55731990)
    terraform      : completed/success      <- the PR validate job
    terraform-prod : cancelled  19:53:45Z   <- the apply
  live queue order1 @ 19:53:58Z: palateful-parser-spot   <- unchanged
  ```

  **The apply never ran, and `gh pr checks` on the merged PR shows a green
  `terraform`.** Anyone confirming the deploy the obvious way — glance at the
  merged PR, see terraform green — concludes the flip is live. It is not.
  Three sessions spent roughly ten minutes reasoning about an apply that had
  already been cancelled before any of us named it.

  **Two distinct defects, and they compound:**

  1. **`mergeStateStatus` does not describe main.** `gh pr view` read `CLEAN`
     for both merges. `CLEAN` is the PR *against* main; it says nothing about
     what main is currently running. There is no field in that response that
     would have shown an in-flight apply, so no amount of care with that call
     resolves it — the check has to be a different call:
     `gh api "repos/…/actions/runs?head_sha=$(git rev-parse origin/main)"`,
     and wait if the tip's run is `in_progress`.
  2. **The job-name collision is permanent, not intermittent.** `terraform`
     (validate) and `terraform-prod` (apply) sit on the same run, and the
     first is green on every PR. Unlike the `gh run list` staleness fault,
     this one is present every single time.
  3. **`gh pr checks` cannot answer the question at all.** On `#96` it reads:

     ```
     gh pr checks 96  -> run 36049602691  branch=fix/dev-odback1  event=pull_request
                         terraform      pass
                         terraform-prod skipping
     gh run view      -> run 36050394812  branch=main             event=push
                         terraform      completed/success
                         terraform-prod completed/cancelled
     ```

     The first is not mislabelling the second — **it is a different run.**
     `gh pr checks` reports the pre-merge PR run, where `terraform-prod`
     correctly skips because a PR never applies. The apply lives on the
     post-merge `push` run, which that command never reads. So
     `terraform-prod: skipping` is a correct answer to a question nobody
     asked, and **no output `gh pr checks` could ever produce would show an
     apply cancelled.** A reader confirming a deploy that way has not
     measured anything.

     (First written here as "the aggregate view relabels `cancelled` as
     `skipping`". That was wrong and worth recording as wrong: it is a
     falsifiable claim about `gh`, it is false, and the first person to test
     it would have discounted this whole entry. The true mechanism is the
     stronger one.)

  **The rule that survives both:** never conclude an apply landed from a job
  name, a green check, or a merge commit. **Read the applied state itself.**
  Here that was `order1` from `describe-job-queues` — which said `spot`
  throughout and was the only reading that never lied. Confirming the change
  is *in the tree* is a separate question again, and needs content not
  ancestry: `merge-base --is-ancestor` is satisfied by a revert too, so pair
  it with reading the value out of `origin/main`.

  Not lost, for the record: `6b4e23ab` descends from `55731990`, so the next
  run carries the change and will apply it — *if no further merge preempts
  that one too*. The state is "delayed and repeatedly preemptable", not
  "reverted", and the distinction matters because the remedy is a merge
  freeze rather than a re-merge.
