---
hash: 7c5cf2
type: dev
created: 2026-07-31T10:24:06-06:00
title: "rsh108 follow-up: run the E-7 observation protocol against live prod"
from: dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md
status: in-progress
blocked_by: [rsh108]
branch: feat/dev-7c5cf2
owner: /devx-loop-2026-07-31T15-54-01-442-22311
---

## Goal

Continue rsh108: remaining acceptance criteria split out by devx split (merge-first).

## Acceptance criteria

- [ ] workflow_dispatch run against current prod reports the true gap, cross-checked against bin/prod-status and git log
- [ ] Synthetic gap > 7 days fails the run and < 7 days passes, via the synthetic-gap-days dispatch input
- [ ] Registering a newer ACTIVE task-definition revision without deploying it does not change the reported gap
- [ ] The scheduled 09:00 MDT trigger fires unattended with no approval prompt, confirmed the next morning after merge
- [ ] Actuals recorded in _devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md

## Carried forward

### State to trust

- parent dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md shipped its committed portion at reduced scope through the normal PR/CI/merge tail

### Gotchas (save time — don't rediscover)

- All remaining ACs require the workflow merged to main plus live AWS access and a next-morning check, so they are human-observation work, not loop-iteration work

### Do NOT

- Do not redo ACs already shipped by the parent — audit its PR diff first

## Status log

- 2026-07-31T10:24:06-06:00 — created by devx split from `dev/dev-rsh108-2026-07-27T12:37-deploy-freeze-visibility.md` (merge-first)
- 2026-07-31T10:24:07-06:00 — claimed by /devx in session /devx-loop-2026-07-31T15-54-01-442-22311
- 2026-07-31T16:32:39.243Z — loop iteration 1: Ran the first E-7 observation steps against live prod, caught and fixed a real bug (workflow had no AWS credentials because the secrets are environment-scoped and the job omitted environment: production), and recorded actuals for steps 2 and 7 in the eval file.
  - Change: Fixed .github/workflows/deploy-freshness.yml: added environment: production to the check-freshness job (the AWS secrets are environment-scoped only; first dispatch run 30647079681 failed with 'Credentials could not be loaded' without it) and rewrote the comment block to record that the production environment empirically has no protection rules, so no approval gate is introduced
  - Change: Recorded actuals in _devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md: step 7 PASS (bin/prod-status prints deployed tag c85e350d, 95d old), step 2 partial (bin/prod-status and git log agree on 95 days; workflow measurement pending re-run), step 1 failure + fix documented, step 6 rationale updated to reflect the environment declaration and its verified zero protection rules
  - Learning: The 'required-reviewer gate on environment: production' that justified omitting the environment was presumption, not fact — gh api shows protection_rules: [] and no branch policy, so declaring the environment costs nothing today; step 6 is now the canary for someone adding rules later
  - Learning: The AWS secrets (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) exist only in the production environment scope — repo-level secrets are just the two Cloudflare ones — so any workflow needing AWS must declare environment: production
  - Learning: Prod is genuinely frozen at c85e350d (95 days old, both api and worker services), so the post-merge real-measurement run must FAIL to be correct — a green run would indicate the check is broken
  - Learning: gh CLI auth and local AWS admin creds both work from this environment, so dispatch-based protocol steps (1-4) are loop-runnable, not human-only as the spec's gotcha claimed; only step 6 (next-morning wait) truly needs calendar time
  - Learning: The workflow fix cannot be live-tested pre-merge: gh workflow run --ref uses the definition from a pushed ref, and pushing is out of bounds for an iteration — steps 1/3/4 re-run must wait for the loop's merge tail
- 2026-07-31T16:43:22.078Z — loop iteration 2: Captured E-7 step-5's live preconditions read-only, filed the prod-mutation half as a MANUAL entry with exact commands, and made the load-bearing family-shortcut property permanently CI-guarded via a mutation-verified self-test extracted from the workflow YAML.
  - Change: Added tools/deploy-freshness-self-test.sh: extracts the measure step out of deploy-freshness.yml (never copies it), runs it against a mocked aws and a backdated sandbox git repo, and asserts 6 cases — the step-5 running-vs-newest-ACTIVE resolution, fresh-prod pass, non-commit tag failure, and the synthetic-gap fail/pass/boundary paths
  - Change: Wired the self-test into ci.yml's lint job unconditionally (not nx-affected — nx does not project-map workflow files), verified it adds no new actionlint findings beyond the 3 that pre-exist on HEAD
  - Change: Mutation-verified the guard: reintroducing the family shortcut, flipping -gt to -ge, and disabling the synthetic branch each fail the intended case and only that case; fixed a tally bug where a case could print 'pass' then fail an output assertion
  - Change: Recorded actuals in the E-7 eval file: step 5 precondition (family has exactly one ACTIVE revision, so the trap is latent), steps 3/4 logic-pinned-offline with dispatch still owed, the mutation evidence table, and a note that 95d vs 96d is a day-boundary artifact of a floor-divided age rather than a disagreement
  - Change: Filed the prod-mutation half of step 5 in MANUAL.md with a tested jq/aws command sequence, a deploy-safe image-tag rationale, and an explicit deregister-when-done warning
  - Learning: Registering a task definition against the prod account is blocked by the permission classifier, so AC 3 is not loop-runnable at all — not merely blocked on merge like ACs 1/2/4. Iteration 1's learning that 'dispatch-based steps are loop-runnable' does not extend to prod mutations.
  - Learning: Step 5 cannot be observed passively even with full AWS read access: the family has exactly one ACTIVE revision (:62) which is also the running one, so both resolution paths agree until someone deliberately registers a second revision.
  - Learning: The newest image in ECR is c2f7982c from 2026-05-03 (89 days old) — image builds stopped around the same time deploys did, so there is no genuinely fresh image available to construct a <7-day synthetic revision from.
  - Learning: The service's PRIMARY deployment was created 2026-07-27, only days ago, while its image is from 2026-04-26 — something re-deployed the stale task definition recently. Worth a look: it means the freeze is not simply 'nothing has run since April'.
  - Learning: Extracting the workflow's bash out of the YAML at test time (indentation-based, no PyYAML — the lint job has no guaranteed poetry env) is what makes this guard trustworthy; a copied script would drift and go on passing against code that is no longer shipped.
- 2026-07-31T16:48:19.617Z — loop iteration 3: Closed the E-7 guard's wiring blind spot — the self-test now pins the schedule, the environment-scoped credentials fix, and the dispatch-input-to-env-var wire, all mutation-verified — and filed exact commands for every remaining human/post-merge observation step.
  - Change: Added three static wiring assertions to tools/deploy-freshness-self-test.sh (dependency-free python3 over the YAML): exactly one 0 15 * * * cron, environment: production on the check-freshness job, and a verified inputs.synthetic-gap-days -> $SYNTHETIC_GAP_DAYS wire cross-checked against the extracted run body. Self-test went 6/6 -> 9/9.
  - Change: Mutation-verified all three: six deliberate regressions (cron changed, cron deleted, environment: line deleted, env: mapping deleted, input renamed, env var renamed) each failed exactly one assertion and nothing else.
  - Change: Filed the remaining human/post-merge observation work in MANUAL.md: one-command dispatches for E-7 steps 1/3/4 with their expected outcomes (step 1 MUST fail — prod is frozen), the step-2 cross-check, and the next-morning schedule check for step 6 with the protection-rule failure signature.
  - Change: Recorded the wiring layer in the E-7 eval file as a blind-spot/mutation table and updated the status line and step-6 row.
  - Learning: The prior guard had a real hole, not a theoretical one: renaming the workflow's env var while the run body kept reading the old name left all six behavioural cases green, because the harness supplies that variable itself. Any harness that injects an input it also claims to test cannot see the wiring that delivers it — assert the wiring separately.
  - Learning: A dropped dispatch-input wire fails in a deceptive direction: the >7d case still fails (measuring real frozen prod) and the <7d case fails too, so the observer reads 'the check is broken' rather than 'the input never landed'. That is why the step-3 log must be checked for the literal 'SYNTHETIC gap of 8d' string, not just the exit status.
  - Learning: actionlint's HEAD baseline for this repo is 5 findings (ci.yml x3, devx-promotion.yml x1, force-deploy.yml x1), not the 3 recorded in iteration 2 — iteration 2 appears to have counted only ci.yml. Future iterations should diff against 5.
  - Learning: Nothing loop-runnable remains: ACs 1/2/4 are blocked on the merge (gh workflow run resolves the definition from a pushed ref) and AC 3 is a prod mutation the permission classifier blocks, so further iterations cannot advance any AC — the loop should halt and hand off to the MANUAL.md entries.
- 2026-07-31T16:55:22.938Z — loop iteration 4: Broke the merge-blocked stalemate on E-7 by building a live-check tool that runs the workflow's own extracted bash against real prod, discharging the measurement half of the dispatch ACs and making step 5's human observation merge-independent.
  - Change: Added tools/deploy-freshness-live-check.sh: runs deploy-freshness.yml's measure step against live ECS/ECR/git from a laptop, reading cluster/service/threshold from the workflow's own env block, read-only, exiting 2 (never 1) on credential/extraction failure so a dead AWS session cannot read as 'prod is fresh'
  - Change: Factored the YAML step extractor into tools/deploy-freshness-extract.py and rewired the self-test to it, so the CI guard and the live check can never run different bash; self-test still 9/9, and a renamed workflow step makes both tools fail loudly (verified)
  - Change: Measured live prod with the shipped logic: real gap 96d/exit 1, synthetic 8d/exit 1 (never reports 96), synthetic 1d/exit 0, boundary 7d/exit 0 — and confirmed all three cross-check legs (workflow step, bin/prod-status, git log) agree at 96d
  - Change: Recorded the actuals in the E-7 eval file: steps 1-4 upgraded from pending to measured, a new section splitting step 1 into a discharged measurement half and a still-owed mechanism half, and a filled-in Result block
  - Change: Rewrote the MANUAL step-5 entry as a three-command before/after diff around the registration (no longer blocked on the merge, only on the prod mutation) and added a scope note to the steps-1/3/4 entry telling the operator that a disagreement there is a mechanism bug, not a logic bug
  - Learning: The 'blocked on merge' framing conflated two different things: the measurement (shipped bash vs real prod) is testable anywhere AWS credentials exist, while only the mechanism (env-scoped credentials inside Actions, the unattended schedule, GitHub's expression layer) actually needs the push. Splitting them recovered four of the five owed observations pre-merge.
  - Learning: Extracting the workflow bash into a shared module paid off immediately and unexpectedly — the same extractor that made the CI guard trustworthy is what made a live pre-merge check possible at all, because both must run the shipped code rather than a copy.
  - Learning: The live check's exit code was initially ambiguous: extraction failure exited 1, the same code as 'prod is stale'. For a check whose failure mode is being green-and-blind, an infrastructure error that mimics a real signal is the same class of bug — hence the exit-2 split.
  - Learning: Adding a real .py file to tools/ brings it into ruff's reach in a way the previous inline heredoc never was (3 findings on first write, now fixed); repo ruff runs via NX-affected so tools/ is not in the CI path, but anyone running ruff repo-wide would have hit them.
- 2026-07-31T17:02:40.357Z — loop iteration 5: Discharged the measurement half of E-7 step 5 — the load-bearing, previously agent-blocked observation — by shimming the single aws answer a prod task-definition registration would change, with a self-validating control proving the injected divergence was real.
  - Change: Added --simulate-newer-revision to tools/deploy-freshness-live-check.sh: shims only the describe-task-definition answer on the family name / would-be-next revision ARN, passes every other call through to real ECS, and proves the shipped bash reports a byte-identical gap before and after — no writes to the AWS account
  - Change: Made the observation self-validating: the tool builds the family-shortcut regression from the extracted bash, runs it against the same shim, and exits 2 rather than reporting a pass unless that regression sees the injected revision (an inert shim would make 'unchanged' vacuous)
  - Change: Mutation-verified both directions against live prod: family shortcut in the shipped YAML → exit 1 with the 96d→0d diff; inert shim → exit 2, no false pass. Fixed an ordering bug found this way where the mutant was misattributed as exit 2
  - Change: Recorded actuals in the E-7 eval file: step 5 upgraded from 'owed' to measurement-PASS with the three-run table, a new section on what the simulation does and does not discharge, and updated status + Result blocks (all seven steps now measured against live prod)
  - Change: Narrowed the MANUAL.md step-5 entry to the one assumption still owed — that a real register-task-definition actually makes the new revision the family's newest ACTIVE while describe-services keeps returning :62
  - Learning: The 'prod mutation, therefore human-only' framing was as soft as the earlier 'blocked on merge' one: a check that reads external state through a small, enumerable set of CLI calls can be observed under a simulated state change by shimming those calls, with everything else real. What stays owed is only the assumption the shim encodes about the external system's semantics — a much smaller claim than the whole step.
  - Learning: A simulation-based observation needs a built-in control or it proves nothing: 'the report did not change' is exactly what an inert shim produces. Making the tool construct the regression it guards against, run it through the same shim, and refuse to pass unless the regression fires is what converts the simulation from suggestive to discriminating.
  - Learning: Verdict ordering matters when a harness derives its control from the code under test: with the control built first, a shipped-bash-already-regressed mutant made control construction impossible and got reported as 'untrustworthy' instead of 'the trap is present'. Decide the verdict first; let control failure only downgrade a pass.
  - Learning: A bash helper that toggles set -e leaves it toggled for its caller — the run-once helper had to use `|| status=$?` instead, or the second and third runs would have inherited errexit state from the first.
- 2026-07-31T17:14:26.311Z — loop iteration 6: Caught the 96-day prod freeze ending live mid-iteration, capturing the check's verdict on both sides of a real deploy, corrected the now-false 'green means broken' guidance in the eval and MANUAL, and closed step 5's last assumed link by verifying the ECS semantics its simulation encodes read-only against live AWS.
  - Change: Added --verify-shim-assumptions to tools/deploy-freshness-live-check.sh: observes read-only in the live account the four ECS behaviours the step-5 shim assumes (A0 family identity, A1 family-name lookup returns newest ACTIVE even when an older one is ACTIVE and the newest runs nowhere, A2 describe-services returns a revision-pinned ARN, A3 revisions contiguous and never reused), exiting 2 'not observable' rather than passing when no witness family exists; all five assertions mutation-verified
  - Change: Measured the check against live prod on both sides of a real deploy that landed at 11:06 MDT: 96d/exit 1 before, 0d/exit 0 after, all three cross-check legs agreeing at each reading
  - Change: Corrected the now-false 'a green run is the failure signal' guidance in both the E-7 eval file and MANUAL.md, re-basing step 1 on agreement with bin/prod-status rather than an expected exit code and promoting step 3 to the discriminating dispatch
  - Change: Recorded new eval sections: the freeze-ending natural experiment with CloudTrail timeline, the A0-A3 assumption-verification table, and the finding that the 2026-07-27 PRIMARY deployment was a force-new-deployment bounce of the same stale :62 rather than a deploy
  - Change: Marked MANUAL's step-5 registration entry as not worth running while prod is fresh (the trap only shows a gap difference against a stale prod) and updated its stale revision numbers from :62/:63 to :63/:64
  - Learning: The 96-day freeze ended at 2026-07-31 11:06 MDT while this eval was being run — prod now runs a same-day image and the check correctly reports exit 0. Any future iteration or operator working from the earlier notes will be working from inverted expectations.
  - Learning: A deployment timestamp is not a freshness signal: CloudTrail shows the 2026-05-03 and 2026-07-27 UpdateService calls both named the already-running :62 with zero RegisterTaskDefinition events in the 90-day window, so the service looked freshly deployed while being 96 days stale. Iteration 2's 'something re-deployed recently' puzzle was two force-new-deployment bounces.
  - Learning: Step 5's discriminating observation had a closing window nobody knew was closing: the family-shortcut trap can only produce a visible gap difference while the running image is stale, so iteration 5 captured it inside the final hour of a 96-day freeze. Re-running --simulate-newer-revision now still passes but proves much less.
  - Learning: An assumption a simulation encodes about an external API can often be observed in the account's existing state instead of asserted from documentation — palateful-migrator-prod already carried an ACTIVE revision nothing runs, which is precisely the divergence the shim fabricates. Look for the natural experiment before concluding a mutation is required.
  - Learning: Mutating a comparison rather than the data produces self-contradicting failure text ('resolved to :54, expected the newest ACTIVE :54'); the mutation still proves the assertion binds, but message quality can only be judged when the underlying data diverges.
- 2026-07-31T17:24:55.156Z — loop iteration 7: Split E-7 step 6 into gate and calendar halves and discharged the gate half with a new mutation-verified --verify-environment-gate mode that proves, from config plus 10 real ungated deployments, that declaring environment: production introduces no approval prompt.
  - Change: Added --verify-environment-gate to tools/deploy-freshness-live-check.sh: reads the environment name out of the workflow, asserts no protection rules or branch policy, finds real deployments into that environment and proves none ever sat in the 'waiting' approval state, and rejects behavioural evidence older than the environment's last config change; exits 2 'not observable' rather than passing when the environment is unreadable or unused
  - Change: Mutation-verified the new mode five ways (environment line deleted, environment renamed, wrong waiting-state pattern, forced required_reviewers rule, forced future updated_at) with each caught by exactly one check; fixed a real bug it exposed where a 404 error body on stdout was parsed as a protection-rule count
  - Change: Recorded actuals in the E-7 eval file: step-6 row upgraded from pending to 'no approval prompt PASS (observed), fires pending', a new G0-G3 observation-and-mutation section, and updated header and Result blocks
  - Change: Narrowed MANUAL.md's step-6 entry to the calendar half only, with the re-runnable gate command and the prediction that the first scheduled run (2026-08-01) will fail on credentials until this branch merges — still a valid half-witness that the cron fired
  - Learning: ci.yml's deploy jobs declare the same environment: production as the freshness check, so the repo already contains behavioural witnesses for the approval-gate question — today's deploy run 30646967338 alone supplied 8 ungated deployments. The natural-experiment pattern from iteration 6 applied to GitHub as well as to AWS.
  - Learning: GitHub's deployments API is the behavioural record for environment gating: a gated job's deployment sits in the 'waiting' state, so 'states never included waiting' distinguishes 'no rule was applied' from 'no rule is configured'. Job timings alone cannot — runner latency and a fast approval look identical.
  - Learning: Behavioural evidence about a policy needs a recency assertion against that policy's updated_at, or it rots invisibly: rules added after the newest witness would gate the next run while every past deployment still looks clean.
  - Learning: The workflow landed on main at 16:24 UTC on 2026-07-31, after that day's 15:00 UTC cron slot, so no scheduled run has ever fired; the first one (2026-08-01) runs main's pre-fix copy and will fail in configure-aws-credentials — which still witnesses that the cron fires unattended.
  - Learning: gh api writes its error body to stdout on 404, so `x=$(gh api ... 2>/dev/null || true)` silently assigns a JSON error payload; the failure branch must blank the variable or downstream parses report nonsense instead of 'unknown'.
