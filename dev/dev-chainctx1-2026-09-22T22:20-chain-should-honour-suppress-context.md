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

⚠️ **It is NOT because `create_task` isolates exception context.** That
is the plausible-sounding protection someone will lean on later, and it
is false. [M] Measured independently by 0a and by palateful-98:

```
async via create_task (the health_router path):  __context__=AuthErr  is_auth_error=True
inline in the handler (the probe_sync path):     __context__=AuthErr  is_auth_error=True
```

A task created *from inside* a handler inherits that handler's context.
What IS true is that **cross-request contamination is impossible** [M]:
a concurrent request sitting mid-`except` cannot poison a different
request's probe —

```
request X mid-except, Y's probe raises:          __context__=None     is_auth_error=False
```

So B needs the *same* call path to be nested inside an auth handler.
Today's is not.

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

## Acceptance criteria

- [ ] `_chain` skips `__context__` on a node whose `__suppress_context__`
      is set, while continuing to walk `__cause__` and `.orig`.
- [ ] `is_auth_error` walks `EXPLICIT_LINKS`, not `ALL_LINKS`. **The
      author has answered: there was no case in mind, and nothing is lost
      by narrowing.** See "The author's answer" below — do not preserve
      `__context__` out of deference to an intent that never existed.
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
