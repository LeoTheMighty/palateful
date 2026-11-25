"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from config import settings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp_server import build_mcp_app
from middleware.error_tracking import ErrorTrackingMiddleware
from middleware.latency_capture import LatencyCaptureMiddleware
from routers.v1_router import v1_router
from utils.api.endpoint import APIException

mcp_app = build_mcp_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on a malformed shelf-life seed (pantry-2).
    from utils.services.shelf_life_service import load_shelf_life_data
    load_shelf_life_data()

    # Register domain-event subscribers (pantry-3, pantry-4, ...).
    from api.subscribers import register_subscribers
    register_subscribers()

    # Load the unit-alias cache (riip-1) once at startup so the hot path
    # never pays a query on the first normalize_unit_display call. Best
    # effort — failures fall back to the lazy-init in the helper. Runs
    # on the sync engine (whitelisted off the event loop per epic design
    # principle #1) — must happen BEFORE the async engine warm-up so
    # sync-first ordering holds (aam-1).
    try:
        from utils.services.database import Database
        from utils.services.units import reload_unit_alias_cache

        startup_db = Database()
        try:
            reload_unit_alias_cache(startup_db.db)
        finally:
            startup_db.close()
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to load unit_alias cache on FastAPI startup"
        )

    # aam-1 / aam-23: async engine pool pre-warm. Prime *every* pooled
    # asyncpg connection (up to DB_ASYNC_POOL_SIZE) with a trivial
    # SELECT 1 so no real request pays asyncpg's prepared-statement
    # cache build (~100-300ms per fresh connection). The checkouts run
    # concurrently on purpose: a sequential loop hands the same
    # connection back on every iteration and only ever warms one.
    # Runs before the `yield`, so the app serves nothing — /v1/health
    # included — until the pool is hot. Lazy-imported so the worker
    # container, which reuses this module indirectly via utils, is not
    # forced to have the async engine configured.
    try:
        import asyncio

        from sqlalchemy import text
        from utils.constants import DB_ASYNC_POOL_SIZE
        from utils.services.database import async_db_engine

        if async_db_engine is not None:  # pragma: no branch
            async def _warm_one() -> None:
                async with async_db_engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))

            # return_exceptions so one bad connection doesn't abandon the
            # other in-flight checkouts mid-warm; the failures are
            # re-raised below into the best-effort handler.
            results = await asyncio.gather(
                *(_warm_one() for _ in range(DB_ASYNC_POOL_SIZE)),
                return_exceptions=True,
            )
            failures = [r for r in results if isinstance(r, BaseException)]
            if failures:
                raise RuntimeError(
                    f"{len(failures)}/{DB_ASYNC_POOL_SIZE} pool connections "
                    f"failed to warm"
                ) from failures[0]
    except Exception:
        # Best effort: a DB blip at boot must not crash-loop the task.
        # Un-warmed connections fall back to lazy init on first use.
        import logging
        logging.getLogger(__name__).exception(
            "Async engine warm-up failed on FastAPI startup"
        )

    # Start the MCP streamable-http session manager for the life of the process.
    # The session manager enforces a single .run() call per instance; tests that
    # enter this lifespan multiple times would trip that guard, so fall back to
    # a bare yield if it has already started.
    mcp_context = None
    try:
        mcp_context = mcp_app.router.lifespan_context(mcp_app)
        await mcp_context.__aenter__()
    except RuntimeError as exc:
        if "can only be called once" not in str(exc):
            raise
        mcp_context = None
    try:
        yield
    finally:
        if mcp_context is not None:
            await mcp_context.__aexit__(None, None, None)
        # Drain the latency writer before closing the DB pool so the last
        # ~2 s of in-flight samples land on disk rather than being lost on
        # ECS SIGTERM. See obs-latency-1.
        try:
            from utils.services.observability import get_request_writer
            get_request_writer().drain()
        except Exception:
            pass
        # Dispose the SQLAlchemy connection pools on shutdown to avoid
        # leaked connections against RDS/PostgreSQL when the container
        # is stopped. Reverse startup order: async first (drains
        # request-scoped sessions still holding asyncpg connections),
        # then sync (writers + one-shot paths).
        try:
            from utils.services.database import async_db_engine
            if async_db_engine is not None:  # pragma: no branch
                await async_db_engine.dispose()
        except Exception:
            pass
        try:
            from utils.services.database import db_engine
            if db_engine is not None:
                db_engine.dispose()
        except Exception:
            pass


app = FastAPI(
    title="Palateful API",
    description="Recipe management and cooking assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

# Error tracking middleware (must be added before CORS so it wraps all requests)
# FastAPI/Starlette runs middleware in reverse registration order, so the
# latency capture sits inside ErrorTrackingMiddleware — latency samples are
# recorded whether or not the inner handlers raised.
app.add_middleware(LatencyCaptureMiddleware)
app.add_middleware(ErrorTrackingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIException handler. APIExceptions raised inside Endpoint.run() are already
# caught there and converted to a CustomJSONResponse; this handler covers the
# path that bypasses the endpoint body — dependencies like get_current_user.
# Without it, a dependency-raised APIException propagates as an unhandled
# exception and the error-tracking middleware logs it as a 500, turning a
# plain expired-token signal into a noisy 500 in error_logs.
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    return JSONResponse(
        content={
            "error_code": exc.code,
            "error_message": exc.detail,
            "data": {},
        },
        status_code=exc.status_code,
    )


# Include routers
app.include_router(v1_router)

# Mount the MCP server at /mcp. Auth is handled inside `mcp_app` via
# MCPAuthMiddleware — do NOT wire FastAPI's Depends(get_current_user) here.
app.mount("/mcp", mcp_app)
