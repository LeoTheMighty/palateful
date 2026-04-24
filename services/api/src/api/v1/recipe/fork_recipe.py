"""Fork recipe to another book endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.recipe_step import RecipeStep
from utils.models.user import User
from utils.services.units import normalize_unit_display


class ForkRecipe(AsyncEndpoint):
    """Fork a recipe into a book you own, preserving lineage."""

    async def execute(self, recipe_id: str, params: "ForkRecipe.Params"):
        """
        Fork a recipe to an owned book, cloning all ingredients and steps with lineage.

        Args:
            recipe_id: The source recipe's ID
            params: Fork parameters with destination_book_id

        Returns:
            New recipe ID and lineage fields.
        """
        user: User = self.user

        # Get source recipe
        recipe = await self.database.find_by(Recipe, id=recipe_id)
        if not recipe:
            raise APIException(
                status_code=404,
                detail="Recipe not found",
                code=ErrorCode.RECIPE_NOT_FOUND,
            )

        # Check source book access (any role — read access suffices for fork)
        src_membership = await self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=recipe.recipe_book_id,
        )
        if not src_membership:
            raise APIException(
                status_code=403,
                detail="You don't have access to this recipe",
                code=ErrorCode.RECIPE_ACCESS_DENIED,
            )

        # Check destination book exists
        dest_book = await self.database.find_by(RecipeBook, id=params.destination_book_id)
        if not dest_book:
            raise APIException(
                status_code=404,
                detail="Destination book not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )

        # Check destination book access (owner only — fork is a personal copy)
        dest_membership = await self.database.find_by(
            RecipeBookUser,
            user_id=str(user.id),
            recipe_book_id=params.destination_book_id,
        )
        if not dest_membership or dest_membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="You must be the owner of the destination book to fork into it",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Get source book name for lineage snapshot
        src_book = await self.database.find_by(RecipeBook, id=recipe.recipe_book_id)
        src_book_name = src_book.name if src_book else "Unknown Book"

        # Clone recipe with lineage fields
        new_recipe = Recipe(
            name=recipe.name,
            description=recipe.description,
            instructions=recipe.instructions,
            servings=recipe.servings,
            prep_time=recipe.prep_time,
            cook_time=recipe.cook_time,
            image_url=recipe.image_url,
            source_url=recipe.source_url,
            tags=list(recipe.tags) if recipe.tags else [],
            embedding=recipe.embedding,
            recipe_book_id=params.destination_book_id,
            forked_from_recipe_id=recipe.id,
            forked_from_book_id=recipe.recipe_book_id,
            forked_from_recipe_name=recipe.name,
            forked_from_book_name=src_book_name,
        )
        await self.database.create(new_recipe)

        # Clone ingredients
        source_ingredients = await self.database.where(
            RecipeIngredient, recipe_id=str(recipe.id)
        ).all()
        for ing in source_ingredients:
            new_ing = RecipeIngredient(
                recipe_id=new_recipe.id,
                ingredient_id=ing.ingredient_id,
                quantity_display=ing.quantity_display,
                # The forked row is a fresh write — coerce the source's
                # unit_display through the canonical normalizer so any
                # historically-freeform units get cleaned up on fork
                # (riip-2 design principle 7). `normalize_unit_display`
                # stays sync (worker contract) and hits a pre-warmed
                # module cache — safe to pass the async session since
                # the cache-miss path (which would `.execute` on the
                # session) doesn't fire in a healthy API process.
                unit_display=normalize_unit_display(
                    ing.unit_display,
                    self.database.db,
                    context={"path": "fork_recipe"},
                ) or ing.unit_display,
                quantity_normalized=ing.quantity_normalized,
                unit_normalized=ing.unit_normalized,
                notes=ing.notes,
                is_optional=ing.is_optional,
                order_index=ing.order_index,
            )
            await self.database.create(new_ing)

        # Clone steps
        source_steps = await self.database.where(
            RecipeStep, recipe_id=str(recipe.id)
        ).all()
        for step in source_steps:
            new_step = RecipeStep(
                recipe_id=new_recipe.id,
                step_number=step.step_number,
                instruction=step.instruction,
                active_time_minutes=step.active_time_minutes,
                timers=step.timers,
                wait_time_minutes=step.wait_time_minutes,
                wait_type=step.wait_type,
                can_prep_ahead=step.can_prep_ahead,
                is_optional=step.is_optional,
            )
            await self.database.create(new_step)

        return success(
            data=ForkRecipe.Response(
                id=str(new_recipe.id),
                forked_from_recipe_id=str(recipe.id),
                forked_from_book_id=str(recipe.recipe_book_id),
                forked_from_recipe_name=recipe.name,
                forked_from_book_name=src_book_name,
            ),
            status=201,
        )

    class Params(BaseModel):
        destination_book_id: str

    class Response(BaseModel):
        id: str
        forked_from_recipe_id: str
        forked_from_book_id: str
        forked_from_recipe_name: str
        forked_from_book_name: str
