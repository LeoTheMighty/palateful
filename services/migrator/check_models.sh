#!/usr/bin/env bash
# Verify that all SQLAlchemy models have a corresponding Alembic migration.
# Exits non-zero if any pending schema changes are detected (i.e. a model
# was added or modified but no migration was generated for it).
#
# Requires DATABASE_URL to be set and migrations to have been applied first
# (the check-models NX target declares migrate-test as a dependsOn).
set -euo pipefail

echo "Checking SQLAlchemy models against migration history..."
poetry run alembic check
echo "All models are up to date."
