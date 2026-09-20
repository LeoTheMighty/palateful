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
