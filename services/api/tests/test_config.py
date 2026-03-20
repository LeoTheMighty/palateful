"""Tests for config.py Settings class."""

import os
from unittest.mock import patch

import pytest


class TestSettings:
    """Tests for the Settings class defaults and validation."""

    def test_settings_defaults(self):
        """Test that Settings has correct default values for fields not overridden by env."""
        from config import Settings

        # Provide required fields; override environment to test default derivation
        s = Settings(
            auth0_domain="test.auth0.com",
            auth0_audience="https://api.test",
            database_url="postgresql://localhost/test",
            environment="development",
        )
        assert s.environment == "development"
        assert s.ai_chat_monthly_token_cap == 500_000
        assert s.aws_region == "us-east-1"
        assert s.cors_origins == ["http://localhost:3000", "http://localhost:8080"]
        # redis_url and auth0_client_id may be set from env; just verify they are strings
        assert isinstance(s.redis_url, str)
        assert isinstance(s.auth0_client_id, str)

    def test_settings_cors_origin_regex(self):
        """Test default CORS origin regex pattern."""
        from config import Settings

        s = Settings(
            auth0_domain="test.auth0.com",
            auth0_audience="https://api.test",
            database_url="postgresql://localhost/test",
        )
        assert "ngrok" in s.cors_origin_regex

    def test_settings_require_non_empty_auth0_domain(self):
        """Test that empty auth0_domain raises ValidationError."""
        from config import Settings

        with pytest.raises(Exception):
            Settings(
                auth0_domain="",
                auth0_audience="https://api.test",
                database_url="postgresql://localhost/test",
            )

    def test_settings_require_non_empty_auth0_audience(self):
        """Test that empty auth0_audience raises ValidationError."""
        from config import Settings

        with pytest.raises(Exception):
            Settings(
                auth0_domain="test.auth0.com",
                auth0_audience="",
                database_url="postgresql://localhost/test",
            )

    def test_settings_require_non_empty_database_url(self):
        """Test that empty database_url raises ValidationError."""
        from config import Settings

        with pytest.raises(Exception):
            Settings(
                auth0_domain="test.auth0.com",
                auth0_audience="https://api.test",
                database_url="",
            )

    def test_settings_model_post_init_defaults(self):
        """Test that model_post_init derives AWS names from environment."""
        from config import Settings

        s = Settings(
            auth0_domain="test.auth0.com",
            auth0_audience="https://api.test",
            database_url="postgresql://localhost/test",
            environment="production",
        )
        assert s.parser_inputs_bucket == "palateful-parser-inputs-production"
        assert s.parser_outputs_bucket == "palateful-parser-outputs-production"
        assert s.batch_job_queue == "palateful-parser-queue-production"
        assert s.batch_job_definition == "palateful-parser-job-production"

    def test_settings_model_post_init_explicit_override(self):
        """Test that explicitly set AWS names are not overridden."""
        from config import Settings

        s = Settings(
            auth0_domain="test.auth0.com",
            auth0_audience="https://api.test",
            database_url="postgresql://localhost/test",
            environment="production",
            parser_inputs_bucket="custom-inputs",
            parser_outputs_bucket="custom-outputs",
            batch_job_queue="custom-queue",
            batch_job_definition="custom-job",
        )
        assert s.parser_inputs_bucket == "custom-inputs"
        assert s.parser_outputs_bucket == "custom-outputs"
        assert s.batch_job_queue == "custom-queue"
        assert s.batch_job_definition == "custom-job"

    def test_settings_model_post_init_development(self):
        """Test that model_post_init uses environment suffix."""
        from config import Settings

        s = Settings(
            auth0_domain="test.auth0.com",
            auth0_audience="https://api.test",
            database_url="postgresql://localhost/test",
            environment="development",
        )
        assert s.parser_inputs_bucket == "palateful-parser-inputs-development"
        assert s.parser_outputs_bucket == "palateful-parser-outputs-development"
        assert s.batch_job_queue == "palateful-parser-queue-development"
        assert s.batch_job_definition == "palateful-parser-job-development"

    def test_settings_partial_override(self):
        """Test setting some AWS fields explicitly while others use defaults."""
        from config import Settings

        s = Settings(
            auth0_domain="test.auth0.com",
            auth0_audience="https://api.test",
            database_url="postgresql://localhost/test",
            environment="staging",
            parser_inputs_bucket="my-custom-bucket",
            # Leave outputs, queue, and definition to be derived
        )
        assert s.parser_inputs_bucket == "my-custom-bucket"
        assert s.parser_outputs_bucket == "palateful-parser-outputs-staging"
        assert s.batch_job_queue == "palateful-parser-queue-staging"
        assert s.batch_job_definition == "palateful-parser-job-staging"


class TestGetSettings:
    """Tests for the get_settings function."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        from config import Settings, get_settings

        # Clear lru_cache to force recreation
        get_settings.cache_clear()
        try:
            result = get_settings()
            assert isinstance(result, Settings)
        finally:
            get_settings.cache_clear()

    def test_get_settings_is_cached(self):
        """Test that get_settings returns the same instance on repeated calls."""
        from config import get_settings

        get_settings.cache_clear()
        try:
            s1 = get_settings()
            s2 = get_settings()
            assert s1 is s2
        finally:
            get_settings.cache_clear()
