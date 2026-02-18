"""Smoke tests for migrator service."""


def test_migrations_directory_exists():
    """Verify the migrations directory structure exists."""
    import os
    migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations", "versions")
    assert os.path.isdir(migrations_dir)
