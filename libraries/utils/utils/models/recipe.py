"""Recipe model."""

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, UUID, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.cooking_log import CookingLog
    from utils.models.recipe_book import RecipeBook
    from utils.models.recipe_ingredient import RecipeIngredient
    from utils.models.recipe_step import RecipeStep
    from utils.models.recipe_version import RecipeVersion
    from utils.models.suggestion import Suggestion


class Recipe(Base):
    """Recipe model."""

    __tablename__ = "recipes"

    # id, created_at, updated_at, archived_at inherited from Base
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    servings: Mapped[int] = mapped_column(Integer, default=1)
    prep_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes
    cook_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    forked_from_recipe_id: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True)
    forked_from_book_id: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True)
    forked_from_recipe_name: Mapped[str | None] = mapped_column(String, nullable=True)
    forked_from_book_name: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, default=list)

    # Vibes (feeling-based categorization)
    primary_vibe: Mapped[str | None] = mapped_column(String(20), nullable=True)
    secondary_vibe: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Public sharing token (set when user generates a public link)
    share_token: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Embedding for semantic search (384 dimensions from all-MiniLM-L6-v2)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    # Foreign keys
    recipe_book_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("recipe_books.id", ondelete="CASCADE"), index=True
    )

    # Relationships
    recipe_book: Mapped["RecipeBook"] = relationship(back_populates="recipes")
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    cooking_logs: Mapped[list["CookingLog"]] = relationship(back_populates="recipe")
    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="recipe")
    steps: Mapped[list["RecipeStep"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    versions: Mapped[list["RecipeVersion"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_recipe_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_recipes_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index("idx_recipes_description_trgm", "description", postgresql_using="gin", postgresql_ops={"description": "gin_trgm_ops"}),
        Index("ix_recipes_share_token", "share_token", unique=True, postgresql_where=text("share_token IS NOT NULL")),
    )
