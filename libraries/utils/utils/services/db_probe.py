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

Rate limiting
-------------
The container health check (30s) and the ALB target group (60s) both land
on this probe, and after FR-5 each fresh connection also costs a
`get_secret_value`. `cached_verdict_async` holds a verdict for
`DB_PROBE_TTL_S` (default 60s) and is **single-flight**: concurrent
misses coalesce onto one in-flight attempt rather than each opening their
own connection. A plain TTL cache would let both checkers through on the
same tick — the exact window the budget is meant to cover.
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

from utils.services.db_credentials import is_auth_error

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


class ProbeVerdict(Enum):
    """Outcome of one fresh-connection attempt.

    Only `AUTH_FAILED` is actionable — it is the single verdict that
    drives a task replacement. The rest are reported for observability
    and all fail open.
    """

    #: Connected and authenticated (or there is nothing to connect to).
    OK = "OK"
    #: Positively identified credential failure. Drives the 503.
    AUTH_FAILED = "AUTH_FAILED"
    #: Reached the network layer but could not establish a session —
    #: timeout, refused connection, DNS. Replacement cannot fix this.
    UNREACHABLE = "UNREACHABLE"
    #: Something nobody anticipated. Fails open by construction: an
    #: unclassified error must never be reported as bad credentials.
    UNKNOWN = "UNKNOWN"


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

    Negatives are rejected for the same reason as `nan`.
    """
    if raw is None:
        return None
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")) or value < 0:
        return None
    return value


async def _connect_once() -> None:
    """Open exactly one new connection and run `SELECT 1`.

    Returns cleanly on success; raises whatever the driver raised on
    failure — classification is the caller's job. A `None` URL is a
    no-op success: there is nothing to authenticate against, so there is
    no credential to be wrong.
    """
    url = _probe_url()
    if not url:
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
        return _classify(exc)
    return ProbeVerdict.OK


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
    try:
        auth = is_auth_error(exc)
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

    ttl = _ttl_default() if ttl_s is None else ttl_s

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


def probe_sync() -> ProbeVerdict:
    """Blocking twin of `probe_async`, for non-async callers.

    Used by the CLI below and by the worker health check (rsh107), which
    has no event loop of its own. Builds its own `NullPool` engine off
    the sync URL for the same reason the async path does.
    """
    from sqlalchemy import create_engine

    from utils import constants

    url = constants.DATABASE_URL
    if not url:
        return ProbeVerdict.OK

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
            connect_args={"connect_timeout": connect_timeout},
        )
    except Exception as exc:  # noqa: BLE001 - classification is the point
        return _classify(exc)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - classification is the point
        return _classify(exc)
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

    Exit code 0 for any fail-open verdict and 1 only for `AUTH_FAILED`,
    mirroring the endpoint: the caller should act on bad credentials and
    ignore everything else. Useful for confirming from a shell whether a
    given environment's credentials are live — which, during the
    2026-07-21 incident, took far longer than it should have.
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
