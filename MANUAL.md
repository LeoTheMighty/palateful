# MANUAL — Things only you can do

## Imported from BMAD backlog (2026-07-27)

- [ ] **Play Console launch runbook** — execute `ANDROID.md` (single operator, Day 1 signup → Day 3 first tag). Code + store assets landed under `epic-android-play-console-launch` (apl-1..4); the Play Console account, listing paste-ins, Data Safety form, and tester recruitment are human-only steps. Source: legacy DEV.md "MANUAL DOCS" + epic-android-play-console-launch.
- [ ] **iOS share-extension ship steps** — execute `SHARE.md`. **Partially done as of 2026-09-20 — do not re-do §1.** Per-part status, each with its evidence:
  - [x] **App ID `com.palateful.palateful.share`** (`SHARE.md` §1a) — Leo read Apple Developer → Identifiers on 2026-09-20; present.
  - [x] **App Group + distribution profile** (`SHARE.md` §1b–1c) — *inferred, not directly read*: App Store Connect is at build 88 and `PalatefulShare.appex` has been in Runner's Embed App Extensions phase since `0a93369e` (2026-04-18), so those archives signed the extension and could not have without both. Believe Xcode over this line if they disagree.
  - [ ] **Xcode signing check on both targets** (`SHARE.md` §2) — still real, and cheap.
  - [ ] **On-device happy-path validation from Safari** (`SHARE.md` §3) — still real; no build has been on a device since the beta expired.
  - [ ] **Device matrix before the next TestFlight submission** (`SHARE.md` §4) — still real.

  Code for sie-1..5 is on main. Row left open because three of five parts genuinely remain. Source: legacy DEV.md "MANUAL DOCS" + epic-share-ios-extension; status refreshed from `dev/dev-tfship1-2026-09-20T11:30-ios-testflight-shortest-path.md`.

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

- [x] **E-7 steps 1/2/3/4 — DONE 2026-07-31, no merge required.** This entry
  said the dispatches were "blocked purely on the merge" because
  `gh workflow run` resolves the definition from a *pushed* ref. True, but
  `--ref` accepts **any** pushed ref — and the loop pushes the WIP branch every
  iteration, so the fixed workflow was dispatchable all along. (Only
  `schedule:` is default-branch-only.) All three ran on `feat/dev-7c5cf2`:

  | Run | Input | Result |
  |---|---|---|
  | 30652052889 | none | success — `:63` / `848311af…` / `Gap: 0 day(s)`, matching `bin/prod-status` and `git log` (step 2) |
  | 30652140468 | `synthetic-gap-days=8` | failure — `SYNTHETIC gap of 8d`, `::error::…8 days old` (the input crossed GitHub's expression layer) |
  | 30652190943 | `synthetic-gap-days=1` | success — `SYNTHETIC gap of 1d`, `Prod image is fresh (1d <= 7d)` |

  Environment-scoped credentials resolved on a non-default branch (run
  30647079681's `configure-aws-credentials` failure is fixed), and the three
  runs' `production` deployments never entered `waiting`. Full write-up in
  `_devx/workstreams/rotation-self-heal/evals/E-7_deploy-freeze-visibility.md`
  ("The dispatch did not need the merge"). **Nothing to do here.**

  To re-run any of them later (e.g. after a workflow change), the recipe still
  works from any pushed branch — judge step 1 by *agreement* with
  `bash bin/prod-status`, not by exit code (a pass is correct now that prod is
  fresh; "green means broken" expired when the 96-day freeze ended at
  2026-07-31 11:06 MDT). Step 3 is the discriminating one — it must fail even
  against fresh prod, and its log must say `SYNTHETIC gap of 8d` rather than
  prod's real age, or the input never landed:
  ```
  bash bin/prod-status            # get the truth first, then compare
  gh workflow run deploy-freshness.yml --ref <your-pushed-branch>
  gh workflow run deploy-freshness.yml --ref <your-pushed-branch> -f synthetic-gap-days=8
  gh workflow run deploy-freshness.yml --ref <your-pushed-branch> -f synthetic-gap-days=1

  gh run list --workflow=deploy-freshness.yml --limit 5
  gh run view <id> --log | grep -E 'Running task definition|Deployed|Gap:|SYNTHETIC'
  ```
  Expect an off-by-one across a UTC midnight when cross-checking — the gap is a
  floor-divided age, so 95d and 96d are the same observation.
- [x] **E-7 step 6a — the cron fires unattended. OBSERVED 2026-09-20, no
  merge required.** `main`'s pre-fix copy fired **50 scheduled runs** between
  2026-08-01T16:05:30Z and 2026-09-19T17:53:49Z, **zero** held for approval.
  The morning this entry was waiting for arrived 50 times while the branch sat
  unmerged. Re-check with:
  ```
  gh run list --workflow=deploy-freshness.yml --event=schedule --limit 60 \
    --json createdAt,conclusion
  ```
- [x] **E-7 step 6b — CLOSED 2026-09-20. The check measured prod for the
  first time in its existence.** Run
  [35528125176](https://github.com/LeoTheMighty/palateful/actions/runs/35528125176)
  fired unattended at **18:09:04Z**, authenticated, and reported:
  ```
  Running task definition: .../task-definition/palateful-api-prod:63
  Deployed commit: 848311af 2026-07-31 10:24:08 -0600
  Gap: 51 day(s); threshold: 7 day(s).
  ::error::Prod is running an image 51 days old (threshold 7d)
  ```
  The 50 firings before it all died in `configure-aws-credentials`
  (`Credentials could not be loaded`) because `main`'s copy had no
  `environment: production`. Run 51 reached ECS. The difference was PR #25.

  🔴 **THIS CHECK WILL REPORT RED ON EVERY FIRING, AND THAT IS CORRECT.**
  If a red `deploy-freshness` cron brought you here: the check is working.
  Prod is genuinely stale — the API has run task-definition `:63` since
  2026-07-31. It will keep reporting red until a change under `services/`
  actually deploys, because `services_to_build` comes up empty for PRs that
  only touch `app/`, `tools/`, `.github/` or docs. **Do not "fix" the check.**
  The fix is landing the deploy. See `rsh102` — the rotation fix must reach
  prod before the 2026-10-29 rotation.

  ⚠ **Do not wait for 09:00 MDT.** These 50 runs normally landed
  **15:27Z–20:44Z** (drift up to 5.7h past the declared `0 15 * * *`), with a
  one-day excursion on 2026-08-28 to 00:19Z and 23:58Z. Check "a run landed in
  the last 24h", never the hour. Note the new 03:00Z slot means the next
  firing after merge may arrive sooner than 15:00Z.
  ✅ **The 24h-threshold breach is fixed in this same branch.** The measured
  interval was **18.3h–31.9h**, and **25 of 49 intervals exceeded 24h** — the
  breach was routine, not a single bad run. Leo chose to
  tighten the schedule rather than loosen the assertion, so the workflow now
  declares two slots 12h apart (`0 15 * * *` + `0 3 * * *`) and the self-test
  asserts the worst nominal gap is ≤12h instead of pinning a literal cron
  string. Note the `--verify-schedule-fires` OK below is still measured over
  the *repo-wide* scheduler (~88% `devx-promotion.yml` at 1–3h), so it does
  not bind to this workflow — read the per-workflow numbers, not that line.
  **Scope — the surrounding checks stay re-runnable in seconds with no AWS:**
  ```
  bash tools/deploy-freshness-live-check.sh --verify-environment-gate   # no approval gate
  bash tools/deploy-freshness-live-check.sh --verify-schedule-fires     # nothing blocks the cron
  ```
  The first (2026-07-31): `production` has `protection_rules: []` *and* the 10
  most recent real deployments into it — 8 from that day's deploy run
  30646967338 — went `queued` → `in_progress` in 1–8 s with zero `waiting`
  states. Strengthened later that day by **this workflow's own** three dispatch
  deployments (5695703361 / 5695719549 / 5695728778, from runs 30652052889 /
  30652140468 / 30652190943): `in_progress` 3–8 s after creation, no `waiting`
  — so the "no approval prompt" half of step 6 is observed for the freshness
  job itself, not inferred from a sibling job that shares the environment.
  The second (2026-07-31): the workflow is registered and `active`
  (not auto-disabled), its `0 15 * * *` cron is on `main` — the only branch
  GitHub schedules from — and this repo's scheduler produced **54 unattended
  `event: schedule` runs over 94h, none gated, longest silence 3.4h**, well
  inside E-7's 24h threshold.

  ⚠ **Superseded 2026-09-20 by this workflow's own record.** The 54 witness
  runs above all belong to `devx-promotion.yml`, whose cron `0 0 31 2 *`
  matches no real date yet fires every 1–3.4h. That inference is no longer
  needed: `deploy-freshness.yml` now has 50 firings of its own, and they
  confirm the scatter directly (00:19Z–23:58Z) while contradicting the
  borrowed cadence figure (31.9h worst case, not 3.4h).

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

## Filed from bqa102 merge (2026-09-20)

- [ ] **Re-run the E-2 eval — `bqa102` merged with its headline AC unverified.**
  PR #12 landed the e2e harness (one-command lifecycle + three latent stack
  fixes), but **AC #6 — two consecutive one-command runs, 8/8 flows each — has
  never been observed green.** It is recorded unmet in
  `dev/dev-bqa102-2026-07-27T11:40-e2e-revival-one-command.md`. Phase 2 of the
  browser-qa-agent workstream is NOT complete, and `DEV.md` keeps its `[-]` row.

  **`DEV.md:44` warned against exactly this merge.** Verbatim, the row read:
  > `PR: https://github.com/LeoTheMighty/palateful/pull/12 (open — **do not merge as if E-2 is green**).`
  The merge went ahead anyway, on Leo's explicit merge-and-record decision of
  2026-09-20, as **harness-shipped and not as E-2 green**. AC #6 was merged
  **knowingly, without a fresh two-consecutive-8/8 verification.** If you are
  reading this looking for the real state: E-2 has never been observed green.

  **The blocker the spec originally named is gone.** `debug/debug-e2edwds`
  (dwds cannot attach against Chrome 150) was resolved 2026-07-30 by
  `dev/dev-fltup1` — Flutter 3.38.9 → 3.41.7 fixed it. Its successor
  `debug/debug-e2egetit` was resolved by PR #18. Both are `status: done`.
  So E-2 is **unverified**, not blocked: nobody has re-run it since the path
  cleared. It may now pass, or fail for a third reason — that is the open
  question.

  **What stops a re-run today is the local chromedriver, not the app.**
  `/opt/homebrew/bin/chromedriver` is a broken symlink to a removed Caskroom
  build (`151.0.7922.71`), and local Chrome is now **153.0.8010.48** (it was
  150 when this story was written). Install a matched, signed driver — the
  Homebrew cask is deprecated and is what rotted here:
  ```
  npx @puppeteer/browsers install chromedriver@153.0.8010.48
  # put the printed directory first on PATH, then:
  bash services/e2e/scripts/e2e_lifecycle.sh
  ```
  The preflight now fails fast and tells you this in <1s rather than after a
  full app build (fixed in the bqa102 merge commit). Then run the eval itself:
  ```
  cd _devx/workstreams && bash run-eval.sh browser-qa-agent/evals/e2_e2e_one_command.sh
  ```
  Do not re-author the eval — it was authored at RED and must stay untouched.
  Record the outcome in the spec's Status log either way; if it fails, file a
  debug spec for the *new* reason rather than reopening `e2edwds`.

---

## Re-check the `production` environment before adding any reviewer to it

`deploy-freshness.yml:69` declares `environment: production`, and that
declaration is load-bearing for PR #25's fix: the AWS secrets exist **only**
as environment-scoped secrets, so without it the job dies at
`aws-actions/configure-aws-credentials@v4` before it can measure anything.

**The guarantee rests on a setting nobody owns.** The comment at
`deploy-freshness.yml:63-68` records that the `production` environment
currently has no protection rules. If a reviewer is ever added,
`check-freshness` stalls waiting for approval and can no longer detect an
**unattended** freeze — which is the only kind it exists to catch.

**The detector must assert the environment has no protection rules, not
merely that the job declares the environment.** Declaring it is necessary
and not sufficient, and only that weaker half is currently guarded (by the
mocked self-test at `ci.yml:162`, which uses a fake ECS and a backdated
sandbox repo — no AWS access, so it cannot exercise the credential path at
all).

Why this matters more than it looks: **the copy of this workflow on `main`
has never succeeded once.** Across its whole history — 54 runs — there are
51 runs on `main` and **0** successes; the only two successes were
`workflow_dispatch` runs on the unmerged fix branch `feat/dev-7c5cf2`.
Classified by failing step (palateful-0e, 2026-09-22): 49 scheduled runs
(2026-08-01 → 09-19) and 1 manual run (07-31) died at
`configure-aws-credentials`, upstream of any verdict; one scheduled run on
08-06 recorded no failed step and is unclassified. So those reds carried no
information: a red never meant "prod is stale", it meant "the check died." The 51-day deploy freeze ran its entire
course underneath a monitor that had never worked.

PR #25 is **verified** (2026-09-22). Every scheduled run since it merged
(09-20 18:09, 09-21 08:39, 09-21 19:55, 09-22 08:18) gets past credentials
and forms a real verdict; run 35704107068 logged `Deployed image:
…/api:848311af… Gap: 52 day(s); threshold: 7 day(s).` → exit 1. The
monitor now works — and is correctly reporting a stale prod **to nobody**,
because nothing in palateful pushes to a human (see `dev-obsgap1` G1/G3).

## dfrcp1 — subscribe to `palateful-prod-alerts` (blocks two detectors)

**Measured 2026-09-22:** the topic exists
(`arn:aws:sns:us-east-1:<account>:palateful-prod-alerts`, created by alrt1 #41)
and `aws sns list-subscriptions-by-topic` returns **empty**. Until someone
subscribes, every alarm publishes into a void — including the two dfrcp1 ships:

- deploy-freshness red verdicts (it has been correctly reporting a stale prod to
  nobody since 2026-09-20)
- the DB probe failing open (`/v1/health` returns 200 while it cannot confirm
  the database is healthy, so `curl -sf` and the container health check both
  pass — this alarm is the only thing that can ever report it)

**Do this (Leo, by hand — deliberately not in Terraform):**

```bash
aws sns subscribe --topic-arn arn:aws:sns:us-east-1:<account>:palateful-prod-alerts \
    --protocol email --notification-endpoint <your-address>
```

Then confirm the email. The address must not enter the repo, Terraform, plan
output or CI logs — this repo and its Actions logs are public. That is why
`modules/alerts` deliberately owns no subscription.

**Then verify both detectors, which nobody has done yet:**

1. `gh workflow run deploy-freshness.yml -f synthetic-gap-days=99` → expect an
   email, and the run red.
2. `aws cloudwatch set-alarm-state --alarm-name palateful-prod-api-fail-open
   --state-value ALARM --state-reason "dfrcp1 verification"` → expect an email.

A configured alarm that has never fired is not a verified one. If step 1 or 2
produces no email, the detector is not working, whatever the AWS console says.

## Verify the first `fixture time-travel` nightly run (filed by fxfuse, 2026-09-23)

`.github/workflows/fixture-time-travel.yml` landed with PR #54 and first fires
at **09:12 UTC**. It has never run in CI — its negative control has only been
proven on a laptop — so until someone reads the first run, "the check still
bites" is a claim, not a measurement.

```bash
gh run list --workflow "fixture time-travel" --limit 3 \
  --json status,conclusion,createdAt,url
```

Read the result by **which step** failed, because the two failures mean
opposite things and want opposite fixes:

- **"Time-travel the suite" fails** → a fixture is on a fuse. Some test's date
  will age out of a `DateTime.now()`-relative window. Triage it like any red
  test, but read `app/tool/time_travel_check.sh`'s header first: an assertion
  on an *absolute* date (or one whose interval crosses a DST boundary when
  shifted) fails here while a real clock advance would not, and that class gets
  a `// no-time-travel` tag rather than a "fix".
- **"Negative control" fails** → **the harness stopped detecting a frozen
  fixture.** Nothing is wrong with the fixtures; the check itself has gone
  blind, which means the green from the step above proves nothing. Fix the
  harness before trusting any subsequent pass. The job prints `::error::` lines
  saying exactly this.

The control re-freezes `_fixtureBase` in
`app/test/features/activity/imports_tab_test.dart` and asserts its regex
matched exactly once. If someone reshapes that anchor, the control throws
`assert n == 1` — which reads as a failure but is really "the control can no
longer find what it rewrites". That is the likeliest first-year breakage.
