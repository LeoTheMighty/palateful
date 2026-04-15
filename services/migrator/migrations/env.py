"""Alembic environment configuration."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from utils.constants import DATABASE_URL

# Import all models to register them with the Base
from utils.db.base import Base
from utils.db.models import (  # noqa: F401
    ActiveTimer,
    Activity,
    Chat,
    CookingLog,
    ErrorLog,
    FriendRequest,
    Friendship,
    ImportItem,
    ImportJob,
    Ingredient,
    IngredientMatch,
    IngredientSubstitution,
    Invitation,
    InviteLink,
    MealEvent,
    MealEventParticipant,
    Notification,
    Pantry,
    PantryIngredient,
    PantryUser,
    ParserJob,
    PrepStep,
    Recipe,
    RecipeBook,
    RecipeBookUser,
    RecipeIngredient,
    RecipeNote,
    RecipeStep,
    RecipeVersion,
    ShoppingList,
    ShoppingListEvent,
    ShoppingListItem,
    ShoppingListUser,
    Suggestion,
    Thread,
    Unit,
    User,
    UserActivity,
    UserFavorite,
)

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from shared utils.constants.

    In prod this is built from component env vars (DB_HOST, DB_USERNAME,
    DB_PASSWORD pulled from the RDS-managed secret, etc.). Locally it
    falls back to the DATABASE_URL env var set in docker-compose.
    """
    url = DATABASE_URL or ""
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
