"""Tests for `utils.constants.DB_POOL_SIZE` / `DB_MAX_OVERFLOW` env overrides.

pim-4b bumped the defaults 10→20 / 20→40. We reimport `utils.constants`
with `importlib.reload` to pick up monkeypatched env vars, then assert:

1. Defaults (env unset) are the post-pim-4b values.
2. Env overrides take precedence so local dev / docker-compose can
   stick with the prior 10/20 values by setting DB_POOL_SIZE / DB_MAX_OVERFLOW.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def reload_constants(monkeypatch):
    def _reload():
        # utils.constants is imported transitively by many modules; we
        # must reload it after env edits to observe the new int() reads.
        import utils.constants as m

        importlib.reload(m)
        return m

    return _reload


def test_default_pool_size_is_20(reload_constants, monkeypatch):
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    m = reload_constants()
    assert m.DB_POOL_SIZE == 20
    assert m.DB_MAX_OVERFLOW == 40


def test_env_override_pool_size(reload_constants, monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "10")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "20")
    m = reload_constants()
    assert m.DB_POOL_SIZE == 10
    assert m.DB_MAX_OVERFLOW == 20


def test_env_override_can_lower_pool(reload_constants, monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "5")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")
    m = reload_constants()
    assert m.DB_POOL_SIZE == 5
    assert m.DB_MAX_OVERFLOW == 0


def test_invalid_env_value_raises(reload_constants, monkeypatch):
    """Non-numeric env values bubble up at module import time — fail
    loud rather than silently falling back to the default."""
    monkeypatch.setenv("DB_POOL_SIZE", "not-a-number")
    with pytest.raises(ValueError):
        reload_constants()
