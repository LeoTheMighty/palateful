"""Tests for health check endpoints."""


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
