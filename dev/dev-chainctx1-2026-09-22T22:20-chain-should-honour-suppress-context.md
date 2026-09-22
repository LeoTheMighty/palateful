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

**Not reachable in prod today** [I, from measured evidence]: [M] outside
`db_probe.py` and its tests the only prod caller is
`health_router.py:32`, which calls `cached_verdict_async()` in a `try`
that is not handling anything else; the probe builds a fresh engine per
call, and `_connect_once`'s `finally` swallows dispose failures rather
than raising over a propagating auth error.

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
- [ ] `is_auth_error` walks `EXPLICIT_LINKS`, not `ALL_LINKS`. Check first
      whether rsh102 had a reason for the wide walk — [I, 3b] its docstring
      argues for `.orig` and `__cause__` specifically, and `__context__`
      may have come along unexamined. If there was a reason, it belongs in
      the spec before the change, not after.
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
