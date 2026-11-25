"""The endpoint's fail-open guard (rsh102, added after adversarial review).

`cached_verdict_async` is not supposed to raise. But "not supposed to" is
not a guarantee, and the consequence of being wrong is specific and bad:
the container health check runs `urllib.request.urlopen`, which raises
`HTTPError` on **any** non-2xx status. A 500 therefore kills the task
exactly as hard as a 503 does — with no credential failure anywhere, and
with `deployment_minimum_healthy_percent = 0` draining the service while
it happens.

So the handler treats *any* escape from the probe as unclassified and
fails open. These tests pin that, because the whole fail-open design is
only as structural as its weakest path.
"""

import pytest


@pytest.fixture
def exploding_probe(monkeypatch):
    """Make the probe raise instead of returning a verdict."""

    def _install(exc):
        async def boom(*args, **kwargs):
            raise exc

        monkeypatch.setattr(
            "routers.v1.health_router.cached_verdict_async", boom
        )

    return _install


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(RuntimeError("probe internals blew up"), id="runtime"),
        pytest.param(ValueError("classifier bug"), id="value"),
        pytest.param(OSError("something at the socket layer"), id="oserror"),
    ],
)
def test_a_raising_probe_still_returns_200(client, exploding_probe, exc):
    exploding_probe(exc)

    response = client.get("/v1/health")

    assert response.status_code == 200, (
        f"{exc!r} escaping the probe must not fail the health check; "
        f"got {response.status_code} {response.json()!r}"
    )


def test_a_raising_probe_reports_an_unclassified_verdict(
    client, exploding_probe
):
    """It must not claim OK either — the probe genuinely did not run."""
    exploding_probe(RuntimeError("probe internals blew up"))

    body = client.get("/v1/health").json()

    assert body == {"status": "ok", "db": "UNKNOWN"}


def test_a_raising_probe_never_reports_auth_failed(client, exploding_probe):
    """The one verdict that drives replacement must require evidence."""
    exploding_probe(RuntimeError("probe internals blew up"))

    assert client.get("/v1/health").json()["db"] != "AUTH_FAILED"
