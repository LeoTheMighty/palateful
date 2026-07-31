"""Tests for health check endpoints.

Green baseline for `health_router.py` as it behaves today. The
credential-aware probe (FR-2 / rsh102) is specified in
`test_health_credential_probe.py`, a registered RED artifact — see that
file's header. When rsh102 ships, the two tests below that pin the
current contract (`{"status": "ok"}` and the blanket 503) become wrong
and must be folded into that file.
"""


def test_health_check(client):
    """Test basic health check returns ok when DB probe succeeds."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_db_failure(client, mock_async_db):
    """Health check returns 503 when DB probe raises (e.g. stale creds)."""
    mock_async_db.db.execute.side_effect = RuntimeError("auth failed")
    response = client.get("/v1/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "db unavailable"}


def test_readiness_check(client):
    """Test readiness check returns ready."""
    response = client.get("/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
