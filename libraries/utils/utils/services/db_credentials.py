"""Credential-failure classification for the DB connection path.

Created by rsh102 (rotation-self-heal Phase 2, FR-2). Phase 5 (rsh105)
extends this module with `SecretPasswordProvider` /
`resolve_password_provider` / `register_rotating_credentials`; the
classifier below is the piece both phases share, which is why it lands
here rather than inside `db_probe`. See "Connect-time resolution" at the
end of this docstring for the Phase 5 surface.

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

Connect-time resolution (rsh105, FR-5a)
---------------------------------------
`register_rotating_credentials(engine)` attaches a `do_connect` listener
that sets `cparams["password"]` from a `SecretPasswordProvider` on every
new DBAPI connection, so a rotated password is picked up without a task
restart. On an auth failure it invalidates the cache, re-resolves, and
retries **exactly once**; a second auth failure, or any non-auth error,
propagates.

With `DB_PASSWORD_SECRET_ARN` unset the whole surface is inert — no
boto3 client, no listener — so local, docker-compose and CI engines are
built exactly as before. `_build_database_url()` in `utils/constants.py`
stays the only place URLs are composed; the listener only overrides the
password per connection.

The `DB_PASSWORD` fallback is legal on the **first** resolution only (a
Secrets Manager outage at boot is then no worse than today). On the
retry path it would hand back the password the database just rejected,
making an SM outage look like "no rotation occurred" — so the retry
raises `CredentialResolutionError` and logs an ERROR instead.

The resolved password lives only in memory. It is never logged.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

import boto3
from botocore.config import Config
from sqlalchemy import event

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


# ---------------------------------------------------------------------------
# Connect-time credential resolution (rsh105)
# ---------------------------------------------------------------------------

SECRET_ARN_ENV = "DB_PASSWORD_SECRET_ARN"
SECRET_TTL_ENV = "DB_SECRET_TTL_S"
FALLBACK_PASSWORD_ENV = "DB_PASSWORD"
DEFAULT_SECRET_TTL_S = 300.0

# Deliberately not `AWSService`'s config: that one is tuned to an S3 NFR
# budget (s3v4 signing, 2s read timeout). This fetch sits on the connect
# path, where a hung call stalls a pool checkout, but a spurious timeout
# costs a failed connect rather than a slow upload.
_SECRETS_MANAGER_CONFIG = Config(
    connect_timeout=3,
    read_timeout=5,
    retries={"max_attempts": 3, "mode": "standard"},
)

# Set on an engine once its listener is attached, so a repeated call is a
# no-op instead of a second provider with its own cache.
_REGISTERED_ATTR = "_palateful_rotating_credentials"


class CredentialResolutionError(RuntimeError):
    """The password could not be resolved and no safe fallback exists.

    Raised on the retry path when Secrets Manager fails, so an SM outage
    during a rotation is told apart from "the database rejected the
    password twice" (which surfaces as the driver's own auth error).

    Its chain carries the Secrets Manager error only, never the auth
    error that triggered the retry, so `is_auth_error` returns False for
    it and the health probe fails open. That is deliberate: a replacement
    task cannot fix a Secrets Manager outage — it would fetch from the
    same unavailable service at startup.
    """


def _region_from_arn(arn: str) -> str | None:
    """`arn:aws:secretsmanager:<region>:...` → `<region>`, else None."""
    parts = arn.split(":")
    if len(parts) >= 6 and parts[0] == "arn" and parts[3]:
        return parts[3]
    return None


def _ttl_from_env() -> float:
    """`DB_SECRET_TTL_S` as a non-negative float, else the default."""
    raw = os.environ.get(SECRET_TTL_ENV, "").strip()
    if not raw:
        return DEFAULT_SECRET_TTL_S
    try:
        ttl = float(raw)
    except ValueError:
        ttl = -1.0
    if not 0 <= ttl < float("inf"):
        logger.warning(
            "%s=%r is not a non-negative number; using %ss",
            SECRET_TTL_ENV,
            raw,
            DEFAULT_SECRET_TTL_S,
        )
        return DEFAULT_SECRET_TTL_S
    return ttl


class SecretPasswordProvider:
    """TTL-cached DB password read from a Secrets Manager secret.

    The secret is the RDS-managed JSON shape (`{"username", "password"}`).
    The boto3 client is built on first use, never at construction, so a
    provider that is never asked costs nothing.
    """

    def __init__(
        self,
        secret_arn: str,
        ttl_s: float = DEFAULT_SECRET_TTL_S,
        client: Any = None,
    ) -> None:
        self._secret_arn = secret_arn
        self._ttl_s = ttl_s
        self._client = client
        self._password: str | None = None
        self._expires_at = 0.0
        self._attempted = False
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = boto3.client(
                "secretsmanager",
                region_name=_region_from_arn(self._secret_arn),
                config=_SECRETS_MANAGER_CONFIG,
            )
        return self._client

    def _fetch(self) -> str:
        response = self._get_client().get_secret_value(SecretId=self._secret_arn)
        password = json.loads(response["SecretString"])["password"]
        if not isinstance(password, str) or not password:
            raise ValueError("secret has no usable 'password' field")
        return password

    def current(self, *, strict: bool = False) -> str:
        """The password, from cache while fresh, else from Secrets Manager.

        When the fetch fails:

        - `strict=True` (the auth-retry path) raises
          `CredentialResolutionError` — never a fallback.
        - A previously resolved value that merely aged out is served
          again for another TTL (last known good beats the env var).
        - On the very first resolution, `DB_PASSWORD` is used if set.
        - Otherwise (the cache was invalidated) it raises.
        """
        with self._lock:
            now = time.monotonic()
            if self._password is not None and now < self._expires_at:
                return self._password

            first = not self._attempted
            self._attempted = True
            try:
                password = self._fetch()
            except Exception as exc:
                return self._on_fetch_failure(exc, now, first=first, strict=strict)

            self._password = password
            self._expires_at = now + self._ttl_s
            return password

    def _on_fetch_failure(
        self, exc: Exception, now: float, *, first: bool, strict: bool
    ) -> str:
        # Messages name the exception type only: botocore errors can echo
        # request details, and nothing credential-adjacent belongs in logs.
        kind = type(exc).__name__
        if strict:
            logger.error(
                "DB auth failed and re-resolving the password from Secrets "
                "Manager also failed (%s); not retrying with the rejected "
                "password",
                kind,
            )
            raise CredentialResolutionError(
                f"Secrets Manager unavailable while re-resolving a rejected "
                f"DB password ({kind})"
            ) from exc

        if self._password is not None:
            logger.warning(
                "Secrets Manager refresh failed (%s); serving the cached "
                "password for another %ss",
                kind,
                self._ttl_s,
            )
            self._expires_at = now + self._ttl_s
            return self._password

        fallback = os.environ.get(FALLBACK_PASSWORD_ENV)
        if first and fallback:
            logger.warning(
                "Secrets Manager unavailable at first resolution (%s); "
                "falling back to %s",
                kind,
                FALLBACK_PASSWORD_ENV,
            )
            self._password = fallback
            self._expires_at = now + self._ttl_s
            return fallback

        logger.error("Secrets Manager unavailable (%s); no fallback password", kind)
        raise CredentialResolutionError(
            f"could not resolve the DB password ({kind})"
        ) from exc

    def invalidate(self) -> None:
        """Drop the cached password; the next `current()` fetches."""
        with self._lock:
            self._password = None
            self._expires_at = 0.0


def resolve_password_provider() -> SecretPasswordProvider | None:
    """A provider for `DB_PASSWORD_SECRET_ARN`, or None when it is unset.

    None is the inert path: callers must then change nothing.
    """
    secret_arn = os.environ.get(SECRET_ARN_ENV, "").strip()
    if not secret_arn:
        return None
    return SecretPasswordProvider(secret_arn, ttl_s=_ttl_from_env())


def _make_do_connect(provider: SecretPasswordProvider):
    def do_connect(dialect, conn_rec, cargs, cparams):
        cparams["password"] = provider.current()
        try:
            return dialect.connect(*cargs, **cparams)
        except Exception as exc:
            if not is_auth_error(exc):
                raise
            logger.warning(
                "DB rejected the cached password; re-resolving from Secrets "
                "Manager and retrying once"
            )

        provider.invalidate()
        cparams["password"] = provider.current(strict=True)
        try:
            return dialect.connect(*cargs, **cparams)
        except Exception as exc:
            if is_auth_error(exc):
                logger.error(
                    "DB rejected the freshly re-resolved password too; not "
                    "retrying again"
                )
            raise

    return do_connect


def register_rotating_credentials(engine: Any) -> bool:
    """Attach connect-time password resolution to `engine`.

    Returns False — having constructed nothing and registered nothing —
    when `DB_PASSWORD_SECRET_ARN` is unset; True once a listener is on
    the engine (a repeat call does not add a second one). Async engines
    are handled through `engine.sync_engine`.
    """
    provider = resolve_password_provider()
    if provider is None:
        return False

    target = getattr(engine, "sync_engine", engine)
    if getattr(target, _REGISTERED_ATTR, False):
        return True

    event.listen(target, "do_connect", _make_do_connect(provider))
    setattr(target, _REGISTERED_ATTR, True)
    return True
