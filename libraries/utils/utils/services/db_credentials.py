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

**`no password supplied` is deliberately not an auth message either**
(selfheal1). libpq raises `fe_sendauth: no password supplied` when the
*client* had nothing to send — an empty `DB_PASSWORD`, or a URL with no
password component. The server never evaluated a credential. A replacement
task reads the same empty value from the same task definition and fails the
same way, so it is the pg_hba case wearing a different message. It is
recognised separately by `is_missing_password` so the probe can log it
loudly, but it fails open.

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
# separate check — the message signal already decides it, admitting a
# genuine credential rejection and refusing the pg_hba, missing-role and
# no-password cases. The discrimination is pinned by
# `test_28000_is_admitted_only_when_the_message_says_credentials` rather
# than by a frozenset nothing reads.

# Lowercased substrings. libpq's wording for a server that evaluated a
# credential and rejected it — the only phrasing that distinguishes "wrong
# password" from "no password". Kept narrow and anchored on libpq's own
# phrasing rather than loose keywords like "auth" or "password", which
# would match unrelated failures (e.g. a DNS error mentioning a hostname
# that happens to contain "auth").
#
# The message is the load-bearing signal — on psycopg2 it is the ONLY one
# (connect-time rejections carry `pgcode=None`) — so whatever is admitted
# here is a reason to destroy a task. Widen it only for a message that
# means a restart would resolve a different credential.
AUTH_MESSAGE_PATTERNS: tuple[str, ...] = ("password authentication failed",)

# The client had no password to send. A configuration error, not a rotated
# credential: see the module docstring. Recognised so it can be reported
# loudly — never so it can drive a 503.
MISSING_PASSWORD_PATTERN = "no password supplied"


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


#: Every link kind. `__context__` is set *implicitly* whenever an exception
#: is raised while another is being handled, so it can carry an error that
#: has nothing to do with this connect attempt.
ALL_LINKS: tuple[str, ...] = ("orig", "__cause__", "__context__")

#: The wrapper spine only: SQLAlchemy's `.orig` and an explicit
#: `raise ... from`. Used where an ambient `__context__` must not decide a
#: verdict — see `is_missing_password`.
EXPLICIT_LINKS: tuple[str, ...] = ("orig", "__cause__")


def _chain(exc: BaseException, links: tuple[str, ...] = ALL_LINKS):
    """Yield `exc` and every wrapped/causing exception beneath it.

    Order is outermost-first. Breadth-first over the link kinds so a
    shallow `.orig` is reached before a deep `__context__` tail, and `seen`
    guards the cycles `__context__` can form during nested handling.
    """
    seen: set[int] = set()
    queue: list[BaseException] = [exc]
    while queue:
        node = queue.pop(0)
        if id(node) in seen:
            continue
        seen.add(id(node))
        yield node
        for attr in links:
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


def is_missing_password(exc: BaseException | None) -> bool:
    """True iff `exc` says the client had no password to send.

    **This vetoes `is_auth_error`** at the call site (`db_probe._classify`).
    Both predicates walk the whole chain, so a retry path can produce a
    chain carrying both phrases — rsh105's `do_connect` listener will do
    exactly that: reject the cached password (`password authentication
    failed`), refresh, get an empty secret, retry (`no password supplied`),
    and raise the second `from` the first. The task then has no password to
    send, which a replacement cannot change, so the fail-open signal has to
    win. Doubt fails open, including doubt about which half of the chain is
    the live one.

    Only recognises libpq's wording, which is all the *sync* driver can
    produce. asyncpg never emits it — with no password it md5-hashes the
    empty string and the server answers `28P01` — so the async path detects
    the same condition from the URL instead
    (`db_probe._url_password_is_blank`).

    Walks `EXPLICIT_LINKS` only, **not** `__context__`. Because this vetoes
    a 503, an ambient context must not reach it: a probe called from inside
    an `except` that happens to be handling a passwordless failure would
    otherwise suppress the self-heal for a genuine, unrelated rotation.
    `.orig` and an explicit `raise ... from` are statements about *this*
    failure; `__context__` is only a statement about when it happened.
    """
    if exc is None:
        return False
    return any(
        MISSING_PASSWORD_PATTERN in str(node).lower()
        for node in _chain(exc, EXPLICIT_LINKS)
    )
