"""Tests for health check endpoints."""


def test_health_check(client):
    """Test basic health check returns ok."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check(client):
    """Test readiness check returns ready."""
    response = client.get("/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
