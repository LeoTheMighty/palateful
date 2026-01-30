"""Share shopping list endpoint - generates a share code."""

import secrets
import string

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


def generate_share_code(length: int = 6) -> str:
    """Generate a random share code."""
    alphabet = string.ascii_uppercase + string.digits
    # Avoid confusing characters
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


class ShareShoppingList(Endpoint):
    """Generate or retrieve a share code for a shopping list."""

    def execute(self, list_id: str, params: "ShareShoppingList.Params"):
        """
        Generate a share code for a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Share options

        Returns:
            Share code and expiration info
        """
        user: User = self.user

        # Find shopping list
        shopping_list = self.database.find_by(ShoppingList, id=list_id)
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        # Check access - must be owner
        if shopping_list.owner_id != user.id:
            raise APIException(
                status_code=403,
                detail="Only the owner can share this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Generate share code if not already shared
        if not shopping_list.share_code:
            # Ensure unique code
            for _ in range(10):  # Try up to 10 times
                code = generate_share_code()
                existing = self.database.find_by(ShoppingList, share_code=code)
                if not existing:
                    break
            else:
                raise APIException(
                    status_code=500,
                    detail="Failed to generate unique share code",
                    code=ErrorCode.INTERNAL_ERROR,
                )

            shopping_list.share_code = code
            shopping_list.is_shared = True
            self.database.db.commit()
            self.database.db.refresh(shopping_list)

        # Ensure owner has membership record
        owner_membership = self.database.find_by(
            ShoppingListUser, shopping_list_id=shopping_list.id, user_id=user.id
        )
        if not owner_membership:
            owner_membership = ShoppingListUser(
                shopping_list_id=shopping_list.id,
                user_id=user.id,
                role="owner",
            )
            self.database.create(owner_membership)

        return success(
            data=ShareShoppingList.Response(
                share_code=shopping_list.share_code,
                is_shared=shopping_list.is_shared,
                share_url=f"/shopping-lists/join/{shopping_list.share_code}",
            )
        )

    class Params(BaseModel):
        regenerate: bool = False  # If True, generate a new code even if one exists

    class Response(BaseModel):
        share_code: str
        is_shared: bool
        share_url: str
