---
hash: af8309
type: dev
created: 2026-07-31T11:38:28-06:00
title: "Continue 7c5cf2: rsh108 follow-up: run the E-7 observation protocol against live prod"
from: dev/dev-7c5cf2-2026-07-31T10:24-rsh108-follow-up-run-the-e-7-observation-protocol.md
status: ready
blocked_by: []
branch: feat/dev-7c5cf2
owner: null
---

## Goal

Continue dev/dev-7c5cf2-2026-07-31T10:24-rsh108-follow-up-run-the-e-7-observation-protocol.md from its pushed WIP branch — the loop split it at budget exhaustion (iteration budget exhausted (8 iterations without acs_met)).

## Acceptance criteria

- [ ] workflow_dispatch run against current prod reports the true gap, cross-checked against bin/prod-status and git log
- [ ] Synthetic gap > 7 days fails the run and < 7 days passes, via the synthetic-gap-days dispatch input
- [ ] Registering a newer ACTIVE task-definition revision without deploying it does not change the reported gap
- [ ] The scheduled 09:00 MDT trigger fires unattended with no approval prompt, confirmed the next morning after merge
- [ ] Actuals recorded in _devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md

## Carried forward

### State to trust

- WIP branch feat/dev-7c5cf2 is pushed to origin with 8 good iteration commit(s) — continue from its tip
- parent spec dev/dev-7c5cf2-2026-07-31T10:24-rsh108-follow-up-run-the-e-7-observation-protocol.md is superseded by this follow-up; its Status log (on the branch) carries the full iteration history

### Gotchas (save time — don't rediscover)

- The 'required-reviewer gate on environment: production' that justified omitting the environment was presumption, not fact — gh api shows protection_rules: [] and no branch policy, so declaring the environment costs nothing today; step 6 is now the canary for someone adding rules later
- The AWS secrets (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) exist only in the production environment scope — repo-level secrets are just the two Cloudflare ones — so any workflow needing AWS must declare environment: production
- Prod is genuinely frozen at c85e350d (95 days old, both api and worker services), so the post-merge real-measurement run must FAIL to be correct — a green run would indicate the check is broken
- gh CLI auth and local AWS admin creds both work from this environment, so dispatch-based protocol steps (1-4) are loop-runnable, not human-only as the spec's gotcha claimed; only step 6 (next-morning wait) truly needs calendar time
- The workflow fix cannot be live-tested pre-merge: gh workflow run --ref uses the definition from a pushed ref, and pushing is out of bounds for an iteration — steps 1/3/4 re-run must wait for the loop's merge tail
- Registering a task definition against the prod account is blocked by the permission classifier, so AC 3 is not loop-runnable at all — not merely blocked on merge like ACs 1/2/4. Iteration 1's learning that 'dispatch-based steps are loop-runnable' does not extend to prod mutations.
- Step 5 cannot be observed passively even with full AWS read access: the family has exactly one ACTIVE revision (:62) which is also the running one, so both resolution paths agree until someone deliberately registers a second revision.
- The newest image in ECR is c2f7982c from 2026-05-03 (89 days old) — image builds stopped around the same time deploys did, so there is no genuinely fresh image available to construct a <7-day synthetic revision from.
- The service's PRIMARY deployment was created 2026-07-27, only days ago, while its image is from 2026-04-26 — something re-deployed the stale task definition recently. Worth a look: it means the freeze is not simply 'nothing has run since April'.
- Extracting the workflow's bash out of the YAML at test time (indentation-based, no PyYAML — the lint job has no guaranteed poetry env) is what makes this guard trustworthy; a copied script would drift and go on passing against code that is no longer shipped.
- The prior guard had a real hole, not a theoretical one: renaming the workflow's env var while the run body kept reading the old name left all six behavioural cases green, because the harness supplies that variable itself. Any harness that injects an input it also claims to test cannot see the wiring that delivers it — assert the wiring separately.
- A dropped dispatch-input wire fails in a deceptive direction: the >7d case still fails (measuring real frozen prod) and the <7d case fails too, so the observer reads 'the check is broken' rather than 'the input never landed'. That is why the step-3 log must be checked for the literal 'SYNTHETIC gap of 8d' string, not just the exit status.
- actionlint's HEAD baseline for this repo is 5 findings (ci.yml x3, devx-promotion.yml x1, force-deploy.yml x1), not the 3 recorded in iteration 2 — iteration 2 appears to have counted only ci.yml. Future iterations should diff against 5.
- Nothing loop-runnable remains: ACs 1/2/4 are blocked on the merge (gh workflow run resolves the definition from a pushed ref) and AC 3 is a prod mutation the permission classifier blocks, so further iterations cannot advance any AC — the loop should halt and hand off to the MANUAL.md entries.
- The 'blocked on merge' framing conflated two different things: the measurement (shipped bash vs real prod) is testable anywhere AWS credentials exist, while only the mechanism (env-scoped credentials inside Actions, the unattended schedule, GitHub's expression layer) actually needs the push. Splitting them recovered four of the five owed observations pre-merge.
- Extracting the workflow bash into a shared module paid off immediately and unexpectedly — the same extractor that made the CI guard trustworthy is what made a live pre-merge check possible at all, because both must run the shipped code rather than a copy.
- The live check's exit code was initially ambiguous: extraction failure exited 1, the same code as 'prod is stale'. For a check whose failure mode is being green-and-blind, an infrastructure error that mimics a real signal is the same class of bug — hence the exit-2 split.
- Adding a real .py file to tools/ brings it into ruff's reach in a way the previous inline heredoc never was (3 findings on first write, now fixed); repo ruff runs via NX-affected so tools/ is not in the CI path, but anyone running ruff repo-wide would have hit them.
- The 'prod mutation, therefore human-only' framing was as soft as the earlier 'blocked on merge' one: a check that reads external state through a small, enumerable set of CLI calls can be observed under a simulated state change by shimming those calls, with everything else real. What stays owed is only the assumption the shim encodes about the external system's semantics — a much smaller claim than the whole step.
- A simulation-based observation needs a built-in control or it proves nothing: 'the report did not change' is exactly what an inert shim produces. Making the tool construct the regression it guards against, run it through the same shim, and refuse to pass unless the regression fires is what converts the simulation from suggestive to discriminating.

### Do NOT

- Do not recreate the parent's work — the WIP branch feat/dev-7c5cf2 already holds it
- Do not rewrite or force-push the WIP branch history

## Status log

- 2026-07-31T11:38:28-06:00 — created by devx split from `dev/dev-7c5cf2-2026-07-31T10:24-rsh108-follow-up-run-the-e-7-observation-protocol.md` (branch-handoff)
