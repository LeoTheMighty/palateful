"""Recipe tools for searching and suggesting recipes."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agent.config import settings
from agent.tools.base import BaseTool, ToolResult


class SearchRecipesTool(BaseTool):
    """Tool to search recipes using semantic search."""

    @property
    def name(self) -> str:
        return "search_recipes"

    @property
    def description(self) -> str:
        return """Search for recipes using natural language. Can find recipes by description,
        ingredients, cuisine type, or cooking style. Uses semantic search for best results.
        Returns recipes that match the query along with their ingredients and preparation info."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query (e.g., 'quick pasta dinner', 'healthy chicken recipes')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of recipes to return",
                    "default": 5,
                },
                "max_cook_time": {
                    "type": "integer",
                    "description": "Maximum total cook time in minutes",
                },
                "pantry_match": {
                    "type": "boolean",
                    "description": "Only return recipes that can be made with user's pantry items",
                    "default": False,
                },
            },
            "required": ["query"],
        }

    def execute(
        self,
        db: Session,
        user_id: str,
        query: str,
        max_results: int = 5,
        max_cook_time: int | None = None,
        pantry_match: bool = False,
    ) -> ToolResult:
        """Search recipes using semantic search."""
        from utils.models import Recipe, RecipeBookUser, RecipeIngredient

        try:
            # Generate embedding for the query
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(settings.embedding_model)
            query_embedding = model.encode(query).tolist()

            # Get user's recipe books
            book_query = select(RecipeBookUser.recipe_book_id).where(
                RecipeBookUser.user_id == user_id
            )
            book_result = db.execute(book_query)
            book_ids = [row[0] for row in book_result.fetchall()]

            if not book_ids:
                return ToolResult(
                    success=True,
                    data={
                        "recipes": [],
                        "message": "User has no recipe books.",
                    },
                )

            # Build query with vector similarity
            # Note: This requires the recipe to have an embedding
            base_query = (
                select(
                    Recipe,
                    Recipe.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .options(
                    selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
                    selectinload(Recipe.recipe_book),
                )
                .where(Recipe.recipe_book_id.in_(book_ids))
                .where(Recipe.archived_at.is_(None))
                .where(Recipe.embedding.is_not(None))
            )

            # Filter by cook time
            if max_cook_time:
                base_query = base_query.where(
                    (Recipe.prep_time + Recipe.cook_time) <= max_cook_time
                )

            # Order by similarity and limit
            base_query = base_query.order_by("distance").limit(max_results * 2)

            result = db.execute(base_query)
            recipe_rows = result.fetchall()

            # Format recipes
            recipes = []
            for row in recipe_rows:
                recipe = row[0]
                distance = row[1]

                recipe_data = {
                    "id": str(recipe.id),
                    "name": recipe.name,
                    "recipe_book_name": recipe.recipe_book.name if recipe.recipe_book else None,
                    "description": recipe.description,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "total_time": (recipe.prep_time or 0) + (recipe.cook_time or 0),
                    "servings": recipe.servings,
                    "relevance_score": round(1 - distance, 3) if distance else 0,
                    "ingredients": [
                        {
                            "name": ri.ingredient.canonical_name if ri.ingredient else ri.original_text,
                            "quantity": ri.quantity,
                            "unit": ri.unit,
                        }
                        for ri in recipe.ingredients
                    ],
                }

                if recipe.image_url:
                    recipe_data["image_url"] = recipe.image_url

                recipes.append(recipe_data)

            # If pantry_match, filter to only recipes makeable with pantry
            if pantry_match:
                from agent.tools.pantry import GetPantryTool

                pantry_tool = GetPantryTool()
                pantry_result = pantry_tool.execute(db, user_id)

                if pantry_result.success and pantry_result.data:
                    pantry_ingredients = {
                        item["ingredient_name"].lower()
                        for item in pantry_result.data.get("items", [])
                    }

                    # Filter recipes where all ingredients are in pantry
                    filtered = []
                    for recipe in recipes:
                        recipe_ingredients = {
                            ing["name"].lower() for ing in recipe["ingredients"]
                        }
                        missing = recipe_ingredients - pantry_ingredients
                        recipe["missing_ingredients"] = list(missing)
                        recipe["can_make"] = len(missing) == 0

                        if len(missing) <= 2:  # Allow up to 2 missing ingredients
                            filtered.append(recipe)

                    recipes = filtered[:max_results]
                    recipes.sort(key=lambda r: len(r.get("missing_ingredients", [])))

            return ToolResult(
                success=True,
                data={
                    "recipes": recipes[:max_results],
                    "total_found": len(recipes),
                    "query": query,
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))


class AddNoteToRecipeTool(BaseTool):
    """Tool to add a note to a recipe."""

    @property
    def name(self) -> str:
        return "add_note_to_recipe"

    @property
    def description(self) -> str:
        return """Add a note to a recipe in the user's collection. Use this when the user
        wants to record a tip, variation, or observation about a recipe.
        You can identify the recipe by its UUID or by name (natural language)."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "note_body": {
                    "type": "string",
                    "description": "Content of the note to add",
                },
                "recipe_id": {
                    "type": "string",
                    "description": "UUID of the recipe to add the note to",
                },
                "recipe_name": {
                    "type": "string",
                    "description": "Name of the recipe (used for search if recipe_id not provided)",
                },
            },
            "required": ["note_body"],
        }

    def execute(
        self,
        db: Session,
        user_id: str,
        note_body: str,
        recipe_id: str | None = None,
        recipe_name: str | None = None,
    ) -> ToolResult:
        """Add a note to a recipe."""
        from utils.models import Recipe, RecipeBookUser
        from utils.models.recipe_note import RecipeNote

        try:
            if not note_body.strip():
                return ToolResult(success=False, error="Note body cannot be empty")

            if not recipe_id and not (recipe_name and recipe_name.strip()):
                return ToolResult(
                    success=False, error="Either recipe_id or recipe_name is required"
                )

            recipe = None

            if recipe_id:
                recipe = db.get(Recipe, recipe_id)
            else:
                # Semantic search for best match by name
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(settings.embedding_model)
                query_embedding = model.encode(recipe_name.strip()).tolist()

                book_query = select(RecipeBookUser.recipe_book_id).where(
                    RecipeBookUser.user_id == user_id
                )
                book_ids = [row[0] for row in db.execute(book_query).fetchall()]

                if not book_ids:
                    return ToolResult(success=False, error="User has no recipe books")

                row = db.execute(
                    select(
                        Recipe,
                        Recipe.embedding.cosine_distance(query_embedding).label("distance"),
                    )
                    .where(Recipe.recipe_book_id.in_(book_ids))
                    .where(Recipe.archived_at.is_(None))
                    .where(Recipe.embedding.is_not(None))
                    .order_by("distance")
                    .limit(1)
                ).fetchone()

                if row:
                    recipe = row[0]

            if not recipe:
                return ToolResult(success=False, error="Recipe not found")

            # Verify user has access (any membership role may add notes)
            membership = db.execute(
                select(RecipeBookUser).where(
                    RecipeBookUser.user_id == user_id,
                    RecipeBookUser.recipe_book_id == recipe.recipe_book_id,
                )
            ).scalar_one_or_none()

            if not membership:
                return ToolResult(success=False, error="Recipe not found or access denied")

            note = RecipeNote(
                recipe_id=recipe.id,
                body=note_body.strip(),
                created_by=user_id,
            )
            db.add(note)
            db.flush()

            return ToolResult(
                success=True,
                data={
                    "note_id": str(note.id),
                    "recipe_id": str(recipe.id),
                    "recipe_name": recipe.name,
                    "note_body": note_body.strip(),
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SuggestRecipeTool(BaseTool):
    """Tool to generate AI recipe suggestions."""

    @property
    def name(self) -> str:
        return "suggest_recipe"

    @property
    def description(self) -> str:
        return """Generate a new recipe suggestion based on available ingredients and preferences.
        This tool uses AI to create custom recipe ideas that match the user's needs."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ingredients to use",
                },
                "cuisine": {
                    "type": "string",
                    "description": "Preferred cuisine type (e.g., 'Italian', 'Asian')",
                },
                "meal_type": {
                    "type": "string",
                    "description": "Type of meal (e.g., 'breakfast', 'dinner', 'snack')",
                },
                "dietary_restrictions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dietary restrictions to consider",
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["easy", "medium", "hard"],
                    "description": "Desired recipe difficulty",
                },
            },
            "required": ["ingredients"],
        }

    def execute(
        self,
        db: Session,
        user_id: str,
        ingredients: list[str],
        cuisine: str | None = None,
        meal_type: str | None = None,
        dietary_restrictions: list[str] | None = None,
        difficulty: str = "medium",
    ) -> ToolResult:
        """Generate a recipe suggestion using LLM."""
        from agent.llm import Message, get_llm_provider

        try:
            provider = get_llm_provider()

            # Build the prompt
            prompt = f"""Create a recipe suggestion using these ingredients: {', '.join(ingredients)}

Requirements:
- Difficulty: {difficulty}
"""
            if cuisine:
                prompt += f"- Cuisine: {cuisine}\n"
            if meal_type:
                prompt += f"- Meal type: {meal_type}\n"
            if dietary_restrictions:
                prompt += f"- Dietary restrictions: {', '.join(dietary_restrictions)}\n"

            prompt += """
Please provide:
1. Recipe name
2. Brief description
3. Estimated prep and cook time
4. Complete ingredient list with quantities
5. Step-by-step instructions
6. Any tips or variations

Format the response as a structured recipe."""

            messages = [
                Message(
                    role="system",
                    content="You are a helpful culinary assistant that creates delicious, practical recipes.",
                ),
                Message(role="user", content=prompt),
            ]

            response = provider.chat(messages, temperature=0.8)

            return ToolResult(
                success=True,
                data={
                    "suggestion": response.content,
                    "based_on_ingredients": ingredients,
                    "cuisine": cuisine,
                    "meal_type": meal_type,
                    "model_used": response.model,
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))
