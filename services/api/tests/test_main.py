"""Tests for main.py application setup."""

from unittest.mock import MagicMock, patch

import pytest


class TestApp:
    """Tests for the FastAPI app created in main.py."""

    def test_app_exists(self):
        """Test that the app is created and is a FastAPI instance."""
        from main import app
        from fastapi import FastAPI

        assert isinstance(app, FastAPI)

    def test_app_title(self):
        """Test that the app has the correct title."""
        from main import app

        assert app.title == "Palateful API"

    def test_app_version(self):
        """Test that the app has the correct version."""
        from main import app

        assert app.version == "0.1.0"

    def test_app_description(self):
        """Test that the app has a description."""
        from main import app

        assert app.description == "Recipe management and cooking assistant API"

    def test_app_has_routes(self):
        """Test that the app has registered routes."""
        from main import app

        route_paths = [r.path for r in app.routes]
        assert any("/v1" in p for p in route_paths)

    def test_health_endpoint_accessible(self, client):
        """Test that the health endpoint is accessible via the app."""
        response = client.get("/v1/health")
        assert response.status_code == 200


class TestLifespan:
    """Tests for the app lifespan (startup/shutdown)."""

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_no_engine(self):
        """Test lifespan shutdown when db_engine is None."""
        from main import lifespan, app

        with patch("utils.services.database.db_engine", None):
            async with lifespan(app):
                pass
        # Should complete without error

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_disposes_engine(self):
        """Test lifespan shutdown disposes the db engine."""
        from main import lifespan, app

        mock_engine = MagicMock()
        with patch("utils.services.database.db_engine", mock_engine):
            async with lifespan(app):
                pass
            mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_engine_dispose_exception(self):
        """Test lifespan shutdown handles engine dispose exception gracefully."""
        from main import lifespan, app

        mock_engine = MagicMock()
        mock_engine.dispose.side_effect = Exception("Connection error")
        with patch("utils.services.database.db_engine", mock_engine):
            # Should not raise
            async with lifespan(app):
                pass
