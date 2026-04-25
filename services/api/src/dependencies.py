"""FastAPI dependency injection for database and authentication."""

import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from config import settings
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.constants import LOGGING_LEVEL
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.services.async_database import AsyncDatabase
from utils.services.database import AsyncSessionLocal, Database, SessionLocal

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)

_E2E_TOKEN = "e2e-test-token"
_E2E_AUTH0_ID = "e2e|test-user"
_DEFAULT_CALENDAR_NAME = "My Calendar"
_TRYING_OUT_BOOK_NAME = "Trying Out"


def get_db():
    """Gets the database session as a FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database():
    """Gets the high level database object as a FastAPI dependency."""
    database = Database()
    try:
        yield database
    finally:
        database.close()


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """Yield a request-scoped AsyncSession (aam-1).

    Stub for the async path. The real `AsyncDatabase` wrapper arrives in
    aam-2 and will be injected via `get_async_database`. Until then this
    exposes the raw session so a handler can exercise the async engine.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "AsyncSessionLocal is not configured — "
            "ASYNC_DATABASE_URL is unset. Set DATABASE_URL (or DB_HOST/DB_USERNAME/etc.)."
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_async_database() -> AsyncGenerator[AsyncDatabase]:
    """Async DB dep (aam-6 lifted from aam-1 stub to AsyncDatabase).

    Yields an `AsyncDatabase` wrapping a request-scoped `AsyncSession`.
    Closes the wrapped session via `await database.close()` on dep exit
    — the wrapper owns the session because it created it.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "AsyncSessionLocal is not configured — "
            "ASYNC_DATABASE_URL is unset. Set DATABASE_URL (or DB_HOST/DB_USERNAME/etc.)."
        )
    database = AsyncDatabase()
    try:
        yield database
    finally:
        await database.close()


async def get_current_user(
    authorization: Annotated[str, Header()],
    database: Database = Depends(get_database)
) -> User:
    """
    Verify JWT token and return current user.
    Creates user if first login.
    """
    # Extract token from "Bearer <token>"
    if not authorization.startswith("Bearer "):
        raise APIException(
            status_code=401,
            detail="Invalid authorization header format",
            code=ErrorCode.INVALID_TOKEN
        )

    token = authorization[7:]  # Remove "Bearer "

    # E2E test bypass: skip Auth0, return a fixed test user
    # Safety: only allow in development/test environments, never in production
    if (settings.e2e_test_mode
            and settings.environment in ("development", "test")
            and token == _E2E_TOKEN):
        user = database.find_or_create_by(
            User,
            auth0_id=_E2E_AUTH0_ID,
            defaults={
                "email": "e2e@palateful.test",
                "name": "E2E Test User",
                "has_completed_onboarding": True,
            },
        )
        if not user.has_completed_onboarding:
            database.update(user, has_completed_onboarding=True)
        _ensure_default_calendar(database, user)
        _ensure_system_trying_out(database, user)
        return user

    # Import verifier here to avoid circular imports
    from utils.services.auth0 import get_auth0_verifier

    # Verify token
    verifier = get_auth0_verifier()
    claims = await verifier.verify_token(token)

    # Get or create user
    logger.info(f"Claims: {claims}")
    auth0_id = claims["sub"]

    user = database.find_or_create_by(
        User,
        auth0_id=auth0_id,
        defaults={
            "email": claims.get("email") or None,
            "name": claims.get("name"),
            "picture": claims.get("picture"),
            "email_verified": claims.get("email_verified", False),
        }
    )

    # Finalize auth: sync missing profile fields and store Auth0 profile
    user = _finalize_auth(database, user, claims)

    # Ensure this user has a default calendar. Idempotent — silent no-op if
    # one already exists. Race-safe via the partial unique index on
    # calendars(owner_id) WHERE is_default = true AND archived_at IS NULL.
    _ensure_default_calendar(database, user)

    # Ensure this user owns a system Trying Out recipe book + default-set.
    # Idempotent — no-op when the user already owns one.
    _ensure_system_trying_out(database, user)

    return user


def _finalize_auth(database, user: User, claims: dict) -> User:
    """Sync profile fields from Auth0 claims when missing, and store full profile snapshot."""
    updates = {}

    # Fill missing core fields from Auth0
    if not user.email and claims.get("email"):
        updates["email"] = claims["email"]
    if not user.name and claims.get("name"):
        updates["name"] = claims["name"]
    if not user.picture and claims.get("picture"):
        updates["picture"] = claims["picture"]
    if claims.get("email_verified") and not user.email_verified:
        updates["email_verified"] = True

    # Store full Auth0 profile snapshot (nickname, given_name, family_name, locale, etc.)
    auth0_profile = {
        k: v for k, v in claims.items()
        if k not in ("sub", "aud", "iss", "iat", "exp", "azp", "scope", "permissions")
    }
    if auth0_profile != user.auth0_profile:
        updates["auth0_profile"] = auth0_profile

    if updates:
        database.update(user, **updates)

    return user


def _ensure_default_calendar(database: Database, user: User) -> Calendar | None:
    """Ensure `user` owns a non-archived default calendar.

    Called on every authed request, so it must be cheap + idempotent:
      - SELECT filtered on archived_at IS NULL (matching the partial unique
        index on calendars); an archived default from some historical flow
        must NOT be treated as the active default.
      - Provisioning INSERT runs inside a SAVEPOINT so a concurrent race
        (Auth0 token refresh replays this path) rolls back only the
        duplicate insert, not any staged writes on the outer request
        transaction.
    """
    active_default = (
        database.db.query(Calendar)
        .filter(
            Calendar.owner_id == user.id,
            Calendar.is_default.is_(True),
            Calendar.archived_at.is_(None),
        )
        .first()
    )
    if active_default is not None:
        return active_default

    try:
        with database.db.begin_nested():
            calendar = Calendar(
                name=_DEFAULT_CALENDAR_NAME,
                owner_id=user.id,
                is_default=True,
                is_shared=False,
            )
            database.create(calendar)
            database.db.flush()

            membership = CalendarUser(
                user_id=user.id,
                calendar_id=calendar.id,
                role="owner",
            )
            database.create(membership)
            database.db.flush()
        return calendar
    except IntegrityError:
        # Concurrent provisioning won the race — re-read the active default.
        # SAVEPOINT has already rolled back the inner transaction; the
        # outer session remains usable.
        return (
            database.db.query(Calendar)
            .filter(
                Calendar.owner_id == user.id,
                Calendar.is_default.is_(True),
                Calendar.archived_at.is_(None),
            )
            .first()
        )


def _find_system_trying_out_book(database: Database, user: User) -> RecipeBook | None:
    """Return the user's active system Trying Out book, or None."""
    return (
        database.db.query(RecipeBook)
        .join(RecipeBookUser, RecipeBookUser.recipe_book_id == RecipeBook.id)
        .filter(
            RecipeBookUser.user_id == user.id,
            RecipeBookUser.role == "owner",
            RecipeBookUser.archived_at.is_(None),
            RecipeBook.is_system.is_(True),
            RecipeBook.archived_at.is_(None),
        )
        .first()
    )


def _ensure_system_trying_out(database: Database, user: User) -> RecipeBook | None:
    """Ensure `user` owns a system Trying Out recipe book + default-set.

    Mirrors `_ensure_default_calendar`: idempotent SELECT-before-INSERT
    inside a SAVEPOINT, with an `IntegrityError` fallback that re-reads
    the concurrent winner. Sets `user.default_recipe_book_id` on the
    book's id only when the user does not already have one — never
    overwrites a custom default the user has already chosen.
    """
    book = _find_system_trying_out_book(database, user)

    if book is None:
        try:
            with database.db.begin_nested():
                book = RecipeBook(
                    name=_TRYING_OUT_BOOK_NAME,
                    is_public=False,
                    is_shared=False,
                    is_system=True,
                )
                database.create(book)
                database.db.flush()

                membership = RecipeBookUser(
                    user_id=user.id,
                    recipe_book_id=book.id,
                    role="owner",
                )
                database.create(membership)
                database.db.flush()
        except IntegrityError:
            # Concurrent provisioning won the race — re-read.
            book = _find_system_trying_out_book(database, user)

    if book is not None and user.default_recipe_book_id is None:
        database.update(user, default_recipe_book_id=book.id)

    return book


async def get_current_user_async(
    authorization: Annotated[str, Header()],
    database: AsyncDatabase = Depends(get_async_database),
) -> User:
    """Async sibling of `get_current_user` (aam-6).

    Resolves the same Auth0 → User → default-calendar flow on the async
    engine. Phase 3 routers depend on this instead of `get_current_user`
    after their own conversion lands. Sync version stays for the
    observation-window dual-dispatch path and for whitelisted sync paths
    (manage.py REPL).
    """
    if not authorization.startswith("Bearer "):
        raise APIException(
            status_code=401,
            detail="Invalid authorization header format",
            code=ErrorCode.INVALID_TOKEN,
        )

    token = authorization[7:]

    if (
        settings.e2e_test_mode
        and settings.environment in ("development", "test")
        and token == _E2E_TOKEN
    ):
        user = await database.find_or_create_by(
            User,
            auth0_id=_E2E_AUTH0_ID,
            defaults={
                "email": "e2e@palateful.test",
                "name": "E2E Test User",
                "has_completed_onboarding": True,
            },
        )
        if not user.has_completed_onboarding:
            await database.update(user, has_completed_onboarding=True)
        await _ensure_default_calendar_async(database, user)
        await _ensure_system_trying_out_async(database, user)
        return user

    from utils.services.auth0 import get_auth0_verifier

    verifier = get_auth0_verifier()
    claims = await verifier.verify_token(token)

    logger.info(f"Claims: {claims}")
    auth0_id = claims["sub"]

    user = await database.find_or_create_by(
        User,
        auth0_id=auth0_id,
        defaults={
            "email": claims.get("email") or None,
            "name": claims.get("name"),
            "picture": claims.get("picture"),
            "email_verified": claims.get("email_verified", False),
        },
    )

    user = await _finalize_auth_async(database, user, claims)
    await _ensure_default_calendar_async(database, user)
    await _ensure_system_trying_out_async(database, user)

    return user


async def _finalize_auth_async(
    database: AsyncDatabase, user: User, claims: dict
) -> User:
    """Async sibling of `_finalize_auth`. Same field-sync logic; the
    update call is now `await database.update(...)`."""
    updates = {}

    if not user.email and claims.get("email"):
        updates["email"] = claims["email"]
    if not user.name and claims.get("name"):
        updates["name"] = claims["name"]
    if not user.picture and claims.get("picture"):
        updates["picture"] = claims["picture"]
    if claims.get("email_verified") and not user.email_verified:
        updates["email_verified"] = True

    auth0_profile = {
        k: v
        for k, v in claims.items()
        if k
        not in ("sub", "aud", "iss", "iat", "exp", "azp", "scope", "permissions")
    }
    if auth0_profile != user.auth0_profile:
        updates["auth0_profile"] = auth0_profile

    if updates:
        await database.update(user, **updates)

    return user


async def _ensure_default_calendar_async(
    database: AsyncDatabase, user: User
) -> Calendar | None:
    """Async sibling of `_ensure_default_calendar`. Race-safe: relies on
    the partial unique index on `calendars(owner_id) WHERE is_default =
    true AND archived_at IS NULL` and catches the IntegrityError raised
    when a concurrent provisioning wins.

    `async with database.db.begin_nested()` mirrors the sync
    `with session.begin_nested()` SAVEPOINT — when the inner INSERT
    races, only the SAVEPOINT rolls back, leaving the outer request
    transaction usable.
    """
    stmt = select(Calendar).where(
        Calendar.owner_id == user.id,
        Calendar.is_default.is_(True),
        Calendar.archived_at.is_(None),
    )
    result = await database.db.execute(stmt)
    active_default = result.scalars().first()
    if active_default is not None:
        return active_default

    try:
        async with database.db.begin_nested():
            calendar = Calendar(
                name=_DEFAULT_CALENDAR_NAME,
                owner_id=user.id,
                is_default=True,
                is_shared=False,
            )
            database.db.add(calendar)
            await database.db.flush()

            membership = CalendarUser(
                user_id=user.id,
                calendar_id=calendar.id,
                role="owner",
            )
            database.db.add(membership)
            await database.db.flush()
        return calendar
    except IntegrityError:
        # Concurrent provisioning won the race — re-read the active default.
        # SAVEPOINT has already rolled back the inner block; the outer
        # transaction stays usable.
        result = await database.db.execute(stmt)
        return result.scalars().first()


async def _find_system_trying_out_book_async(
    database: AsyncDatabase, user: User
) -> RecipeBook | None:
    """Async sibling of `_find_system_trying_out_book`."""
    stmt = (
        select(RecipeBook)
        .join(RecipeBookUser, RecipeBookUser.recipe_book_id == RecipeBook.id)
        .where(
            RecipeBookUser.user_id == user.id,
            RecipeBookUser.role == "owner",
            RecipeBookUser.archived_at.is_(None),
            RecipeBook.is_system.is_(True),
            RecipeBook.archived_at.is_(None),
        )
    )
    result = await database.db.execute(stmt)
    return result.scalars().first()


async def _ensure_system_trying_out_async(
    database: AsyncDatabase, user: User
) -> RecipeBook | None:
    """Async sibling of `_ensure_system_trying_out`. Same idempotent
    SELECT-before-INSERT + IntegrityError-on-race pattern; sets
    `user.default_recipe_book_id` only when the user does not already
    have one.
    """
    book = await _find_system_trying_out_book_async(database, user)

    if book is None:
        try:
            async with database.db.begin_nested():
                book = RecipeBook(
                    name=_TRYING_OUT_BOOK_NAME,
                    is_public=False,
                    is_shared=False,
                    is_system=True,
                )
                database.db.add(book)
                await database.db.flush()

                membership = RecipeBookUser(
                    user_id=user.id,
                    recipe_book_id=book.id,
                    role="owner",
                )
                database.db.add(membership)
                await database.db.flush()
        except IntegrityError:
            book = await _find_system_trying_out_book_async(database, user)

    if book is not None and user.default_recipe_book_id is None:
        await database.update(user, default_recipe_book_id=book.id)

    return book


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Verify the current user is an admin. Raises 403 if not."""
    if not user.is_admin:
        raise APIException(
            status_code=403,
            detail="Admin access required",
            code=ErrorCode.FORBIDDEN,
        )
    return user


async def require_admin_async(
    user: User = Depends(get_current_user_async),
) -> User:
    """Async sibling of `require_admin` (aam-20).

    Routes through `get_current_user_async` so the admin router runs on
    the async engine end-to-end. Same 403 behavior.
    """
    if not user.is_admin:
        raise APIException(
            status_code=403,
            detail="Admin access required",
            code=ErrorCode.FORBIDDEN,
        )
    return user


async def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
    database: Database = Depends(get_database),
) -> User | None:
    """Resolve the current user when a JWT is present, else return None.

    Used by endpoints that support anonymous callers — e.g. the
    client-latency ingest (`POST /v1/client-latencies`, cla-1b), which
    accepts pre-login cold-start and onboarding events without a JWT.
    If the header is malformed or the token is invalid we return None
    (rather than 401) so the anonymous path stays reachable; any
    downstream rate-limit / validation logic owns abuse protection.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        return None
    try:
        return await get_current_user(
            authorization=authorization,
            database=database,
        )
    except APIException:
        return None
    except Exception:
        # Auth0 verifier / DB / anything unexpected — fail open to
        # anonymous. Telemetry ingest must never hard-fail on optional
        # auth; a 500 here would take down client-side perf reporting.
        logger.exception("get_optional_user: auth resolution failed")
        return None


async def get_optional_user_async(
    authorization: Annotated[str | None, Header()] = None,
    database: AsyncDatabase = Depends(get_async_database),
) -> User | None:
    """Async sibling of `get_optional_user` (aam-21).

    Used by the client-latency ingest endpoint after its async conversion.
    Fail-open semantics are identical: header missing or token invalid →
    return None so the anonymous path stays reachable.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        return None
    try:  # pragma: no cover - exercised via integration; unit tests use the anon path
        return await get_current_user_async(
            authorization=authorization,
            database=database,
        )
    except APIException:  # pragma: no cover - fail-open on invalid token
        return None
    except Exception:  # pragma: no cover - fail-open on verifier / DB failure
        logger.exception("get_optional_user_async: auth resolution failed")
        return None
