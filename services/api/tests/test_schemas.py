"""Tests for Pydantic schema validation — covers 0% schema files."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest


class TestImportJobSchemas:
    """Cover schemas/import_job.py by instantiation."""

    def test_start_import_request_url(self):
        from schemas.import_job import StartImportRequest

        req = StartImportRequest(source_type="url", url="https://example.com/recipe")
        assert req.source_type == "url"
        assert req.url == "https://example.com/recipe"

    def test_start_import_request_url_list(self):
        from schemas.import_job import StartImportRequest

        req = StartImportRequest(
            source_type="url_list", urls=["https://a.com", "https://b.com"]
        )
        assert req.source_type == "url_list"
        assert len(req.urls) == 2

    def test_import_job_response(self):
        from schemas.import_job import ImportJobResponse

        resp = ImportJobResponse(
            id="job-1",
            source_type="url",
            status="processing",
            recipe_book_id="rb-1",
            total_items=5,
            processed_items=2,
            succeeded_items=1,
            failed_items=1,
            pending_review_items=0,
            total_ai_cost_cents=10,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert resp.status == "processing"
        assert resp.recipe_book_id == "rb-1"

    def test_import_item_summary(self):
        from schemas.import_job import ImportItemSummary

        item = ImportItemSummary(
            id="item-1",
            status="succeeded",
            source_type="url",
            source_url="https://example.com",
            recipe_name="Test",
            error_message=None,
            created_at=datetime.now(UTC),
        )
        assert item.status == "succeeded"

    def test_import_item_detail(self):
        from schemas.import_job import ImportItemDetail

        item = ImportItemDetail(
            id="item-1",
            import_job_id="job-1",
            status="pending_review",
            source_type="url",
            source_url="https://example.com",
            raw_data={"html": "<div>recipe</div>"},
            parsed_recipe=None,
            user_edits=None,
            error_message=None,
            error_code=None,
            retry_count=0,
            created_recipe_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert item.retry_count == 0

    def test_update_import_item_request(self):
        from schemas.import_job import UpdateImportItemRequest

        req = UpdateImportItemRequest(user_edits={"name": "Updated Name"})
        assert req.user_edits == {"name": "Updated Name"}

    def test_import_item_list_response(self):
        from schemas.import_job import ImportItemListResponse

        resp = ImportItemListResponse(items=[], total=0, has_more=False)
        assert resp.total == 0

    def test_parsed_ingredient(self):
        from schemas.import_job import ParsedIngredient

        ing = ParsedIngredient(
            text="2 cups flour",
            quantity=2.0,
            unit="cups",
            name="flour",
            is_optional=False,
        )
        assert ing.name == "flour"
        assert ing.text == "2 cups flour"

    def test_parsed_recipe(self):
        from schemas.import_job import ParsedRecipe

        recipe = ParsedRecipe(name="Test Recipe")
        assert recipe.name == "Test Recipe"
        # default_factory fields
        assert recipe.ingredients == []
        assert recipe.keywords == []


class TestMealEventSchemas:
    """Cover schemas/meal_event.py by instantiation."""

    def test_participant_input(self):
        from schemas.meal_event import ParticipantInput

        p = ParticipantInput(user_id="u1")
        assert p.user_id == "u1"
        assert p.role == "guest"  # default

    def test_participant_response(self):
        from schemas.meal_event import ParticipantResponse

        p = ParticipantResponse(
            user_id="u1",
            role="host",
            status="accepted",
            user_name="Alice",
            user_email="alice@test.com",
            assigned_tasks=[],
            created_at=datetime.now(UTC),
        )
        assert p.status == "accepted"
        assert p.created_at is not None

    def test_recipe_summary(self):
        from schemas.meal_event import RecipeSummary

        r = RecipeSummary(
            id="r1",
            name="Pasta",
            description=None,
            prep_time=10,
            cook_time=20,
            image_url=None,
        )
        assert r.prep_time == 10

    def test_meal_event_create(self):
        from schemas.meal_event import MealEventCreate

        ev = MealEventCreate(
            title="Dinner",
            scheduled_at=datetime.now(UTC),
            meal_type="dinner",
        )
        assert ev.title == "Dinner"
        assert ev.meal_type == "dinner"

    def test_meal_event_create_full(self):
        from schemas.meal_event import MealEventCreate

        ev = MealEventCreate(
            title="Sunday Brunch",
            description="Family meal",
            scheduled_at=datetime.now(UTC),
            meal_type="breakfast",
            recipe_id="r1",
            pantry_id="p1",
            notify_prep_start=True,
            prep_start_offset_minutes=30,
            notify_cook_start=True,
            cook_start_offset_minutes=10,
            is_shared=True,
            is_recurring=True,
            recurrence_rule="WEEKLY:SUN",
            recurrence_end_date=date.today(),
        )
        assert ev.is_shared is True
        assert ev.is_recurring is True

    def test_meal_event_update(self):
        from schemas.meal_event import MealEventUpdate

        ev = MealEventUpdate(title="Updated Dinner")
        assert ev.title == "Updated Dinner"

    def test_meal_event_response(self):
        from schemas.meal_event import MealEventResponse

        resp = MealEventResponse(
            id="e1",
            title="Dinner",
            description=None,
            scheduled_at=datetime.now(UTC),
            meal_type="dinner",
            status="planned",
            recipe=None,
            pantry_id=None,
            owner_id="u1",
            notify_prep_start=False,
            prep_start_offset_minutes=60,
            notify_cook_start=False,
            cook_start_offset_minutes=15,
            is_shared=False,
            is_recurring=False,
            recurrence_rule=None,
            recurrence_end_date=None,
            participants=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert resp.owner_id == "u1"
        assert resp.status == "planned"
        assert resp.is_recurring is False

    def test_meal_event_list_item(self):
        from schemas.meal_event import MealEventListItem

        item = MealEventListItem(
            id="e1",
            title="Dinner",
            description=None,
            scheduled_at=datetime.now(UTC),
            meal_type="dinner",
            status="planned",
            recipe=None,
            is_shared=False,
            is_recurring=False,
            participant_count=0,
            created_at=datetime.now(UTC),
        )
        assert item.participant_count == 0
        assert item.status == "planned"
        assert item.is_recurring is False

    def test_meal_event_list_response(self):
        from schemas.meal_event import MealEventListResponse

        resp = MealEventListResponse(items=[], total=0, limit=20, offset=0)
        assert resp.total == 0
        assert resp.limit == 20
        assert resp.offset == 0

    def test_invite_participant_request(self):
        from schemas.meal_event import InviteParticipantRequest

        req = InviteParticipantRequest(user_id="u2")
        assert req.role == "guest"  # default

    def test_respond_to_invite_request(self):
        from schemas.meal_event import RespondToInviteRequest

        req = RespondToInviteRequest(status="accepted")
        assert req.status == "accepted"


class TestShoppingListSchemas:
    """Cover schemas/shopping_list.py by instantiation."""

    def test_shopping_list_item_create(self):
        from schemas.shopping_list import ShoppingListItemCreate

        item = ShoppingListItemCreate(name="Milk", quantity=Decimal("1"), unit="gallon")
        assert item.name == "Milk"

    def test_shopping_list_item_update(self):
        from schemas.shopping_list import ShoppingListItemUpdate

        item = ShoppingListItemUpdate(is_checked=True)
        assert item.is_checked is True

    def test_shopping_list_item_response(self):
        from schemas.shopping_list import ShoppingListItemResponse

        item = ShoppingListItemResponse(
            id="i1",
            name="Eggs",
            quantity=Decimal("12"),
            unit="count",
            is_checked=False,
            checked_by_user_id=None,
            category=None,
            ingredient_id=None,
            recipe_id=None,
            already_have_quantity=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert item.name == "Eggs"

    def test_shopping_list_create(self):
        from schemas.shopping_list import ShoppingListCreate

        sl = ShoppingListCreate(name="Weekly groceries")
        assert sl.name == "Weekly groceries"

    def test_shopping_list_create_with_items(self):
        from schemas.shopping_list import ShoppingListCreate, ShoppingListItemCreate

        sl = ShoppingListCreate(
            name="Dinner prep",
            meal_event_id="e1",
            pantry_id="p1",
            items=[ShoppingListItemCreate(name="Butter", quantity=Decimal("1"), unit="stick")],
        )
        assert len(sl.items) == 1

    def test_shopping_list_update(self):
        from schemas.shopping_list import ShoppingListUpdate

        sl = ShoppingListUpdate(name="Updated list", status="in_progress")
        assert sl.status == "in_progress"

    def test_shopping_list_response(self):
        from schemas.shopping_list import ShoppingListResponse

        resp = ShoppingListResponse(
            id="sl1",
            name="Groceries",
            owner_id="u1",
            status="pending",
            meal_event_id=None,
            pantry_id=None,
            items=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert resp.status == "pending"

    def test_shopping_list_list_item(self):
        from schemas.shopping_list import ShoppingListListItem

        item = ShoppingListListItem(
            id="sl1",
            name="Groceries",
            status="pending",
            item_count=5,
            checked_count=2,
            created_at=datetime.now(UTC),
        )
        assert item.item_count == 5

    def test_shopping_list_list_response(self):
        from schemas.shopping_list import ShoppingListListResponse

        resp = ShoppingListListResponse(items=[], total=0, limit=20, offset=0)
        assert resp.total == 0
        assert resp.limit == 20
        assert resp.offset == 0

    def test_generate_shopping_list_request_rejects_check_pantry(self):
        """Post-str-ing-2: GenerateShoppingListRequest sets extra='forbid'
        so the retired `check_pantry` field now raises ValidationError."""
        from pydantic import ValidationError
        from schemas.shopping_list import GenerateShoppingListRequest

        # Empty body is valid (the request is parameter-less now).
        req = GenerateShoppingListRequest()
        assert req is not None

        with pytest.raises(ValidationError):
            GenerateShoppingListRequest(check_pantry=True)


class TestTimerSchemas:
    """Cover schemas/timer.py by instantiation."""

    def test_timer_create(self):
        from schemas.timer import TimerCreate

        t = TimerCreate(label="Boil water", duration_seconds=600)
        assert t.label == "Boil water"
        assert t.duration_seconds == 600

    def test_timer_create_with_optional(self):
        from schemas.timer import TimerCreate

        t = TimerCreate(
            label="Step 3",
            duration_seconds=300,
            meal_event_id="e1",
            recipe_step_id="s1",
            notify_on_complete=False,
        )
        assert t.notify_on_complete is False

    def test_timer_update(self):
        from schemas.timer import TimerUpdate

        t = TimerUpdate(status="paused")
        assert t.status == "paused"

    def test_timer_update_add_seconds(self):
        from schemas.timer import TimerUpdate

        t = TimerUpdate(add_seconds=60)
        assert t.add_seconds == 60

    def test_timer_response(self):
        from schemas.timer import TimerResponse

        resp = TimerResponse(
            id="t1",
            label="Timer 1",
            duration_seconds=600,
            status="running",
            started_at=datetime.now(UTC),
            paused_at=None,
            elapsed_when_paused=0,
            notify_on_complete=True,
            notification_sent=False,
            remaining_seconds=300,
            is_expired=False,
            meal_event_id=None,
            recipe_step_id=None,
            user_id="u1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert resp.remaining_seconds == 300
        assert resp.notify_on_complete is True

    def test_timer_list_response(self):
        from schemas.timer import TimerListResponse

        resp = TimerListResponse(items=[], total=0)
        assert resp.total == 0
