"""Demo test for the `async_client` fixture (aam-4).

The fixture spins an `httpx.AsyncClient` against the real FastAPI app
via `ASGITransport`, with both sync and async DB deps overridden to a
`MockAsyncDatabase`. This validates the plumbing end-to-end before any
Phase 3 story relies on it.

`/v1/health` is the smallest stable endpoint we can hit (no DB,
already async). When Phase 3 stories convert their handlers, they'll
add their own per-domain async test files using this same fixture.
"""


async def test_async_client_can_reach_health_endpoint(async_client):
    response = await async_client.get("/v1/health")
    assert response.status_code == 200


async def test_mock_async_db_yields_through_dependency(
    async_client, mock_async_db
):
    """Override-resolution sanity: the MockAsyncDatabase is the same
    instance the dep yields. Phase 3 tests rely on configuring
    `mock_async_db.set_find_by(...)` before issuing the request and
    knowing the handler sees the same instance."""
    from dependencies import get_async_database
    from main import app

    # The override is set by the fixture; resolve it to confirm.
    override = app.dependency_overrides[get_async_database]
    gen = override()
    yielded = await gen.__anext__()
    assert yielded is mock_async_db
