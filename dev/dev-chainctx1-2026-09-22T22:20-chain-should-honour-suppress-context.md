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

- 2026-09-22T22:20 — 3b supplied the fail-safe-inversion framing and the
  `DatabaseNotConfigured` caution; both folded in above.
- 2026-09-22T22:20 — filed by palateful-98. Idea and the two-variant
  measurement from palateful-0a; hit while reviewing rsh105's fail-open
  path. Sent to 0a and 3b for the traversal question before anyone
  implements.
