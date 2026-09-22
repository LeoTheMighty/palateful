---
hash: chainctx1
type: dev
created: 2026-09-22T22:20:00-06:00
title: _chain should honour __suppress_context__ — make `raise ... from` an explicit signal
from: dev/dev-rsh105-2026-07-27T12:34-secrets-manager-password-provider.md
status: ready
owner: null
branch: null
---

## Goal

`_chain` (`libraries/utils/utils/services/db_credentials.py`) walks
`__context__` unconditionally. Python already carries the author's
statement about whether that ambient context is meaningful —
`raise X from Y` sets `__suppress_context__ = True`, meaning "Y is the
cause; the exception that happened to be in flight is not". The
classifier ignores it.

The cost is that a correct fail-open in rsh105 is protected by nothing
more than **two lines sitting outside an `except` block**, where moving
them inward reads as tidier and silently converts a Secrets Manager
outage into a full service drain.

**This is not a one-liner.** `_chain` is the traversal underneath
`is_auth_error` (0a), `is_missing_password` (3b, #52), and both probe
paths. Changing what it walks changes every verdict computed from it.
Scope it accordingly.

## The concrete case

[M] Measured on rsh105's listener (`_make_do_connect`), by moving the two
lines and running the suite:

```
retry OUTSIDE the except (as shipped):
   __cause__=SM  __context__=SM  __suppress_context__=True
   chain-walk reaches the AUTH error: False    -> fails open, correct

retry INSIDE the except (one natural refactor away):
   __cause__=SM  __context__=SM  __suppress_context__=True
   chain-walk reaches the AUTH error: True     -> AUTH_FAILED -> 503 -> drain
```

`from exc` sets `__suppress_context__` in **both** variants, so it is not
what saves the shipped version. What saves it is that the re-resolve sits
after the handler closes, so the auth error is no longer being handled.
That is a dangerous thing to depend on: the construct that looks like the
guarantee isn't one, and the real guarantee is invisible whitespace.

## The deeper asymmetry (3b, and the reason the flag alone is not enough)

[M, 3b] The traversal is **inverted from a fail-safe standpoint today**:

| predicate | effect of a True | chain walked |
|---|---|---|
| `is_auth_error` | **drives** a 503 → task replacement | `ALL_LINKS`, incl. implicit `__context__` (`db_credentials.py:156`) |
| `is_missing_password` | only **vetoes** a 503 | `EXPLICIT_LINKS` |

That is backwards. The destructive signal should demand the strongest
evidence and the narrowest chain; the fail-open signal can afford to be
generous. The Secrets Manager measurement above is precisely what the
inversion produces — an ambient outage raised inside a handler making
`is_auth_error` True, from an exception that was never about credentials.

The flag fix alone only helps where someone wrote `raise ... from`. The
asymmetry bites wherever an exception is merely raised inside an `except`,
which needs no `from` at all. So this spec carries both.

## Severity: latent today, live at rsh106

**The sentence that makes it legible:** B and C below are the *same
exception*, and they get different verdicts depending on what happened to
be in flight when the probe classified them.

[M] Measured against the real `_classify` on the current tree:

```
A  within-attempt   RuntimeError raised while handling THAT attempt's auth error
                    -> AUTH_FAILED      (arguably correct: auth did fail here)
B  caller-nested    TimeoutError raised while handling an UNRELATED auth error
                    -> AUTH_FAILED      <-- the bug: a transient becomes "replace this task"
C  plain timeout    TimeoutError, no ambient handler
                    -> UNREACHABLE
```

**`__context__` is set implicitly by the interpreter.** It needs no
`raise ... from`, and therefore no author intent, to appear. That is why
honouring `__suppress_context__` cannot fix this on its own: the flag is
only present where someone wrote `from`, and the dangerous shape needs
nobody to have written anything.

**Not reachable in prod today, and the reason matters.** [M] Outside
`db_probe.py` and its tests the only prod caller is
`health_router.py:32`, which calls `cached_verdict_async()` in a `try`
that is not handling anything else. **That is the whole reason — full
stop.**

**Creation does not isolate exception context — and it does not matter.**
Stated that way round deliberately: the true half is non-obvious and
worth keeping, and only the conclusion drawn from it was wrong. The
verdict leaves the probe as a *return value*, and no caller frame ever
re-raises it, so caller-side contamination cannot happen no matter what
the caller is handling. A note that only said "this can't happen" would
invite the next reader to re-derive the tempting wrong path; this shows
the path and closes it.

⚠️ **Two plausible explanations of why are both FALSE**, and each was
proposed, measured and refuted by the peer who proposed it:

- "asyncio isolates exception state per task" (3b) — no.
- "a task inherits the context of the frame that created it" (98) — also
  no.

[M] The true rule, measured on 3.13.5 by 3b and reproduced by 98 —
**the awaiting frame at the moment the exception propagates is what sets
`__context__`**, because `await` re-raises the task's exception in that
frame and the re-raise picks up whatever that frame is handling:

```
task created INSIDE except, awaited OUTSIDE  -> __context__ = None
task created AND awaited inside the except   -> __context__ = AuthErr
coroutine awaited directly inside the except -> __context__ = AuthErr
```

Creation site is irrelevant: rows 1 and 2 create the task identically.

**Consequence, and it bounds this spec's blast radius tightly** [M, 3b,
end to end]: the exception `_classify` sees always propagates into
`probe_async`'s own `try`, and that frame is never itself an `except`.
So **no caller can contaminate the classification, whatever it is doing
when it calls** — 3b measured a caller missing the cache from inside an
unrelated auth handler and the clean caller served from that same shared
task; both got `UNREACHABLE`.

**The invariant is therefore violable only from `_connect_once` and
below.** That is where the tests belong, and the fix does not need to
defend against callers at all.

[M, 0a, against the **real merged module** rather than a model] Both
sides of that bound, confirmed:

```
caller A (inside an except handling an auth error):  UNREACHABLE
caller B (clean frame, served from A's cache):       UNREACHABLE
control  (no ambient handler):                       UNREACHABLE

timeout while an auth error is handled below _connect_once -> AUTH_FAILED
```

**What the false verdict looks like in prod logs, verbatim:**

```
db probe: credential failure — this task cannot re-authenticate without a restart (TimeoutError: )
```

The probe announces a **credential failure** and offers a `TimeoutError`
**with an empty message** as its evidence. An operator reading this
during an incident sees a confident claim about credentials backed by
nothing. The same exception with no auth error anywhere in scope gives
`UNREACHABLE` — same type, opposite verdict, decided entirely by what an
unrelated frame happened to be handling.

**Two named conditions make it live — both are the next stories in this
workstream:**

1. **rsh106** wires rsh105's `do_connect` listener into the engine sites.
   There, the only thing between a Secrets Manager outage and a full
   drain is the *indentation of two lines* in `_make_do_connect`. [M]
   Move them inside the handler and `is_auth_error` starts returning True
   for an SM outage.
2. **rsh107** adds a second consumer: a worker process that catches DB
   errors around its own work — the caller-nested shape exactly.

**This therefore BLOCKS rsh106**, and is not merely blocked-by rsh105.
A latent bug with a named date of becoming live is more actionable than
a severity rating.

## The invariant to assert (3b) — not the flag fix

**Every auth error reachable in the chain must belong to the attempt
being classified.**

That is the property. `__suppress_context__` is one mechanism that
partially serves it and, measured, does not touch the timeout path at
all — so a spec that pins the flag does not survive the next mechanism,
and a spec that pins the invariant does.

**A third reachable shape, inside `db_probe.py` itself** [M, found by 3b,
reproduced by palateful-98]:

```
budget expires while an auth error is being handled
  -> wait_for raises TimeoutError, __context__=CancelledError -> chain reaches the auth error
  -> is_auth_error=True -> AUTH_FAILED
```

**And `wait_for` does NOT "set no `from`"** — that was 98's description
and it is wrong in a way that would misdirect the fix. [M, 0a,
reproduced by 98]:

```
TimeoutError:    __cause__=CancelledError  __context__=CancelledError  __suppress_context__=True
  CancelledError: __cause__=None           __context__=AuthErr         __suppress_context__=False
```

`wait_for` sets an explicit cause **and** the suppress flag. The
suppress-aware walk correctly skips `TimeoutError.__context__` — and
still reaches the auth error, via
`TimeoutError --__cause__--> CancelledError --__context__--> AuthErr`.

**The general lesson, which is the real argument for the invariant:**
any *unsuppressed* node reached through an explicit cause re-opens the
entire context tail behind it. A per-node flag check can never close
that, because the flag says "ignore **my** ambient context" and says
nothing about a node three hops down. Reproduce it by shrinking `PROBE_TOTAL_TIMEOUT_S` in the test
and having `_connect_once` await past it inside an `except` handling an
auth error — no change to the real budget.

**And the limit of that finding, stated in this order:** mechanically, a
timeout produces `AUTH_FAILED` and therefore a drain. But in that
scenario the auth error **belongs to the attempt** — the credentials
really were rejected — so the verdict is *correct, reached by the wrong
mechanism*. It is a false positive only once an auth error that does
**not** belong to the attempt can be in scope. Today nothing produces
one: fresh engine, one attempt per call. "A timeout drains the service"
is accurate and reads as a live false positive, which it is not yet.

**Which is exactly why this gates rsh106** [3b]: the listener rejects a
cached password (auth error #1), refreshes, and proceeds — so an auth
error that the refresh *already resolved* stays reachable for whatever
fails next. That is the commit where the wrong mechanism finally produces
the wrong answer. rsh107 adds a consumer but no resolved-then-proceed
auth error, so "before rsh107" would let the real window open first.

## Acceptance criteria

- [ ] `_chain` skips `__context__` on a node whose `__suppress_context__`
      is set, while continuing to walk `__cause__` and `.orig`.
- [ ] ⛔ **WITHDRAWN: "narrow `is_auth_error` to `EXPLICIT_LINKS`" as a
      standalone fix.** It is not merely insufficient, it is **harmful**.
      [M] Measured on the `:96-104` shape (cleanup fails while *this
      attempt's* auth error is handled): `ALL_LINKS=True`,
      `EXPLICIT_LINKS=False`. Narrowing alone turns a genuine rotation
      accompanied by a noisy cleanup into `UNREACHABLE` — no 503, no
      replacement, **no self-heal**. That is the six-day-outage shape
      rsh102 exists to close. Found by 3b, confirmed here.
- [ ] **Scope moves first.** `_classify` is given the attempt's own
      exception and decides ownership where the attempt boundary is
      known; only then is the link set a live question. The link-set
      choice cannot be correct on its own — see "Why no link set works".
- [ ] **The invariant above is asserted**, not merely the flag: a test
      that an auth error which does not belong to the attempt cannot
      produce `AUTH_FAILED`.
- [ ] **One test against a REAL SQLAlchemy-wrapped error**, not a
      hand-built wrapper — the live-driver file
      (`test_db_credentials_live_drivers.py`) already has the machinery
      and a running Postgres. Without it the suite pins a wrapper shape
      the drivers do not produce, and cannot distinguish a correct fix
      from one that only looks correct against the fixtures.
- [ ] **A timeout-path test at the budget boundary** — the one shape that
      reaches the bug through code we already ship, and the one the flag
      fix alone leaves green.
- [ ] **A test asserting shape B directly**: a non-auth probe failure
      raised inside an unrelated auth handler classifies as non-auth.
      [0a] It passes today for a reason nobody wrote down, and would
      start failing the moment someone nests a caller — which is exactly
      the regression the narrowing exists to make impossible.
- [ ] Every existing verdict is re-derived, not assumed: `is_auth_error`
      and `is_missing_password` keep their current answers for every case
      pinned in `test_db_credentials_classifier.py`,
      `test_db_credentials_live_drivers.py` and `test_db_probe.py`. Any
      answer that changes is a finding to adjudicate with the predicate's
      owner, not a test to update.
- [ ] A test asserting the flag is honoured, driven through a real
      `raise ... from` rather than a hand-built exception. ⚠️ A
      hand-constructed error has no implicit `__context__`, so a test built
      that way passes whether or not the traversal changed — the same
      vacuous-green shape this workstream keeps producing.
- [ ] rsh105's load-bearing-dedent comment in `_make_do_connect` is
      retired (or rewritten to point here) once the flag is honoured, so
      the codebase does not keep claiming a guarantee it no longer needs.
- [ ] `is_missing_password`'s docstring no longer cites the rsh105 retry
      path it describes today — [M] `_fetch` rejects a missing/empty/
      non-string `password` field before any connect, and the retry path
      has no env fallback, so the listener raises
      `CredentialResolutionError` rather than connecting passwordless.
      Reword per 3b: the veto defends a shape we cannot enumerate (any
      caller whose chain carries both phrases should fail open, because a
      task with no password to send cannot be fixed by replacing it), not
      a description of what the listener does. Deferred here from #45 by
      41's call, to avoid another CI cycle on an approved PR.
- [ ] `is_missing_password`'s deliberate `EXPLICIT_LINKS` traversal is
      reconciled with the new behaviour — it already excludes
      `__context__` for its own reasons, and the two mechanisms must not
      double up into something neither owner intended.

## The author's answer (0a, who wrote `_chain` and `is_auth_error`)

[M] rsh102's AC required `exc` → `.orig` → `__cause__`. **Three links.
`__context__` is not among them** — it was added beyond the AC. The
acceptance auditor recorded it neutrally at the time as "a superset of
the three the AC names", and nobody asked what a superset costs.

[M] `db_credentials.py:21-22`, same author, same commit: *"a false
negative costs a delayed self-heal; a false positive costs an outage.
The matcher is deliberately narrow."*

`__context__` can only ever **add** matches. It cannot recover a rotation
that `.orig`/`__cause__` would miss; it can only turn non-auth failures
into `AUTH_FAILED`. So the destructive predicate was widened in the one
direction the file itself calls catastrophic, in the commit that says the
matcher is deliberately narrow. The stated reasoning was false-negative
coverage — "catch more wrapping shapes" — and the false-positive cost was
never weighed.

**Nothing is lost by narrowing the walk.** The fix is to bring
`is_auth_error` down to `EXPLICIT_LINKS`, not to widen the veto.

## Why no link set works (3b — the finding that redirects this spec)

The two cases are **the same graph shape with opposite right answers**:

| case | shape | right answer |
|---|---|---|
| `:96-104` cleanup failure during *this attempt's* auth error | `RuntimeError.__context__ -> Auth` | `AUTH_FAILED` — the self-heal firing |
| the timeout case | `TimeoutError -> CancelledError.__context__ -> Auth` | **not** `AUTH_FAILED` once the auth error is not the attempt's |

`is_auth_error` cannot see attempt ownership, so **no choice of links is
correct for both.** Traversal narrowing is therefore not a fix on its
own; it is a fix only once scope moves. 3b's one-line statement of the
invariant, which covers both rows:

> The classifier answers *"was this attempt's connection refused on
> credentials"*, and only the code that owns the attempt can say which
> errors are this attempt's.

"Follow wrapping, not history" is **how** to implement it; this is
**why**.

[M, 3b] Worth knowing for the design: inside the probe the same-attempt
cleanup case mostly never reaches the classifier anyway —
`_connect_once`'s `finally` swallows dispose failures precisely so a
noisy dispose cannot mask an auth error
(`test_a_failing_dispose_does_not_mask_an_auth_error`). The timeout path
is the one that does reach it, because cancellation is not swallowed.

## Two merged tests stand in the way — update, do not delete

[M, 3b, confirmed by 98] `test_db_credentials_classifier.py` pins the
behaviour this spec changes, in two places:

⚠️ **This spec said earlier that `:96-104` should be inverted. That was
wrong** — 98 proposed it and 0a agreed; 3b read the test and refuted it.
Recorded here rather than silently corrected, because inverting it is the
intuitive move and the next reader will have the same instinct.

1. **`test_auth_error_found_through_context_chain` (:96-104)** — **keep
   the assertion.** It is not the bug pinned as a requirement: in that
   shape the auth error *belongs to the attempt* (credentials genuinely
   rejected, cleanup merely failed afterwards), so `AUTH_FAILED` is
   correct and is the self-heal firing. Rewrite the docstring to say what
   it actually pins — *a cleanup failure during this attempt's own auth
   error must still classify `AUTH_FAILED`* — and **add the opposite case
   beside it**: an auth error that does **not** belong to the attempt
   must not. The pair is the specification.
2. **`test_auth_error_found_through_cause_chain` (:85-93)** — keep the
   assertion, rewrite the docstring: its stated justification is the
   **caller** surface ("the shape a re-raising caller produces"), which
   3b and 0a have measured closed.

   ⚠️ The earlier reason given here for keeping it — "it is the only pin
   on wrapper-spine traversal" — **is false**, caught by 0a. [M]
   `test_auth_error_found_through_sqlalchemy_orig` (:80) pins the wrapper
   spine via `wrapped()`, which builds `OperationalError(stmt, {}, orig)`
   — `.orig`, never `__cause__`. 3b asserted it, 98 repeated it, 0a
   checked it. Keeping `:85-93` may still be right; that justification is
   not available.

Handle both the way selfheal1 handled rsh102's E-2 fixture: **update in
the same commit with the reasoning in the diff**, and never let either
quietly weaken into an assertion that passes whatever the code does.

## Does `__cause__` survive the rule? Measured: on the wrapper path it is redundant

0a raised that "follow wrapping, not history" taken literally excludes
`__cause__` too — it is `raise X from Y`, an author's attribution of a
*different* exception — and flagged that it could not establish whether
SQLAlchemy sets `__cause__` alongside `.orig` on a real wrapped error.

[M, 98, SQLAlchemy 2.0.45, real wrapped DBAPI error from
`conn.execute(text(...))` against a missing table]:

```
type        : sqlalchemy OperationalError
.orig       : sqlite3.OperationalError
__cause__   : sqlite3.OperationalError
cause is orig : True          <-- the same object
```

So on the wrapper path `__cause__` carries nothing `.orig` does not.

⚠️ **THE TRAP: the test fixtures and the real driver disagree here, and
the suite cannot tell you so** [M, 3b, confirmed by 98]:

```
real SQLAlchemy wrap (2.0.45):                __cause__ is .orig -> True
hand-built OperationalError(stmt, {}, orig):  __cause__ is .orig -> False  (__cause__ is None)
```

Every classifier test builds wrappers the hand-built way — `wrapped()`
is used at `:84`, `:142`, `:253`, `:269` and its own definition. So:

- a fix that narrows to `.orig`-only passes the suite **and** is right in
  prod;
- a fix that leans on `__cause__ is .orig` passes in prod and **fails**
  the suite;
- a fix that silently depends on `__cause__` for the wrapper spine is
  **green in every test** (where `__cause__` is `None`, so `.orig`
  carries it) and diverges only on real errors.

The suite cannot distinguish the third from the first. That is the
"fixtures agree with the spec, the drivers don't" shape — the same gap
that produced this workstream's original miss. The one path that is **not**
wrapped is rsh105's `do_connect` listener, which sees the raw DBAPI error
(pinned by `test_unwrapped_dbapi_error_matches_too`) — the error is then
the node itself, needing no link at all. Neither observation licenses
dropping `__cause__` globally: that decision belongs with the scope
change, not before it.

## The one-sentence rule (3b): follow wrapping, not history

`.orig` means *the same error, unwrapped* — structural, always safe to
follow. `__cause__` / `__context__` mean *a different error, related in
time* — which is the ambiguity that produced all of this.

**Read it as "follow the wrapper spine, whichever attribute expresses
it"** [3b, on their own rule]: `.orig` always, and `__cause__` **when it
is the same object as `.orig`**. Applied literally as "`__cause__` is
history, drop it", someone would drop a link that on real errors *is*
the wrapper spine.

## Implementation note (0a): graph shape is the wrong basis

The invariant **cannot be enforced by traversal rules alone**, for the
reason above. It likely needs `_classify` to be *given* the attempt's own
exception explicitly — knowing which exception `_connect_once` raised and
refusing to consider anything not reachable from it by `.orig`/
`__cause__` — rather than inferring scope from graph shape. Graph shape
is what defeats every traversal-only fix tried here.

## Technical notes

- Owners to consult: 0a wrote `_chain` / `is_auth_error` / `_sqlstate_of`;
  3b added `is_missing_password` and the `EXPLICIT_LINKS` split in #52.
- Blast radius includes `services/api/src/routers/v1/health_router.py`
  via the probe verdicts, so this is not confined to `libraries/utils`.
- [I, 3b] **Do not let `DatabaseNotConfigured`'s lookup
  (`db_probe.py:393`) narrow by accident** when `_chain`'s default
  changes. It deliberately matches anywhere in the chain and it is
  fail-open, so wide is correct there — a mechanical "make everything
  narrow" edit would break it silently.
- Do not bundle into rsh105 (#45) — that PR's scope is the provider
  surface with zero call sites wired.

## Status log

- 2026-09-22T23:50 — **the spec's central AC was withdrawn.** 3b showed
  that narrowing `is_auth_error` to `EXPLICIT_LINKS` is harmful, not just
  insufficient: [M] it turns a real rotation with a noisy cleanup into
  `UNREACHABLE`, deleting the self-heal. The two cases are the same graph
  shape with opposite right answers, so no link set works and scope must
  move first. 0a separately refuted the "only pin on wrapper-spine
  traversal" claim, and 98 measured that SQLAlchemy sets
  `__cause__` **is** `.orig` on the wrapper path.
- 2026-09-22T23:30 — mechanism corrected twice more, each time by the
  peer who proposed the wrong version: 3b established that the
  **awaiting** frame sets `__context__` (refuting both "tasks isolate"
  and 98's "task inherits its creator"), which bounds violations to
  `_connect_once` and below; 0a established that `wait_for` sets an
  explicit cause and the leak is a two-hop path through an unsuppressed
  `CancelledError`, so no per-node flag check can close it. 98
  reproduced both before recording them.
- 2026-09-22T22:55 — 0a answered both open questions: no intent behind
  the wide walk (it contradicts the same file's stated principle), and B
  is not prod-reachable — but NOT via task isolation, which 0a
  hypothesised, measured, and refuted before sending. palateful-98
  independently reproduced all three measurements. Severity unchanged:
  lands before rsh106.
- 2026-09-22T22:40 — severity measured by palateful-98 (A/B/C table
  above) and ranked with 41: lands before rsh106; not escalated tonight,
  because "prod is drainable right now" is not supported by the evidence.
  If 0a or 3b constructs a prod-reachable B, it escalates immediately.
- 2026-09-22T22:20 — 3b supplied the fail-safe-inversion framing and the
  `DatabaseNotConfigured` caution; both folded in above.
- 2026-09-22T22:20 — filed by palateful-98. Idea and the two-variant
  measurement from palateful-0a; hit while reviewing rsh105's fail-open
  path. Sent to 0a and 3b for the traversal question before anyone
  implements.
