"""FastAPI dependency injection for database and authentication."""

import logging
from typing import Annotated

from fastapi import Depends, Header
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.constants import LOGGING_LEVEL
from utils.models.user import User
from utils.services.database import Database, SessionLocal

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)


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

    # Import verifier here to avoid circular imports
    from utils.services.auth0 import get_auth0_verifier

    # Verify token
    verifier = get_auth0_verifier()
    claims = await verifier.verify_token(token)

    # Get or create user
    logger.info(f"Claims: {claims}")
    auth0_id = claims["sub"]
    user = database.find_by(User, auth0_id=auth0_id)

    user = database.find_or_create_by(
        User,
        auth0_id=auth0_id, 
        defaults={
            "email": claims.get("email", ""),
            "name": claims.get("name"),
            "picture": claims.get("picture"),
            "email_verified": claims.get("email_verified", False)
        }
    )

    return user
