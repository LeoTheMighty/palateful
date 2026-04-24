"""Export all user recipe data as JSON."""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import AsyncEndpoint, success
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_note import RecipeNote
from utils.models.recipe_step import RecipeStep
from utils.models.recipe_version import RecipeVersion
from utils.models.user import User


class ExportRecipes(AsyncEndpoint):
    """Export user's entire recipe collection as JSON."""

    async def execute(self):
        user: User = self.user

        # Find all active book memberships for this user
        memberships = await self.database.where(
            RecipeBookUser, user_id=user.id
        ).all()

        books_data = []
        total_recipe_count = 0

        for membership in memberships:
            book = await self.database.find_by(
                RecipeBook, id=membership.recipe_book_id
            )
            if not book:
                continue

            # Get all non-archived recipes in this book
            recipes = await self.database.where(
                Recipe, recipe_book_id=book.id
            ).all()

            recipes_data = []
            for recipe in recipes:
                steps = await self.database.where(
                    RecipeStep, recipe_id=recipe.id, asc="step_number"
                ).all()

                ingredients_result = await self.db.execute(
                    select(RecipeIngredient, Ingredient)
                    .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
                    .where(RecipeIngredient.recipe_id == recipe.id)
                    .where(RecipeIngredient.archived_at.is_(None))
                    .order_by(RecipeIngredient.order_index)
                )
                ingredients = ingredients_result.all()

                notes = await self.database.where(
                    RecipeNote, recipe_id=recipe.id
                ).all()

                versions = await self.database.where(
                    RecipeVersion,
                    recipe_id=recipe.id,
                    asc="version_number",
                    include_archived=True,
                ).all()

                recipes_data.append({
                    "id": str(recipe.id),
                    "recipe_book_id": str(recipe.recipe_book_id),
                    "name": recipe.name,
                    "description": recipe.description,
                    "instructions": recipe.instructions,
                    "servings": recipe.servings,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "image_url": recipe.image_url,
                    "source_url": recipe.source_url,
                    "tags": recipe.tags or [],
                    "forked_from_recipe_id": str(recipe.forked_from_recipe_id) if recipe.forked_from_recipe_id else None,
                    "forked_from_book_id": str(recipe.forked_from_book_id) if recipe.forked_from_book_id else None,
                    "forked_from_recipe_name": recipe.forked_from_recipe_name,
                    "forked_from_book_name": recipe.forked_from_book_name,
                    "created_at": recipe.created_at.isoformat(),
                    "updated_at": recipe.updated_at.isoformat(),
                    "ingredients": [
                        {
                            "canonical_name": ing.canonical_name,
                            "quantity_display": float(ri.quantity_display) if ri.quantity_display else None,
                            "unit_display": ri.unit_display,
                            "notes": ri.notes,
                        }
                        for ri, ing in ingredients
                    ],
                    "steps": [
                        {
                            "step_number": s.step_number,
                            "instruction": s.instruction,
                            "duration_minutes": s.active_time_minutes,
                        }
                        for s in steps
                    ],
                    "notes": [
                        {
                            "body": n.body,
                            "created_at": n.created_at.isoformat(),
                        }
                        for n in notes
                    ],
                    "versions": [
                        {
                            "version_number": v.version_number,
                            "snapshot": v.snapshot,
                            "created_at": v.created_at.isoformat(),
                        }
                        for v in versions
                    ],
                })

            total_recipe_count += len(recipes_data)
            books_data.append({
                "id": str(book.id),
                "name": book.name,
                "description": book.description,
                "role": membership.role,
                "recipes": recipes_data,
            })

        return success(
            data=ExportRecipes.Response(
                exported_at=datetime.now(UTC).isoformat(),
                recipe_count=total_recipe_count,
                book_count=len(books_data),
                books=books_data,
            )
        )

    class Response(BaseModel):
        exported_at: str
        recipe_count: int
        book_count: int
        books: list[dict]
