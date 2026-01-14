"""Auth0 JWT verification service."""

import httpx
from functools import lru_cache
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
from typing import Optional

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode


class Auth0Verifier:
    """Verify Auth0 JWT tokens."""

    def __init__(self, domain: str, audience: str):
        self.domain = domain
        self.audience = audience
        self.algorithms = ["RS256"]
        self._jwks: Optional[dict] = None

    async def _get_jwks(self) -> dict:
        """Fetch JWKS from Auth0 (cached in instance)."""
        if self._jwks is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{self.domain}/.well-known/jwks.json"
                )
                response.raise_for_status()
                self._jwks = response.json()
        return self._jwks

    def clear_jwks_cache(self) -> None:
        """Clear the JWKS cache (useful for testing)."""
        self._jwks = None

    async def verify_token(self, token: str) -> dict:
        """
        Verify JWT token and return claims.

        Args:
            token: The JWT token string

        Returns:
            dict: Token claims including 'sub', 'email', 'name', etc.

        Raises:
            APIException: If token is invalid or expired
        """
        try:
            jwks = await self._get_jwks()
            unverified_header = jwt.get_unverified_header(token)

            # Find the signing key
            rsa_key = {}
            kid = unverified_header.get("kid")

            if not kid:
                raise APIException(
                    status_code=401,
                    detail="Token missing key ID",
                    code=ErrorCode.INVALID_TOKEN
                )

            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }
                    break

            if not rsa_key:
                raise APIException(
                    status_code=401,
                    detail="Unable to find appropriate key",
                    code=ErrorCode.INVALID_TOKEN
                )

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=f"https://{self.domain}/"
            )

            return payload

        except ExpiredSignatureError:
            raise APIException(
                status_code=401,
                detail="Token has expired",
                code=ErrorCode.TOKEN_EXPIRED
            )
        except JWTError as e:
            raise APIException(
                status_code=401,
                detail=f"Invalid token: {str(e)}",
                code=ErrorCode.INVALID_TOKEN
            )
        except httpx.HTTPError as e:
            raise APIException(
                status_code=500,
                detail=f"Failed to fetch JWKS: {str(e)}",
                code=ErrorCode.INTERNAL_ERROR
            )


# Global verifier instance (cached)
_verifier: Optional[Auth0Verifier] = None


def get_auth0_verifier() -> Auth0Verifier:
    """Get the Auth0 verifier instance."""
    global _verifier
    if _verifier is None:
        # Import settings lazily to avoid circular imports
        from utils.constants import AUTH0_DOMAIN, AUTH0_AUDIENCE
        _verifier = Auth0Verifier(
            domain=AUTH0_DOMAIN,
            audience=AUTH0_AUDIENCE
        )
    return _verifier


def clear_auth0_verifier_cache() -> None:
    """Clear the global verifier cache (useful for testing)."""
    global _verifier
    if _verifier:
        _verifier.clear_jwks_cache()
    _verifier = None


# Legacy functions for backwards compatibility
async def get_jwks() -> dict:
    """Fetch JWKS from Auth0."""
    verifier = get_auth0_verifier()
    return await verifier._get_jwks()


async def get_auth0_public_key(token: str) -> dict:
    """Get the public key for verifying a JWT."""
    verifier = get_auth0_verifier()
    jwks = await verifier._get_jwks()

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
    clear_auth0_verifier_cache()
