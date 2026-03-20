"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.v1_router import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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
