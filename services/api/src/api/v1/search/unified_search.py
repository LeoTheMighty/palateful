"""Unified search endpoint - recipes (my + public) and users."""

from pydantic import BaseModel
from sqlalchemy import exists, or_, select
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

        my_recipes = self._search_my_recipes(query, limit, user)
        public_recipes = self._search_public_recipes(query, limit, user)
        users = self._search_users(query, limit, user)

        return success(
            data=UnifiedSearch.Response(
                query=query,
                my_recipes=my_recipes,
                public_recipes=public_recipes,
                users=users,
            )
        )

    def _recipe_matches(self, query: str):
        """Build recipe match conditions for name, description, and ingredients."""
        ingredient_match = exists(
            select(RecipeIngredient.recipe_id)
            .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
            .where(
                RecipeIngredient.recipe_id == Recipe.id,
                Ingredient.canonical_name.ilike(f"%{query}%"),
            )
        )

        return or_(
            Recipe.name.ilike(f"%{query}%"),
            Recipe.description.ilike(f"%{query}%"),
            ingredient_match,
        )

    def _search_my_recipes(self, query: str, limit: int, user: User):
        """Search recipes in books the user has access to."""
        # Get recipe book IDs the user is a member of
        my_book_ids = (
            self.db.execute(
                select(RecipeBookUser.recipe_book_id)
                .where(RecipeBookUser.user_id == user.id)
            )
            .scalars()
            .all()
        )

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
        """Search recipes in public books the user does NOT have access to."""
        # Find the owner of each public book
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

    # Response models

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
