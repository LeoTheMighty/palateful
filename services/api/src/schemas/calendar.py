"""Calendar-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class CalendarCreateRequest(BaseModel):
    """Request schema for creating a calendar."""
    name: str
    description: str | None = None


class CalendarUpdateRequest(BaseModel):
    """Request schema for updating a calendar."""
    name: str | None = None
    description: str | None = None


class CalendarResponse(BaseModel):
    """Response schema for a calendar summary."""
    id: str
    name: str
    description: str | None = None
    is_default: bool = False
    is_shared: bool = False
    owner_id: str
    # Required — no default. A silent "owner" default would become a
    # permissions leak once sharing lands and the join legitimately
    # returns NULL for edge cases (member row archived mid-request).
    user_role: str
    member_count: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CalendarMemberResponse(BaseModel):
    """Response schema for a single calendar member."""
    user_id: str
    name: str | None = None
    role: str
    invited_by_id: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CalendarDetailResponse(CalendarResponse):
    """Detail response — calendar summary plus its members."""
    members: list[CalendarMemberResponse] = []


class CalendarListResponse(BaseModel):
    """Flat list of calendars the user is an active member of.

    No `total` field: this epic is explicit about no pagination. Adding
    one would force a breaking bump later when pagination arrives.
    """
    items: list[CalendarResponse]
