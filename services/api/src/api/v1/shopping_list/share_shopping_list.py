"""Share shopping list endpoint - generates a share code."""

import secrets
import string

from pydantic import BaseModel
from utils.api.endpoint import APIException, AsyncEndpoint, success
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


class ShareShoppingList(AsyncEndpoint):
    """Generate or retrieve a share code for a shopping list."""

    async def execute(self, list_id: str, params: "ShareShoppingList.Params"):
        """
        Generate a share code for a shopping list.

        Args:
            list_id: The shopping list's ID
            params: Share options

        Returns:
            Share code and expiration info
        """
        user: User = self.user

        shopping_list = await self.database.find_by(ShoppingList, id=list_id)
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail=f"Shopping list with ID '{list_id}' not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        if shopping_list.owner_id != user.id:
            raise APIException(
                status_code=403,
                detail="Only the owner can share this shopping list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        if not shopping_list.share_code:
            for _ in range(10):
                code = generate_share_code()
                existing = await self.database.find_by(ShoppingList, share_code=code)
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
            await self.database.db.commit()
            await self.database.db.refresh(shopping_list)

        owner_membership = await self.database.find_by(
            ShoppingListUser, shopping_list_id=shopping_list.id, user_id=user.id
        )
        if not owner_membership:  # pragma: no cover — owner record usually exists
            owner_membership = ShoppingListUser(
                shopping_list_id=shopping_list.id,
                user_id=user.id,
                role="owner",
            )
            await self.database.create(owner_membership)

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
