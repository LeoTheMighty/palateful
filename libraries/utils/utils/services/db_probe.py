"""Fresh-connection database probe (rotation-self-heal Phase 2, FR-2).

The problem this exists to solve
--------------------------------
ECS resolves `DB_PASSWORD` into the task environment **once, at task
start**. When RDS rotates the managed master-user secret, every running
task is left holding a credential that no longer works. SQLAlchemy's
connection pool hides this: already-established connections stay
authenticated, so a task keeps answering a pooled `SELECT 1` long after
it can no longer open a *new* connection. That is precisely why the
previous `/v1/health` implementation — which probed a pooled connection
via `Depends(get_async_database)` — structurally could not observe a
rotation, and why the 2026-07-21 outage ran six days.

So `poolclass=NullPool` here is the entire point, not an optimization.
Every probe must be a genuinely new connection, with a real TCP + TLS
handshake and a real authentication exchange.

Fail-open
---------
A probe verdict of `AUTH_FAILED` becomes a 503, which becomes an ECS task
replacement. That is the self-heal: a restarted task re-resolves the
rotated password. But replacement cannot fix a timeout, a refused
connection, or DNS — there it converts a transient blip into a full
outage, because both services run
`deployment_minimum_healthy_percent = 0`. Everything that is not a
positively-identified auth failure therefore classifies as a
*non*-failing verdict. See `db_credentials.is_auth_error`.

The test for "may this 503?" is always the same: **would a restart change
the outcome?** A rotated password — yes, the new task resolves the new one.
An empty password, a pg_hba rejection, a missing `DATABASE_URL` — no: the
replacement reads the same task definition and fails identically, and with
no healthy floor the service drains to zero and stays there (selfheal1).

Every fail-open branch logs the phrase **`failing open`**. **No alarm
consumes it yet** — dfrcp1 is the spec that will add the CloudWatch metric
filter, and until it ships and is applied, every fail-open verdict here is
silent. The phrase is pinned as a contract now
(`test_every_fail_open_verdict_logs_failing_open`) precisely so that
filter has something stable to match: a rewording would otherwise drop a
whole failure mode from alerting while every verdict test still passed.

Rate limiting
-------------
The container health check (30s) and the ALB target group (60s) both land
on this probe, and after FR-5 each fresh connection also costs a
`get_secret_value`. `cached_verdict_async` holds a verdict for
`DB_PROBE_TTL_S` (default 60s) and is **single-flight**: concurrent
misses coalesce onto one in-flight attempt rather than each opening their
own connection. A plain TTL cache would let both checkers through on the
same tick — the exact window the budget is meant to cover.

Rate limiting — the sync path has no cache, deliberately
--------------------------------------------------------
`probe_sync` is **not** cached and **not** single-flight, and porting
`cached_verdict_async`'s machinery to it would be worse than useless:

    A module-global TTL cache in a process that starts fresh every
    invocation rate-limits nothing. It passes its own tests, looks
    correct, and never prevents a single connection.

rsh107 consumes this module as a container health check — `CMD-SHELL`
running `python -m utils.services.db_probe` — which is a **new Python
interpreter every tick**. `_cached` / `_inflight` are module globals;
they start empty every time. The async cache works only because uvicorn
is one long-lived process serving `/v1/health`.

What rate-limits the sync path is therefore the **schedule**: at an
interval of `SYNC_PROBE_MIN_CHECK_INTERVAL_S` or slower, the invocation
rate is already what `DB_PROBE_TTL_S` buys the async side. That makes the
interval a load-bearing assumption living in Terraform, invisible from
here — so it is pinned by `test_sync_probe_interval_assumption_holds`
rather than by this paragraph. A comment that can rot into a lie is worse
than no comment.

If an **in-process** caller of `probe_sync` ever appears (today there is
none outside this module's own tests), it needs its own rate limiting and
this reasoning no longer covers it.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from enum import Enum

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from utils.services.db_credentials import (
    _chain,
    is_auth_error,
    is_missing_password,
)

logger = logging.getLogger(__name__)

DEFAULT_PROBE_TTL_S = 60.0

# A probe that hangs is as bad as a probe that lies. The probe runs inline
# in the `/v1/health` request, so its budget has to fit inside the
# *tightest* consumer:
#
#   ALB target group   timeout = 3s  (terraform/modules/alb/main.tf:65)
#   container health   timeout = 5s  (terraform/modules/ecs/main.tf:321)
#
# A budget at or above 3s means the fail-open 200 is never delivered on
# the very scenario fail-open exists for: against a blackholed database
# the probe would still be waiting when the ALB gave up, and a timed-out
# check scores exactly like a failed one. `unhealthy_threshold = 3` then
# deregisters the target — mass replacement, non-auth cause.
#
# TOTAL, not just connect: `connect_args["timeout"]` bounds asyncpg's
# connection establishment only. A half-open TCP after an RDS failover
# completes the handshake and then hangs in `SELECT 1`, where nothing
# would otherwise stop it — the leader's task never resolves and every
# later caller coalesces onto it forever. Hence `asyncio.wait_for` around
# the whole attempt in `probe_async`.
PROBE_TOTAL_TIMEOUT_S = 2.5
PROBE_CONNECT_TIMEOUT_S = 2.0

# --- the sync twin's budget (syncprobe1) ---------------------------------
#
# `asyncio.wait_for` has NO sync equivalent, so `probe_sync` cannot be
# wrapped in one hard deadline. Three libpq settings cover three different
# ways the same attempt hangs, and it is worth being precise about which
# covers what, because the obvious one covers the least:
#
#   connect_timeout           establishment only (already set above)
#   statement_timeout         the SERVER cancels a slow `SELECT 1`
#   keepalives + count/interval   the CLIENT gives up on a dead peer
#
# `statement_timeout` alone does NOT close the gap this story is about.
# It is enforced server-side: after an RDS failover leaves a half-open
# TCP, the server is not reachable to enforce anything and the client sits
# in `recv()` with no data. Only TCP keepalives bound that case, and they
# bound it at `idle + interval * count`, not at the statement budget.
#
# So the honest statement of the sync budget is:
#   * slow-but-alive database  -> statement_timeout, ~0.5s
#   * unreachable at connect   -> connect_timeout, ~2s (libpq clamps 1->2)
#   * half-open after failover -> keepalives, ~9s worst case
#   * anything else            -> the container's `healthCheck.timeout`,
#                                 which is the only true hard deadline and
#                                 belongs to rsh107, not to this module.
PROBE_SYNC_STATEMENT_TIMEOUT_MS = 500
PROBE_SYNC_KEEPALIVES_IDLE_S = 3
PROBE_SYNC_KEEPALIVES_INTERVAL_S = 2
PROBE_SYNC_KEEPALIVES_COUNT = 3

#: The interval at or above which a caller may invoke `probe_sync` without
#: a cache in front of it. **This is a contract with rsh107's worker health
#: check**, and `test_sync_probe_interval_assumption_holds` fails if that
#: check is ever configured to run faster. See "Rate limiting — the sync
#: path has no cache, deliberately" in the module docstring for why the
#: schedule, rather than a cache, is the rate limit here.
SYNC_PROBE_MIN_CHECK_INTERVAL_S = 30.0

#: The `ENVIRONMENT` values under which a database is *expected*: exactly
#: the ones Terraform injects into the ECS task definitions
#: (`terraform/environments/{prod,dev}/main.tf` → `modules/ecs`). An
#: explicit allowlist, not a guess: anywhere else (tests, local runs with
#: no DB) an absent URL is a legitimate state and still classifies `OK`.
#: `"production"` is included because the root `SETUP.md`'s production
#: `.env` template used that spelling: a task deployed from that template
#: before envspell1 corrected it must not silently lose this verdict.
#: (envspell1 has since routed the gates through `utils.environment`; this
#: entry stays because keeping it is the fail-safe direction.)
#: Compared case-insensitively and whitespace-stripped, so `"PROD"` or a
#: newline-padded value cannot silently disable `NOT_CONFIGURED`.
#: `test_every_terraform_environment_is_covered` fails if a new Terraform
#: environment is added without being listed here.
DEPLOYED_ENVIRONMENTS: frozenset[str] = frozenset({"prod", "dev", "production"})


class DatabaseNotConfigured(Exception):
    """A database is expected here and no URL is configured.

    Passed to `_classify` as an exception rather than returned as a verdict
    so the seam's contract stays "return on success, raise on failure" and
    classification stays in one place. `_connect_once` raises it; the sync
    path constructs it and hands it straight to `_classify`, which matches
    it anywhere in the chain so an intervening wrapper cannot degrade the
    verdict to `UNKNOWN`.
    """


class ProbeVerdict(Enum):
    """Outcome of one fresh-connection attempt.

    Only `AUTH_FAILED` is actionable — it is the single verdict that
    drives a task replacement. The rest are reported for observability
    and all fail open.
    """

    #: Connected and authenticated — or no database is expected here, so
    #: there is nothing to connect to.
    OK = "OK"
    #: Positively identified credential failure. Drives the 503.
    AUTH_FAILED = "AUTH_FAILED"
    #: Reached the network layer but could not establish a session —
    #: timeout, refused connection, DNS. Replacement cannot fix this.
    UNREACHABLE = "UNREACHABLE"
    #: Something nobody anticipated. Fails open by construction: an
    #: unclassified error must never be reported as bad credentials.
    UNKNOWN = "UNKNOWN"
    #: A database is expected (deployed environment) but no URL is
    #: configured — e.g. an empty injected `DB_PASSWORD`, which makes
    #: `constants._build_database_url()` fall through to an unset
    #: `DATABASE_URL`. Not `OK`: the task is not healthy, every real request
    #: will fail. Not a 503: a restart re-reads the same task definition.
    NOT_CONFIGURED = "NOT_CONFIGURED"


# --------------------------------------------------------------------------
# Seams
#
# `_now`, `_probe_url` and `_connect_once` are module-level so tests can
# patch them individually: a fake clock without a fake connection, or a
# failing connection without a fake clock.
# --------------------------------------------------------------------------


def _now() -> float:
    """Monotonic clock seam. Monotonic, not wall-clock, so an NTP step
    cannot make a cached verdict look arbitrarily old or fresh."""
    return time.monotonic()


def _probe_url() -> str | None:
    """The async URL to probe, or `None` when there is nothing to probe.

    Read from `utils.constants` at call time rather than imported at
    module scope: the constant is computed from the environment at import,
    and reading it late keeps this honest under tests that adjust the
    environment, and under any future in-process credential refresh.
    """
    from utils import constants

    return constants.ASYNC_DATABASE_URL


def _url_password_is_blank(url: str | None) -> bool:
    """True iff `url` is a URL that carries no usable password.

    The async driver cannot tell us this. Given `password=None`, asyncpg's
    md5 path hashes the empty string and sends it, so the *server* answers
    `28P01 password authentication failed` — indistinguishable at the
    classifier from a rotated credential, and therefore a 503 that drains
    the service over a task that never had a password (selfheal1 Case 1, on
    the path `/v1/health` actually uses). libpq's `no password supplied`
    wording exists only on the sync driver.

    So the async path asks the configuration instead of the driver: if the
    URL we just failed to authenticate with has no password in it, the
    server had nothing real to reject and a replacement task will build the
    same URL.

    A whitespace-only password counts as blank — a trailing space or
    newline is a routine secret-extraction artifact, and a password made of
    whitespace is not one a rotation would produce.

    Unparseable input — and an absent URL, which is a different condition
    with its own verdict (`NOT_CONFIGURED`) — returns False: this function
    only ever *downgrades* a 503, so uncertainty must leave the self-heal
    alone. A rotation that goes unhealed is the six-day outage.
    """
    if not url:
        return False
    try:
        from sqlalchemy.engine.url import make_url

        password = make_url(url).password
    except Exception:  # noqa: BLE001 - never let URL parsing decide a verdict
        return False
    return password is None or not str(password).strip()


def _database_expected() -> bool:
    """Whether this process is somewhere a database must exist.

    Read at call time, like `_probe_url`, for the same reasons.
    """
    from utils import constants
    from utils.environment import canonical_environment

    # envspell1: normalisation is shared, the DEFAULT is not. This predicate
    # keeps its own allowlist and its own unknown -> False, because an
    # unrecognised value here must not start asserting NOT_CONFIGURED for
    # every local run with no database. `is_recording_environment`'s unknown -> True is
    # right for recorders and wrong here.
    return canonical_environment(constants.ENVIRONMENT) in DEPLOYED_ENVIRONMENTS


def _ttl_default() -> float:
    """`DB_PROBE_TTL_S`, read per-call so it is configurable at runtime.

    The environment wins over `constants.DB_PROBE_TTL_S` because that
    constant is frozen at import; reading late means the TTL can be
    changed without a redeploy.
    """
    raw = os.environ.get("DB_PROBE_TTL_S")
    if raw:
        parsed = _coerce_ttl(raw)
        if parsed is not None:
            return parsed
        logger.warning(
            "DB_PROBE_TTL_S=%r is not a usable TTL; falling back to the "
            "configured default",
            raw,
        )

    from utils import constants

    configured = _coerce_ttl(getattr(constants, "DB_PROBE_TTL_S", None))
    return DEFAULT_PROBE_TTL_S if configured is None else configured


def _coerce_ttl(raw: object) -> float | None:
    """Parse a TTL, returning `None` for anything unusable.

    Rejects more than just non-numbers, because the two numeric edge
    values are the dangerous ones and neither looks like a typo:

      `inf` — the first verdict observed at boot is served for the life
              of the task, so a rotation is never detected. That is the
              2026-07-21 outage, reintroduced by a config value.
      `nan` — every comparison against it is False, so the cache never
              hits and each request opens a fresh connection (and, after
              FR-5, a `get_secret_value`), defeating the rate limit this
              module exists to provide.

    Negatives are rejected for the same reason as `nan`, and so is
    **zero**: a TTL of 0 means no comparison ever holds, so every caller
    opens a fresh connection and a `get_secret_value` with it. It defeats
    the budget exactly as `nan` does, and it is likelier to be typed.
    """
    if raw is None:
        return None
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")) or value <= 0:
        return None
    return value


async def _connect_once() -> None:
    """Open exactly one new connection and run `SELECT 1`.

    Returns cleanly on success; raises whatever the driver raised on
    failure — classification is the caller's job. A `None` URL is a
    no-op success where no database is expected, and `DatabaseNotConfigured`
    where one is.
    """
    url = _probe_url()
    if not url:
        if _database_expected():
            raise DatabaseNotConfigured("no async database URL is configured")
        return

    from utils import constants

    connect_args = dict(getattr(constants, "ASYNC_DB_CONNECT_ARGS", {}) or {})
    connect_args.setdefault("timeout", PROBE_CONNECT_TIMEOUT_S)

    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args=connect_args,
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        # NullPool holds nothing, but the engine still owns a dialect and
        # its own bookkeeping; disposing keeps a probe every 60s for the
        # life of a task from accumulating them.
        #
        # Swallow dispose failures: an exception raised in `finally`
        # REPLACES the one propagating out of the body, so a noisy
        # dispose would turn a genuine `InvalidPasswordError` into an
        # unclassified one — verdict UNKNOWN, 200, rotation missed.
        try:
            await engine.dispose()
        except Exception:  # noqa: BLE001
            logger.warning("db probe: engine dispose failed", exc_info=True)


async def probe_async() -> ProbeVerdict:
    """One uncached fresh-connection probe. Never raises.

    The whole attempt is bounded by `PROBE_TOTAL_TIMEOUT_S`. A timeout is
    not a credential failure, so it fails open like any other
    connectivity problem.
    """
    try:
        await asyncio.wait_for(_connect_once(), timeout=PROBE_TOTAL_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 - classification is the point
        return _downgrade_passwordless_auth_failure(_classify(exc), _safe_probe_url())
    return ProbeVerdict.OK


def _safe_probe_url() -> str | None:
    """`_probe_url()`, never raising. It is a seam; seams get patched."""
    try:
        return _probe_url()
    except Exception:  # noqa: BLE001
        logger.warning("db probe: probe URL lookup failed", exc_info=True)
        return None


def _downgrade_passwordless_auth_failure(
    verdict: ProbeVerdict, url: str | None
) -> ProbeVerdict:
    """Turn a 503 into a fail-open when we never sent a password.

    Only ever downgrades `AUTH_FAILED`, and only when the URL that failed
    carries no usable password. Everything else passes through untouched,
    so a genuine rotation still self-heals.

    **Load-bearing precondition, for rsh105/rsh106.** This is safe because
    `constants._build_database_url()` composes a URL only when `DB_PASSWORD`
    is truthy, so in a deployed environment a passwordless URL means a
    genuinely absent password rather than a password supplied by some other
    route. FR-5 supplies the password at connect time through a
    `do_connect` listener; if anyone then drops `DB_PASSWORD` from the task
    definition — the natural end-state of "the secret is resolved at connect
    time" — every URL becomes passwordless and **every real rotation
    rejection would silently downgrade here, deleting the self-heal.** Tie
    any such change to this function: it must then consult the listener's
    resolved credential, not the URL.
    """
    if verdict is not ProbeVerdict.AUTH_FAILED or not _url_password_is_blank(url):
        return verdict

    logger.error(
        "db probe: authentication was rejected for a URL that carries no "
        "password — a configuration error, not a rotation, and a restart "
        "rebuilds the same URL; failing open",
    )
    return ProbeVerdict.UNREACHABLE


def _classify(exc: BaseException) -> ProbeVerdict:
    """Map a connect failure onto a verdict, failing open on doubt.

    `is_auth_error` reads attributes and calls `str()` on driver-supplied
    exception objects, and it runs *inside* an `except` block — so if it
    raises, its exception replaces the verdict and propagates out of the
    probe, reaching the endpoint as a 500. The container health check
    (`urllib.request.urlopen`) raises `HTTPError` on any non-2xx, so a
    500 kills the task exactly as hard as a 503 would. Doubt fails open,
    including doubt about the classifier itself.
    """
    if any(isinstance(node, DatabaseNotConfigured) for node in _chain(exc)):
        from utils import constants

        logger.error(
            "db probe: no database configured in deployed environment %r — "
            "every real request will fail, and a restart re-reads the same "
            "task definition so it cannot fix this; failing open",
            constants.ENVIRONMENT,
        )
        return ProbeVerdict.NOT_CONFIGURED

    # Order matters: the missing-password signal VETOES the auth signal, it
    # does not lose to it. Both predicates walk the whole exception chain,
    # so a retry path can produce a chain carrying both phrases (rsh105's
    # listener: reject cached password -> refresh -> empty secret -> retry).
    # A task with no password to send is not fixed by replacing it, and
    # doubt fails open.
    try:
        missing_password = is_missing_password(exc)
        auth = not missing_password and is_auth_error(exc)
    except Exception:  # noqa: BLE001 - the classifier itself misbehaved
        logger.exception(
            "db probe: classifier raised on %s — failing open",
            type(exc).__name__,
        )
        return ProbeVerdict.UNKNOWN

    if auth:
        logger.error(
            "db probe: credential failure — this task cannot re-authenticate "
            "without a restart (%s: %s)",
            type(exc).__name__,
            exc,
        )
        return ProbeVerdict.AUTH_FAILED

    # Error, not warning: this is a deployment configuration fault that will
    # not clear on its own, unlike the transient cases below.
    if missing_password:
        logger.error(
            "db probe: this task has no database password to send — a "
            "configuration error a restart cannot fix; failing open (%s: %s)",
            type(exc).__name__,
            exc,
        )
        return ProbeVerdict.UNREACHABLE

    # `TimeoutError` (which `asyncio.TimeoutError` aliases on 3.11+) is
    # itself an `OSError` subclass, so the wait_for timeout lands here.
    if isinstance(exc, OperationalError | OSError):
        logger.warning(
            "db probe: database unreachable, failing open (%s: %s)",
            type(exc).__name__,
            exc,
        )
        return ProbeVerdict.UNREACHABLE

    logger.warning(
        "db probe: unclassified failure, failing open (%s: %s)",
        type(exc).__name__,
        exc,
    )
    return ProbeVerdict.UNKNOWN


# --------------------------------------------------------------------------
# Single-flight TTL cache
# --------------------------------------------------------------------------

#: `(observed_at, verdict)` or None. `observed_at` is stamped when the
#: probe *started*, so the documented "one fresh connection per TTL"
#: budget holds regardless of how long the probe itself took.
_cached: tuple[float, ProbeVerdict] | None = None
#: The in-flight probe, if one is running. A TASK, not a bare future, and
#: deliberately independent of whichever caller happened to start it: if
#: that caller's request is torn down the probe still completes and every
#: coalesced waiter still gets a verdict. A future completed by the leader
#: inline would instead propagate the leader's cancellation to all of them
#: — and an ALB timeout cancelling the handler makes that the common case,
#: not a corner one.
_inflight: asyncio.Task[ProbeVerdict] | None = None


def _reset_verdict_cache() -> None:
    """Drop the cached verdict and any in-flight probe.

    The cache is process-global, so a leaked `AUTH_FAILED` would make
    every other test that touches `/v1/health` order-dependent. The
    autouse fixture in `services/api/tests/conftest.py` calls this.
    """
    global _cached, _inflight
    _cached = None
    if _inflight is not None and not _inflight.done():
        _inflight.cancel()
    _inflight = None


def _clear_inflight(task: asyncio.Task[ProbeVerdict]) -> None:
    """Retire `task` from the in-flight slot — but only if it is still ours.

    Clearing unconditionally lets a finishing probe blank a *newer*
    probe's registration (reset-then-reprobe makes this reachable), after
    which the next caller sees an empty slot and opens a second
    concurrent connection — silently breaking the single-flight guarantee
    this module exists to provide.
    """
    global _inflight
    if _inflight is task:
        _inflight = None


async def _run_probe() -> ProbeVerdict:
    """Probe once and publish the verdict. The body of the shared task."""
    global _cached
    started = _now()
    verdict = await probe_async()
    _cached = (started, verdict)
    return verdict


async def cached_verdict_async(ttl_s: float | None = None) -> ProbeVerdict:
    """The current verdict, at most one fresh connection per `ttl_s`.

    Single-flight: a caller arriving while a probe runs awaits that probe
    rather than starting its own.
    """
    global _inflight

    # Routed through `_coerce_ttl` rather than trusted: an explicit
    # `ttl_s=0` / `nan` / negative from a caller defeats the rate limit
    # just as surely as the same value from the environment, and that
    # path was validated while this one was not.
    coerced = None if ttl_s is None else _coerce_ttl(ttl_s)
    if ttl_s is not None and coerced is None:
        logger.warning(
            "cached_verdict_async(ttl_s=%r) is not a usable TTL; using the "
            "configured default",
            ttl_s,
        )
    ttl = _ttl_default() if coerced is None else coerced

    cached = _cached
    if cached is not None and (_now() - cached[0]) < ttl:
        return cached[1]

    loop = asyncio.get_running_loop()
    inflight = _inflight

    # A task belongs to the loop that created it. Anything running more
    # than one loop per process — `asyncio.run` per Celery task, which is
    # what `utils/tasks/task.py` does and what rsh107's worker health
    # check will reach — can otherwise find a leaked task from a dead loop
    # here and raise "attached to a different loop" on every later call.
    if inflight is not None and inflight.get_loop() is not loop:
        inflight = None

    if inflight is None or inflight.done():
        inflight = loop.create_task(_run_probe())
        _inflight = inflight
        inflight.add_done_callback(_clear_inflight)

    # `shield` so a caller whose own request is cancelled does not cancel
    # the shared probe out from under everyone else waiting on it.
    return await asyncio.shield(inflight)


# --------------------------------------------------------------------------
# Sync surface
# --------------------------------------------------------------------------


def _sync_connect_args(connect_timeout: int) -> dict:
    """libpq settings bounding each way a sync probe can hang.

    `options` carries `statement_timeout`, which the **server** enforces
    against a slow `SELECT 1`. The keepalive settings are what bound a
    **dead peer**, where the server can enforce nothing because nothing
    reaches it — the half-open TCP after an RDS failover that this story
    exists to stop hanging on.

    A psycopg2-only shape: the async twin passes asyncpg's own
    `timeout` and gets its hard deadline from `asyncio.wait_for` instead.
    """
    return {
        "connect_timeout": connect_timeout,
        "options": f"-c statement_timeout={PROBE_SYNC_STATEMENT_TIMEOUT_MS}",
        "keepalives": 1,
        "keepalives_idle": PROBE_SYNC_KEEPALIVES_IDLE_S,
        "keepalives_interval": PROBE_SYNC_KEEPALIVES_INTERVAL_S,
        "keepalives_count": PROBE_SYNC_KEEPALIVES_COUNT,
    }


def probe_sync() -> ProbeVerdict:
    """Blocking twin of `probe_async`, for non-async callers.

    Used by the CLI below and by the worker health check (rsh107), which
    has no event loop of its own. Builds its own `NullPool` engine off
    the sync URL for the same reason the async path does.

    **Behaviour change (syncprobe1):** the probe now sets
    `statement_timeout` and TCP keepalives on its own connection, so a
    query that hangs is cancelled rather than blocking forever. This
    affects the probe's connection only — `NullPool`, opened and disposed
    per call — never the application engines in `utils.services.database`.
    A cancelled `SELECT 1` surfaces as a driver error, classifies
    non-auth, and therefore **fails open**: a slow database reports
    `UNREACHABLE`, never `AUTH_FAILED`.
    """
    from sqlalchemy import create_engine

    from utils import constants

    url = constants.DATABASE_URL
    if not url:
        if not _database_expected():
            return ProbeVerdict.OK
        # Inside a try for the same reason `create_engine` is below: an
        # exception escaping here reaches the CLI as exit 1, which it
        # documents as AUTH_FAILED — during an incident that reads as "the
        # credentials rotated" when nothing of the sort happened.
        try:
            return _classify(
                DatabaseNotConfigured("no sync database URL is configured")
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "db probe: classifying an absent URL failed; failing open"
            )
            return ProbeVerdict.UNKNOWN

    # libpq's `connect_timeout` is an integer number of seconds, and 0
    # means "wait indefinitely" — so a sub-second budget must round UP to
    # 1, never truncate to 0. (libpq also silently clamps 1 to 2.)
    connect_timeout = max(1, math.ceil(PROBE_CONNECT_TIMEOUT_S))

    # Classified, not raised: `create_engine` raises `ArgumentError` on a
    # malformed URL, and the async twin classifies that same input rather
    # than raising. An uncaught raise here would also give the CLI exit
    # code 1, which it documents as AUTH_FAILED — during an incident an
    # operator reads exit 1 and concludes the credentials rotated when
    # the URL is merely malformed.
    try:
        engine = create_engine(
            url,
            poolclass=NullPool,
            connect_args=_sync_connect_args(connect_timeout),
        )
    except Exception as exc:  # noqa: BLE001 - classification is the point
        return _classify(exc)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - classification is the point
        return _downgrade_passwordless_auth_failure(_classify(exc), url)
    finally:
        # Swallowed for the same reason as the async twin: an exception
        # from `finally` replaces the one propagating out of the body,
        # which would downgrade a real auth failure to UNKNOWN.
        try:
            engine.dispose()
        except Exception:  # noqa: BLE001
            logger.warning("db probe: sync engine dispose failed", exc_info=True)
    return ProbeVerdict.OK


def main(argv: list[str] | None = None) -> int:
    """`python -m utils.services.db_probe` — probe once, print, exit.

    Exit `1` **only** for `AUTH_FAILED`; `0` for every fail-open verdict,
    `NOT_CONFIGURED` included.

    The exit code is not an operator-facing severity scale, because the
    caller that matters is not a human. rsh107 wires this module as the
    worker container's `CMD-SHELL` health check, and ECS treats **any**
    non-zero exit as unhealthy — so a distinct code for `NOT_CONFIGURED`
    would replace the worker task over precisely the condition this module
    invented that verdict to stop replacing tasks over, on a service with
    `deployment_minimum_healthy_percent = 0` and no ALB floor. The printed
    verdict name is what serves the operator; the exit code answers one
    question only, and it is "should this task be replaced?".
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m utils.services.db_probe",
        description="Open one fresh DB connection and classify the result.",
    )
    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="probe via the asyncpg URL instead of the sync psycopg2 one",
    )
    args = parser.parse_args(argv)

    verdict = asyncio.run(probe_async()) if args.use_async else probe_sync()

    print(verdict.name)
    return 1 if verdict is ProbeVerdict.AUTH_FAILED else 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
