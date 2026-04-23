"""Tests for GET /v1/flags/perf (cla-1c)."""

from __future__ import annotations

from unittest.mock import patch


class TestGetPerfFlags:
    def test_defaults_are_on(self, unauthed_client):
        """Baseline — fresh settings ship with ingest on and full sampling."""
        response = unauthed_client.get("/v1/flags/perf")
        assert response.status_code == 200
        body = response.json()
        assert body["ingest_enabled"] is True
        assert body["sampling_rate"] == 1.0

    def test_reflects_kill_switch_off(self, unauthed_client):
        """`CLIENT_LATENCY_INGEST_ENABLED=false` surfaces in the response."""
        with patch(
            "api.v1.flags.get_perf_flags.settings",
        ) as mock_settings:
            mock_settings.client_latency_ingest_enabled = False
            mock_settings.client_latency_sampling_rate = 1.0
            response = unauthed_client.get("/v1/flags/perf")
            assert response.status_code == 200
            body = response.json()
            assert body["ingest_enabled"] is False
            assert body["sampling_rate"] == 1.0

    def test_reflects_partial_sampling(self, unauthed_client):
        """Partial sampling rate surfaces verbatim."""
        with patch(
            "api.v1.flags.get_perf_flags.settings",
        ) as mock_settings:
            mock_settings.client_latency_ingest_enabled = True
            mock_settings.client_latency_sampling_rate = 0.1
            response = unauthed_client.get("/v1/flags/perf")
            assert response.status_code == 200
            body = response.json()
            assert body["ingest_enabled"] is True
            assert body["sampling_rate"] == 0.1

    def test_endpoint_is_unauthenticated(self, unauthed_client):
        """No Authorization header needed — anonymous pre-login clients
        must be able to honor the kill-switch too."""
        response = unauthed_client.get("/v1/flags/perf")
        assert response.status_code == 200

    def test_sampling_rate_out_of_range_rejected_at_config_load(self):
        """Settings validator rejects rates outside [0.0, 1.0] — the
        operator can't accidentally ship a nonsensical value."""
        from pydantic import ValidationError

        # Test the validator directly — avoids loading the full Settings
        # class (which requires DATABASE_URL etc).
        from config import Settings

        with patch.dict(
            "os.environ",
            {
                "AUTH0_DOMAIN": "x",
                "AUTH0_AUDIENCE": "y",
                "DATABASE_URL": "postgresql://t@t/t",
                "CLIENT_LATENCY_SAMPLING_RATE": "1.5",
            },
            clear=False,
        ):
            try:
                Settings()
            except ValidationError as e:
                assert "client_latency_sampling_rate" in str(e)
            else:
                raise AssertionError(
                    "Expected ValidationError for out-of-range sampling rate"
                )
