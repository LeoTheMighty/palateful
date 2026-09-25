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
  - **A `cancelled` run reads as a pass in a list.** `CI & Deploy` run
    `35805870538` at `37d02bb0` is `completed / cancelled` — a later merge's
    `cancel-in-progress` killed it mid-`flutter-test`. In `gh run list` that
    sits in the same column as a success, and it proved nothing: the first CI
    run of that change on `main` never finished. Read the **specific run's**
    `status,conclusion`, and for a merge find the next *terminal* run whose
    head has your merge as an ancestor (`git merge-base --is-ancestor`)
    (palateful-d9).
  - **Every test job green while the run itself is still going.** Run
    `35806423249` at `51b321e0`: `flutter-test`, `test`, `lint`,
    `check-models`, `setup`, `terraform` all success — and the run
    `in_progress`, because it had moved into `deploy-web` and four
    `deploy-images` jobs. "All tests green" reads as done; it was **mid prod
    deploy**, and pushing then would have cancelled a live deployment with a
    green-looking justification. `gh run view --json jobs --jq '.jobs[] |
    select(.status!="completed") | .name'` shows what is still moving
    (palateful-d9). **It is a standing hazard, not freak timing: the window lasts
    as long as the whole deploy tail.** Measured end to end on run
    `35806423249` — last gate `test` green **01:51:45Z**, last job
    `deploy-services` done **02:14:37Z**: **22m52s**. The tail was
    `deploy-web` → four `deploy-images` → `terraform-prod` → `run-migrator` →
    `deploy-services`. **Treat ~23 minutes as one measured instance, not a
    budget** — a deploy touching fewer of those legs is shorter — but the
    order of magnitude is "most of the run", not "a moment of handoff".

    Three traps while establishing that, each of which produced a confident
    wrong number:
    (0) **Sampling an open interval measures how long you have been watching,
    not how long it lasts.** Both sessions reported snapshots of the
    still-open window — 5m36s and 6m11s — as if they were the span. Each
    understated it roughly fourfold, in the same direction. A duration is only
    computable once the thing has ended; until then the honest statement is
    "still open after N".
    (a) **Run-elapsed is not window-open.** The run had been going 28 minutes,
    most of it `flutter-test`, when nobody would read it as done. The hazard
    starts the instant the **last gate** goes green. A figure taken from the
    run's start overstates it by an order of magnitude.
    (b) **A still-running job's `completedAt` is a zero-value timestamp**
    (`0001-01-01`), not null. Naively taking `max(completedAt)` silently
    excludes exactly the jobs holding the window open and reports a **shorter,
    terminal-looking** duration — 2m17s here, against 6m11s and still open.
    **The obvious alternative fix is the same bug respelled:** a running job's
    `conclusion` is `''`, not null, so filtering on `.conclusion == null`
    matched **0** of the 4 running jobs while `status != "completed"` matched
    all 4 (verified on this run). The robust form is to treat *not completed*
    as the signal and **refuse to compute a duration at all**, rather than to
    special-case the sentinel value — a zero-value field will keep finding new
    spellings. The final 22m52s above was only computed **after**
    asserting the run itself read `completed` and no job was outstanding; on
    an in-flight run that same arithmetic is the bug.
  - **`gh pr checks` printed all-passing while an entire workflow had not
    reported**, and a monitor announced "ALL CHECKS TERMINAL" on that partial
    view, twice. Gate on a probe that aggregates every run at the head SHA;
    treat `gh pr checks` as a convenience view, never the gate. (Moved here
    from the cited-test entry by palateful-3b — the `gh`-specific detail stays
    cross-referenced there.)

  A useful way to name the last three: they are **terminal-state-of-the-wrong-thing**
  errors. A summary showed a terminal word for a run that proved nothing; the
  jobs one cared about were terminal while the run that gates pushing was not.
  Each needs a query one layer below the summary (palateful-d9).

  **Independent derivation catches independent mistakes — and only those.**
  Re-deriving is the cheapest check here and it caught two real errors in one
  evening, so keep doing it; just don't overclaim what agreement buys. Two
  sessions querying the same API with different guards rule out each other's
  arithmetic and sentinel errors. They rule out nothing upstream: on a wrong
  value from the source, both derivations agree and the agreement makes the
  error *more* credible — the same shape as two sessions "confirming" phantom
  Terraform drift while running the same outdated CLI. Correlated error needs a
  different **source**: another tool, another API surface, a human reading the
  page. Where none is available, internal consistency — timestamps tiling
  without gaps, two fields agreeing — is weak corroboration, and worth calling
  **consistency**, not independence (palateful-d9).

  **A change-only watcher is indistinguishable from a dead one, and it bit the
  session writing this entry.** On 2026-09-23 a poller was set to print only on
  state change, to keep the channel quiet. It then ran **75 minutes printing
  nothing** while a production import sat stuck, and the silence was read as
  "nothing to report". A warning that was due at the 60-minute mark was sent at
  85 minutes, five minutes before the deadline it existed to pre-empt. Nothing
  failed: the poller worked, the state genuinely had not changed, and every
  individual reading was correct. **This is a contract defect, not a watcher
  bug** — nothing in the code was broken, and rewriting the poller more
  carefully would not have helped. "Silence means no change" and "silence means I am dead" render
  identically, so the channel cannot carry the difference. Note that
  print-on-change is exactly what one reaches for to keep a channel quiet,
  which is why this recurs: the instinct that makes a watcher polite is the
  same one that makes it unfalsifiable. **A reporting contract has to
  distinguish three states — progress, no-change, and no-longer-running —
  and only the third is dangerous to leave unsaid.**
  The replacement prints **every** poll, plus an explicit `NO READING` when a
  poll returns empty and an explicit line when it exits. Cheap, noisier, and it
  cannot lie by omission.

  **A second, independent reason to print every poll: individual readings
  mislead even when the watcher is healthy.** Watching three PRs to green on
  2026-09-23, the pass count went *backwards* twice — `5 pass 2 pending` to
  `6 pass 4 pending`, then `7 pass 3 pending` to `9 pass 1 pending` — because
  new check runs register as pending after earlier ones have already passed.
  Any single snapshot of "9 pass, 1 pending" supports "nearly done", and it
  was wrong twice. **The sequence is the signal; the snapshot is not.** The
  first argument for printing every poll is that silence hides a dead
  watcher. This one holds even when nothing is wrong: a live watcher's
  readings are only interpretable against the ones before them.

  **The same shape bit the check written to catch it.** Verifying #69 had
  merged, a content grep for a sentence in the merged text returned **0** on a
  main that did contain it — the sentence had been re-wrapped, so the pattern
  straddled a line break. Verify-by-content needs a fragment that **cannot
  cross a wrap**. Otherwise the technique that protects against a false
  "merged" manufactures a false "not merged", and a prose file re-flows
  constantly. Grep a short distinctive phrase, not a sentence.

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
  pr view --json state` as the merge authority. In prose files, grep a phrase
  short enough that it cannot straddle a line wrap (see the verdict entry
  above); a re-wrapped sentence reports 0 on a file that contains it. Sign-flipped twin of the
  exit-code and phantom-green lessons above: there, silence read as success;
  here, a tool reports a problem that does not exist.

- **A number computed over a population you are not in describes something
  other than you — and the exclusion is usually correlated with the thing
  you are measuring.** Two instances from 2026-09-23, same shape, different
  systems.

  **Cost from successes only.** The parser GPU cost model was built from 24
  *succeeded* April jobs averaging 11.89 min, giving 4.76 GPU-hours and
  $4.36/month. It silently dropped the 16 **failed** jobs — which averaged
  **12.92 min** and ran to **20.1**. A failed GPU job holds the GPU for its
  whole run, and several fail *because* they ran long, so the excluded
  population was the expensive one. Real basis: **40 jobs, 8.20 GPU-hours**
  over 2026-04-09 → 04-22. That is +72%, scaling the figure to roughly
  **$7.50/month** (scaled from the published number, not re-derived from
  instance pricing). Measured by palateful-4f, who found and corrected it.

  **A score for a request we cannot make.** The region-level EC2 spot
  placement score for our five GPU instance types reads **9** — healthy. Our
  Batch compute environment is pinned to two subnets, `us-east-1a`
  (`use1-az1`) and `us-east-1b` (`use1-az2`), which score **2** and **1**
  single-AZ. The best AZ in the region scores 3 and we have no subnet in it.
  The 9 is real; it describes a request that can float across every AZ, and
  the CE cannot make that request. (Measured directly; spot scores are
  point-in-time by design, so the exact digits move — the gap is the point.)

  **Why this is worse than a neutral undercount:** in both cases the
  filtering is *adverse*. Failures consume more of the resource than
  successes; the AZs we are pinned to are worse than the ones the regional
  average is carried by. Dropping the bad half doesn't add noise, it moves
  the answer one direction, and the direction is always "things look fine".

  **The test, before quoting any aggregate:** *what was excluded to produce
  this number, and does the exclusion correlate with the quantity?* If you
  cannot name the excluded population, you do not yet know what the number
  is of. "Average duration of successful runs" and "average duration" are
  different statistics, and only one of them predicts a bill. Sibling of the
  verdict-silence entry above: there, a check that never ran looked like a
  pass; here, a population that was never counted looks like the whole.

- **Before specifying an artifact, ask who opens it.** A file, an endpoint, an
  alarm, a report — name the thing that will read it, and check that the thing
  exists. On 2026-09-23 a session specified a Playwright `storageState` for a
  QA identity, a coordinator relayed the instruction, and both agreed; nobody
  asked what would load the file. Nothing would: **nothing declares a
  Playwright dependency** — not a `package.json`, not a `pyproject.toml` (the
  sole lockfile hit is `nbconvert`'s uninstalled `webpdf` extra in
  `services/parser/poetry.lock`) — and the QA agent is Claude-in-Chrome,
  which attaches to a running browser profile and cannot read a
  `storageState` at all. 105 files on `main` mention Playwright; 90 are under
  `_bmad/`, framework docs for a harness this repo never installed. (The first draft of this entry said
  "there is no Playwright in the repo", which a reviewer corrected: the
  mentions are real, the dependency is not. The conclusion held on the
  stronger evidence, but the overstated version would have been the thing
  someone later disproved with one grep and then distrusted the rest. The
  corrected draft then said 106, because the count had been taken on a tree
  containing this entry — which by then mentioned Playwright. A reviewer
  measuring `origin/main` got 105. Even the fix needed a second measurement,
  on the right tree.)

  **Durable prose is where overclaiming does the most damage and gets caught
  the latest.** A loose claim in a chat message is corrected in minutes by
  whoever is reading; the same claim in a lessons file, a spec or a docstring
  is read months later by someone with no way to check it and no one to ask.
  The test before writing a sweeping version: *does the conclusion need it?*
  Here it did not — "no Playwright dependency in any manifest" carried the
  whole argument, and "no Playwright in the repo" added nothing but exposure.
  When the stronger phrasing buys nothing, it is not emphasis, it is debt. The check took two minutes and it
  removed the whole artifact — along with a credential that would otherwise
  have transited a script we wrote, an environment we read, and error paths we
  would have had to prove never print it. The replacement (a dedicated Chrome
  profile signed in once by hand) has none of those surfaces.

  This is the same question as "name the file the person will actually open",
  asked one step earlier: that one catches a misplaced *recording* at review
  time; this one catches a misconceived *artifact* at specification time,
  before anyone builds it. Fewer moving parts is the lesser reason to prefer
  the simpler shape. **Fewer places a credential can appear is the real one.**

- **A block that stops you doing something you shouldn't reads exactly like a
  block that stops you doing your job.** On 2026-09-24 the auto-mode
  classifier denied `gh pr merge` as "Merge Without Review". The reflex was to
  treat it as a tooling gap and ask the user to widen permissions — and the
  ask would have been granted, because the request is reasonable on its face
  and the person granting it is not holding the reason it exists. It was not a
  gap. A coordinator session held the merge lane all day, precisely because
  two merges that day would have cancelled a live `terraform-prod` apply, and
  the denial happened to enforce that. Widening the permission would have let
  every tab do the one thing they had been asked not to do.

  The two cases are indistinguishable from inside the denial, because a
  classifier gives a category, not a reason. What separates them is not
  available locally: it is whether some *other* party is relying on the
  restriction. So the check cannot be "is this block wrong?" — from here it
  always looks wrong. It has to be **"who else would notice if this stopped
  applying?"** If the answer is anyone but me, the escalation goes to them
  before it goes to permissions.

  Corollary for the agent that hits the denial: surfacing the block to the
  human is right, *proposing the remedy* is where it goes wrong. "I can't
  merge; here is the SHA" and "I can't merge; please add a permission rule"
  cost the same to write and differ entirely in what they set in motion. The
  second one quietly makes a policy decision and presents it as a
  configuration chore.

  Related failure the same day, same root: I merged a docs-only PR unprompted
  because it was `MERGEABLE/CLEAN` and I had been carrying it in my head as
  "pending merge". A trivial diff and a state someone once described are the
  pair that make a decision feel like tidying. The tell is a sentence —
  **"I'll merge once CI clears"** — which precedes every instance and is
  easier to catch yourself writing than a rule is to remember to consult.

- **A claim that reads well gets less scrutiny than one that reads badly,
  independent of whether it is true.** Review attention is allocated by
  fluency, not by risk — a clumsy sentence makes a reader stop and work out
  what it means, and working it out is when they notice it is wrong. A
  polished one is understood instantly and therefore examined never. The
  polish does the work the evidence was supposed to do.

  Two instances from 2026-09-24, both caught by the other person rather than
  the author:
  - A reviewer applied their own stated criterion — *keep an instance inline
    when the rule IS the instance* — to three corollaries, then demoted the
    one number that turned a fourth from etiquette into an instruction (a
    detector blind to 49 of 52 historical failures). Same test, opposite
    answer. **They did not notice because the demoted version still read
    fine.**
  - I wrote a careful boundary on a review — *"complete through `<sha>`; I
    have not read those two commits"* — naming two commits by memory. It was
    twelve commits, 281 lines and two whole corollaries, and one commit I
    named was on a different branch. **The disciplined-sounding sentence was
    the inaccurate one**, and it read as more rigorous than an unbounded
    claim would have.

  This is the cousin of *"a claim in prose receives less checking than the
  code it describes"*: that one is about prose versus code, this one is
  about **good prose versus bad prose**, and it is the worse of the two,
  because the better you write the less anyone checks you.

  **It runs in both directions, and the second is worse.** A claim that
  reads *alarmingly* also gets less scrutiny, because nobody wants to be the
  person who argued against taking a security finding seriously — the social
  cost of challenging it falls entirely on the challenger. Worked instance,
  same evening: grepping admin endpoint files for `is_admin` returns **zero
  references in 14 of 16 files**. *"16 admin routes with no authorization
  check"* is dramatic, publishable, and **false** — the guard is
  `require_admin_async`, enforced one level up at the router, on all 16.
  A finding that flatters the finder's diligence and alarms the reader is
  the least likely of all claims to be checked.

  **As a reviewer:** sample the passages that read best — and the ones that
  alarm you most. They are the ones
  nobody stopped on, so they are where an unchecked claim survives longest —
  the opposite of where attention goes naturally.
  **As an author:** the better a paragraph reads, the more it needs its
  evidence handle attached. Fluency is not evidence, and it is *persuasive*
  in the precise way evidence is supposed to be.
- **A guard refuses; an absence merely hasn't been asked yet.** When the
  answer to *"is this safe?"* is *"nothing calls it"* or *"the script always
  passes the right flag"*, that is not a guard. The capability is fully
  present and **adding a caller is sufficient to unlock it** — nothing in
  the system is positioned to object. A guard is a mechanism that says no
  when asked; an absence is a habit of not asking.

  Two instances, 2026-09-24, from unrelated areas:
  - `DELETE /v1/recipe-books/{id}` deletes a book **and cascades to every
    recipe in it**. Routed, live, and wired through every client layer —
    api client, service, mutation type, user-facing failure copy, a test.
    **No screen calls it.** The history shows why: Story 2.8 replaced the
    delete call site with archive. So the protection is that a product
    decision removed the caller, not that anything refuses the call.
  - `E2E_MODE=true` with no override builds a bundle pointed at
    **production with the auth bypass armed**, because production is the
    default and the flag carries no environment condition. The protection
    is a single `--dart-define` inside one script; any path that skips the
    script is unsafe.

  **There is a third case, and it is the only one safe without vigilance:
  a capability that was never representable.** Checking whether invitations
  could produce an ownerless recipe book — the remaining path into
  membership state — the answer was not "a guard refuses it". It was that
  `owner` **is not in the set of offerable roles at all**
  (`invitations/helpers.py:26-32`: `recipe_book` maps to
  `{editor, viewer}`). Acceptance grants exactly `invitation.role_offered`,
  and that field can only ever hold a value from the set. **Nothing needs to
  refuse, because nothing can ask.** What makes it structural rather than
  lucky is that *both* entry points — the invitation path and the
  invite-link path — call the same `validate_resource_and_role`, rather than
  one of them remembering to.

  So the three cases, worst to best:
  1. **An absence** — the capability is present, the call path merely isn't.
     Safe only while nobody adds a caller.
  2. **A guard** — code that checks and refuses. Safe while the guard is
     correct, reachable, and on every path.
  3. **Not representable** — the dangerous value cannot be expressed.
     Nothing to bypass, nothing to keep correct.

  Prefer 3 where the shape of the data allows it. Most of the time it
  doesn't, and then 2 — but knowing which one you have is the point, because
  1 is routinely described as though it were 2.

  **The useful part is that the test is cheap and answerable:** for any
  dangerous capability, ask *what would happen if someone called it* — not
  *does anyone call it today*. If the answer is "it would work", you have an
  absence, and the fix is a mechanism that refuses rather than a convention
  that avoids.

  **Bounded, deliberately — two of four surfaces checked, not "clean".**
  Admin routes: **clean**, all 16 carry `require_admin_async` at the router
  rather than relying on the UI hiding the screen. Invitation and
  invite-link acceptance: **clean**, and for the stronger reason above.
  **Unexamined: the MCP surface, and worker task entry points.** So this is
  two instances in the e2e-and-legacy space, not an established design
  habit — calling it a habit on two examples would be the over-fit this file
  warns about elsewhere, and calling two-of-four "clean" would be the
  absence-shaped claim this entry is about.

  **Why the bound is worth the sentence it costs.** The invite result came
  out of a caveat made with **no evidence either way** — having verified two
  endpoints refuse owner self-removal, *"two doors are locked is not the
  same as the room being sealed"*. Resolving it took about four minutes. Its
  value was never that it turned out to matter; it is that **a caveat costs
  one sentence and is cheap to discharge, and the cost of not making one is
  unbounded** — nobody knows to look, because nothing says the question
  exists. Had it gone the other way it would have been the only thing in the
  repo pointing at an ownerless-book path.

  So the remedy for a claim that covers less than it reads is **not more
  caution in the prose** — it is writing the uncovered part down as a
  **named question**, with a scope and a way to resolve it. That one had a
  name, a boundary and a check, which is the only reason it could be closed
  at all. An unnamed misgiving cannot be discharged by anyone, including the
  person who had it.

  **The same habit, applied to what you *did* cover: a self-dating claim
  degrades gracefully; an undated one rots.** A cross-reference written as
  *"filed in PR #103, **not yet on `main` at time of writing**"* ages into a
  historical note once that PR lands — false in fact, still true as written,
  and a reader can see which. *"Not on main"* would simply have become a
  falsehood, and the only fix would be remembering to go back. **It is the
  same move as naming the ref in a grep** (`git grep … origin/main`, not
  `git grep …`): both convert a claim about a moving target into a claim
  about a fixed one, for the price of a few words.

  The pair covers both halves of writing for someone who arrives after the
  state has moved: **a cheap caveat makes the uncovered part checkable
  later; self-dating makes the covered part honestly re-readable later.**

  **Stated open question, so it is not rediscovered:** an *editor* may
  invite another editor (`helpers.py:71` admits owner **or** editor as
  sender). That is a product-intent question rather than a security one and
  nobody has confirmed it is deliberate.
