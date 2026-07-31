# MANUAL — Things only you can do

## Imported from BMAD backlog (2026-07-27)

- [ ] **Play Console launch runbook** — execute `ANDROID.md` (single operator, Day 1 signup → Day 3 first tag). Code + store assets landed under `epic-android-play-console-launch` (apl-1..4); the Play Console account, listing paste-ins, Data Safety form, and tester recruitment are human-only steps. Source: legacy DEV.md "MANUAL DOCS" + epic-android-play-console-launch.
- [ ] **iOS share-extension ship steps** — execute `SHARE.md` (App ID + App Group + provisioning profile, Xcode signing for `PalatefulShare`, on-device happy-path validation, device matrix before next TestFlight). Code for sie-1..5 is on main. Source: legacy DEV.md "MANUAL DOCS" + epic-share-ios-extension.

## Filed from btri01 legacy triage (2026-07-27)

- [ ] **Read back the Auth0 app's Allowed Logout URLs** — needed to finish
  `debug/debug-lgort1-2026-07-27T17:41-auth0-logout-returnto-malformed.md`.
  In the Auth0 dashboard → Applications → "Palateful Mobile" → Settings →
  Application URIs, copy out both **Allowed Callback URLs** and **Allowed
  Logout URLs** verbatim. The code currently sends
  `com.palateful.app://auth.palateful.app/ios/com.palateful.app/callback`
  as the logout `returnTo`, while `auth0_flutter` registers
  `com.palateful.app://auth.palateful.app/ios/com.palateful.palateful/callback`
  (bundle id, not scheme, in the path). `docs/SETUP.md:97` claims the logout
  list is `com.palateful.app://logout-callback`, which matches neither — the
  doc is stale and the real list is the only way to know which URL the fix
  should send. No agent can read the dashboard.

- [ ] **Confirm a real push lands after the quiet-hours fix deploys** — the
  btri01 push-notification verdict rests on code + unit tests, not on a
  device. Two steps, both human-only: (1) run
  `DATABASE_URL=<prod-url> python services/api/scripts/inspect_user_push.py
  --id-or-email leonid@ac93.org` to confirm your row actually has an FCM
  token registered (the agent's prod-script runs are blocked by the
  permission classifier whenever the script text touches `push_tokens`);
  (2) after the next backend deploy, trigger a *non-forced* push in the
  evening — e.g. start a recipe import and let it reach `awaiting_review`
  around 5–8pm Denver. Before the fix that window was 100% suppressed, so
  it is the sharpest possible check. The admin "Send test push" button is
  NOT a valid check here: it passes `force=True` and bypasses the exact
  code path that was broken.

## Filed from 7c5cf2 / E-7 observation (2026-07-31)

- [ ] **E-7 step 5 — register a prod task-definition revision without
  deploying it, and confirm the reported gap does not move.** This is the
  load-bearing observation for `deploy-freshness.yml`: a check that resolves
  the task definition by *family name* returns the newest **registered**
  revision instead of the **running** one, so a frozen prod reads as fresh —
  green and blind, masking the exact failure the check exists to catch.
  Human-only because it mutates the production AWS account (the agent's
  `aws ecs register-task-definition` call was blocked by the permission
  classifier).
  - **⚠ Not worth running right now (2026-07-31).** The trap is "the newest
    *registered* revision masks an older *running* one", so it can only show a
    gap difference while prod is **stale**. The 96-day freeze ended at 11:06
    MDT today, so a registration now would show "gap unchanged" trivially —
    the same answer a broken check gives. The discriminating observation was
    taken at ~11:00, inside the last hour of the freeze (see the scope note).
    Revive this entry the next time prod goes stale; until then the offline
    self-test, which pins a 96d fixture permanently, is what carries the
    property. Note also that the revision numbers below have moved on: prod
    now runs `:63`, so a registration would create `:64`.
  - **Scope note (2026-07-31): most of this is already discharged.**
    `bash tools/deploy-freshness-live-check.sh --simulate-newer-revision`
    shims the single `describe-task-definition` answer a registration would
    change, passes every other call through to real ECS, and showed the
    shipped bash producing a **byte-identical** report before and after
    (`:62`, `c85e350d…`, 96d, exit 1) — while its built-in control, the same
    bash with the family shortcut reintroduced, reported the undeployed image
    as `Gap: 0 day(s)` / "fresh". So the check's *insensitivity* to a newer
    ACTIVE revision is proven against live prod. What this step still adds is
    one thing: confirming that a **real** registration actually creates that
    divergence — new revision becomes the family's newest ACTIVE while
    `describe-services` keeps returning `:62`. That is documented AWS
    behaviour and it is the assumption the simulation encodes. Run the
    sequence below if you want it observed rather than assumed; run
    `--simulate-newer-revision` first, since a failure there means the check
    itself regressed and no registration is needed to know it. **Update
    2026-07-31:** the ECS behaviour that assumption rests on is no longer
    assumed either — `bash tools/deploy-freshness-live-check.sh
    --verify-shim-assumptions` observes it read-only in the live account
    (family-name lookup returns the newest ACTIVE revision even when an older
    one is still ACTIVE and the newest runs nowhere — witnessed on
    `palateful-migrator-prod`, ACTIVE `:34` and `:54`; the service's ARN is
    revision-pinned; revisions are contiguous and never reused). All four
    checks passed. What is left for a real registration is the composition of
    those, in one API call.
  - Precondition captured 2026-07-31: family `palateful-api-prod` has
    exactly **one** ACTIVE revision, `:62`, and it *is* the running one
    (`describe-services` → `:62`), on image tag `c85e350d…` (2026-04-26).
    So the two resolution paths currently agree and the trap is latent —
    you have to create the divergence to see it.
  - Registration alone does **not** deploy anything; ECS only changes
    running tasks on `update-service`. Use tag
    `c2f7982c506beefbb9f41d141c6595abe19da540` — it is a real image already
    in ECR (pushed 2026-05-03, 89 days old) and a real commit on `main`, so
    even an unlucky concurrent deploy would ship something legitimate rather
    than an unpullable tag. It is *newer* than the deployed image, which is
    what makes the case discriminating: the shortcut would report 89d, the
    correct path 96d.
    ```
    export AWS_REGION=us-east-1
    ECR=592349850338.dkr.ecr.us-east-1.amazonaws.com/palateful/api
    aws ecs describe-task-definition \
      --task-definition arn:aws:ecs:us-east-1:592349850338:task-definition/palateful-api-prod:62 \
      --query taskDefinition --output json > /tmp/td62.json
    jq '{family, taskRoleArn, executionRoleArn, networkMode, containerDefinitions,
         volumes, placementConstraints, requiresCompatibilities, cpu, memory,
         runtimePlatform} | with_entries(select(.value != null))
        | .containerDefinitions[0].image =
          "'"$ECR"':c2f7982c506beefbb9f41d141c6595abe19da540"' \
      /tmp/td62.json > /tmp/td63.json
    # Baseline BEFORE registering, so "unchanged" is a comparison, not a memory.
    bash tools/deploy-freshness-live-check.sh    # expect :62, c85e350d…, ~96d, exit 1

    NEW=$(aws ecs register-task-definition --cli-input-json file:///tmp/td63.json \
            --query taskDefinition.taskDefinitionArn --output text)

    # THE OBSERVATION: identical output. Any mention of :63, of c2f7982c…, or a
    # gap near 89d is the family-shortcut trap, i.e. the check is green-and-blind.
    bash tools/deploy-freshness-live-check.sh

    aws ecs deregister-task-definition --task-definition "$NEW"   # ALWAYS clean up
    bash tools/deploy-freshness-live-check.sh    # confirm you're back where you started
    ```
  - The live check runs the workflow's own bash, extracted from the workflow
    YAML, so this observes the shipped logic without needing the workflow
    merged or dispatched — this step is **not** blocked on the merge, only on
    the prod mutation. Repeat via `gh workflow run` afterwards if you want the
    Actions-side confirmation too, but the discriminating evidence is above.
  - **Deregister when done.** Leaving `:63` ACTIVE means the next
    `deploy-services` run (which resolves by family, correctly, for its own
    purpose) would ship that older image. Revision numbers are never reused,
    so after cleanup the family is byte-identical to how you found it except
    that the next terraform apply writes `:64`.
  - Then record the actual in
    `_devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md`
    (step 5 row) and tick the AC in
    `dev/dev-7c5cf2-2026-07-31T10:24-rsh108-follow-up-run-the-e-7-observation-protocol.md`.
  - Regression coverage already exists offline:
    `tools/deploy-freshness-self-test.sh` (CI `lint` job) models this exact
    scenario against a mocked ECS and was mutation-verified to fail when the
    family shortcut is reintroduced. That guards the code between
    observations; it does not substitute for this one.

- [ ] **E-7 steps 1/3/4 — re-dispatch `deploy-freshness` once this branch is
  on `main`.** Blocked purely on the merge, not on a human judgement: the
  first dispatch (run 30647079681) died in `configure-aws-credentials`
  because the job omitted `environment: production`, and `gh workflow run`
  always uses the definition at the *pushed* ref, so the fix cannot be
  exercised before it lands. All three are one command each.
  **Scope note (2026-07-31):** the *measurement* half of all three is already
  discharged — `bash tools/deploy-freshness-live-check.sh [--synthetic-gap-days N]`
  ran the same extracted bash against live prod and produced 96d/exit 1,
  8d/exit 1, 1d/exit 0, 7d/exit 0. What these dispatches add is the
  *mechanism*: environment-scoped credentials resolving inside Actions, and
  `inputs.synthetic-gap-days` surviving GitHub's expression layer. If a run
  below disagrees with those numbers, the difference is in the mechanism, not
  in the check's logic — start at the `configure-aws-credentials` step and the
  `SYNTHETIC gap of Nd` line, not at the bash.
  **⚠ Expectations changed at 2026-07-31 11:06 MDT — the 96-day freeze ended
  mid-observation** (real deploy of `848311af`; the check went from
  `Gap: 96 day(s)` / exit 1 to `Gap: 0 day(s)` / exit 0 six minutes later).
  Earlier drafts of this entry said step 1 MUST FAIL. That was true only while
  the freeze was live. **Judge step 1 by agreement, not by exit code:** run
  `bash bin/prod-status` first, and the dispatch must report the same tag and
  the same age. A disagreement is the finding; a pass on freshly deployed prod
  is correct. Step 3 is now the discriminating dispatch, because it forces a
  failure on demand regardless of prod's state.
  ```
  # Step 1 — real measurement. Must AGREE with bin/prod-status and
  # `git log -1 --format=%ci <tag>`, whatever it reports. (Green is a valid
  # result now that prod is fresh; it was the failure signal only during the
  # freeze.)
  bash bin/prod-status            # get the truth first, then compare
  gh workflow run deploy-freshness.yml --ref main
  # Step 3 — synthetic gap over the threshold. MUST FAIL, and the log must
  # say "SYNTHETIC gap of 8d" (not prod's real age) or the input never landed.
  # This is the discriminating one: it must fail even though prod is fresh.
  gh workflow run deploy-freshness.yml --ref main -f synthetic-gap-days=8
  # Step 4 — synthetic gap under it. MUST PASS. Note this is now weaker than
  # it was: with prod fresh, a run that ignored the input entirely would also
  # pass, so step 3 carries the proof that the input lands.
  gh workflow run deploy-freshness.yml --ref main -f synthetic-gap-days=1

  gh run list --workflow=deploy-freshness.yml --limit 5
  gh run view <id> --log | grep -E 'Running task definition|Deployed|Gap:'
  ```
  - Step 2 is then free: cross-check step 1's `Gap:` against
    `bin/prod-status` and `git log -1 --format=%ci <tag>`. Expect an
    off-by-one across a UTC midnight — the gap is a floor-divided age, so
    95d and 96d are the same observation, not a disagreement.
- [ ] **E-7 step 6 — the morning after the merge, confirm the 09:00 MDT run
  *fired*.** Calendar-time only; nothing to set up.
  ```
  gh run list --workflow=deploy-freshness.yml --event=schedule --limit 3
  ```
  **Scope — only the firing itself is still owed.** Everything around it is
  observed, and both checks are re-runnable in seconds with no AWS:
  ```
  bash tools/deploy-freshness-live-check.sh --verify-environment-gate   # no approval gate
  bash tools/deploy-freshness-live-check.sh --verify-schedule-fires     # nothing blocks the cron
  ```
  The first (2026-07-31): `production` has `protection_rules: []` *and* the 10
  most recent real deployments into it — 8 from that day's deploy run
  30646967338 — went `queued` → `in_progress` in 1–8 s with zero `waiting`
  states. The second (2026-07-31): the workflow is registered and `active`
  (not auto-disabled), its `0 15 * * *` cron is on `main` — the only branch
  GitHub schedules from — and this repo's scheduler produced **54 unattended
  `event: schedule` runs over 94h, none gated, longest silence 3.4h**, well
  inside E-7's 24h threshold.

  ⚠ **Record the actual UTC time the run lands — do not just confirm "it ran
  at 09:00".** Those 54 witness runs all belong to `devx-promotion.yml`, whose
  cron is `0 0 31 2 *` — an expression that matches no real date — yet it fires
  every 1–3.4h. Whatever schedules workflows in this repo is not following the
  cron as written, so the *time* of the freshness run is a genuine unknown that
  only this observation can settle. Its *frequency* is what E-7's threshold
  needs, and that is already measured.

  Its conclusion depends on prod's actual freshness, not on a fixed
  expectation: `success` while prod is current (it has been since 2026-07-31
  11:06 MDT), `failure` once a real gap opens past 7 days. Do not read
  `success` as "the check is broken" — that inversion was only valid during
  the freeze.

  **If you look before this branch merges:** the copy of the workflow on
  `main` still predates the `environment: production` fix, so the first
  scheduled run (earliest 2026-08-01, since the workflow landed at 16:24 UTC
  on 2026-07-31 — after that day's 15:00 UTC slot) will die in
  `configure-aws-credentials`. That failure is still a useful half-witness:
  a run that fires and then fails proves the cron fired unattended. What it
  cannot show is the fixed job succeeding.

  A `waiting` status means someone added a protection rule to the
  `production` environment since 2026-07-31; the check is then blind to
  unattended freezes, and the fix is to exempt this job or move the AWS
  secrets to repo scope. `tools/deploy-freshness-self-test.sh` pins the cron
  and the `environment:` declaration on every PR, but it cannot observe a rule
  added on the GitHub side — `--verify-environment-gate` can, and this run
  is the backstop.

  **No run at all** (not even a failing one) means the workflow itself is not
  being scheduled. Re-run `--verify-schedule-fires` first: it distinguishes the
  three causes — GitHub auto-disabled the workflow for repo inactivity (S0,
  fix: `gh workflow enable deploy-freshness.yml`), the cron is not on the
  default branch (S1), or the repo's scheduler has gone quiet generally (S2/S3).

## /devx-init deferred work

- [ ] **devx-init: supervisor-install-deferred** — OS-supervisor install deferred by non-interactive `devx init`
  Bare `devx init` never installs launchd/systemd/Task Scheduler units
  unattended. To install the manager/concierge supervisor, run the
  interactive `/devx-init` flow (or see docs/SETUP.md). Until then,
  `devx manage` / `devx loop` run only while you start them yourself.
  Filed: 2026-07-27T16:00:08.032Z  <!-- devx:init-failure:supervisor-install-deferred -->

## Cross-repo work awaiting a commit

- [ ] **arci1 — commit the `await-remote-ci` fix in `~/personal/devx`** (filed
  2026-07-27). `debug/debug-arci1-*` is filed in *this* repo, but the buggy
  code is the `@devx/cli` package: `src/lib/devx/await-remote-ci.ts` plus its
  two test files. Those edits are sitting **uncommitted on `main` in
  `~/personal/devx`** — this repo's worktree can only carry the
  `.claude/commands/devx.md` half of the change. Someone has to branch,
  commit, and PR them there.
  - Files changed: `src/lib/devx/await-remote-ci.ts`,
    `src/lib/loop/tail.ts` (comment only),
    `test/await-remote-ci.test.ts`,
    `test/devx-await-remote-ci-cli.test.ts`, `.claude/commands/devx.md`,
    `skills/devx.md` (the latter is generated — `npm run sync:skills`).
  - `npm test` was run there and is green — re-run 2026-07-27 after the
    change was complete: **120 files / 2350 tests passed**, exit 0 (that
    script also runs `npm run build` and `tsc --noEmit`).
  - Live check against the commit from the spec (`408aeaf` on
    `feat/dev-rsh101`): the probe now returns
    `{"conclusion":"failure","workflowName":"devx-ci"}` where it used to
    return `{"conclusion":"success","runId":30296754787}`. The all-green
    sibling commit `f7a8ab4` still returns `success`, so this is not a
    blanket red.
  - **Re-running that live check:** `feat/dev-rsh101` was deleted locally
    after the rsh101 merge, so the CLI form
    (`devx devx-helper await-remote-ci feat/dev-rsh101 --once`) now exits 2
    at stage `git-rev-parse` — the branch ref no longer resolves. The runs
    still exist on the remote, so pin the sha through the library instead
    (read-only; no branch or worktree changes):
    ```
    node --input-type=module -e '
    import { probeRemoteCi } from "/Users/leonidbelyi/personal/devx/dist/lib/devx/await-remote-ci.js";
    const r = await probeRemoteCi("feat/dev-rsh101", {
      repoRoot: "/Users/leonidbelyi/personal/palateful",
      headSha: "408aeafb53de10e3bebcf018ca42f36868b1e620",
    });
    console.log(JSON.stringify(r));'
    ```
    Verified again this way on 2026-07-27 against the rebuilt `dist/`:
    `408aeaf` → `failure` / `devx-ci` with `runs` naming both workflows;
    `f7a8ab4` → `success`.
  - Note `npm test` runs `npm run build`, so `~/personal/devx/dist/` — which
    the globally-linked `devx` binary executes — **already has the new
    behaviour** even though the source is uncommitted. Reverting the source
    without re-running `npm run build` would leave the two out of sync.
  - `.claude/commands/devx.md` is the source of truth for the skill body;
    `skills/devx.md` is a generated mirror (`sync-skills.mjs` copies
    commands → skills, and a drift-guard test fails if you edit the mirror).
    This repo's `.claude/commands/devx.md` is a copy of that file with a
    `<!-- devx-skill ... -->` banner prepended.
