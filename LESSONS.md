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
  environment it lies in five separate ways.** Over 2026-09-20/22 five
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
     for reading, because it produces no error at all, and a blank status reads
     as "fine" when skimming. (zsh's equivalent is lowercase `$pipestatus`.)
  5. **`;` where you meant `&&`, between a test and a commit.** `flutter test
     …; git commit … && git push` commits and pushes whatever the suite did —
     the status existed, was never consulted, and the result is a red branch
     rather than a wrong answer on screen (2026-09-22, impvis1, fab56b40: a
     fixture-date guard failure pushed, caught only when reading the log
     afterwards). The other four mislead you; this one ships. Gate the commit
     on the run — `cmd && git commit` — or capture the status and branch on it.

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

- **A spec written from a message thread is written from relayed context,
  and relayed context goes stale.** `ncfgverdict1` was filed asking for a
  `NOT_CONFIGURED` verdict to be *created*; it already existed, shipped by
  #52 — enum, return site, `degraded` rendering, and the CLI's exit-code
  reasoning all merged. Two peers had described the gap accurately when
  they described it; the source moved underneath the description. A
  reviewer caught one AC that contradicted the implementation, and opening
  the file showed the whole framing was stale, not one clause. Same family
  as the cited-test lesson above: a description of code is not the code.
  Fix: before filing a spec, open every file it names and read the current
  state, even when — especially when — the person who described it wrote
  it. Correct the framing, not just the clause the reviewer flagged, and
  say in the spec that the first draft was wrong so nobody implements
  against a premise that was never true. Twice in one day (2026-09-22).

- **The absence of a verdict reads as a verdict.** This is the umbrella over
  several entries here. A check that never ran, a query that matched nothing,
  a loop that iterated zero times and a detector nobody subscribed to all
  produce the same artifact as success: **silence, or a zero**. Nothing in the
  output says "I did not measure this", so a skim reads it as "measured, and
  fine". Over 2026-09-20/23 it cost this repo real time roughly a dozen times.

  Distinguish it from two neighbours, because merging them makes all three
  unactionable. **Wrong evidence** — a measurement on the wrong driver, a test
  that checks its own construction — is covered by the provenance entries
  (palateful-cc). **Provenance as proof** — a cited test trusted because
  someone said it passed — is the cited-test entry (palateful-3b,
  `fd732fab`). **This entry is the third case: no evidence at all, with the
  absence read as positive evidence.** Wrong-thing, said-so, and no-thing.

  Instances, each measured:
  - **An empty CloudWatch Insights result is not a zero.** A `parse`-regex
    query matched nothing; "0 password-authentication failures" read as good
    news. A positive control on a string known to be present is what exposed
    it — and the real count was 573,039.
  - **`terraform state pull` re-stamps the *local* CLI's version.** Asked who
    wrote prod state, it answered with my own version (1.4.2); the raw S3
    object said 1.16.3. A tool answering a different question than the one
    asked. Read the object, not the tool. This shipped a wrong claim into a
    merged spec before it was caught.
  - **A watcher loop that exhausts its iterations prints its trailing lines
    and no verdict.** Nearly reported a green SHA with nothing behind it, on a
    PR that was conflicting at that moment.
  - **A CloudWatch metric filter sees only log events**, so "no fail-open
    lines" and "no API at all" are the same picture: no datapoints. Under
    `treat_missing_data = notBreaching` the alarm stays green through a total
    outage (palateful-cc, found by 4f in review).
  - **An alarm with no subscriber.** Configured, wired, in OK state, and
    `list-subscriptions-by-topic` empty. Every dashboard reads "alarm
    configured"; it is operationally identical to no alarm, and **nothing
    anywhere reports it as wrong** (palateful-cc).
  - **A test that skips when its dependency is absent.** Stopping the local
    Postgres removes the measurement and the suite still prints *passed*.
    Skip-as-pass is the purest form, because pytest designed it to look benign
    (palateful-3b).
  - **A guard whose empty result and its failure produced the same exit
    code** — an empty `grep` piped into `while read` ran once with an empty
    value and set status 1 (palateful-3b).
  - **`gh pr checks` printed all-passing while an entire workflow had not
    reported**, and a monitor announced "ALL CHECKS TERMINAL" on that partial
    view, twice. Gate on a probe that aggregates every run at the head SHA;
    treat `gh pr checks` as a convenience view, never the gate. (Moved here
    from the cited-test entry by palateful-3b — the `gh`-specific detail stays
    cross-referenced there.)

  **The test, before believing any clean result: what does this print when the
  thing it measures never ran — and who receives that?** If the first answer
  is indistinguishable from success, it is not yet a check. If the second is
  "nobody", it is not yet a detector. The alarm-with-no-subscriber passes the
  first clause and fails the second.

  **The enforcement is cheaper than the reasoning: drive the check into the
  failure state *the test names*, not merely into some failure state.** A test
  can fail for a reason unrelated to its subject just as easily as it can pass
  for one, so "it goes red without the fix" is not enough — simulate the
  specific defect. On `impvis1`, five tests were called regression coverage and
  **only two actually failed without the fix**; the other three were guards
  that passed before it (palateful-79). Where a test passes for a reason
  unrelated to the thing it names, that is the neighbouring *wrong-evidence*
  mechanism rather than this one — see the provenance entries. A mutation test of one CI guard
  against ten planted violations caught four shapes it had silently missed,
  including the exact form the codebase already used (palateful-3b). Where the
  signal is *silence*, first show that silence is abnormal — treating missing
  data as breaching is only defensible after measuring that 288/288 five-minute
  buckets are normally populated (palateful-cc).

  The counter-example worth copying: 4f's cart verification reported its
  **denominator** — 3 cart loads, recorder demonstrably alive across those
  minutes — before claiming "0 `_TypeError` since the deploy". Forty minutes
  earlier the same sentence would have been worthless, because the denominator
  was zero.

- **`git cherry` and `git diff origin/main` both lie about a squash-merged
  branch, in the direction that makes you distrust a correct merge.**
  Cleaning up three merged worktrees on 2026-09-23, `git cherry origin/main
  <branch>` reported 2, 2 and 12 "unmerged" commits — for PRs that `gh pr
  view` showed MERGED — and `git diff origin/main --stat` showed thousands
  of deletions on each. Both are artifacts: squashing rewrites patch-ids so
  `cherry` cannot match the commits, and the diff was the worktree being
  *behind* main, not missing from it. Believe either one and you keep dead
  worktrees forever, or "restore" work that is already shipped. Fix: verify
  by **content** — grep main for the symbols, sections or file the branch
  added (`git show origin/main:<path> | grep -c <symbol>`) — and treat `gh
  pr view --json state` as the merge authority. Sign-flipped twin of the
  exit-code and phantom-green lessons above: there, silence read as success;
  here, a tool reports a problem that does not exist.
