# LESSONS — What devx has learned

<!-- devx-empty-state-start -->
> **What goes here:** one bullet per lesson. Written by LearnAgent (Phase 5)
> or by you (`devx lessons --add`). Consumed by ManageAgent + the user +
> the mobile app. Lessons that change behavior should also leave a memory
> entry; lessons here are durable, human-readable artifacts. This
> empty-state header auto-deletes once this file holds three or more
> items.
<!-- devx-empty-state-end -->


- **A stale `app/build/unit_test_assets` makes `flutter test` lie, at scale.**
  On 2026-09-20 a July shader bundle produced **94 false failures** locally on
  a tree CI reported green — every `tester.tap(...)` test died with
  `Asset 'shaders/ink_sparkle.frag' manifest could not be decoded:
  Unsupported runtime stages format version. Expected 1, got 0.` The failure
  text reads like ordinary fixture drift ("the row I expected isn't there"),
  and three of them had already been filed as a real bug (`imptb1`) and
  dispatched to an agent before being traced back to the bundle. Fix:
  `rm -rf app/build/unit_test_assets`. Triage rule: if the failure count
  tracks *tap-driven* tests, `grep -c ink_sparkle.frag` the run — if that
  equals the failure count, it is all environmental. Note `flutter --version`
  does **not** catch this: local was correctly pinned to CI's 3.41.7
  throughout, so the obvious check passes and proves nothing.

- **Verify after a destructive loop rather than trusting its exit code.**
  A loop that silently iterates zero times exits `0` and looks like a clean
  no-op. On 2026-09-20 a 13-item lock-release loop deleted nothing while
  reporting success: `for s in $VAR` does not word-split in zsh, so the whole
  list bound to `$s` as a single token and every file reported MISSING. The
  transferable part is the verify step, not the shell trivia — re-list the
  thing you meant to change and count it. The same discipline caught it that
  had already backed up all 19 lock files before touching them.

- **In a shared worktree, no `pull` / `checkout --` / `stash` / `clean` /
  branch switch without first checking `git status` for other tabs'
  uncommitted work.** Re-read-before-edit and diff-before-commit protect a
  *committed* row from being overwritten; they do nothing for an
  *uncommitted* one, which syncing destroys outright with no git copy to
  recover from. Instance: `dev-stalebk1` sat as a dirty `DEV.md` row plus a
  5080-byte **untracked** spec while this session was 4 commits behind a
  `main` whose incoming #12 also touched `DEV.md` — the natural fix
  (snapshot, sync, restore) would have eaten it silently. Compounding factor:
  the worktree carries untracked test junk (`services/api/test.db`,
  `coverage-reports/`, `test-reports/`, `tools/perf-budgets.yaml.bak`), which
  is what makes someone reach for `git clean -fd` and makes the destruction
  look routine. Six tabs share this one checkout.
  **A rule that requires vigilance is weaker than one with a command
  attached.** Run this against *current* `main`, not the main you branched
  from — it returns 0 when you are safe:
  ```
  git diff origin/main $(git merge-tree --write-tree origin/main <branch>) \
    -- DEBUG.md | grep -E '^[-+]- \[' | grep -vc <your-row>
  ```

- **Coordination that protects one invariant can quietly create the defect
  you are cleaning up.** On 2026-09-20 a session correctly stayed off
  `DEV.md` to protect another session's sync point; the cost was `fxfuse` —
  a story committed to `main` but invisible to `devx next` because it had no
  row, which is precisely the stale-bookkeeping shape `stalebk1` was filed
  about. Both decisions were right in isolation. The gap closed only because
  the session said out loud what it had chosen *not* to do. Name your
  omissions at handoff; they do not show up in any diff.

- **Write the check and the claim as two separate sentences.** Most of this
  repo's bookkeeping failures are one substitution: something true of a
  *proxy* read as the fact itself. "Present in the open-PR list" → "merged"
  (a wrong dispatch this session). "Saved a file in the main checkout" →
  not a push to `main` (killed CI run 35521385327 via a claim commit).
  "The lock is stale" → "the owner is gone" (devx's detector records the
  CLI's own PID, which exits on return). "`ci.yml` is green" → "the
  scheduled credential path works" (#25 — the only freshness reference in
  `ci.yml` is a *mocked* self-test; the real job lives in
  `deploy-freshness.yml` and never ran). And inside that last one, a second
  pair: "deploy-freshness is red" → "prod is stale", when the red meant the
  check died at credential load before forming any verdict at all. The check
  and the claim are one step apart, and nobody verifies the step.

- **A monitor isolated from one dependency it was designed to outlive is not
  isolated from the next one nobody thought of.** `deploy-freshness.yml`
  lives in its own workflow file on purpose — its header argues, correctly,
  that "the check shares its fate with the CI system whose silent breakage it
  exists to catch," so a red `ci.yml` must not be able to skip it. It then
  shared its fate with the credential scoping instead, and never succeeded
  once on `main` in 51 runs. The mitigation was carefully reasoned and aimed
  at the wrong failure mode. Ask what *else* the monitor depends on, and
  assert that it has actually produced a verdict recently — not merely that
  it ran.

- **Re-read the current state before applying a draft you wrote earlier.**
  Draft freshness is its own hazard, distinct from clobbering. The dangerous
  case is not overwriting a stale row with a current one — it is overwriting
  a **more current** row with a stale draft, where the resulting diff reads
  as tidying up. On 2026-09-20 this session had a prepared edit for
  `bqa102`: clear the dead blocker, move the row. Between drafting and
  applying, another session had already cleared the blocker, recorded the
  AC #6 debt, deliberately kept the row at `[-]` with the reason stated
  inline ("Row stays `[-]`; Phase 2 is not complete"), and found something
  the draft's author had not — the E-2 re-run is blocked on a local
  chromedriver that is a broken symlink to a removed Caskroom 151 build
  while Chrome is now 153. Applying the draft would have regressed a
  deliberate decision into what looked like progress.
  The defence is **not** the pre-commit assertion: that compares your tree
  to `origin/main` and would have passed, because the change really was
  yours and really was intentional. The only thing that catches this is
  reading the row as it stands now and asking whether your draft still
  describes an improvement. The longer a queue waits — and this one waited
  through a five-PR merge wave — the more of it has been overtaken.

- **An exit status you didn't capture directly is not a reading, and in this
  environment it lies in four separate ways.** Over 2026-09-20/21 four
  sessions each got a false or empty "pass" from the same family:
  1. **Piped `$?`.** `npm test | tail -20; echo "rc=$?"` reports `tail`'s
     exit. One session printed `REAL_EXIT=0` over eleven typecheck failures.
  2. **Unconditional echo.** `cmd | head; echo "typecheck ok"` prints "ok"
     whatever happened; there is no status in it at all.
  3. **Harness notifications report the last command.** A background task
     whose chain ends in `echo` is reported as "completed (exit code 0)" over
     a real failure.
  4. **`${PIPESTATUS[0]}` is bash-only, and the shell here is zsh**, where it
     expands to nothing and prints a blank `EXIT=`. This is the most dangerous
     of the four, because it produces no error at all, and a blank status reads
     as "fine" when skimming. (zsh's equivalent is lowercase `$pipestatus`.)

  Fix: put nothing between the command and its status —
  `cmd > log 2>&1; echo "X_EXIT=$?"`, or `cmd && echo ok || echo FAILED` —
  then grep the log's own summary line (`Test Files … passed`) as a second,
  independent signal. If the two disagree, trust neither until you know why.
  Knowing about the trap was not enough: one session had saved it to memory an
  hour before falling into it, and caught it only because reading the log had
  become a habit. The habit is the control; the knowledge is not.

- **A cited test is not evidence until someone has read it or watched it
  fail.** Both real finds in selfheal1 (2026-09-22) came from distrusting
  stated evidence rather than from reviewing the diff.
  1. **The spec's own measured claim was measured on the wrong driver.**
     rsh102 admitted `no password supplied` as an auth message. Against a live
     server, psycopg2 does emit it — and **asyncpg never does**: given no
     password it md5-hashes the empty string, so the server answers `28P01
     password authentication failed`, byte-identical to a real rotation.
     `/v1/health` runs asyncpg. Removing the message pattern therefore fixed
     the case only on the path nothing uses, and the spec's own named trigger
     could still drain prod. Mocks agreed with the spec; the drivers did not.
  2. **A test whose docstring named this exact guard could not fail.**
     `test_only_auth_failed_is_actionable` asserted
     `{v for v in ProbeVerdict if v is AUTH_FAILED} == {AUTH_FAILED}` — true
     by construction for any enum contents — under the docstring "guards the
     fail-open invariant against a careless enum addition". selfheal1 added a
     member to that enum and it stayed green. A test that cannot fail is worse
     than no test: it occupies the slot where a real one would go, and its
     name is load-bearing for everyone who greps instead of reading.

  The link between them is provenance reading as proof. "rsh102 measured
  this" and "rsh102 wrote that test for this purpose" both *sound* like
  verification. The author of this story cited the test to a peer as
  verification without opening it, and the peer nearly accepted it on that
  say-so; the peer opened it, and that is the only reason it was caught.
  Fix: before relying on a test, read its assertion, or mutate the thing it
  claims to guard and watch it go red. Before relying on a measurement, check
  what was measured — which driver, which environment, which code path.
  Replacements for a tautological test should ship mutation-verified, and the
  replacement should assert something a literal cannot satisfy on its own.

  3. **A guard asserting the wrong invariant is not a weaker guard — it is an
     obstacle.** The replacement written for (2) in dfrcp1 asserted "exactly
     one `ProbeVerdict` is compared against in `health_router`". That is not
     the invariant. selfheal1 correctly singles out `NOT_CONFIGURED` for a
     `degraded` **200** — still failing open, nothing replaced — so the guard
     went red on a legitimate change while still admitting the thing it
     existed to catch (a second verdict driving a 503 would have to be
     compared against too, and so would have looked identical). It was caught
     only by rebasing onto the branch it would have blocked. Fix: assert the
     **consequence**, not a proxy for it — "only `AUTH_FAILED` produces a 503"
     rather than "only `AUTH_FAILED` is mentioned", because the 503 is what
     replaces the task. Same root as (1) and (2): a proxy standing in for the
     fact, from the third direction — a measurement of the wrong thing, a test
     that checks its own construction, and now a guard aimed one level off the
     property it protects.

     The counter-example from the same story is worth keeping beside it,
     because it shows the discipline working: the fail-open phrase sweep in
     that PR derives its verdict set from the `ProbeVerdict` enum rather than
     a list, and passed unchanged against selfheal1's nine emitters and its
     new enum member. That design claim was made to a peer **before** the
     other branch existed and survived contact with it. Anchor a guard to the
     thing that changes, and it keeps working; anchor it to a restatement of
     the thing, and it breaks on the first correct change.

  4. **A test can exercise real production code, pass, and still measure
     something that could not have failed.** (acttab1, 2026-09-22, palateful-79.)
     A widget test pumped `ActivityScreen(initialTab: 'imports')`, then pumped
     `ActivityScreen()`, drove the counts and asserted the tab. It passed
     identically before and after the fix, while the commit message cited it
     as pinning the behaviour change. Flutter never remounted: both trees were
     `ProviderScope > MaterialApp > ActivityScreen` with the same runtimeType
     and null keys, so `Widget.canUpdate` held at every level — the Element
     was updated, the **State object reused**, `initState` never ran again.
     There was no second screen. The one screen still held
     `hasExplicitTab == true`, had registered no count listeners, and the
     counts fired into nothing.

     Generally: **re-pumping the same widget type with no distinguishing key
     does not give you a fresh `State`**, whatever the constructor arguments
     say. The null key is the load-bearing condition, measured with an
     isolated probe counting `initState` calls: same type and null keys,
     pumped twice → `inits=1`; same type with **distinct keys** → `inits=2`;
     two in one tree → `inits=2`. So plenty of legitimate re-pumps do remount,
     and distinct keys are the remedy rather than a coincidence. What stays
     suspect until checked is every test of the form "what happens when a
     second X mounts".

     **The tell was inside the passing run.** The helper was
     `_selectedTabs(tester).single`, and `.single` throws on more than one
     match. That it never threw proved exactly one TabBar was mounted, which
     proved the second screen did not exist. The disconfirming evidence was
     produced, printed nothing, and went unread — a green run's incidental
     facts are evidence too, and this class is caught by reading them rather
     than by adding another assertion.

  The spine of all four: **an instrument aimed at the wrong thing returns a
  real answer to a question nobody asked**, and a real answer is the hardest
  kind to doubt. The wrong driver, the self-satisfying assertion, the guard
  aimed one level off its property, the screen that was never rebuilt — in
  each, the apparatus worked and the aim was off. Two more from the same day,
  recorded here rather than as their own entry: a go_router test asserted on
  "the last build" while the old route rebuilds behind the new one in an
  `IndexedStack`, and so reported the **opposite** answer; and
  `terraform state pull` re-stamps the running CLI's version, so asking it who
  wrote state returns your own version (1.4.2 reported, 1.16.3 in the raw S3
  object) — that one reached a merged spec as a wrong claim.

  Fix, in the order that actually catches things: say out loud what the
  instrument would report if the thing you care about had never happened; if
  that is indistinguishable from the answer you just got, you have not
  measured it yet. Then read the incidental facts of the passing run, not only
  its verdict.

- **`gh pr checks <n>` can report every check passing while a whole workflow
  is still running.** On PR #52 it listed three checks (lint/test/coverage,
  all `pass`) and no pending rows, while `CI & Deploy` — the workflow that
  runs the Flutter tests and the prod Terraform apply — was still
  `in_progress` at the same head. A monitor watching `all(.bucket!="pending")`
  announced "ALL CHECKS TERMINAL" on that partial view, twice. Same family as
  the exit-status traps above: a summary line that describes less than you
  think it does. Fix: gate on a probe that aggregates **every run at the head
  SHA** (`devx devx-helper await-remote-ci`, which folds all workflows into one
  verdict), and treat `gh pr checks` as a convenience view, never as the gate.

- **Merging to `main` cancels whatever `main` is already running — including a
  `terraform-prod` apply mid-flight.** `ci.yml` keys `concurrency` on
  `refs/heads/main` with `cancel-in-progress: true`, so each merge kills the
  previous merge's run. Measured 2026-09-24: two merges eight seconds apart
  cancelled #96's `terraform-prod` at 19:53:45Z, before the Batch queue flip
  applied. The merges succeeded, the PRs read "merged", and the change they
  were carrying never reached production.

  **`mergeStateStatus: CLEAN` does not cover this.** It describes the PR
  against `main`; it says nothing about what `main` is currently running. The
  pre-merge check that does:

  ```bash
  gh api "repos/<owner>/<repo>/actions/runs?head_sha=$(git rev-parse origin/main)"
  ```

  If `main`'s tip has an `in_progress` run, wait.

  Two consequences that outlive the incident:

  1. **A merged PR is not a deployed PR, and the gap is silent.** A cancelled
     run is not a red run — nothing pages, nothing retries, and the PR page
     looks identical either way. After a merge that matters, verify the thing
     in production (`describe-services` for the running task definition, the
     deployed image tag against the merge SHA), not the merge.
  2. **The failure is in the lane, not in any one change.** Each merge is
     individually correct; the second is what destroys the first. So the check
     belongs to whoever holds the merge button for the lane, and it has to run
     *before* the merge — afterwards there is nothing to observe but a run that
     quietly stopped.

  This is the same family as the entry above, arrived at from the operational
  side rather than the instrumental one: a capability described (or acted on)
  at the moment it was *decided* rather than the moment it was *available*.
  The distance between those two is however long the lane takes, and every
  instance today lived in that gap — an alarm count stated before the apply, a
  deploy history stated from memory rather than from ECS, a cleanup script
  described as ready while its PR was still open, and this one, which was not a
  description at all but an action taken through the rule that exists to
  prevent it.
