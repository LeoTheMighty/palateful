"""Database session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_engine(database_url: str):
    """Create async SQLAlchemy engine."""
    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Global session factory - initialized by the application
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Initialize the global session factory."""
    global _session_factory
    engine = create_engine(database_url)
    _session_factory = create_session_factory(engine)
    return _session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session."""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call init_session_factory first.")
    async with _session_factory() as session:
        yield session
