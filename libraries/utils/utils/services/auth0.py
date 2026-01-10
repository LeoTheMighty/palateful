"""Auth0 JWT verification service."""

import httpx
from jose import jwt

from config import settings

# Cache for JWKS
_jwks_cache: dict | None = None


async def get_jwks() -> dict:
    """Fetch JWKS from Auth0."""
    global _jwks_cache

    if _jwks_cache is not None:
        return _jwks_cache

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{settings.auth0_domain}/.well-known/jwks.json"
        )
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache


async def get_auth0_public_key(token: str) -> dict:
    """Get the public key for verifying a JWT."""
    jwks = await get_jwks()

    # Get the key ID from the token header
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    if not kid:
        raise ValueError("Token missing kid header")

    # Find the matching key
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }

    raise ValueError(f"Key {kid} not found in JWKS")


def clear_jwks_cache() -> None:
    """Clear the JWKS cache (useful for testing)."""
    global _jwks_cache
    _jwks_cache = None
