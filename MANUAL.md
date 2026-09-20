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
