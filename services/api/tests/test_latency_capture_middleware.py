"""Tests for LatencyCaptureMiddleware.

Uses a minimal FastAPI app (not the production `main.py` TestClient) so
we don't pull Auth0 + every route's dependency graph into the test. We
mount the middleware, a few sample routes, and verify the capture side
effect.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware.latency_capture import LatencyCaptureMiddleware


class _SpyWriter:
    def __init__(self):
        self.samples: list[dict] = []

    def enqueue(self, sample):
        self.samples.append(sample)


@pytest.fixture
def spy_writer():
    return _SpyWriter()


@pytest.fixture
def client(spy_writer):
    app = FastAPI()
    app.add_middleware(LatencyCaptureMiddleware)

    @app.get("/v1/recipes/{recipe_id}")
    def _get_recipe(recipe_id: str):
        return {"id": recipe_id}

    @app.get("/v1/errors")
    def _boom():
        raise ValueError("boom")

    @app.get("/health")
    def _health():
        return {"ok": True}

    @app.get("/ready")
    def _ready():
        return {"ok": True}

    # Patch the writer getter used by the middleware so we record into spy.
    with patch(
        "middleware.latency_capture.get_request_writer",
        lambda: spy_writer,
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ----------------------------------------------------------------------
# Matched route → one sample, normalized_path is the template.
# ----------------------------------------------------------------------


def test_matched_route_records_sample(client, spy_writer):
    r = client.get("/v1/recipes/abc-123")
    assert r.status_code == 200
    assert len(spy_writer.samples) == 1
    sample = spy_writer.samples[0]
    assert sample["method"] == "GET"
    assert sample["normalized_path"] == "/v1/recipes/{recipe_id}"
    assert sample["status_code"] == 200
    assert sample["duration_ms"] >= 0


# ----------------------------------------------------------------------
# /health + /ready are hard-skipped.
# ----------------------------------------------------------------------


def test_health_and_ready_not_captured(client, spy_writer):
    client.get("/health")
    client.get("/ready")
    assert spy_writer.samples == []


# ----------------------------------------------------------------------
# Unmatched route (404) is skipped — no scope["route"] template to normalize.
# ----------------------------------------------------------------------


def test_unmatched_route_is_skipped(client, spy_writer):
    r = client.get("/v1/does-not-exist")
    assert r.status_code == 404
    assert spy_writer.samples == []


# ----------------------------------------------------------------------
# Endpoint that raises still records a sample (status derived from response
# or defaulted to 500 when the response is absent).
# ----------------------------------------------------------------------


def test_raising_endpoint_still_captures(client, spy_writer):
    r = client.get("/v1/errors")
    assert r.status_code == 500
    assert len(spy_writer.samples) == 1
    assert spy_writer.samples[0]["normalized_path"] == "/v1/errors"


# ----------------------------------------------------------------------
# Capture path never raises even if the writer blows up.
# ----------------------------------------------------------------------


def test_enqueue_exception_does_not_surface(spy_writer):
    app = FastAPI()
    app.add_middleware(LatencyCaptureMiddleware)

    @app.get("/v1/ping")
    def _ping():
        return {"ok": True}

    class _Exploding:
        def enqueue(self, _sample):
            raise RuntimeError("writer on fire")

    with patch(
        "middleware.latency_capture.get_request_writer",
        lambda: _Exploding(),
    ):
        with TestClient(app) as c:
            r = c.get("/v1/ping")
            assert r.status_code == 200  # request must still succeed
