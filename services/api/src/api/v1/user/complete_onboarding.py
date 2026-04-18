"""Complete user onboarding endpoint."""

import logging

from api.v1.shopping_list.bootstrap import ensure_default_shopping_list
from schemas.user import OnboardingRequest, OnboardingResponse, RecipeBookResponse, UserResponse
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User

logger = logging.getLogger(__name__)


class CompleteOnboarding(Endpoint):
    """Complete user onboarding with name and start method selection."""

    def execute(self, params: OnboardingRequest):
        """
        Complete the onboarding process:
        1. Validate and update user's name
        2. Create a default recipe book
        3. Add user as owner of the recipe book
        4. Set the recipe book as user's default
        5. Mark onboarding as complete
        """
        user: User = self.user

        # Guard against double-completion
        if user.has_completed_onboarding:
            user_response = UserResponse(
                id=str(user.id),
                email=user.email,
                name=user.name,
                username=user.username,
                picture=user.picture,
                has_completed_onboarding=user.has_completed_onboarding,
                default_recipe_book_id=str(user.default_recipe_book_id) if user.default_recipe_book_id else None,
                created_at=user.created_at,
                username_changed_at=user.username_changed_at,
            )
            return success(
                data=OnboardingResponse(
                    success=True,
                    user=user_response,
                    start_method=params.start_method,
                )
            )

        # 1. Validate and update user's name
        name = params.name.strip()
        if not name:
            raise APIException(
                status_code=400,
                detail="Name cannot be empty",
                code=ErrorCode.VALIDATION_ERROR,
            )
        user.name = name

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

        # 5. Mark onboarding as complete + record notification permission state
        user.has_completed_onboarding = True
        if params.notification_permission_status is not None:
            user.notification_permission_status = params.notification_permission_status

        # Commit all changes
        self.db.commit()
        self.db.refresh(user)
        self.db.refresh(recipe_book)

        # Post-commit: idempotently ensure the user has a default shopping list.
        # Wrapped in try/except so a failure here does NOT fail onboarding —
        # the migration backfill sweep catches any users missed this way.
        # (See services/api/src/api/v1/shopping_list/bootstrap.py)
        try:
            ensure_default_shopping_list(user, self.db)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "complete_onboarding.default_list_post_commit_failed",
                extra={"user_id": str(user.id), "error": str(exc)},
            )

        # Build response
        user_response = UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            username=user.username,
            picture=user.picture,
            has_completed_onboarding=user.has_completed_onboarding,
            default_recipe_book_id=str(user.default_recipe_book_id) if user.default_recipe_book_id else None,
            created_at=user.created_at,
            username_changed_at=user.username_changed_at,
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
