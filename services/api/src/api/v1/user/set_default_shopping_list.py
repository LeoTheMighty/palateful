"""Set default shopping list endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User


class SetDefaultShoppingList(Endpoint):
    """Set the user's default shopping list."""

    def execute(self, params: "SetDefaultShoppingList.Params"):
        user: User = self.user

        if params.shopping_list_id is None:
            # Clear both default and previous
            user.default_shopping_list_id = None
            user.previous_shopping_list_id = None
            self.db.commit()
            self.db.refresh(user)
            return success(
                data=SetDefaultShoppingList.Response(
                    default_shopping_list_id=None,
                    previous_shopping_list_id=None,
                )
            )

        # Validate the list exists and user has access
        shopping_list = self.database.find_by(
            ShoppingList, id=params.shopping_list_id
        )
        if not shopping_list or shopping_list.archived_at is not None:
            raise APIException(
                status_code=404,
                detail="Shopping list not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )

        # Check user owns or is a member of the list
        is_owner = str(shopping_list.owner_id) == str(user.id)
        is_member = False
        if not is_owner:
            membership = (
                self.db.query(ShoppingListUser)
                .filter(
                    ShoppingListUser.shopping_list_id == shopping_list.id,
                    ShoppingListUser.user_id == user.id,
                    ShoppingListUser.archived_at.is_(None),
                )
                .first()
            )
            is_member = membership is not None

        if not is_owner and not is_member:
            raise APIException(
                status_code=403,
                detail="You do not have access to this shopping list",
                code=ErrorCode.FORBIDDEN,
            )

        # Shift current default to previous
        if user.default_shopping_list_id and str(user.default_shopping_list_id) != str(params.shopping_list_id):
            user.previous_shopping_list_id = user.default_shopping_list_id

        # Set new default
        user.default_shopping_list_id = shopping_list.id
        self.db.commit()
        self.db.refresh(user)

        return success(
            data=SetDefaultShoppingList.Response(
                default_shopping_list_id=str(user.default_shopping_list_id) if user.default_shopping_list_id else None,
                previous_shopping_list_id=str(user.previous_shopping_list_id) if user.previous_shopping_list_id else None,
            )
        )

    class Params(BaseModel):
        shopping_list_id: str | None = None

    class Response(BaseModel):
        default_shopping_list_id: str | None = None
        previous_shopping_list_id: str | None = None
