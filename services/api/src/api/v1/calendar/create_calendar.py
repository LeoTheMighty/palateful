"""Create calendar endpoint."""

from datetime import UTC, datetime

from pydantic import BaseModel
from schemas.calendar import CalendarResponse
from utils.api.endpoint import Endpoint, success
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.user import User


class CreateCalendar(Endpoint):
    """Create a new calendar owned by the authenticated user."""

    def execute(self, params: "CreateCalendar.Params"):
        user: User = self.user

        calendar = Calendar(
            name=params.name,
            description=params.description,
            owner_id=user.id,
            is_default=False,
            is_shared=False,
        )
        self.database.create(calendar)
        self.database.db.refresh(calendar)

        membership = CalendarUser(
            user_id=user.id,
            calendar_id=calendar.id,
            role="owner",
            last_opened_at=datetime.now(UTC),
        )
        self.database.create(membership)
        self.database.db.refresh(membership)

        return success(
            data=CalendarResponse(
                id=str(calendar.id),
                name=calendar.name,
                description=calendar.description,
                is_default=calendar.is_default,
                is_shared=calendar.is_shared,
                owner_id=str(calendar.owner_id),
                user_role="owner",
                member_count=1,
                created_at=calendar.created_at,
                updated_at=calendar.updated_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        name: str
        description: str | None = None

    class Response(CalendarResponse):
        pass
