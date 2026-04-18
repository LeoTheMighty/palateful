"""Unified search endpoint - recipes (my + public), meals, and users."""

from pydantic import BaseModel
from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.friendship import Friendship
from utils.models.ingredient import Ingredient
from utils.models.meal import Meal
from utils.models.meal_recipe import MealRecipe
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.user import User


class UnifiedSearch(Endpoint):
    """Unified search across recipes and users."""

    def execute(
        self,
        q: str,
        limit: int = 20,
        book_id: str | None = None,
        tags: str | None = None,
        max_prep_time: int | None = None,
        max_cook_time: int | None = None,
        scope: str | None = None,
    ):
        user: User = self.user

        query = q.strip()
        filter_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        if len(query) < 2:
            raise APIException(
                status_code=400,
                detail="Search query must be at least 2 characters",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Scope gate — parsed as a comma-separated set (md-1).
        # None / unknown values fall back to "everything" so old clients
        # stay working. `scope=recipes` (old bugs-cal-2 behaviour) keeps
        # the no-users, no-meals semantics. `scope=recipes,meals` is what
        # the new search screen sends. `scope=meals` skips the recipe +
        # user tiers entirely for callers that only care about Meals.
        include_recipes, include_meals, include_users = self._resolve_scope(scope)

        limit = min(limit, 50)

        # Cache book IDs — reused by exact, fuzzy, and semantic tiers
        my_book_ids = self._get_my_book_ids(user)
        # Validate book_id belongs to the user before using it as a filter.
        # Without this check, any authenticated user could pass an arbitrary book_id
        # and access recipes from books they are not a member of.
        if book_id:
            my_book_id_strs = {str(bid) for bid in my_book_ids}
            if book_id not in my_book_id_strs:
                book_id = None  # ignore unauthorized/non-existent book filter
        effective_book_ids = [bid for bid in my_book_ids if str(bid) == book_id] if book_id else my_book_ids
        filter_conditions = self._filter_conditions(filter_tags, max_prep_time, max_cook_time)

        # Tier 1: exact ILIKE search (name, description, ingredient, tag)
        my_exact = (
            self._search_my_recipes(query, limit, user, effective_book_ids, filter_conditions)
            if include_recipes
            else []
        )
        pub_exact = (
            self._search_public_recipes(query, limit, user, filter_conditions)
            if include_recipes
            else []
        )
        users = self._search_users(query, limit, user) if include_users else []
        my_meals = (
            self._search_my_meals(query, limit, user, my_book_ids)
            if include_meals
            else []
        )

        # Tier 2: fuzzy pg_trgm (only when exact results don't fill the limit)
        my_exact_ids = {r.id for r in my_exact}
        pub_exact_ids = {r.id for r in pub_exact}

        my_fuzzy: list = []
        if include_recipes and len(my_exact) < limit:
            my_fuzzy = self._search_my_recipes_fuzzy(
                query, limit - len(my_exact), user, effective_book_ids,
                exclude_ids=my_exact_ids,
                filter_tags=filter_tags,
                max_prep_time=max_prep_time,
                max_cook_time=max_cook_time,
            )

        pub_fuzzy: list = []
        if include_recipes and len(pub_exact) < limit:
            pub_fuzzy = self._search_public_recipes_fuzzy(
                query, limit - len(pub_exact), user,
                exclude_ids=pub_exact_ids,
                filter_tags=filter_tags,
                max_prep_time=max_prep_time,
                max_cook_time=max_cook_time,
            )

        # Tier 3: semantic pgvector (only when both exact+fuzzy don't fill the limit)
        my_semantic: list = []
        pub_semantic: list = []
        my_total = len(my_exact) + len(my_fuzzy)
        pub_total = len(pub_exact) + len(pub_fuzzy)

        if include_recipes and (my_total < limit or pub_total < limit):
            query_embedding = self._generate_query_embedding(query)
            if query_embedding is not None:
                if my_total < limit:
                    all_my_ids = my_exact_ids | {r.id for r in my_fuzzy}
                    my_semantic = self._search_my_recipes_semantic(
                        query_embedding,
                        limit - my_total,
                        user,
                        effective_book_ids,
                        exclude_ids=all_my_ids,
                        filter_conditions=filter_conditions,
                    )
                if pub_total < limit:
                    all_pub_ids = pub_exact_ids | {r.id for r in pub_fuzzy}
                    pub_semantic = self._search_public_recipes_semantic(
                        query_embedding,
                        limit - pub_total,
                        user,
                        exclude_ids=all_pub_ids,
                        filter_conditions=filter_conditions,
                    )

        return success(
            data=UnifiedSearch.Response(
                query=query,
                my_recipes=my_exact + my_fuzzy + my_semantic,
                public_recipes=pub_exact + pub_fuzzy + pub_semantic,
                my_meals=my_meals,
                users=users,
            )
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_scope(scope: str | None) -> tuple[bool, bool, bool]:
        """Return (include_recipes, include_meals, include_users) for a scope.

        * `None` or unknown values → everything (backward-compat).
        * `recipes` (bugs-cal-2 locked) → recipes only, no users, no meals.
        * `meals` → meals only, no recipes, no users.
        * any comma-set containing both `recipes` and `meals` → everything.
        """
        if not scope:
            return (True, True, True)
        scope_set = {s.strip() for s in scope.split(",") if s.strip()}
        if scope_set == {"recipes"}:
            return (True, False, False)
        if scope_set == {"meals"}:
            return (False, True, False)
        if {"recipes", "meals"}.issubset(scope_set):
            return (True, True, True)
        # Unknown scope (or recipes+users combos etc.) → default to
        # everything so legacy callers keep their results.
        return (True, True, True)

    def _get_my_book_ids(self, user: User) -> list:
        """Return recipe book IDs the user is a member of."""
        return (
            self.db.execute(
                select(RecipeBookUser.recipe_book_id)
                .where(RecipeBookUser.user_id == user.id)
            )
            .scalars()
            .all()
        )

    def _recipe_matches(self, query: str):
        """Build OR condition matching name, description, ingredients, and tags."""
        ingredient_match = exists(
            select(RecipeIngredient.recipe_id)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .where(
                RecipeIngredient.recipe_id == Recipe.id,
                Ingredient.canonical_name.ilike(f"%{query}%"),
            )
        )

        # array_to_string(tags, ',') converts ['italian','dinner'] → 'italian,dinner'
        # NULL tags → NULL ilike → NULL (falsy) → no false positives on null tags
        tag_match = func.array_to_string(Recipe.tags, ",").ilike(f"%{query}%")

        return or_(
            Recipe.name.ilike(f"%{query}%"),
            Recipe.description.ilike(f"%{query}%"),
            ingredient_match,
            tag_match,
        )

    def _filter_conditions(
        self,
        filter_tags: list[str],
        max_prep_time: int | None,
        max_cook_time: int | None,
    ) -> list:
        """Build SQLAlchemy WHERE conditions for tags and time filters.

        Book filtering is handled separately: my-recipes tiers use effective_book_ids,
        and public-recipes tiers already exclude the user's own books via .notin_().
        """
        conditions = []
        for tag in filter_tags:
            conditions.append(func.array_to_string(Recipe.tags, ",").ilike(f"%{tag}%"))
        if max_prep_time is not None:
            conditions.append(or_(Recipe.prep_time.is_(None), Recipe.prep_time <= max_prep_time))
        if max_cook_time is not None:
            conditions.append(or_(Recipe.cook_time.is_(None), Recipe.cook_time <= max_cook_time))
        return conditions

    # ── Tier 1: exact ILIKE ──────────────────────────────────────────────────

    def _search_my_recipes(
        self, query: str, limit: int, user: User, book_ids: list | None = None, filter_conditions: list | None = None
    ):
        """Search recipes in books the user has access to (exact ILIKE)."""
        my_book_ids = book_ids if book_ids is not None else self._get_my_book_ids(user)
        filter_conditions = filter_conditions or []

        if not my_book_ids:
            return []

        results = (
            self.db.execute(
                select(Recipe, RecipeBook.name.label("book_name"))
                .join(RecipeBook, Recipe.recipe_book_id == RecipeBook.id)
                .options(
                    selectinload(Recipe.ingredients)
                    .selectinload(RecipeIngredient.ingredient)
                )
                .where(
                    Recipe.recipe_book_id.in_(my_book_ids),
                    Recipe.archived_at.is_(None),
                    self._recipe_matches(query),
                    *filter_conditions,
                )
                .order_by(
                    (Recipe.name.ilike(query)).desc(),
                    (Recipe.name.ilike(f"{query}%")).desc(),
                    Recipe.updated_at.desc(),
                )
                .limit(limit)
            )
            .all()
        )

        return [
            UnifiedSearch.RecipeResult(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                image_url=recipe.image_url,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                recipe_book_id=str(recipe.recipe_book_id),
                recipe_book_name=book_name,
                ingredients=[
                    ri.ingredient.canonical_name
                    for ri in recipe.ingredients[:5]
                ],
                tags=recipe.tags or [],
            )
            for recipe, book_name in results
        ]

    def _search_public_recipes(self, query: str, limit: int, user: User, filter_conditions: list | None = None):
        """Search recipes in public books the user is NOT a member of (exact ILIKE)."""
        filter_conditions = filter_conditions or []
        owner_subq = (
            select(
                RecipeBookUser.recipe_book_id,
                User.id.label("owner_id"),
                User.username.label("owner_username"),
                User.picture.label("owner_picture"),
            )
            .join(User, RecipeBookUser.user_id == User.id)
            .where(RecipeBookUser.role == "owner")
            .subquery()
        )

        results = (
            self.db.execute(
                select(
                    Recipe,
                    RecipeBook.name.label("book_name"),
                    owner_subq.c.owner_id,
                    owner_subq.c.owner_username,
                    owner_subq.c.owner_picture,
                )
                .join(RecipeBook, Recipe.recipe_book_id == RecipeBook.id)
                .options(
                    selectinload(Recipe.ingredients)
                    .selectinload(RecipeIngredient.ingredient)
                )
                .outerjoin(
                    owner_subq,
                    owner_subq.c.recipe_book_id == RecipeBook.id,
                )
                .where(
                    RecipeBook.is_public == True,  # noqa: E712
                    Recipe.archived_at.is_(None),
                    Recipe.recipe_book_id.notin_(
                        select(RecipeBookUser.recipe_book_id)
                        .where(RecipeBookUser.user_id == user.id)
                    ),
                    self._recipe_matches(query),
                    *filter_conditions,
                )
                .order_by(
                    (Recipe.name.ilike(query)).desc(),
                    (Recipe.name.ilike(f"{query}%")).desc(),
                    Recipe.updated_at.desc(),
                )
                .limit(limit)
            )
            .all()
        )

        return [
            UnifiedSearch.PublicRecipeResult(
                id=str(recipe.id),
                name=recipe.name,
                description=recipe.description,
                image_url=recipe.image_url,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                recipe_book_id=str(recipe.recipe_book_id),
                recipe_book_name=book_name,
                ingredients=[
                    ri.ingredient.canonical_name
                    for ri in recipe.ingredients[:5]
                ],
                owner=UnifiedSearch.OwnerInfo(
                    id=str(owner_id) if owner_id else None,
                    username=owner_username,
                    picture=owner_picture,
                ),
            )
            for recipe, book_name, owner_id, owner_username, owner_picture in results
        ]

    # ── Tier 2: fuzzy pg_trgm ────────────────────────────────────────────────

    def _search_my_recipes_fuzzy(
        self,
        query: str,
        limit: int,
        user: User,
        book_ids: list,
        exclude_ids: set,
        filter_tags: list | None = None,
        max_prep_time: int | None = None,
        max_cook_time: int | None = None,
    ):
        """Fuzzy pg_trgm search for recipes in user's books.

        Wrapped in try/except so the tier degrades gracefully when pg_trgm
        is unavailable (e.g. in local test environments).
        """
        if not book_ids:
            return []
        filter_tags = filter_tags or []
        try:
            exclude_list = [str(eid) for eid in exclude_ids]
            exclude_clause = "AND r.id != ALL(:exclude_ids)" if exclude_list else ""
            prep_clause = "AND (r.prep_time IS NULL OR r.prep_time <= :max_prep_time)" if max_prep_time is not None else ""
            cook_clause = "AND (r.cook_time IS NULL OR r.cook_time <= :max_cook_time)" if max_cook_time is not None else ""
            tag_clauses = "\n".join(
                f"AND array_to_string(r.tags, ',') ILIKE :filter_tag_{i}"
                for i in range(len(filter_tags))
            )
            params: dict = {
                "book_ids": [str(bid) for bid in book_ids],
                "query": query,
                "limit": limit,
            }
            if exclude_list:
                params["exclude_ids"] = exclude_list
            if max_prep_time is not None:
                params["max_prep_time"] = max_prep_time
            if max_cook_time is not None:
                params["max_cook_time"] = max_cook_time
            for i, tag in enumerate(filter_tags):
                params[f"filter_tag_{i}"] = f"%{tag}%"

            rows = self.db.execute(
                text(f"""
                    SELECT r.id, r.name, r.description, r.image_url,
                           r.prep_time, r.cook_time, r.recipe_book_id,
                           rb.name AS book_name
                    FROM recipes r
                    JOIN recipe_books rb ON r.recipe_book_id = rb.id
                    WHERE r.recipe_book_id = ANY(:book_ids)
                      AND r.archived_at IS NULL
                      {exclude_clause}
                      {prep_clause}
                      {cook_clause}
                      {tag_clauses}
                      AND (
                        similarity(r.name, :query) > 0.2
                        OR r.name % :query
                        OR similarity(r.description, :query) > 0.2
                      )
                    ORDER BY similarity(r.name, :query) DESC
                    LIMIT :limit
                """),
                params,
            ).all()

            return [
                UnifiedSearch.RecipeResult(
                    id=str(row.id),
                    name=row.name,
                    description=row.description,
                    image_url=row.image_url,
                    prep_time=row.prep_time,
                    cook_time=row.cook_time,
                    recipe_book_id=str(row.recipe_book_id),
                    recipe_book_name=row.book_name,
                    ingredients=[],
                )
                for row in rows
            ]
        except Exception:
            return []

    def _search_public_recipes_fuzzy(
        self,
        query: str,
        limit: int,
        user: User,
        exclude_ids: set,
        filter_tags: list | None = None,
        max_prep_time: int | None = None,
        max_cook_time: int | None = None,
    ):
        """Fuzzy pg_trgm search for public recipes the user is not a member of."""
        filter_tags = filter_tags or []
        try:
            exclude_list = [str(eid) for eid in exclude_ids]
            exclude_clause = "AND r.id != ALL(:exclude_ids)" if exclude_list else ""
            prep_clause = "AND (r.prep_time IS NULL OR r.prep_time <= :max_prep_time)" if max_prep_time is not None else ""
            cook_clause = "AND (r.cook_time IS NULL OR r.cook_time <= :max_cook_time)" if max_cook_time is not None else ""
            tag_clauses = "\n".join(
                f"AND array_to_string(r.tags, ',') ILIKE :filter_tag_{i}"
                for i in range(len(filter_tags))
            )
            params: dict = {
                "user_id": str(user.id),
                "query": query,
                "limit": limit,
            }
            if exclude_list:
                params["exclude_ids"] = exclude_list
            if max_prep_time is not None:
                params["max_prep_time"] = max_prep_time
            if max_cook_time is not None:
                params["max_cook_time"] = max_cook_time
            for i, tag in enumerate(filter_tags):
                params[f"filter_tag_{i}"] = f"%{tag}%"

            rows = self.db.execute(
                text(f"""
                    SELECT r.id, r.name, r.description, r.image_url,
                           r.prep_time, r.cook_time, r.recipe_book_id,
                           rb.name AS book_name,
                           u.id AS owner_id, u.username AS owner_username,
                           u.picture AS owner_picture
                    FROM recipes r
                    JOIN recipe_books rb ON r.recipe_book_id = rb.id
                    LEFT JOIN recipe_book_users rbu_owner
                           ON rb.id = rbu_owner.recipe_book_id
                          AND rbu_owner.role = 'owner'
                    LEFT JOIN users u ON rbu_owner.user_id = u.id
                    WHERE rb.is_public = TRUE
                      AND r.archived_at IS NULL
                      AND rb.id NOT IN (
                          SELECT recipe_book_id FROM recipe_book_users
                          WHERE user_id = :user_id
                      )
                      {exclude_clause}
                      {prep_clause}
                      {cook_clause}
                      {tag_clauses}
                      AND (
                        similarity(r.name, :query) > 0.2
                        OR r.name % :query
                        OR similarity(r.description, :query) > 0.2
                      )
                    ORDER BY similarity(r.name, :query) DESC
                    LIMIT :limit
                """),
                params,
            ).all()

            return [
                UnifiedSearch.PublicRecipeResult(
                    id=str(row.id),
                    name=row.name,
                    description=row.description,
                    image_url=row.image_url,
                    prep_time=row.prep_time,
                    cook_time=row.cook_time,
                    recipe_book_id=str(row.recipe_book_id),
                    recipe_book_name=row.book_name,
                    ingredients=[],
                    owner=UnifiedSearch.OwnerInfo(
                        id=str(row.owner_id) if row.owner_id else None,
                        username=row.owner_username,
                        picture=row.owner_picture,
                    ),
                )
                for row in rows
            ]
        except Exception:
            return []

    # ── Tier 3: semantic pgvector ────────────────────────────────────────────

    def _generate_query_embedding(self, query: str) -> list[float] | None:
        """Generate a 384-dim embedding for the query via OpenAI.

        Returns None if the OpenAI call fails or the key is not set,
        so the semantic tier degrades gracefully.
        """
        try:
            from openai import OpenAI

            client = OpenAI()  # reads OPENAI_API_KEY from env
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=query,
                dimensions=384,
            )
            return resp.data[0].embedding
        except Exception:
            return None

    def _search_my_recipes_semantic(
        self,
        query_embedding: list[float],
        limit: int,
        user: User,
        book_ids: list,
        exclude_ids: set,
        filter_conditions: list | None = None,
    ):
        """Semantic cosine-distance search for recipes in user's books."""
        if not book_ids:
            return []
        filter_conditions = filter_conditions or []
        try:
            distance = Recipe.embedding.cosine_distance(query_embedding)
            stmt = (
                select(Recipe, RecipeBook.name.label("book_name"))
                .join(RecipeBook, Recipe.recipe_book_id == RecipeBook.id)
                .where(
                    Recipe.recipe_book_id.in_(book_ids),
                    Recipe.archived_at.is_(None),
                    Recipe.embedding.is_not(None),
                    distance < 0.7,
                    *filter_conditions,
                )
                .order_by(distance)
                .limit(limit)
            )
            if exclude_ids:
                stmt = stmt.where(Recipe.id.notin_(list(exclude_ids)))

            results = self.db.execute(stmt).all()
            return [
                UnifiedSearch.RecipeResult(
                    id=str(recipe.id),
                    name=recipe.name,
                    description=recipe.description,
                    image_url=recipe.image_url,
                    prep_time=recipe.prep_time,
                    cook_time=recipe.cook_time,
                    recipe_book_id=str(recipe.recipe_book_id),
                    recipe_book_name=book_name,
                    ingredients=[
                        ri.ingredient.canonical_name
                        for ri in recipe.ingredients[:5]
                    ],
                    tags=recipe.tags or [],
                )
                for recipe, book_name in results
            ]
        except Exception:
            return []

    def _search_public_recipes_semantic(
        self,
        query_embedding: list[float],
        limit: int,
        user: User,
        exclude_ids: set,
        filter_conditions: list | None = None,
    ):
        """Semantic cosine-distance search for public recipes the user is not a member of."""
        filter_conditions = filter_conditions or []
        try:
            owner_subq = (
                select(
                    RecipeBookUser.recipe_book_id,
                    User.id.label("owner_id"),
                    User.username.label("owner_username"),
                    User.picture.label("owner_picture"),
                )
                .join(User, RecipeBookUser.user_id == User.id)
                .where(RecipeBookUser.role == "owner")
                .subquery()
            )

            distance = Recipe.embedding.cosine_distance(query_embedding)
            stmt = (
                select(
                    Recipe,
                    RecipeBook.name.label("book_name"),
                    owner_subq.c.owner_id,
                    owner_subq.c.owner_username,
                    owner_subq.c.owner_picture,
                )
                .join(RecipeBook, Recipe.recipe_book_id == RecipeBook.id)
                .outerjoin(owner_subq, owner_subq.c.recipe_book_id == RecipeBook.id)
                .where(
                    RecipeBook.is_public == True,  # noqa: E712
                    Recipe.archived_at.is_(None),
                    Recipe.recipe_book_id.notin_(
                        select(RecipeBookUser.recipe_book_id)
                        .where(RecipeBookUser.user_id == user.id)
                    ),
                    Recipe.embedding.is_not(None),
                    distance < 0.7,
                    *filter_conditions,
                )
                .order_by(distance)
                .limit(limit)
            )
            if exclude_ids:
                stmt = stmt.where(Recipe.id.notin_(list(exclude_ids)))

            results = self.db.execute(stmt).all()
            return [
                UnifiedSearch.PublicRecipeResult(
                    id=str(recipe.id),
                    name=recipe.name,
                    description=recipe.description,
                    image_url=recipe.image_url,
                    prep_time=recipe.prep_time,
                    cook_time=recipe.cook_time,
                    recipe_book_id=str(recipe.recipe_book_id),
                    recipe_book_name=book_name,
                    ingredients=[
                        ri.ingredient.canonical_name
                        for ri in recipe.ingredients[:5]
                    ],
                    owner=UnifiedSearch.OwnerInfo(
                        id=str(owner_id) if owner_id else None,
                        username=owner_username,
                        picture=owner_picture,
                    ),
                )
                for recipe, book_name, owner_id, owner_username, owner_picture in results
            ]
        except Exception:
            return []

    # ── meals ────────────────────────────────────────────────────────────────

    def _search_my_meals(
        self,
        query: str,
        limit: int,
        user: User,
        book_ids: list,
    ):
        """Search Meals in books the user can read (exact ILIKE only, v1).

        Ranking: direct-name/description matches rank before component-name
        matches; within each rank, ORDER BY `updated_at DESC`.

        Direct hits get `matched_component=None`. Component hits get the
        first matching component's `{recipe_id, name}` surfaced so the
        client can render the "Matches: X" disclosure.
        """
        if not book_ids:
            return []

        direct_rows = self.db.execute(
            select(Meal, RecipeBook.name.label("book_name"))
            .join(RecipeBook, Meal.recipe_book_id == RecipeBook.id)
            .options(
                selectinload(Meal.components)
                .selectinload(MealRecipe.recipe)
                .selectinload(Recipe.recipe_book)
            )
            .where(
                Meal.recipe_book_id.in_(book_ids),
                Meal.archived_at.is_(None),
                or_(
                    Meal.name.ilike(f"%{query}%"),
                    Meal.description.ilike(f"%{query}%"),
                ),
            )
            .order_by(
                (Meal.name.ilike(query)).desc(),
                (Meal.name.ilike(f"{query}%")).desc(),
                Meal.updated_at.desc(),
            )
            .limit(limit)
        ).all()

        direct_meal_ids = {meal.id for meal, _ in direct_rows}

        component_rows: list = []
        remaining = limit - len(direct_rows)
        if remaining > 0:
            comp_stmt = (
                select(Meal, RecipeBook.name.label("book_name"))
                .join(RecipeBook, Meal.recipe_book_id == RecipeBook.id)
                .options(
                    selectinload(Meal.components)
                    .selectinload(MealRecipe.recipe)
                    .selectinload(Recipe.recipe_book)
                )
                .where(
                    Meal.recipe_book_id.in_(book_ids),
                    Meal.archived_at.is_(None),
                    exists(
                        select(MealRecipe.meal_id)
                        .join(Recipe, MealRecipe.recipe_id == Recipe.id)
                        .where(
                            MealRecipe.meal_id == Meal.id,
                            Recipe.name.ilike(f"%{query}%"),
                        )
                    ),
                )
                .order_by(Meal.updated_at.desc())
                .limit(remaining)
            )
            if direct_meal_ids:
                comp_stmt = comp_stmt.where(
                    Meal.id.notin_(list(direct_meal_ids))
                )
            component_rows = self.db.execute(comp_stmt).all()

        results: list[UnifiedSearch.MealSearchResult] = []
        for meal, book_name in direct_rows:
            results.append(
                self._build_meal_search_result(
                    meal, book_name, matched_component=None
                )
            )
        lowered = query.lower()
        for meal, book_name in component_rows:
            matched = next(
                (
                    c
                    for c in meal.components
                    if c.recipe is not None
                    and c.recipe.name
                    and lowered in c.recipe.name.lower()
                ),
                None,
            )
            matched_payload: UnifiedSearch.MatchedComponent | None = None
            if matched is not None:
                matched_payload = UnifiedSearch.MatchedComponent(
                    recipe_id=str(matched.recipe_id),
                    name=matched.recipe.name,
                )
            results.append(
                self._build_meal_search_result(
                    meal, book_name, matched_component=matched_payload
                )
            )
        return results

    def _build_meal_search_result(
        self,
        meal: Meal,
        book_name: str,
        *,
        matched_component,
    ):
        """Shape a Meal into a search result — reuses availability logic
        from the grid tile so components that the user lost read access
        to (or archived) do not leak their image URL into the response.
        """
        top_image_urls: list[str] = []
        for comp in meal.components:
            if len(top_image_urls) >= 4:
                break
            recipe = comp.recipe
            if recipe is None or recipe.archived_at is not None:
                continue
            book = recipe.recipe_book
            if book is None or book.archived_at is not None:
                continue
            if not recipe.image_url:
                continue
            top_image_urls.append(recipe.image_url)
        component_count = len(meal.components)
        return UnifiedSearch.MealSearchResult(
            id=str(meal.id),
            name=meal.name,
            description=meal.description,
            recipe_book_id=str(meal.recipe_book_id),
            recipe_book_name=book_name,
            component_count=component_count,
            top_component_image_urls=top_image_urls,
            matched_component=matched_component,
        )

    # ── users ────────────────────────────────────────────────────────────────

    def _search_users(self, query: str, limit: int, user: User):
        """Search users, friends first."""
        search_query = query.lower()
        if search_query.startswith("@"):
            search_query = search_query[1:]

        search_results = (
            self.db.execute(
                select(User)
                .outerjoin(
                    Friendship,
                    (Friendship.user_id == user.id) & (Friendship.friend_id == User.id),
                )
                .where(
                    User.id != user.id,
                    User.username.isnot(None),
                    or_(
                        User.username.ilike(f"%{search_query}%"),
                        User.name.ilike(f"%{search_query}%"),
                    ),
                )
                .order_by(
                    (Friendship.friend_id.isnot(None)).desc(),
                    (User.username == search_query).desc(),
                    (User.username.startswith(search_query)).desc(),
                    User.username,
                )
                .limit(limit)
            )
            .scalars()
            .all()
        )

        # Get friendship/request status in bulk
        user_ids = [u.id for u in search_results]

        friendships = set(
            self.db.execute(
                select(Friendship.friend_id).where(
                    Friendship.user_id == user.id,
                    Friendship.friend_id.in_(user_ids),
                )
            ).scalars().all()
        )

        sent_requests = {
            r.to_user_id: r.id
            for r in self.db.execute(
                select(FriendRequest).where(
                    FriendRequest.from_user_id == user.id,
                    FriendRequest.to_user_id.in_(user_ids),
                    FriendRequest.status == "pending",
                )
            ).scalars().all()
        }

        received_requests = {
            r.from_user_id: r.id
            for r in self.db.execute(
                select(FriendRequest).where(
                    FriendRequest.to_user_id == user.id,
                    FriendRequest.from_user_id.in_(user_ids),
                    FriendRequest.status == "pending",
                )
            ).scalars().all()
        }

        results = []
        for u in search_results:
            if u.id in friendships:
                status = "friends"
            elif u.id in sent_requests:
                status = "request_sent"
            elif u.id in received_requests:
                status = "request_received"
            else:
                status = "none"

            results.append(
                UnifiedSearch.UserResult(
                    id=str(u.id),
                    username=u.username,
                    name=u.name,
                    picture=u.picture,
                    friendship_status=status,
                )
            )

        return results

    # ── Response models ──────────────────────────────────────────────────────

    class RecipeResult(BaseModel):
        id: str
        name: str
        description: str | None = None
        image_url: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        recipe_book_id: str
        recipe_book_name: str
        ingredients: list[str] = []
        tags: list[str] = []

    class OwnerInfo(BaseModel):
        id: str | None = None
        username: str | None = None
        picture: str | None = None

    class PublicRecipeResult(BaseModel):
        id: str
        name: str
        description: str | None = None
        image_url: str | None = None
        prep_time: int | None = None
        cook_time: int | None = None
        recipe_book_id: str
        recipe_book_name: str
        ingredients: list[str] = []
        owner: "UnifiedSearch.OwnerInfo"

    class UserResult(BaseModel):
        id: str
        username: str | None = None
        name: str | None = None
        picture: str | None = None
        friendship_status: str

    class MatchedComponent(BaseModel):
        recipe_id: str
        name: str

    class MealSearchResult(BaseModel):
        id: str
        name: str
        description: str | None = None
        recipe_book_id: str
        recipe_book_name: str
        component_count: int
        top_component_image_urls: list[str] = []
        matched_component: "UnifiedSearch.MatchedComponent | None" = None

    class Response(BaseModel):
        query: str
        my_recipes: list["UnifiedSearch.RecipeResult"]
        public_recipes: list["UnifiedSearch.PublicRecipeResult"]
        my_meals: list["UnifiedSearch.MealSearchResult"] = []
        users: list["UnifiedSearch.UserResult"]
