# Apparent coverage — the worked instances

**Companion to the `LESSONS.md` entry *"A detector can look like coverage
while providing none."*** The entry carries the root, the eleven corollaries
and each one's rule. **This file carries the evidence.**

Split out on 2026-09-24 at 3b's recommendation, measured rather than felt:
inline, the entry was **798 lines in a 1,273-line `LESSONS.md` — 63% of the
file, and 44× its median entry of 18 lines**, replacing one of 56. That
changes what `LESSONS.md` is.

**The risk of this split, named by 3b when proposing it:** an evidence file
nobody opens makes the instances decorative, and the entry becomes eleven
assertions with citations — *uncomfortably close to (h)*. Two rules follow
and both are honoured in the entry:

1. **Linked per corollary, never once at the top.**
2. **Every inline rule carries its actionable half.** A reader who never
   opens this file still knows what to do differently. Where that could not
   be done, **the instance stayed inline** — see (c)'s empty-scan case and
   (j)'s sweep, which are load-bearing rather than illustrative.

---

# Owner: this session (pen taken at 0a's offer). For review by 0a and 3b.

**Index — the shape in eight lines, for the reader who has ninety seconds.
The instances below are what make it persuasive; they are for the reader
who has thirty.**

**The third column is the honest part** (3b's suggestion, and the entry's
own thesis applied to itself): without it, eleven corollaries *read* as
eleven defences. Four are habits, and **two have no detector at all.**

| | | what catches it |
|---|---|---|
| **(a)** | A detector must be proven able to fail. Drive it into the failure state once. | tooling |
| **(b)** | Its output must reach a human by a path independent of what it watches. | tooling |
| **(c)** | A clean reading must be distinguishable from an empty one. Assert non-zero input. | tooling |
| **(d)** | Evidence must cover the path *and the input in use* — not *a* path. | a person re-measuring |
| **(e)** | A guard can enforce a condition's *spelling* without enforcing its *presence*. | tooling |
| **(f)** | A post-change check needs a prior value, or it cannot fail. | a person re-measuring |
| **(g)** | Verified the shape, never the capability. Confirm the account can *create* it. | a person re-measuring |
| **(h)** | A claim in prose gets less checking than the code it describes, and carries more weight. | **nothing** |
| **(i.1)** | A corrected premise does not correct its derived numbers — grep every *spelling*. | a habit |
| **(i.2)** | …and anything *computed* from it, which no text search can reach. | **nothing** |
| **(j)** | A remedy has preconditions, checked less often than the diagnosis. | a habit |

---

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
  - **(a) applied to a fix, not a detector.** (palateful-3b, #108.) The
    calendar rendered its empty state before the first fetch resolved, so a
    loading week was indistinguishable from an empty one. The first fix
    early-returned a spinner for the whole body — and **reintroduced the
    same indistinguishability one level up**: a new week is not a first
    load, but it looks exactly like one, because the provider is keyed by
    range. It blanked the week header on every navigation. **A screenshot
    review would have passed it.** What caught it was two *existing*
    navigation tests, written for another purpose entirely — **which is the
    strongest argument for keeping tests that assert structure nobody is
    currently changing.**

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

  **The worst case of (c), and the only one with no answer in it at all.**
  Every other instance in this entry is a *correct answer to a different
  question*. This one is **no answer, rendered indistinguishable from a
  good one by the output format** — and it sat directly on the safety check
  for a push to a **public** repository.

  - Auditing eight branches for credentials before publishing them, the
    scan pipeline hit `ugrep: error: invalid syntax` on `^\+\+\+`, wrote
    the error to **stderr**, and left **empty stdout** beneath a header
    reading *"blank = no hits"*. **The scan never ran.** The output of a
    clean audit and of an audit that did not execute were byte-identical.
  - **Nothing but a negative control would have caught it.** Not care, not
    re-reading the command, not checking the output twice — the command
    *looked* right and its output *looked* like success. Planting
    `+password = hunter2` and asserting the scanner returns **1** converts
    an unfalsifiable clean into a tested one.
  - **Second instance the same hour, same shape, different cause:** a push
    verifier reported `MISMATCH` on four branches that had pushed
    correctly, because it compared `git rev-parse --short` (8 characters)
    against `cut -c1-7`. **The comparator was wrong, not the thing
    compared.**
  - **Rule: before trusting a check that reports "fine", prove it can
    report "not fine".** (leonidbelyi-41.) Both of these were working
    commands producing confident wrong readings, and in both the fault was
    in the apparatus rather than the subject. A check you have never seen
    fail is a check you have never tested.

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
  - **The cost, and what it changed:** selfheal1 Case 1 as *specified*
    proposed dropping the `no password supplied` pattern so an unset
    `DB_PASSWORD` stops causing a 503 loop. On asyncpg that mechanism is
    **inert** — the missing password still returns `28P01`, which rsh102's
    own narrowing treats as sufficient. A filed fix that would have looked
    right and changed nothing on the path that matters.
    **The measurement killed the mechanism before it shipped, so what
    landed in `fd732fab` decides from the credential rather than the
    error**: `_url_password_is_blank()` (`db_probe.py:249`) asks the
    configuration, and the downgrade at `:419` turns `AUTH_FAILED` into
    `UNREACHABLE` **only** when the URL that failed carries no usable
    password. Everything else passes through, so a genuine rotation still
    self-heals. *(Read from `origin/main` rather than from the spec —
    3b flagged that the original wording described a proposal in the
    present tense and would read in three months as a live bug.)*
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
  - **A shared object store means `git show <sha>` proves nothing about the
    remote.** (3b, who caught it in their own verification and stopped
    short of overstating it.) Their `git fetch` of a pushed branch failed
    with `Permission denied (publickey)`, yet `git show e7c07fe1` **worked**
    — every worktree in this repo shares one object store, and another
    session had already pulled the object. For a moment the content of an
    object *believed* to have come from the remote had been verified
    without the remote ever being reached. `git ls-remote` closed it: the
    remote genuinely carries that SHA, and content-addressing then makes
    the local object necessarily identical. **Both halves are needed; only
    the second one talks to the remote.**
  - Environmental, and load-bearing for the above: **git's push and fetch
    error messages were unreliable in this window.** Two sessions, same
    hour — a push that reported `Permission denied (publickey)` three times
    had in fact already succeeded (`Everything up-to-date` on the next
    attempt), and a fetch reported the same permissions error for what was
    a transport failure. `ssh -T git@github.com` authenticated fine
    throughout. **Confirm with `git ls-remote` before concluding anything
    from a push or fetch error**, in either direction: the failure messages
    were wrong about both success and cause — and about **persistence**,
    which is the third shape: a genuine failure of push *and* `ls-remote`
    in the same command, both succeeding seconds later, nothing changed.
    **Unreliable about success, about cause, and about persistence.** No
    amount of care at the reading layer fixes a reading that varies; only
    retrying and cross-checking does, which is (c)'s answer arriving at
    the transport layer. (3b.)
  - **The consequence that makes this dangerous rather than annoying:
    never re-push on the strength of an error message.** (41.) A retry
    after a *false* failure is how you get duplicate commits, or a
    force-push over your own successful work. Check the remote first;
    retry the *check*; re-push only once the remote is reachable and
    demonstrably lacks the commit.
  - **A half-right rule is worse than none once it has been circulated,
    because it carries the authority of having come from coordination.**
    (41, on their own earlier guidance.) The first version said *"verify
    with `ls-remote`"* — which leaves a reader taking one failed
    `ls-remote` as proof of an outage. Same class of wrong answer, one
    step along.
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
  - **Second instance, and it is the same error committed while diagnosing
    the first.** Asked whether the incapable environment had *tried*, this
    session ran `describe-fleets` and `describe-spot-instance-requests`,
    got nothing from either, and reported that the on-demand environment
    "produced zero instance requests and zero EC2 fleets" — building part
    of the non-fall-through finding on it. **Batch managed compute
    environments launch through an Auto Scaling Group and use neither
    API.** Both correctly returned nothing, because nothing uses them.
    `describe-scaling-activities` showed **216 failed launches**, each
    carrying `VcpuLimitExceeded … your current vCPU limit of 0`.
  - **An empty result from the wrong API is indistinguishable from an idle
    system.** That is (g) with a new face: not "is the account permitted to
    create this" but "is this query pointed at the mechanism actually in
    use". Both are the layer beneath the one being checked, and both
    produce a confident, well-formed, entirely wrong reading. Cross-check
    with (c): the reading was empty *and* clean, and the denominator —
    *does this API ever return anything for this resource?* — was never
    asked.
  - It makes the non-fall-through finding **stronger, not weaker**: Batch
    had a repeated, explicit, unambiguous failure from its own ASG, 216
    times, and still did not move to order 2. **Stronger again on
    2026-09-24:** with the quota granted and order 2 fully capable, Batch
    *still* left on-demand at `desiredvCpus 0` while order 1 failed every
    ten seconds. The earlier observation was never a clean test — order 2
    was also incapable. **Order 2 is not a fallback.**
  - **The actionable form, and it is about predictions rather than
    queries: a falsifiable prediction must name which *store* to read.**
    An exact timestamp is not sufficient. The watcher's 90-minute deadline
    was called to within **13 seconds** — and a session checking
    `describe-jobs` at 12 and 43 seconds *after* it fired read `RUNNABLE`,
    correctly, and concluded it had not run. **No value `describe-jobs`
    could have returned would have shown otherwise**, because the watcher
    writes the database and never touches the AWS job. *"AWS says
    `RUNNABLE`"* and *"the DB says `failed`"* were **simultaneously true**.
    An exact time aimed at the wrong surface is still unfalsifiable — it
    just fails silently, later. (With palateful-0a, who hit it and named
    it.)
  - The check that collapses all three of these into one question:
    **could this call have returned the other answer?** If not, it cannot
    bear on the claim, however true its output is.
  - **And the reason this defect survives: the repetition felt like
    corroboration.** (palateful-0a's formulation, of my error.) I ran
    `describe-fleets` and `describe-spot-instance-requests` against Batch
    repeatedly over two days and built a reported finding on them. **Running
    an incapable call more often produces more confidence and no more
    information.** So this class is not worn down by use — it survives
    exactly as long as nobody asks the question, and heavy use makes it
    *more* entrenched rather than less. **Suspect the calls you trust most**,
    because they are the ones you have never re-derived.
  - A second self-inflicted case the same evening, smaller and worth
    keeping for the symmetry: a stated recovery window
    (*"expect ~19:58–20:05Z, later than that is worth a second look"*)
    derived from **one** model of how CloudWatch aligns a 900s evaluation
    window, with the model left unstated. 0a produced a second, equally
    plausible derivation giving **20:06–20:16Z** — so the threshold I
    attached would have flagged a healthy recovery as a defect. **A
    threshold is only as good as the model behind it, and a threshold
    quoted without its model reads as measured.**
  - **Twice in one day, by two sessions, independently.** (palateful-0a.)
    Checking this session's claim that the ASGs publish no CloudWatch
    metrics, 0a's first query filtered ASG names on `Batch` — which matched
    nothing — and returned `[]`. **They nearly confirmed a true finding
    from an empty query rather than from an empty metrics list.** Same
    shape, same afternoon, opposite direction: one of us reached a false
    conclusion through the wrong API and the other nearly reached a true
    one. *The conclusion being right does not make the instrument right*,
    and a true answer obtained from an API that could not have told you
    otherwise is indistinguishable from a lucky one.
  - Second-order, and worth its own line because the fallback design
    assumed the opposite: **Batch does not fall through an incapable order
    1.** With on-demand at order 1 and its quota at 0, Batch held
    `desiredvCpus = 4` on the incapable environment for **67 minutes** and
    never reached order 2. An untested assumption about a dependency's
    behaviour is the same illusion one layer out.
  - **Reconciling this with the opposite-sounding observation in (h)**,
    because the two bullets discuss the same counter and a sceptical reader
    will test them against each other first. They are not in conflict:
    **fall-through within a fixed order never happened; re-pointing after
    the order itself changed happened within a minute.** Batch binds the
    environment at scheduling, so an incapable order 1 simply holds — but
    editing `computeEnvironmentOrder` re-evaluates that binding. Two
    different mechanisms, one counter. Neither was verified before it was
    relied on, which is why both are here.

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

  **Demonstrated instance, 2026-09-24 — `gh pr checks` cannot tell you
  whether the apply ran.** (Found by palateful-0a; my first write-up of it
  was wrong and their correction is the version below.)

  `odback1`'s deploy was cancelled mid-flight by two merges landing on
  `main` (`cancel-in-progress`, both keyed on `refs/heads/main`), killing
  `terraform-prod` before it started. **The flip did not apply.** Yet:

  ```
  gh pr checks 96   terraform       pass
                    terraform-prod  skipping
  ```

  **That is not a mislabelled cancellation. It is a different run.**
  Verified by following the links the command emits:

  ```
  gh pr checks 96 -> run 36049602691  sha 39a6347d  branch fix/dev-odback1  event pull_request
  the cancelled apply -> run 36050394812  sha 55731990  branch main         event push
  ```

  `terraform-prod: skipping` is **correct** for the pre-merge run — a pull
  request never applies. **`gh pr checks` reads the PR's run and is
  structurally incapable of reporting the post-merge apply**, which lives
  on the `push` run against `main` that it never looks at.

  So it is *"a correct answer to a question nobody asked"* — and it is the
  **"could this call have returned the other answer?"** check again, in a
  command everyone runs constantly. **No output of `gh pr checks` could
  ever have shown that apply cancelled.** A reader confirming a deploy that
  way has measured nothing.

  **Rule: never confirm an apply from a PR's checks. Read the applied
  state.** Throughout this incident `order1` from `describe-job-queues` was
  the only reading that never lied.

  **The general form, and it cuts both ways: the run's status is a claim
  about CI; the resource is the fact.** (leonidbelyi-41's phrasing.) When
  they disagree — or when one is merely *absent* — the resource wins.

  - **Direction 1, the failure that opened the evening:** `terraform`
    reported `success` while `terraform-prod` was cancelled, so a green job
    stood in for an apply that never ran.
  - **Direction 2, the same day, inverted:** the queue order read
    `ONDEMAND` from AWS at 20:40:05Z while the job that caused it had **no
    conclusion at all** — mid-flight, no status to report. **Waiting for
    the green job would have meant reporting something already true as
    though it were not yet.** The change was live; only the *claim about
    it* was pending.
  - So the status view is not merely *less* reliable than the resource —
    it is **differently timed**, and it lags in one direction and leads in
    the other. Neither error is visible from the status view alone.

  **And a note on my own error here, because it is (h) in miniature:** I
  wrote that the view *"relabels `cancelled` as `skipping`"*. That is a
  falsifiable claim about `gh`, and it is **false** — the first person to
  test it would find `gh` behaving correctly and discount everything around
  it. **A wrong mechanism attached to a right conclusion is worse than no
  mechanism**, because it is the part a sceptical reader checks first.

  **(i) A corrected premise does not correct the numbers derived from
  it.** Distinct from a stale fact and from a wrong measurement: the fact
  *was* corrected, in the sentence that stated it, and the arithmetic
  downstream went on propagating. (This session, 2026-09-24.)

  - Worked instance. I assumed the parser image's **11.8 GB layer** held
    the pre-baked model, and predicted an `allow_patterns` change would
    take it "**~11.8 GB → ~2 GB**". I then *proved* the model lives in the
    **3.5 GB** layer — that is how I read its configs — and **repeated the
    old figure anyway**, in a commit message, a code comment, two specs and
    a PR body. Measured after the apply: the model layer went
    **3,495 MB → 1,494 MB**, about **2 GB**, not ~10. A 14.63 GB image
    would have read as a failed fix against my published number.
  - **Corrections travel to the sentence that was wrong. They do not travel
    to the arithmetic downstream of it.** (leonidbelyi-41's framing.)

  **The rule, in two parts, because one is not enough:**

  1. **When you correct a premise, grep for every *spelling* of the number
     you derived from it.** Mine appeared as `~11.8 GB -> ~2 GB`,
     `~11 GB → ~2–3 GB` (en-dash and arrow), and I would have declared the
     sweep clean after matching only the first.
  2. **And for anything *computed* from it, which no textual search can
     find.** A `~6–9 GB` cost estimate in a different spec's comment never
     contained "11.8" at all; it was derived from it. **You only find that
     one by knowing what you computed** — the grep cannot help you.

     **Part 2 has no detector, and it is not a rule in the way part 1 is.**
     (3b.) Part 1 is mechanical: run the grep, vary the spelling, done. Part
     2 asks you to remember what you multiplied — and **a reader who treats
     the two-part rule as uniformly actionable will run the grep, find all
     three spellings, and still ship the derived figure.** Stated plainly
     here because the pair otherwise reads as complete when half of it is
     an appeal to memory. Same admission as (h).

  **Note the shape of (1)'s near-miss**: a sweep that reports success after
  matching one of three spellings is *the same failure the rule exists to
  prevent*, committed by the rule. Compare (c): the clean reading and the
  incomplete one are indistinguishable without asserting coverage.

  - **A wrong figure that merges is a wrong figure inherited.** The bad
    number reached `main` in `Dockerfile.batch:58` and would have taught
    the next reader that `allow_patterns` saves 10 GB, **with no reason to
    doubt it** — the comment sits beside the code it describes, which is
    exactly what makes a code comment persuasive.

  **(j) A remedy has preconditions, and they are checked less often than
  the diagnosis.** A fix copied from a case where it worked can plan
  clean, apply clean, and do nothing — because the condition that made it
  work was in the *situation*, not in the fix. (palateful-0a, 2026-09-24,
  who caught it before it was applied.)

  - Worked instance. `asgalarm1` reached `ALARM` correctly and then **could
    not return to `OK`** — 32 minutes after the last datapoint, two full
    900s periods, `TreatMissingData = notBreaching`, no transition. The
    obvious diagnosis was right: the metric filter has **no
    `defaultValue`**, so a quiet period emits *nothing* rather than a zero
    and the alarm sees missing data. **The obvious remedy —
    `default_value = 0`, which this repo already uses twice — would have
    changed nothing.**
  - **Why.** `defaultValue` emits a zero for each *non-matching* log event
    the filter processes. It needs traffic. Both existing uses say so in
    their own comments: `alarm_fail_open.tf` relies on *"a datapoint for
    every log event the filter processes, matching or not"* (288/288
    buckets), and `alarm_rds_auth.tf` on the export's *"steady checkpoint
    heartbeat"*. **Both depend on the log group carrying unrelated
    traffic.**
  - **The new alarm's log group has none.** Verified: `/aws/events/
    palateful-prod-asg-launch-failure` is fed by exactly one EventBridge
    rule, pattern `{"detail-type":["EC2 Instance Launch Unsuccessful"],
    "source":["aws.autoscaling"]}`. **Every delivered event matches**, so a
    quiet period is **zero lines**, not non-matching lines, and
    `defaultValue` has nothing to fire on. 0 events since 19:51Z.
  - **So the remedy would have planned clean, applied clean, and done
    nothing** — which is `applygap1`'s failure arriving *as a fix*. The
    diagnosis was checked; the remedy's precondition was not, because it
    came with a track record.
  - **The check: a fix that worked elsewhere carries the elsewhere with
    it.** Ask what made it work there, then confirm that thing is present
    here. A precedent is evidence about a situation, not about a
    mechanism.
  - **What nobody claimed, and it is the disciplined part.** 0a had already
    predicted the recovery twice (~20:06:51Z, ~20:15:51Z) and been wrong
    twice, so declined to assert *"CloudWatch does not evaluate without
    data"* on top of a model already shown incomplete. One datum contradicts
    the simple version anyway: `17:23:51 INSUFFICIENT_DATA → OK` happened
    with **no data ever recorded**, so absence *can* drive a transition.
    **The observation stands without a mechanism; the mechanism stays
    open.**
  **Operational consequence — promoted out of the instance, because it is a
  property of every alarm in the account and not of this one.** (3b.)

  **An alarm that fires correctly and cannot leave `ALARM` is stuck loud.**
  CloudWatch alarms are **edge-triggered** — they notify on state
  *transition* — so while one sits in `ALARM`, every **subsequent** incident
  is silent. If the recovery is slow, the blind window is long; if recovery
  never comes, a detector built to end exactly this failure is **permanently
  deaf after its first real firing.**

  *(Measured on 2026-09-24: recovery took **46m20s** from the last datapoint.
  So the window is bounded, not infinite — but 46 minutes of silence begins
  the moment the first incident is detected.)*

  **And unlike most of this entry, it is mechanically sweepable.** The
  exposure is a **pair**, and both halves are queryable:

  1. does the metric filter set **`defaultValue`**? and
  2. does its log group receive events the filter's pattern **does not**
     match?

  **An alarm is exposed when the answer to both is no** — no default, and a
  dedicated log group, so a quiet period produces no datapoints rather than
  zeroes. `describe-metric-filters` answers the first for every filter in
  the account; the second needs one look at what writes to each log group.
  **That is a sweep somebody could actually run**, which is more than can
  be said for most of what is written here.

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

## The entry caught itself: this document's own review accounting

**Worked example of (h) and (i), found in the review of this entry,
2026-09-24.** Recorded here rather than inside a corollary because it is
about *this file*. **(h)** because the inaccurate thing was a claim in
prose, and nothing checked it; **(i)** because a true-as-stated claim was
then reused for a purpose it did not cover.

**3b, whose claim it was, offered it as an (h) instance themselves** — and
argued it is a cleaner one than their Playwright miscount, *"because there
was no carelessness in the framing at all, only in the number inside it."*
**The disciplined-sounding sentence was the inaccurate one.**

palateful-3b completed a review pass and reported it with unusual care —
*"complete through `e7c07fe1`, minus two commits I have not read"* — and
explicitly refused to let the word "reviewed" cover material they had not
opened, saying **that distinction is the entry's own subject.**

**It was wrong by 6×.** Measured:

| | `e7c07fe1` (the review point) | `e35c7dea` (current) |
|---|---|---|
| lines | 417 | **698** |
| corollaries | 9 | **11** |
| commits since | — | **12** |

The twelve added **281 lines and two entirely new corollaries**, (i) and
(j), which no reviewer has seen. One of the two commits 3b named was not
even on this branch.

**Nothing about that conduct was careless.** The claim was bounded, honest,
and volunteered. **It was checked against memory rather than against the
branch** — and a carefully-bounded honest claim is *precisely* the kind that
gets trusted without re-derivation. `git log e7c07fe1..HEAD` was the only
thing that produced the real number.

**It then propagated one hop, which is the part worth keeping.** The
coordinator was about to record the entry as *"waiting on 0a alone"* — a
true-as-stated claim used for a purpose it did not cover. **Two people
behaving correctly, and the state of the document drifting to 60% reviewed
while reading as done.**

**The honest state, at the time of writing:** 3b's pass covers 417 of 698
lines and 9 of 11 corollaries; 0a has signed off on **(g)** only; **nobody
has read (i) or (j).** The author measuring their own twelve commits is
bookkeeping, not review.

**And the general rule the whole exercise produced** (leonidbelyi-41):
**never let two views of one source corroborate each other — they are the
same claim twice.** `CLEAN` beside an empty run list, a rollup beside a
listing, a status view beside a status view. Independence is a property of
the *failure modes*, not of the commands.

## Landing plan — REPLACE, don't append (hazard flagged by 3b via 0a)

`LESSONS.md` on main already carries 3b's **"A cited test is not evidence
until someone has read it or watched it fail"** (merged in `fd732fab`,
#52). Appending this entry beside it ships the three-overlapping-entries
problem *inside the fix for it*.

**Checked rather than remembered, because "nothing of its content is lost"
is the load-bearing claim here.** 3b's #52 work landed as **two separate
bullets**, not one: *"A cited test is not evidence…"* at `LESSONS.md:141`
and *"`gh pr checks <n>` can report every check passing…"* at `:197`. So
replacing the first does **not** take the second with it — which is why the
plan below is safe, and it happened to be true for a reason neither of us
had stated until 3b read the file. Confirm both line numbers before
editing; they move.

So, when the lane opens:

0. **Delete this file.** `docs/PROPOSED-lessons-consolidated-entry.md`
   exists only so the draft could be reviewed without touching the shared
   `LESSONS.md`. Leaving it ships the entry **twice** — a 366-line
   near-copy that greps identically and then drifts. **That is this
   entry's own duplication hazard, delivered by the commit that fixes
   it.** (3b.) The landing commit must remove it.

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
