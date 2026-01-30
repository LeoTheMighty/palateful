"""MealEvent-related Pydantic schemas."""

from datetime import date, datetime

from pydantic import BaseModel


class ParticipantInput(BaseModel):
    """Input for adding a participant to a meal event."""

    user_id: str
    role: str = "guest"  # host | cohost | guest
    assigned_tasks: list[str] = []


class ParticipantResponse(BaseModel):
    """Response for a meal event participant."""

    user_id: str
    user_email: str | None = None
    user_name: str | None = None
    status: str  # invited | accepted | declined | maybe
    role: str  # host | cohost | guest
    assigned_tasks: list[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class RecipeSummary(BaseModel):
    """Summary of recipe for display in meal events."""

    id: str
    name: str
    description: str | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    image_url: str | None = None

    class Config:
        from_attributes = True


class MealEventCreate(BaseModel):
    """Request schema for creating a meal event."""

    title: str
    description: str | None = None
    scheduled_at: datetime
    meal_type: str  # breakfast | lunch | dinner | snack
    recipe_id: str | None = None
    pantry_id: str | None = None

    # Notification preferences
    notify_prep_start: bool = True
    prep_start_offset_minutes: int = 60
    notify_cook_start: bool = True
    cook_start_offset_minutes: int = 30

    # Sharing
    is_shared: bool = False

    # Recurring settings
    is_recurring: bool = False
    recurrence_rule: str | None = None  # e.g., "WEEKLY:SUN,TUE"
    recurrence_end_date: date | None = None


class MealEventUpdate(BaseModel):
    """Request schema for updating a meal event."""

    title: str | None = None
    description: str | None = None
    scheduled_at: datetime | None = None
    meal_type: str | None = None
    status: str | None = None  # planned | shopping | prepping | cooking | completed | skipped
    recipe_id: str | None = None
    pantry_id: str | None = None

    # Notification preferences
    notify_prep_start: bool | None = None
    prep_start_offset_minutes: int | None = None
    notify_cook_start: bool | None = None
    cook_start_offset_minutes: int | None = None

    # Sharing
    is_shared: bool | None = None

    # Recurring settings
    is_recurring: bool | None = None
    recurrence_rule: str | None = None
    recurrence_end_date: date | None = None


class MealEventResponse(BaseModel):
    """Response schema for a meal event with full details."""

    id: str
    title: str
    description: str | None = None
    scheduled_at: datetime
    meal_type: str
    status: str

    # Notification preferences
    notify_prep_start: bool
    prep_start_offset_minutes: int
    notify_cook_start: bool
    cook_start_offset_minutes: int

    # Sharing
    is_shared: bool

    # Recurring settings
    is_recurring: bool
    recurrence_rule: str | None = None
    recurrence_end_date: date | None = None
    parent_event_id: str | None = None

    # Related entities
    recipe: RecipeSummary | None = None
    pantry_id: str | None = None
    owner_id: str
    participants: list[ParticipantResponse] = []

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MealEventListItem(BaseModel):
    """Summary schema for a meal event in a list."""

    id: str
    title: str
    description: str | None = None
    scheduled_at: datetime
    meal_type: str
    status: str
    is_shared: bool
    is_recurring: bool
    recipe: RecipeSummary | None = None
    participant_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class MealEventListResponse(BaseModel):
    """Response schema for a paginated list of meal events."""

    items: list[MealEventListItem]
    total: int
    limit: int
    offset: int


class InviteParticipantRequest(BaseModel):
    """Request to invite a participant to a meal event."""

    user_id: str | None = None
    email: str | None = None
    role: str = "guest"  # host | cohost | guest
    message: str | None = None


class RespondToInviteRequest(BaseModel):
    """Request to respond to a meal event invitation."""

    status: str  # accepted | declined | maybe
