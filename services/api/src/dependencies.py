"""FastAPI dependency injection for database and authentication."""

import logging
from typing import Annotated

from config import settings
from fastapi import Depends, Header
from sqlalchemy.exc import IntegrityError
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.constants import LOGGING_LEVEL
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.user import User
from utils.services.database import Database, SessionLocal

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)

_E2E_TOKEN = "e2e-test-token"
_E2E_AUTH0_ID = "e2e|test-user"
_DEFAULT_CALENDAR_NAME = "My Calendar"


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
