"""Organize shopping list by store sections endpoint."""

from pydantic import BaseModel

from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User

from .utils.store_sections import (
    STORE_SECTIONS,
    get_section_display_name,
    get_section_for_category,
    get_section_order,
)


class OrganizeByStore(Endpoint):
    """Organize shopping list items by store sections."""

    def execute(
        self,
        list_id: str,
        params: "OrganizeByStore.Params",
    ):
        """
        Organize shopping list items by store section for efficient shopping.

        This endpoint:
        1. Auto-assigns store sections based on item categories
        2. Sets store_order for each item based on section
        3. Returns items grouped by section

        Args:
            list_id: The shopping list's ID
            params: Organization options

        Returns:
            Items grouped by store section with updated order
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

        # Check access
        is_owner = shopping_list.owner_id == user.id
        membership = self.database.find_by(
            ShoppingListUser, shopping_list_id=list_id, user_id=user.id
        )
        can_edit = is_owner or (
            membership
            and membership.role in ("owner", "editor")
            and not membership.archived_at
        )
        if not can_edit:
            raise APIException(
                status_code=403,
                detail="You don't have permission to organize this list",
                code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
            )

        # Get unchecked items
        items = [item for item in shopping_list.items if not item.is_checked]

        # Auto-assign sections if requested
        if params.auto_assign_sections:
            for item in items:
                if not item.store_section and item.category:
                    item.store_section = get_section_for_category(item.category)

        # Set store order based on section
        for item in items:
            item.store_order = get_section_order(item.store_section)

        self.database.db.commit()

        # Group items by section
        sections_dict: dict[str, list[ShoppingListItem]] = {}
        for item in items:
            section = item.store_section or "other"
            if section not in sections_dict:
                sections_dict[section] = []
            sections_dict[section].append(item)

        # Sort sections by store order
        sorted_sections = sorted(
            sections_dict.items(),
            key=lambda x: get_section_order(x[0]),
        )

        # Build response
        sections_response = []
        for section_key, section_items in sorted_sections:
            # Sort items within section by name
            section_items.sort(key=lambda x: x.name.lower())

            sections_response.append(
                OrganizeByStore.SectionResponse(
                    section=section_key,
                    display_name=get_section_display_name(section_key),
                    order=get_section_order(section_key),
                    items=[
                        OrganizeByStore.ItemResponse(
                            id=str(item.id),
                            name=item.name,
                            quantity=float(item.quantity) if item.quantity else None,
                            unit=item.unit,
                            category=item.category,
                            store_section=item.store_section,
                            store_order=item.store_order,
                        )
                        for item in section_items
                    ],
                    item_count=len(section_items),
                )
            )

        return success(
            data=OrganizeByStore.Response(
                sections=sections_response,
                total_items=len(items),
                sections_used=len(sections_response),
            )
        )

    class Params(BaseModel):
        auto_assign_sections: bool = True

    class ItemResponse(BaseModel):
        id: str
        name: str
        quantity: float | None = None
        unit: str | None = None
        category: str | None = None
        store_section: str | None = None
        store_order: int | None = None

    class SectionResponse(BaseModel):
        section: str
        display_name: str
        order: int
        items: list["OrganizeByStore.ItemResponse"]
        item_count: int

    class Response(BaseModel):
        sections: list["OrganizeByStore.SectionResponse"]
        total_items: int
        sections_used: int


class GetStoreSections(Endpoint):
    """Get available store sections."""

    def execute(self):
        """
        Get the list of available store sections with display names.

        Returns:
            List of store sections with order
        """
        sections = [
            GetStoreSections.SectionInfo(
                key=section[0],
                display_name=section[1],
                order=section[2],
            )
            for section in STORE_SECTIONS
        ]

        return success(data=GetStoreSections.Response(sections=sections))

    class SectionInfo(BaseModel):
        key: str
        display_name: str
        order: int

    class Response(BaseModel):
        sections: list["GetStoreSections.SectionInfo"]
