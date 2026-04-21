"""Auth0 JWT verification service.

JWKS cache sits behind a three-tier read-through:

1. In-memory module-global (the original behavior — survives the request,
   dies on task restart).
2. Redis (pim-5, 2026-04-21) — warm across task restarts, shared across
   concurrent API tasks. Fail-open: if Redis is unreachable we fall
   through to (1) without raising.
3. Fresh fetch from `https://{domain}/.well-known/jwks.json`.

TTLs:
- Hard TTL: 1 hour — after this the value is considered stale and
  must not be served.
- Soft TTL: 50 minutes — after this a request serving a cached value
  schedules a background refresh so the next request gets a fresh copy
  and the hard TTL never fires mid-request.

Single-flight: concurrent cold fetches inside one task dedupe via an
`asyncio.Lock` keyed to the verifier instance. Five parallel task
starts hit Auth0 once (the instance that won the lock); the other
four wait and read from Redis/in-memory once the winner populates.
"""


import asyncio
import json
import logging
import time

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.services.redis_client import safe_get, safe_set

logger = logging.getLogger(__name__)

# Hard TTL: after this, cached JWKS can no longer be served.
_JWKS_HARD_TTL_S = 3600
# Soft TTL: after this, serve the cache but trigger a background refresh.
# Guarantees the hard TTL boundary is never hit during a live request.
_JWKS_SOFT_TTL_S = 3000  # 50 minutes
_JWKS_REDIS_KEY_PREFIX = "auth0:jwks:v1:"


class Auth0Verifier:
    """Verify Auth0 JWT tokens."""

    def __init__(self, domain: str, audience: str):
        self.domain = domain
        self.audience = audience
        self.algorithms = ["RS256"]
        # In-memory tier. `_jwks_fetched_at` is the epoch timestamp of the
        # last *authoritative* fetch (not a stale-hit); both in-memory and
        # Redis tiers record the same value so the TTL check is consistent
        # regardless of which tier served.
        self._jwks: dict | None = None
        self._jwks_fetched_at: float = 0.0
        # Single-flight lock. Scoped to the verifier instance (effectively
        # per-(issuer, audience) pair) so concurrent cold fetches do one
        # Auth0 round-trip, not N.
        self._fetch_lock = asyncio.Lock()
        self._bg_refresh_task: asyncio.Task | None = None

    # ─── Public surface ────────────────────────────────────────────

    async def _get_jwks(self) -> dict:
        """Read-through JWKS lookup. Always returns a usable value or raises.

        Staleness behavior:
          - In-memory hit <soft TTL: serve as-is.
          - In-memory hit ≥soft TTL, <hard TTL: serve + async refresh.
          - In-memory hit ≥hard TTL: drop it, fall through to Redis.
          - Redis hit <soft TTL: hydrate in-memory + serve.
          - Redis hit ≥soft TTL, <hard TTL: hydrate + serve + async refresh.
          - Redis hit ≥hard TTL: treat as miss; single-flight fetch.
          - All miss: single-flight fetch from Auth0.
        """
        now = time.time()
        age = now - self._jwks_fetched_at

        # In-memory tier
        if self._jwks is not None and age < _JWKS_HARD_TTL_S:
            if age >= _JWKS_SOFT_TTL_S:
                self._schedule_background_refresh()
            return self._jwks

        # Redis tier
        redis_value = await safe_get(self._redis_key())
        if redis_value is not None:
            parsed = _try_parse_redis_value(redis_value)
            if parsed is not None:
                jwks, fetched_at = parsed
                age_redis = now - fetched_at
                if age_redis < _JWKS_HARD_TTL_S:
                    self._jwks = jwks
                    self._jwks_fetched_at = fetched_at
                    if age_redis >= _JWKS_SOFT_TTL_S:
                        self._schedule_background_refresh()
                    return jwks

        # Miss — single-flight to Auth0.
        async with self._fetch_lock:
            # Re-check both tiers after acquiring the lock; another coroutine
            # may have populated them while we were waiting.
            now = time.time()
            age = now - self._jwks_fetched_at
            if self._jwks is not None and age < _JWKS_HARD_TTL_S:
                return self._jwks

            jwks = await self._fetch_from_auth0()
            fetched_at = time.time()
            self._jwks = jwks
            self._jwks_fetched_at = fetched_at
            await self._write_to_redis(jwks, fetched_at)
            return jwks

    def clear_jwks_cache(self) -> None:
        """Drop the in-memory tier. Useful for tests.

        Does NOT delete the Redis entry — other tasks may still be serving
        from it, and the hard TTL guarantees it self-expires within an
        hour. If a coordinated drop is truly needed in prod, rotate the
        key prefix (`_JWKS_REDIS_KEY_PREFIX`).
        """
        self._jwks = None
        self._jwks_fetched_at = 0.0
        if self._bg_refresh_task is not None and not self._bg_refresh_task.done():
            self._bg_refresh_task.cancel()
        self._bg_refresh_task = None

    async def verify_token(self, token: str) -> dict:
        """Verify JWT and return claims.

        Raises:
            APIException: if token is invalid/expired or JWKS cannot be
            obtained from Auth0 (Redis + in-memory both miss AND the
            upstream Auth0 fetch failed).
        """
        try:
            jwks = await self._get_jwks()
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            if not kid:
                raise APIException(
                    status_code=401,
                    detail="Token missing key ID",
                    code=ErrorCode.INVALID_TOKEN,
                )

            rsa_key: dict = {}
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"],
                    }
                    break

            if not rsa_key:
                raise APIException(
                    status_code=401,
                    detail="Unable to find appropriate key",
                    code=ErrorCode.INVALID_TOKEN,
                )

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=f"https://{self.domain}/",
            )

            return payload

        except ExpiredSignatureError:
            raise APIException(
                status_code=401,
                detail="Token has expired",
                code=ErrorCode.TOKEN_EXPIRED,
            ) from None
        except JWTError as e:
            raise APIException(
                status_code=401,
                detail=f"Invalid token: {str(e)}",
                code=ErrorCode.INVALID_TOKEN,
            ) from e
        except httpx.HTTPError as e:
            raise APIException(
                status_code=500,
                detail=f"Failed to fetch JWKS: {str(e)}",
                code=ErrorCode.INTERNAL_ERROR,
            ) from e

    # ─── Internal helpers ──────────────────────────────────────────

    def _redis_key(self) -> str:
        return f"{_JWKS_REDIS_KEY_PREFIX}{self.domain}"

    async def _fetch_from_auth0(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{self.domain}/.well-known/jwks.json"
            )
            response.raise_for_status()
            return response.json()

    async def _write_to_redis(self, jwks: dict, fetched_at: float) -> None:
        payload = json.dumps({"jwks": jwks, "fetched_at": fetched_at})
        await safe_set(self._redis_key(), payload, ex=_JWKS_HARD_TTL_S)

    def _schedule_background_refresh(self) -> None:
        """Fire-and-forget refresh. Prevents the hard TTL from biting.

        If a prior background refresh is still in-flight, don't stack a
        second one — the lock inside `_refresh_now` dedupes anyway, but
        spawning a second task just wastes memory.
        """
        if (
            self._bg_refresh_task is not None
            and not self._bg_refresh_task.done()
        ):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop (sync context, rare in prod). Skip the refresh;
            # the next request that hits the hard TTL will trigger a
            # single-flight re-fetch inline.
            return
        self._bg_refresh_task = loop.create_task(self._refresh_now())

    async def _refresh_now(self) -> None:
        async with self._fetch_lock:
            try:
                jwks = await self._fetch_from_auth0()
            except httpx.HTTPError as e:
                # Log and swallow — background refresh must never surface
                # as a request failure. Next request re-enters
                # `_get_jwks()` and re-tries.
                logger.warning(
                    "Background JWKS refresh failed (%s: %s)",
                    type(e).__name__,
                    e,
                )
                return
            fetched_at = time.time()
            self._jwks = jwks
            self._jwks_fetched_at = fetched_at
            await self._write_to_redis(jwks, fetched_at)


def _try_parse_redis_value(raw: str) -> tuple[dict, float] | None:
    """Decode a Redis JWKS blob. Returns None on any parse failure.

    We treat parse failures as a cache miss rather than raising so a
    corrupt Redis key self-heals on the next fetch.
    """
    try:
        decoded = json.loads(raw)
        jwks = decoded["jwks"]
        fetched_at = float(decoded["fetched_at"])
        if not isinstance(jwks, dict):
            return None
        return jwks, fetched_at
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


# Global verifier instance (cached)
_verifier: Auth0Verifier | None = None


def get_auth0_verifier() -> Auth0Verifier:
    """Get the Auth0 verifier instance."""
    global _verifier
    if _verifier is None:
        from utils.constants import AUTH0_AUDIENCE, AUTH0_DOMAIN
        _verifier = Auth0Verifier(
            domain=AUTH0_DOMAIN,
            audience=AUTH0_AUDIENCE,
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

    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    if not kid:
        raise ValueError("Token missing kid header")

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
