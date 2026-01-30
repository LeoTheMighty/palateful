"""RecipeBook model."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.models.base import Base

if TYPE_CHECKING:
    from utils.models.import_job import ImportJob
    from utils.models.recipe import Recipe
    from utils.models.recipe_book_user import RecipeBookUser


class RecipeBook(Base):
    """RecipeBook model - collection of recipes."""

    __tablename__ = "recipe_books"

    # id, created_at, updated_at, archived_at inherited from Base
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    members: Mapped[list["RecipeBookUser"]] = relationship(
        back_populates="recipe_book", cascade="all, delete-orphan"
    )
    recipes: Mapped[list["Recipe"]] = relationship(
        back_populates="recipe_book", cascade="all, delete-orphan"
    )
    import_jobs: Mapped[list["ImportJob"]] = relationship(
        back_populates="recipe_book", cascade="all, delete-orphan"
    )
