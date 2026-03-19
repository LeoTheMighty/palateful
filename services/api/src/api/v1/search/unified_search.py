"""Unified search endpoint - recipes (my + public) and users."""

from pydantic import BaseModel
from sqlalchemy import exists, func, or_, select, text
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.friend_request import FriendRequest
from utils.models.friendship import Friendship
from utils.models.ingredient import Ingredient
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.recipe_ingredient import RecipeIngredient
from utils.models.user import User


class UnifiedSearch(Endpoint):
    """Unified search across recipes and users."""

    def execute(self, q: str, limit: int = 20):
        user: User = self.user

        query = q.strip()
        if len(query) < 2:
            raise APIException(
                status_code=400,
                detail="Search query must be at least 2 characters",
                code=ErrorCode.VALIDATION_ERROR,
            )

        limit = min(limit, 50)

        # Cache book IDs — reused by exact, fuzzy, and semantic tiers
        my_book_ids = self._get_my_book_ids(user)

        # Tier 1: exact ILIKE search (name, description, ingredient, tag)
        my_exact = self._search_my_recipes(query, limit, user, my_book_ids)
        pub_exact = self._search_public_recipes(query, limit, user)
        users = self._search_users(query, limit, user)

        # Tier 2: fuzzy pg_trgm (only when exact results don't fill the limit)
        my_exact_ids = {r.id for r in my_exact}
        pub_exact_ids = {r.id for r in pub_exact}

        my_fuzzy: list = []
        if len(my_exact) < limit:
            my_fuzzy = self._search_my_recipes_fuzzy(
                query, limit - len(my_exact), user, my_book_ids, exclude_ids=my_exact_ids
            )

        pub_fuzzy: list = []
        if len(pub_exact) < limit:
            pub_fuzzy = self._search_public_recipes_fuzzy(
                query, limit - len(pub_exact), user, exclude_ids=pub_exact_ids
            )

        # Tier 3: semantic pgvector (only when both exact+fuzzy don't fill the limit)
        my_semantic: list = []
        pub_semantic: list = []
        my_total = len(my_exact) + len(my_fuzzy)
        pub_total = len(pub_exact) + len(pub_fuzzy)

        if my_total < limit or pub_total < limit:
            query_embedding = self._generate_query_embedding(query)
            if query_embedding is not None:
                if my_total < limit:
                    all_my_ids = my_exact_ids | {r.id for r in my_fuzzy}
                    my_semantic = self._search_my_recipes_semantic(
                        query_embedding,
                        limit - my_total,
                        user,
                        my_book_ids,
                        exclude_ids=all_my_ids,
                    )
                if pub_total < limit:
                    all_pub_ids = pub_exact_ids | {r.id for r in pub_fuzzy}
                    pub_semantic = self._search_public_recipes_semantic(
                        query_embedding,
                        limit - pub_total,
                        user,
                        exclude_ids=all_pub_ids,
                    )

        return success(
            data=UnifiedSearch.Response(
                query=query,
                my_recipes=my_exact + my_fuzzy + my_semantic,
                public_recipes=pub_exact + pub_fuzzy + pub_semantic,
                users=users,
            )
        )

    # ── helpers ──────────────────────────────────────────────────────────────

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

    # ── Tier 1: exact ILIKE ──────────────────────────────────────────────────

    def _search_my_recipes(
        self, query: str, limit: int, user: User, book_ids: list | None = None
    ):
        """Search recipes in books the user has access to (exact ILIKE)."""
        my_book_ids = book_ids if book_ids is not None else self._get_my_book_ids(user)

        if not my_book_ids:
            return []

        results = (
            self.db.execute(
                select(Recipe, RecipeBook.name.label("book_name"))
                .join(RecipeBook, Recipe.recipe_book_id == RecipeBook.id)
                .where(
                    Recipe.recipe_book_id.in_(my_book_ids),
                    Recipe.archived_at.is_(None),
                    self._recipe_matches(query),
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
            )
            for recipe, book_name in results
        ]

    def _search_public_recipes(self, query: str, limit: int, user: User):
        """Search recipes in public books the user is NOT a member of (exact ILIKE)."""
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
    ):
        """Fuzzy pg_trgm search for recipes in user's books.

        Wrapped in try/except so the tier degrades gracefully when pg_trgm
        is unavailable (e.g. in local test environments).
        """
        if not book_ids:
            return []
        try:
            exclude_list = [str(eid) for eid in exclude_ids]
            exclude_clause = "AND r.id != ALL(:exclude_ids)" if exclude_list else ""
            params: dict = {
                "book_ids": [str(bid) for bid in book_ids],
                "query": query,
                "limit": limit,
            }
            if exclude_list:
                params["exclude_ids"] = exclude_list

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
    ):
        """Fuzzy pg_trgm search for public recipes the user is not a member of."""
        try:
            exclude_list = [str(eid) for eid in exclude_ids]
            exclude_clause = "AND r.id != ALL(:exclude_ids)" if exclude_list else ""
            params: dict = {
                "user_id": str(user.id),
                "query": query,
                "limit": limit,
            }
            if exclude_list:
                params["exclude_ids"] = exclude_list

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
    ):
        """Semantic cosine-distance search for recipes in user's books."""
        if not book_ids:
            return []
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
    ):
        """Semantic cosine-distance search for public recipes the user is not a member of."""
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

    class Response(BaseModel):
        query: str
        my_recipes: list["UnifiedSearch.RecipeResult"]
        public_recipes: list["UnifiedSearch.PublicRecipeResult"]
        users: list["UnifiedSearch.UserResult"]
