"""Async DB test fixtures (aam-4).

Mirror of the sync `db_session` pattern in `test_helper/conftest.py` but
for `AsyncSession`. Lives in its own module so callers that don't need
the async path don't pay the import cost (asyncpg is heavy).

Both fixtures are conditional on `ASYNC_DATABASE_URL` being set — the
worker + parser test images don't ship asyncpg, so they import
`test_helper` without these fixtures resolving. The skip-on-missing-URL
pattern keeps the dual-driver world coherent: any test that asks for
`async_db_session` while the URL is unset is told why it's skipped, not
left to crash deep inside SQLAlchemy.

Nested-tx rollback parity with the sync fixture: each test runs inside a
SAVEPOINT so commits inside production code don't escape the test, and
the outer transaction rolls back on teardown.
"""

import contextlib

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text


@pytest.fixture(scope="session")
def async_postgres_engine():
    """Create the async postgres engine once per testing session.

    Uses `ASYNC_DATABASE_URL` (asyncpg-scheme) derived in `utils.constants`
    from the same `DATABASE_URL` the sync engine reads. Skips the test if
    the URL is unset so the worker test image (no asyncpg) keeps passing.
    """
    from utils.constants import ASYNC_DATABASE_URL, ASYNC_DB_CONNECT_ARGS

    if not ASYNC_DATABASE_URL:
        pytest.skip("ASYNC_DATABASE_URL not set — skipping async DB fixture")

    # Mirrors the prod engine in `utils.services.database` — passes
    # `connect_args=ASYNC_DB_CONNECT_ARGS` so sslmode intent is
    # translated to asyncpg's `ssl` param the same way prod does.
    # Without this, a test DATABASE_URL with `sslmode=require` would
    # drop out of the connect-arg translation and either fail on the
    # verifying default context or connect without TLS — either way,
    # drift from prod behavior.
    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        connect_args=ASYNC_DB_CONNECT_ARGS,
    )
    yield engine


@pytest_asyncio.fixture
async def async_db_session(async_postgres_engine):
    """Async fixture providing an AsyncSession with savepoint rollback.

    Mirrors the sync `db_session` pattern: the outermost transaction
    rolls back on teardown so test mutations never leak; inside that, a
    SAVEPOINT is held continuously and re-opened after every commit so
    production code that calls `session.commit()` inside its own scope
    doesn't break test isolation.
    """
    connection = await async_postgres_engine.connect()
    transaction = await connection.begin()

    AsyncSessionLocal = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    session = AsyncSessionLocal()
    await session.begin_nested()

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _restart_savepoint(sess, _tx):
        if not sess.in_nested_transaction():
            sess.begin_nested()

    try:
        yield session
        # Defensive: a session left in an inconsistent state by the test
        # shouldn't mask the real failure with a teardown error.
        with contextlib.suppress(Exception):  # pragma: no cover
            await session.execute(text("SELECT pg_advisory_unlock_all();"))
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def async_database(async_db_session):
    """High-level `AsyncDatabase` wrapper bound to the test's session.

    Sync twin: `database` fixture in `test_helper/conftest.py`.
    """
    from utils.services.async_database import AsyncDatabase

    return AsyncDatabase(db=async_db_session)
