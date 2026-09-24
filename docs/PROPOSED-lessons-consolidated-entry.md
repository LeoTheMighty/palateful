# Prepared LESSONS.md entry — one entry, corollaries (a)-(h)
# Owner: this session (pen taken at 0a's offer). For review by 0a and 3b.

- **A detector can look like coverage while providing none.** Configured is
  not working. Everything below is one shape: something reads as covered,
  and the reading is indistinguishable from real coverage.

  0a proposed the root as *"a green detector proves the detector ran, not
  that the thing it watches is healthy"*. That covers two of the three
  corollaries but not (b): `deploy-freshness` was **red** 52 times and
  still provided no coverage, because nobody heard it. The root has to be
  about **apparent coverage**, not about green, or the loudest instance
  falls outside it.

  **(a) A detector must be proven able to fail.** Drive it into the failure
  state once, deliberately.
  - `test_only_auth_failed_is_actionable` claimed to guard the fail-open
    invariant "against a careless enum addition" and **could not fail**:
    `{v for v in ProbeVerdict if v is AUTH_FAILED} == {AUTH_FAILED}` is
    true by construction. It was decorative through the exact event it
    existed for — selfheal1 adding `NOT_CONFIGURED`. (3b, #52.)
  - rsh102's credential probe **structurally could not observe the
    rotation it exists for**: a pooled connection stays authenticated, so
    the probe never sees the credential change.
  - An alarm that has never been in ALARM state is a *configured*
    detector, not a *verified* one. `set-alarm-state` costs one command.

  **(b) A detector's output must reach a human by a path independent of
  what it watches.** Mine, plus cc's half.
  - `deploy-freshness` announced its own death through the GitHub Actions
    UI — and Leo has Actions email notifications switched off
    deliberately. 52 failures against 2 successes, visible the whole time
    to nobody. Not inattention: **structure**. The sharper form: it isn't
    that the monitor's verdict was wrong for 51 of 52 runs — **there was
    no delivery path for any verdict, right or wrong.**
    See also the existing entry *"A monitor isolated from one dependency
    it was designed to outlive…"*, which reached (b)'s conclusion
    independently — *assert it has produced a verdict recently, not merely
    that it ran* — **before** anyone knew the notification path was off.
    Keep both: that entry carries a lesson this one doesn't, that the
    mitigation was **carefully reasoned and aimed at the wrong failure
    mode** (isolated from a red `ci.yml`, then sharing fate with the
    credential scoping). Two entries about the same workflow, neither
    stale.
  - A monitor must not depend on the thing it monitors. `error_logs` lived
    in the database that was refusing connections, so ~100 days of auth
    failures could not be recorded. `deploy-freshness` was isolated in its
    own workflow file *against a red `ci.yml`* — then died on the
    credential scoping it was never isolated from.
  - The test to run over any detector: **what does this need in order to
    work, and is that inside the blast radius of the failure it exists to
    catch?** Not "can the recorder fail" — every recorder can. (Applied
    loosely it condemns everything and decides nothing.)
  - Sometimes the answer is that the detector **structurally cannot** cover
    a case. Name and assign the gap; don't paper it. cc's #48 notify step
    cannot fire when AWS credentials are the failure, because publishing
    needs them — **49 of the 52** historical failures.

  **(c) A clean reading must be distinguishable from an empty one.** Assert
  non-zero input before believing a zero.
  - Four log queries returned 0 because the start timestamp was parsed as
    local and sat six hours in the future — the query matched nothing at
    all. Caught only because the stream list came back empty too. (0a.)
    *Listed here and deliberately not also in the exit-status entry: the
    same instance in two places is the duplication this consolidation
    removes, in miniature.*
  - Distinct from the existing entry *"An exit status you didn't capture
    directly is not a reading"*, and both should stay. That one is **the
    status you read is not the status of the thing** — piped `$?`,
    unconditional `echo`, shell plumbing. (c) is **the reading is empty
    and looks clean** — no input, rather than the wrong channel. Merging
    would give (c) four bash specifics that aren't about coverage, and
    strip that entry of the concreteness that makes it usable.
  - A guard reported "6 references, clean pass" while blind to the 16
    healthy ones: it counted only stale-*shaped* hits, so "nothing is
    stale" and "I matched almost nothing" were the same output.
  - A suite case wrote a fixture the guard could not see (`git ls-files`
    skips unstaged files) and **passed green while testing air**.
  - "0 cart errors since the deploy" was meaningless until the
    **denominator** moved: 0 errors over 0 cart loads is silence. It
    became evidence only at 3 loads / 3×200 / 0 errors, with 17 client
    rows in the same minutes proving the recorder was alive.
  - Fix: `tools/stale-pointer-check.py` prints what it scanned and **exits
    2 on an implausible count** rather than passing.

  **(d) Evidence must cover the path AND the input in use — not *a* path.**
  The tell is provenance standing in for scope: "rsh102 measured this"
  sounds like verification and never says *what was covered*.
  - Measured on an isolated pg16 (0a): `psycopg2` with **no** password
    emits libpq's `fe_sendauth: no password supplied`, `sqlstate=None`.
    **`asyncpg` never emits that string** — given no password it hashes the
    empty one, so the server answers `28P01 password authentication
    failed`, **byte-identical to a wrong password**. `/v1/health` runs
    asyncpg.
  - The measurement was correct, live and real. It covered *wrong
    password* on both drivers, and was then generalised to *missing
    password*, which it never touched.
  - **The cost, and it nearly shipped:** selfheal1 Case 1 proposes dropping
    the `no password supplied` pattern so an unset `DB_PASSWORD` stops
    causing a 503 loop. On asyncpg that changes nothing — the missing
    password still returns `28P01`, which rsh102's own narrowing treats as
    sufficient. A filed fix that would have looked right and changed
    nothing on the path that matters.
  - This is why (d) is its own corollary: nothing was green-by-construction
    (a) and no reading was empty (c). **(a) and (c) were caught by tooling;
    (d) reached a story's acceptance criteria and would have shipped.**
  - **"I measured it" has a hidden argument — *which tree, which
    environment* — and it defaults to whatever you are standing in.**
    (palateful-3b, who found it in their own correction.) Three layers in
    one paragraph: a sweeping claim (*"there is no Playwright anywhere in
    the repo"*); then the corrected claim, **measured on the wrong tree**;
    then the right number. The branch HEAD counted **106** files and
    `origin/main` counted **105** — and the 106th was **`LESSONS.md`
    itself**, which by then contained the word. *The entry doing the
    counting had entered its own count.*
  - **Even the fix needed a second measurement**, on a tree nobody had
    checked they were in. Being told "measure it" does not help; naming the
    ref does. Write `git grep … origin/main`, not `git grep …`.
  - Third layer, same shape one notch smaller: *"zero `package.json` files
    depend on it"* was **accurate and incomplete** — it never asked about
    Python. No `pyproject.toml` declares Playwright either, and the sole
    lockfile hit is `nbconvert`'s uninstalled `webpdf` extra. A true
    statement about one ecosystem, offered as a statement about the repo.

  **(e) A guard can enforce the *spelling* of a condition without enforcing
  its *presence*.** (palateful-0a.) `envspell1`'s CI gate greps for
  comparisons against `ENVIRONMENT`, so it catches a check written wrong
  and is **structurally blind to a check that isn't there**. The absent
  case is the more dangerous one: a misspelled check fails closed and gets
  caught, while an absent one is indistinguishable from code that never
  needed one.
  - Worked instance: sweeping for `e2e_test_mode` found four reads — three
    guarded by the environment predicate, one (`agent_loop.py:58`) with no
    environment condition at all. **The gate cannot see the fourth,
    because the thing it greps for is the thing that is missing.** Filed
    as `e2echat1` (#67).
  - Distinct from (a), and it does not collapse into it: (a) is a detector
    that can *never* fire. This is one that fires correctly across every
    case it can see, while a whole category sits outside its field of
    view. **A guard can satisfy (a) completely and still have this
    problem.**

  **(f) A post-change check needs a prior value, or it cannot fail.**
  (palateful-0e.) (c) is about a reading with no *input*; this is about a
  reading with no *contrast* — and it belongs to the verification layer
  rather than the detection layer.
  - Worked instance, 2026-09-23. Replacing a Batch compute environment
    mints a new ARN, and the job queue references environments **by ARN**.
    If Terraform doesn't rewire the queue in the same apply, order 2 points
    at a **deposed** environment and the fallback **silently does not
    exist**. The check "order 2 points at an on-demand CE with 5 types"
    returns **PASS either way** — because the deposed environment is also
    an on-demand CE with the same name shape. **The after-state alone
    cannot distinguish success from the failure.**
  - What made it a real check: 0e recorded the *old* ARN suffix
    (`…677700000002`) **before** the apply, so afterwards the new
    `…011700706000000001` proved the rewire. Both sessions then tested it
    as *set membership of each queue ARN against live CE ARNs*, so a
    deposed reference surfaces as unresolvable rather than as a
    plausible-looking name.
  - Rule: before a change, write down the value that will distinguish
    success from failure afterwards. If you can't name one, the check you
    are planning cannot fail.
  - **Generalised (palateful-3b): a review's strength is bounded by how
    checkable the baseline was, not by how carefully the reviewer read.**
    A "found nothing" over byte-exact replaced code is strong, because
    *stricter or looser?* is mechanically decidable; the same diligence
    against a fuzzy check replacing a fuzzy one, or a brand-new gate, buys
    almost nothing **and reads identically**. It explains two unrelated
    results from the same day: the asyncpg measurement mattered because
    the drivers were a checkable baseline and the spec's prose was not,
    and the tautological test survived because it had **no** baseline to
    be diffed against. Actionable half: **pin current behaviour in a test
    before changing it**, so a later review has something to diff.

  **(g) Verified the shape, never the capability.** Every check can be
  fail-capable, baselined and honest and still ask only whether the
  *configuration* is correct — never whether the account is *permitted to
  instantiate it*. (This session, corrected by the outcome.)
  - Worked instance, 2026-09-23. pcap1 added an on-demand GPU compute
    environment as a fallback for when spot has no capacity. It was
    planned, applied, matched against a pre-registered plan, and confirmed
    at 5 instance types, `max 8`, `ENABLED`/`VALID`, queue order 2.
    palateful-0e then **independently re-confirmed all of it against live
    AWS** and caught a real defect while doing so (the pool was narrower
    than spot's). Every check passed, twice, by two sessions.
  - The account's service quota `L-DB2E81BA` *"Running On-Demand G and VT
    instances"* is **0**, `adjustable: true`, and the quota-change history
    is **empty** — it has been 0 since the account was created. **The
    fallback was structurally incapable of launching a single instance from
    the moment it was written**, and it was the thing Leo's imports were
    waiting on. (Independently re-verified by 0a from the live account.)
  - **What made checking feel unnecessary: the adjacent quota was fine.**
    `L-3819A6DF` *"All G and VT Spot Instance Requests"* is **32**. Two
    near-identically named GPU quotas, one healthy and one zero — so
    anyone asking *"do we have GPU quota in this account?"* would find a
    reassuring number and stop. The reassuring reading was **real**; it
    just answered a different question. That is the trap's actual
    geometry, and it generalises past AWS. (0a.)
  - Sharper than *"nobody checked"*: **someone plausibly did check, and got
    a true answer to the wrong question.** (41.) Pair this with the
    corollary's headline — *verified the shape, never the capability* is
    the same failure seen from the other side. One says the check was at
    the wrong altitude; this says the check **succeeded**, which is why
    nothing felt unfinished. A false reassurance you can attribute to
    carelessness teaches nothing; this one survives diligence.
  - The remedy is a support request, not a redesign — `adjustable: true`
    means hours of AWS turnaround. Worth knowing mid-incident. It also
    sharpens the signature: **an adjustable quota at 0 with an empty change
    history is specifically "nobody ever asked"**, as distinct from a hard
    limit you must design around.
  - What makes it the illusion and not just a miss: a quota of 0 produces a
    `VALID` compute environment, a healthy status, a standing
    `desiredvCpus`, and **silence**. There is no failing check to notice.
    AWS reports the configuration as correct because it *is* correct.
  - It was invisible rather than merely unnoticed: `parser_ondemand_gpu`
    first entered the module on 2026-09-22 (#63), so before that the queue
    had exactly one compute environment and it was spot. April ran on spot
    **by construction**. Nothing had ever asked the account to run an
    on-demand G instance — and **the first thing that did was the fallback
    built to make the pipeline more reliable.**
  - Rule: **for any resource a change depends on, confirm the account can
    actually create it — not merely that the configuration refers to it
    correctly.** For AWS that is `service-quotas get-service-quota` plus
    `list-requested-service-quota-change-history-by-quota`; an empty
    history on a zero quota means nobody has ever tried.
  - Distinct from (e), which it most resembles. **(e) is about one guard's
    field of view; (g) is about every guard being at the wrong altitude.**
    (Sharpened by 0a.) In (e) another guard could have caught it. In (g)
    **no guard at the configuration layer could ever have caught it**,
    however many you add or however rigorously you run them — which is
    exactly why two independent sessions both passed. Entitlement sits
    underneath configuration, and thoroughness at the wrong layer reads
    precisely like thoroughness.
  - **Therefore: after a miss of this shape, a third confirmation of the
    same layer buys nothing** — and adding one is the instinct. Change
    altitude instead.
  - Second-order, and worth its own line because the fallback design
    assumed the opposite: **Batch does not fall through an incapable order
    1.** With on-demand at order 1 and its quota at 0, Batch held
    `desiredvCpus = 4` on the incapable environment for **67 minutes** and
    never reached order 2. An untested assumption about a dependency's
    behaviour is the same illusion one layer out.

  **(h) A claim in prose receives less checking than the code it describes,
  while carrying more weight.** (Observed by palateful-3b in their own
  work; written here because it is not personal — it happened to at least
  three sessions on 2026-09-23.)

  **Why it is structural, not carelessness.** A diff **renders as a
  change**: someone reviews it, CI runs against it, a guard greps it. A
  claim in prose *about* that same code renders as nothing. It arrives
  already sounding like a finding, and **no mechanism anywhere asks it to
  prove itself.** So assertions end up carrying more weight than the code
  while receiving less checking — exactly backwards from where the risk is.
  Note where every other corollary here was caught: (a), (c) and (e) by
  tooling, (d) and (f) by a person re-measuring. **Nothing catches (h)
  except another session happening to look.**

  - 3b's four tonight, all assertions, none in a diff: *"there is no
    Playwright anywhere in the repo"* (sweeping and unneeded); the
    corrected count **measured on the wrong tree**; *"4f owns the
    browser-QA area"* (relayed unchecked — the only evidence was a layout
    migration commit); and *"zero `package.json` files depend on it"*
    (accurate, incomplete, offered as a repo-wide claim).
  - Mine, same shape, different surface — **descriptions that read as
    findings**: *"the timeout path writes `completed_at` without bumping
    `updated_at`"* (a mechanism I never opened the code to check — 0e found
    `now()` is transaction-start time, so **no** write is special); and
    *"don't count on the queued job migrating, Batch binds at
    scheduling"* — sound-sounding reasoning, contradicted an hour later by
    watching `desiredvCpus` move from `od=4/spot=0` to `od=0/spot=4` within
    a minute of the reorder. **The advice was right and the reason was
    invented.**
  - Earlier the same day, the same shape: *"the parser has never run"*, from
    three empty Batch log groups that were empty because retention had
    expired. The DB had 9 succeeded batches.

  **Actionable half — "be careful with claims" is unactionable, so:
  state the check, not just the conclusion.** (3b.) A durable claim about
  the codebase carries its **evidence handle** — the command *and the ref*:

  > not *"there is no Playwright in the repo"*
  > but *"`git grep -il playwright origin/main` → 105, all docs, no
  > manifest declares it"*

  That does three things at once: it forces you to actually run something,
  it names the ref (see (d) — *which tree* defaults to whatever you are
  standing in), and it hands the next reader a **disproof mechanism**
  instead of an assertion to trust or distrust wholesale.

  **The cheap version, before writing a claim into anything durable:
  could someone check this without asking me?** If not, produce the handle
  or mark it unverified.

  **(h) has no detector, and the rule above is not one.** (3b pressed on
  this, and the entry would have been dishonest without it.) "State the
  check" is a **habit**, and habits are the weakest control we have —
  tonight's own evidence is that the exit-status trap was written down in
  someone's memory file an hour before they fell into it. Writing a rule
  down does not close a gap. **Believing it did would be this entry's root
  failure wearing this entry's clothes.**

  What a real detector would look like, sketched rather than built: **a
  check that any prose claim in `LESSONS.md` or a spec which names a file,
  symbol or count must carry a ref or be marked unverified** — greppable
  and mechanical, in the shape of the existing `no-silent-catch` and
  `stale-pointer` guards. 3b judges it would have caught three of their
  four. Nobody has built it. **Until someone does, the honest status of (h)
  is: detected by other people noticing, and by nothing else.**

  **Two live instances of the illusion, measured 2026-09-22:**
  - `palateful-prod-alerts` has **0 subscriptions**, and the account has
    **0 CloudWatch alarms and 0 composite alarms**. No speakers and no
    listeners — and the topic's existence was being counted as progress.
    An alarm wired to a topic nobody subscribes to is operationally
    identical to no alarm, and it reads as done on every dashboard.
  - An SNS subscription in `PendingConfirmation` **appears in the console
    and delivers nothing**, and `list-subscriptions-by-topic` returns it —
    so `length(Subscriptions)` counts exactly the case that delivers
    nothing. Given nobody has subscribed yet, that is the *likely first
    state*. Any check must count **confirmed** subscriptions:
    `length(Subscriptions[?starts_with(SubscriptionArn, 'arn:')])`, since
    an unconfirmed one carries the literal string `PendingConfirmation`
    in that field. (0a.)

  **Deliberately excluded:** the six phantom Terraform "tag-only" diffs
  from planning with a local 1.4.2 against 1.16.3 state. Same family in
  spirit — *the output looked right and meant nothing* — but it is a
  measurement-validity failure, not apparent coverage, and it already
  lives in tfpin1. Kept out so this entry stays one shape. (0a raised the
  dilution risk; agreed.)

---

## Landing plan — REPLACE, don't append (hazard flagged by 3b via 0a)

`LESSONS.md` on main already carries 3b's **"A cited test is not evidence
until someone has read it or watched it fail"** (merged in `fd732fab`,
#52). Appending this entry beside it ships the three-overlapping-entries
problem *inside the fix for it*.

So, when the lane opens:

1. **Replace** 3b's "A cited test is not evidence…" entry with this one.
   Its two instances are folded in with attribution — the rsh102 driver
   mismatch under (d), `test_only_auth_failed_is_actionable` under (a) —
   and nothing of its content is lost.
2. **Do NOT delete** the other entries. Several are separate lessons that
   landed today and are not duplicates of this one; this entry
   cross-references them as instances instead:
   - "An exit status you didn't capture directly is not a reading" → (c)
     cross-references it explicitly in both directions; real overlap,
     different mechanism (wrong channel vs no input). 0a read it and
     confirmed: do not merge.
   - "A monitor isolated from one dependency…" → **(b)'s strongest
     overlap** — it is (b)'s own instance and reached (b)'s conclusion
     first. Kept because it carries the reasoning lesson (b) doesn't;
     (b) now states the fact it could not have known and points at it.
   - "Verify after a destructive loop…" → (c)
   - "Write the check and the claim as two separate sentences" → adjacent
   - "`gh pr checks <n>` can report every check passing while a whole
     workflow is missing" → (c), kept as its own operational gotcha
   Consolidating three *overlapping new* entries into one was the brief.
   Deleting other people's already-merged, distinct entries is not, and
   would be the same over-correction this entry warns about.
