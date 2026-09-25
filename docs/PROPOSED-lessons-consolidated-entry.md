# Prepared LESSONS.md entry — the entry itself (evidence lives in a companion)

Evidence: `docs/LESSONS-apparent-coverage-evidence.md`, linked per corollary.
Split on 3b's measured recommendation — inline this was **798 lines in a
1,273-line `LESSONS.md`, 63% of the file** against a median entry of 18.

---

- **A detector can look like coverage while providing none.** Configured is
  not working. Everything below is one shape: something reads as covered,
  and the reading is indistinguishable from real coverage.

  The root is **apparent coverage**, not "a green detector proves the
  detector ran" — because `deploy-freshness` was **red** 52 times and still
  provided no coverage, since nobody heard it. A root about *green* leaves
  the loudest instance outside it.

  **The third column is the honest part.** Without it, eleven corollaries
  read as eleven defences — **four are habits, and two have no detector at
  all.**

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

  **(a) A detector must be proven able to fail.** Drive it into the failure
  state once, deliberately. A test that cannot fail, a probe that cannot
  observe the thing it exists for, an alarm that has never been in ALARM —
  all are *configured*, not *verified*. `set-alarm-state` costs one command.
  **This applies to fixes as well as detectors.**
  → *evidence: tautological enum test, rsh102's pooled-connection probe,
  3b's calendar fix that reintroduced the same ambiguity one level up.*

  **(b) A detector's output must reach a human by a path independent of what
  it watches.** Ask: *what does this need in order to work, and is that
  inside the blast radius of the failure it exists to catch?* Where it
  structurally cannot cover a case, **name and assign the gap; don't paper
  it** — and **say how much it misses**, because that is the actionable
  half. cc's #48 notify step **cannot fire when AWS credentials are the
  failure, since publishing needs them — and that was 49 of the 52
  historical failures.** Without the number, "name the gap" is good
  manners; with it, **the detector was structurally blind to 94% of what it
  existed to catch, and saying so was the deliverable.**
  → *evidence: 52 unheard `deploy-freshness` failures; `error_logs` living
  in the database that was refusing connections.*

  **(c) A clean reading must be distinguishable from an empty one.** Assert
  non-zero input before believing a zero. **Two cases worth keeping inline,
  because they are the rule rather than illustrations of it:**

  - **A scan that never ran reports exactly like a clean scan.** Auditing
    eight branches before a push to a **public** repo, the pipeline hit
    `ugrep: invalid syntax`, wrote to stderr, and left empty stdout under a
    header reading *"blank = no hits"*. **Only a negative control catches
    this** — plant `+password = hunter2` and assert the scanner returns 1.
    Not care, not re-reading: the command looked right and the output looked
    like success.
  - **Never let two views of one source corroborate each other — they are
    the same claim twice.** `CLEAN` beside an empty run list; a rollup
    beside a listing. **Independence is a property of the failure modes, not
    of the commands.**

  **Before trusting a check that reports "fine", prove it can report "not
  fine".**

  **And note what the failures had in common.** Four query bugs in one
  evening — two wrong `awk` ranges, a short-vs-full SHA comparison, a
  miscounted commit range — and **every one reported the safe-sounding
  answer**: *"no pointers"*, *"MISMATCH"*, *"reviewed minus two"*. All
  understated rather than overstated. **That is luck, not design** (3b), and
  a set of broken comparators that happened to fail conservatively is not
  evidence that the next one will.
  → *evidence: six-hour timestamp skew, the stale-pointer guard's blind
  count, a fixture the guard could not see, "0 cart errors" over 0 loads.*

  **(d) Evidence must cover the path AND the input in use — not *a* path.**
  The tell is provenance standing in for scope: *"rsh102 measured this"*
  sounds like verification and never says what was covered. **What makes it
  hard is that nothing looks wrong: the measurement is correct, live and
  real — it just covered a different input.** (The asyncpg case measured
  *wrong password* on both drivers, and was then generalised to *missing
  password*, which it never touched.) **(a) and (c) are caught by tooling;
  (d) reached a story's acceptance criteria and would have shipped.**
  → *evidence: the asyncpg/psycopg2 driver mismatch; the wrong-tree grep;
  `git show` proving nothing about a remote across a shared object store.*

  **(e) A guard can enforce the *spelling* of a condition without enforcing
  its *presence*.** The absent case is the more dangerous one: a misspelled
  check fails closed and gets caught; an absent one is indistinguishable
  from code that never needed it. **Distinct from (a)** — a guard can
  satisfy (a) completely and still be blind to a whole category.
  → *evidence: `envspell1`'s grep, and the fourth `e2e_test_mode` read.*

  **(f) A post-change check needs a prior value, or it cannot fail.**
  **Before a change, write down the value that will distinguish success from
  failure afterwards. If you can't name one, the check you are planning
  cannot fail.** Generalised: *a review's strength is bounded by how
  checkable the baseline was, not by how carefully the reviewer read* — so
  **pin current behaviour in a test before changing it.**
  → *evidence: the deposed Batch CE ARN that passed a "looks right" check.*

  **(g) Verified the shape, never the capability.** Every check can be
  fail-capable, baselined and honest and still ask only whether the
  *configuration* is correct — never whether the account is **permitted to
  instantiate it**. **For any resource a change depends on, confirm the
  account can actually create it.** For AWS: `get-service-quota` plus
  `list-requested-service-quota-change-history-by-quota`.

  Three faces of the same altitude error, all worth the words:

  - **The reassuring reading was real; it answered a different question.**
    Two near-identical GPU quotas, one at 32 and one at 0.
  - **An empty result from the wrong API is indistinguishable from an idle
    system.** Ask: **could this call have returned the other answer?** If
    not, it cannot bear on the claim however true its output is.
  - **The repetition felt like corroboration.** Running an incapable call
    more often produces more confidence and no more information — so
    **suspect the calls you trust most**, because they are the ones you have
    never re-derived.

  **A falsifiable prediction must also name which *store* to read**, not
  only when. *"AWS says RUNNABLE"* and *"the DB says failed"* were
  simultaneously true.
  → *evidence: `L-DB2E81BA` at 0 since account creation; `describe-fleets`
  against a Batch ASG; the watcher deadline called to 13 seconds and read on
  the wrong surface.*

  **(h) A claim in prose receives less checking than the code it describes,
  while carrying more weight.** Structural, not careless: **a diff renders
  as a change** — reviewed, CI'd, grepped — and **a claim about that code
  renders as nothing.** It arrives sounding like a finding and no mechanism
  asks it to prove itself.

  **State the check, not just the conclusion.** A durable claim carries its
  **evidence handle** — the command *and the ref*: not *"there is no
  Playwright in the repo"* but *"`git grep -il playwright origin/main` → 105,
  all docs, no manifest declares it"*. **Cheap test before writing anything
  durable: could someone check this without asking me?**

  **(h) has no detector, and the rule above is not one.** Habits are the
  weakest control we have. **Writing a rule down does not close a gap** —
  believing it did would be this entry's root failure wearing this entry's
  clothes. A real detector would be greppable — *prose claims naming a file,
  symbol or count must carry a ref or be marked unverified* — and **nobody
  has built it.**
  → *evidence: four assertions from one session in one evening, none in a
  diff; the run-status/resource pair in both directions.*

  **(i) A corrected premise does not correct the numbers derived from it.**
  Distinct from a stale fact and from a wrong measurement: the fact *was*
  corrected, in the sentence that stated it, and the arithmetic downstream
  kept propagating. **Corrections travel to the sentence that was wrong.
  They do not travel to the arithmetic downstream of it.**

  1. **Grep every *spelling* of the number** — hyphen, en-dash, arrow.
  2. **And anything *computed* from it, which no text search can reach.**
     **Part 2 is not a rule the way part 1 is, and has no detector.** Part 1
     is mechanical; part 2 asks you to remember what you multiplied. A
     reader treating the pair as uniformly actionable will run the grep,
     find all three spellings, and **still ship the derived figure.**

  **A wrong figure that merges is a wrong figure inherited** — a comment
  beside the code it describes is exactly what makes it persuasive.
  → *evidence: `~11.8 GB → ~2 GB` surviving its own refutation into five
  places; this entry's own review accounting understating its gap by 6×.*

  **(j) A remedy has preconditions, and they are checked less often than the
  diagnosis.** A fix copied from where it worked can plan clean, apply clean
  and **do nothing** — because the condition that made it work was in the
  *situation*, not in the fix. **A precedent is evidence about a situation,
  not about a mechanism: ask what made it work there, then confirm that
  thing is present here.**

  **The sweep this produced, kept inline because it is executable and most
  of this entry is not.** An **edge-triggered** alarm that cannot leave
  `ALARM` is **stuck loud** — every subsequent incident is silent for the
  duration (measured: **46m20s**). An alarm is exposed when **both** are
  true:

  1. its metric filter sets **no `defaultValue`**, **and**
  2. its log group receives **no events the pattern fails to match** — so a
     quiet period yields no datapoints rather than zeroes.

  `describe-metric-filters` answers the first for every filter in the
  account; the second needs one look at what writes to each log group.
  → *evidence: `default_value = 0` would not have rescued `asgalarm1`, and
  why the two existing uses work.*

  **Deliberately excluded:** the six phantom Terraform "tag-only" diffs from
  planning 1.4.2 against 1.16.3 state. Same family in spirit, but a
  measurement-validity failure rather than apparent coverage, and it already
  lives in `tfpin1`.

---

## Landing plan

1. **Delete `docs/PROPOSED-lessons-consolidated-entry.md`** (this file) in
   the landing commit. It exists only so the draft could be reviewed without
   touching the shared `LESSONS.md`. Leaving it ships the entry **twice**.
2. **Keep `docs/LESSONS-apparent-coverage-evidence.md`** — the entry links
   to it per corollary.
3. **Replace** 3b's *"A cited test is not evidence until someone has read it
   or watched it fail"* — `LESSONS.md:141` on main, 56 lines. Its two
   instances are folded in with attribution.
4. **Do not delete** 3b's *"`gh pr checks <n>` can report every check
   passing…"* at `:197`. Verified by reading the file: #52 landed as **two**
   separate bullets. Re-confirm both line numbers before editing; they move.

**Review state:** 3b's pass is complete at 798 lines and all eleven
corollaries. **0a has signed off on (g) only** and has not read (i), (j), or
anything added on 2026-09-24. The author measuring their own commits is
bookkeeping, not review.
