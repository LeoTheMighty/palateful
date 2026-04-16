"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp_server import build_mcp_app
from middleware.error_tracking import ErrorTrackingMiddleware
from routers.v1_router import v1_router

mcp_app = build_mcp_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on a malformed shelf-life seed (pantry-2).
    from utils.services.shelf_life_service import load_shelf_life_data
    load_shelf_life_data()

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
        # Dispose the SQLAlchemy connection pool on shutdown to avoid leaked
        # connections against RDS/PostgreSQL when the container is stopped.
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

# Include routers
app.include_router(v1_router)

# Mount the MCP server at /mcp. Auth is handled inside `mcp_app` via
# MCPAuthMiddleware — do NOT wire FastAPI's Depends(get_current_user) here.
app.mount("/mcp", mcp_app)
