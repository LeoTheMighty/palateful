"""Tests for the riip-4 GET /v1/units/aliases endpoint.

aam-21: handler is now `AsyncEndpoint`, so the mock is on
`mock_async_db.db.execute` (an AsyncMock) rather than `mock_db.db.execute`.
"""

from unittest.mock import AsyncMock


def _stub_two_queries(mock_async_db, *, alias_rows, canonical_rows):
    """Configure mock_async_db.db.execute to return alias rows then canonical rows.

    The endpoint issues two `await db.execute(...)` calls in order:
      1. select(UnitAlias.alias, UnitAlias.canonical_unit) → list of tuples
      2. select(Unit.name).scalars()                        → list of names
    """

    class _AliasResult:
        def all(self):
            return [(a, c) for a, c in alias_rows]

    class _CanonicalResult:
        def scalars(self):
            return self

        def all(self):
            return list(canonical_rows)

    mock_async_db.db.execute = AsyncMock(
        side_effect=[_AliasResult(), _CanonicalResult()]
    )


def test_get_unit_aliases_returns_map_and_canonical(client, mock_async_db):
    _stub_two_queries(
        mock_async_db,
        alias_rows=[("tablespoon", "tbsp"), ("grams", "g")],
        canonical_rows=["tbsp", "tsp", "cup", "g"],
    )
    response = client.get("/v1/units/aliases")
    assert response.status_code == 200
    body = response.json()
    assert body["aliases"] == {"tablespoon": "tbsp", "grams": "g"}
    # Canonical list is sorted in the response.
    assert body["canonical"] == ["cup", "g", "tbsp", "tsp"]


def test_get_unit_aliases_emits_24h_cache_control(client, mock_async_db):
    _stub_two_queries(mock_async_db, alias_rows=[], canonical_rows=[])
    response = client.get("/v1/units/aliases")
    assert response.status_code == 200
    assert "max-age=86400" in response.headers["cache-control"]
    assert "public" in response.headers["cache-control"]


def test_get_unit_aliases_requires_auth(unauthed_client, mock_db):
    """No `Authorization` header → endpoint refuses (mirror /v1/* policy)."""
    response = unauthed_client.get("/v1/units/aliases")
    assert response.status_code in (401, 422)


def test_get_unit_aliases_handles_empty_seed(client, mock_async_db):
    _stub_two_queries(mock_async_db, alias_rows=[], canonical_rows=[])
    response = client.get("/v1/units/aliases")
    assert response.status_code == 200
    assert response.json() == {"aliases": {}, "canonical": []}
