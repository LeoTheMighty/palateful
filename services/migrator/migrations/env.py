"""Alembic environment configuration."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Import all models to register them with the Base
from utils.db.base import Base
from utils.db.models import (  # noqa: F401
    Chat,
    CookingLog,
    Ingredient,
    IngredientSubstitution,
    Pantry,
    PantryIngredient,
    PantryUser,
    Recipe,
    RecipeBook,
    RecipeBookUser,
    RecipeIngredient,
    Thread,
    Unit,
    User,
)

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL", "")
    # Convert asyncpg URL to psycopg2 for sync operations
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
