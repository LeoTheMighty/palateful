"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from palateful_utils.db.session import init_session_factory
from src.config import settings
from src.routers import health, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Initialize database session factory
    init_session_factory(settings.database_url)
    yield
    # Shutdown: Clean up resources if needed


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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(users.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Palateful API", "version": "0.1.0"}
