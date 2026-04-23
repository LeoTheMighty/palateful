"""Tests for services/api/src/utils/route_redaction.py (cla-1b helper)."""

from __future__ import annotations

import pytest

from api.v1.client_latency.route_redaction import is_route_redacted, redact_route


class TestIsRouteRedacted:
    @pytest.mark.parametrize(
        "route",
        [
            None,
            "",
            "/",
            "/home",
            "/recipes",
            "/recipes/edit",
            "/recipes/:id/edit",
            "/recipes/{id}/edit",
            "/v1/recipes/:recipe_id",
            "/section/abc-def",  # short hex-like but not a UUID
            "/page/123",  # short numeric — not flagged
            "/page?ref=42",  # query stripped
        ],
    )
    def test_allows_template_or_literal_paths(self, route):
        assert is_route_redacted(route) is True

    @pytest.mark.parametrize(
        "route",
        [
            "/recipes/abcd1234-ef56-7890-abcd-ef1234567890",
            "/users/00000000-0000-0000-0000-000000000000/profile",
            "/books/ABCD1234-EF56-7890-ABCD-EF1234567890/view",
            "/items/1234567",  # 7-digit PK
        ],
    )
    def test_flags_raw_identifier_segments(self, route):
        assert is_route_redacted(route) is False

    def test_query_and_fragment_are_ignored(self):
        # Only path segments are inspected.
        assert is_route_redacted("/home?ref=abcd1234-ef56-7890-abcd-ef1234567890") is True
        assert is_route_redacted("/home#abcd1234-ef56-7890-abcd-ef1234567890") is True


class TestRedactRoute:
    def test_passthrough_on_empty(self):
        assert redact_route(None) is None
        assert redact_route("") == ""

    def test_replaces_uuid_segments(self):
        assert (
            redact_route("/recipes/abcd1234-ef56-7890-abcd-ef1234567890/edit")
            == "/recipes/:id/edit"
        )

    def test_replaces_long_numeric_segments(self):
        assert redact_route("/users/1234567/profile") == "/users/:id/profile"

    def test_preserves_existing_templates(self):
        assert redact_route("/recipes/:id/edit") == "/recipes/:id/edit"
        assert redact_route("/recipes/{id}/edit") == "/recipes/{id}/edit"

    def test_strips_query_and_fragment(self):
        assert redact_route("/home?ref=x") == "/home"
        assert redact_route("/home#anchor") == "/home"

    def test_short_numeric_left_alone(self):
        # Versioning / pagination / small literals must not be rewritten.
        assert redact_route("/v1/page/42") == "/v1/page/42"
