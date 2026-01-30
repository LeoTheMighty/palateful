"""Complete user onboarding endpoint."""

from schemas.user import OnboardingRequest, OnboardingResponse, RecipeBookResponse, UserResponse
from utils.api.endpoint import Endpoint, success
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User


class CompleteOnboarding(Endpoint):
    """Complete user onboarding with name and start method selection."""

    def execute(self, params: OnboardingRequest):
        """
        Complete the onboarding process:
        1. Update user's name
        2. Create a default recipe book
        3. Add user as owner of the recipe book
        4. Set the recipe book as user's default
        5. Mark onboarding as complete
        """
        user: User = self.user

        # 1. Update user's name
        user.name = params.name

        # 2. Create default recipe book
        recipe_book = RecipeBook(
            name="My Recipes",
            description="Your personal recipe collection",
            is_public=False,
        )
        self.db.add(recipe_book)
        self.db.flush()  # Get the recipe book ID

        # 3. Add user as owner of the recipe book
        membership = RecipeBookUser(
            user_id=user.id,
            recipe_book_id=recipe_book.id,
            role="owner",
        )
        self.db.add(membership)

        # 4. Set as default recipe book
        user.default_recipe_book_id = recipe_book.id

        # 5. Mark onboarding as complete
        user.has_completed_onboarding = True

        # Commit all changes
        self.db.commit()
        self.db.refresh(user)
        self.db.refresh(recipe_book)

        # Build response
        user_response = UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            picture=user.picture,
            has_completed_onboarding=user.has_completed_onboarding,
            default_recipe_book_id=str(user.default_recipe_book_id) if user.default_recipe_book_id else None,
            created_at=user.created_at,
        )

        recipe_book_response = RecipeBookResponse(
            id=str(recipe_book.id),
            name=recipe_book.name,
            description=recipe_book.description,
            is_public=recipe_book.is_public,
            created_at=recipe_book.created_at,
        )

        return success(
            data=OnboardingResponse(
                success=True,
                user=user_response,
                recipe_book=recipe_book_response,
                start_method=params.start_method,
            )
        )

    class Params(OnboardingRequest):
        """Alias for request params."""
        pass

    class Response(OnboardingResponse):
        """Alias for response."""
        pass
