"""Credential-failure classification for the DB connection path.

Created by rsh102 (rotation-self-heal Phase 2, FR-2). Phase 5 (rsh105)
extends this module with `SecretPasswordProvider` /
`resolve_password_provider` / `register_rotating_credentials`; the
classifier below is the piece both phases share, which is why it lands
here rather than inside `db_probe`.

Why classification is load-bearing
----------------------------------
The health probe returns 503 — which ECS turns into a task replacement —
**only** when it can positively identify an authentication failure.
Everything else fails open. Both prod services run
`deployment_minimum_healthy_percent = 0` (`ecs/main.tf:371`, `:473`), so
a 503 from every task at once drains the service completely. That is the
correct response to a rotated credential (the tasks are unrecoverable
until they restart and re-resolve `DB_PASSWORD`) and exactly the wrong
response to a network blip, which replacement cannot fix and only
escalates.

So a false negative costs a delayed self-heal; a false positive costs an
outage. The matcher is deliberately narrow.

Matching strategy
-----------------
Two independent signals, either of which is sufficient:

1. **SQLSTATE** — `28P01` (`invalid_password`) only. psycopg2 exposes it
   as `.pgcode`, asyncpg as `.sqlstate`; both are checked.
2. **Message text** — connect-time errors from libpq arrive without a
   `PGresult`, so `.pgcode` is commonly `None` (plan.md:332-340) and the
   SQLSTATE signal alone would miss the single most important case.

**`28000` is deliberately not sufficient on its own.** It is
`invalid_authorization_specification`, which PostgreSQL's
`ClientAuthentication()` also raises for a pg_hba rejection ("no
pg_hba.conf entry for host ...", including the `rds.force_ssl` case where
the probe connects without TLS) and for a missing role ("role ... does
not exist"). None of those are fixed by replacing the task — a restarted
task re-reads the same config and fails identically — so treating them as
credential failures would drain a service to zero and keep it there. They
are caught by signal 2 when, and only when, the message actually says the
credentials were rejected.

Both signals are applied at every node of the exception chain. SQLAlchemy wraps
the DBAPI error (`.orig`), and `raise ... from exc` links the original
(`__cause__`/`__context__`) — but rsh105's `do_connect` listener sees the
**unwrapped** DBAPI error, because SQLAlchemy only wraps above the pool
creator. The same call therefore has to handle both shapes.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# The one SQLSTATE that means "this password is wrong" and nothing else.
# Deliberately not the whole class 28 — see the module docstring for why
# `28000` is excluded here; widening this set widens the blast radius of
# a false positive, and a false positive is an outage.
AUTH_SQLSTATES: frozenset[str] = frozenset({"28P01"})

# NOTE: `28000` deliberately has no constant of its own. It needs no
# separate check — the message signal already decides it, admitting the
# genuine "no password supplied" case and rejecting the pg_hba and
# missing-role cases. The discrimination is pinned by
# `test_28000_is_admitted_only_when_the_message_says_credentials` rather
# than by a frozenset nothing reads.

# Lowercased substrings. libpq's wording for the two ways a connection is
# refused on credentials. Kept narrow and anchored on libpq's own
# phrasing rather than loose keywords like "auth" or "password", which
# would match unrelated failures (e.g. a DNS error mentioning a hostname
# that happens to contain "auth").
AUTH_MESSAGE_PATTERNS: tuple[str, ...] = (
    "password authentication failed",
    "no password supplied",
)


def _sqlstate_of(exc: BaseException) -> str | None:
    """Pull a SQLSTATE off `exc`, whichever driver produced it.

    psycopg2 uses `.pgcode`, asyncpg uses `.sqlstate`. Either may be
    present-but-`None` on a connect-time error, so this returns `None`
    rather than raising when neither carries a usable value.
    """
    for attr in ("pgcode", "sqlstate"):
        value = getattr(exc, attr, None)
        if isinstance(value, str) and value:
            return value
    return None


def _chain(exc: BaseException):
    """Yield `exc` and every wrapped/causing exception beneath it.

    Order is outermost-first. Breadth-first over the three link kinds so
    a shallow `.orig` is reached before a deep `__context__` tail, and
    `seen` guards the cycles `__context__` can form during nested
    handling.
    """
    seen: set[int] = set()
    queue: list[BaseException] = [exc]
    while queue:
        node = queue.pop(0)
        if id(node) in seen:
            continue
        seen.add(id(node))
        yield node
        for attr in ("orig", "__cause__", "__context__"):
            nxt = getattr(node, attr, None)
            if isinstance(nxt, BaseException):
                queue.append(nxt)


def is_auth_error(exc: BaseException | None) -> bool:
    """True iff `exc` is positively identifiable as a credential failure.

    Walks `exc` → `.orig` → `__cause__` / `__context__` and returns True
    on the first node carrying an auth SQLSTATE *or* an auth message.
    Uncertainty returns False — the caller fails open, so "don't know"
    must never be reported as "credentials are bad".
    """
    if exc is None:
        return False

    for node in _chain(exc):
        sqlstate = _sqlstate_of(node)
        if sqlstate in AUTH_SQLSTATES:
            return True

        # `str(node)` on a SQLAlchemy wrapper already includes the orig's
        # message, so this also catches drivers that surface the text
        # without ever setting a SQLSTATE.
        message = str(node).lower()
        if any(pattern in message for pattern in AUTH_MESSAGE_PATTERNS):
            return True

    return False
