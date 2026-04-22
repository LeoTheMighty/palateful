"""Unit tests for `notification_copy` — the central title/body library."""

from types import SimpleNamespace

from utils.services.notification_copy import (
    _resolve_actor_name,
    _truncate_note,
    cook_feedback_prompt,
    import_needs_review,
    meal_event_invite_accepted,
    recipe_added,
    recipe_cooked_by_partner,
    recipe_forked,
    recipe_note_added,
)


class TestImportNeedsReview:
    def test_single_with_recipe_name(self):
        title, body = import_needs_review(
            recipe_name="Sweet Potato Quiche", count=1
        )
        assert "Sweet Potato Quiche" in title
        assert "ready" in title.lower()
        assert "🍳" in title
        assert body == "Tap to confirm the details we extracted."

    def test_single_with_no_recipe_name(self):
        title, body = import_needs_review(recipe_name=None, count=1)
        assert title == "Your recipe is ready to review"
        assert body == "Tap to confirm the details we extracted."

    def test_single_with_empty_string_name_falls_back(self):
        title, _ = import_needs_review(recipe_name="", count=1)
        # Empty string is falsy → uses fallback.
        assert title == "Your recipe is ready to review"

    def test_bulk_uses_count_only(self):
        title, body = import_needs_review(recipe_name="Ignored", count=5)
        assert title == "Your bulk import is ready"
        assert body == "5 recipes need a quick review."

    def test_bulk_default_count_is_1_so_singular(self):
        title, _ = import_needs_review(recipe_name=None)
        # default count=1 → singular variant
        assert title == "Your recipe is ready to review"


class TestRecipeAdded:
    def test_basic(self):
        title, body = recipe_added(
            actor_name="Sarah",
            recipe_name="Banana Bread",
            book_name="Weeknight Dinners",
        )
        assert "Weeknight Dinners" in title
        assert "🍳" in title
        assert body == "Sarah added Banana Bread"

    def test_unicode_in_recipe_name(self):
        title, body = recipe_added(
            actor_name="Léa",
            recipe_name="Crêpes",
            book_name="Brunch 🥞",
        )
        assert "Brunch 🥞" in title
        assert body == "Léa added Crêpes"


class TestResolveActorName:
    def test_uses_first_word_of_name(self):
        actor = SimpleNamespace(name="Sarah Smith", username="sm", email="s@x.com")
        assert _resolve_actor_name(actor) == "Sarah"

    def test_falls_back_to_username_when_name_blank(self):
        actor = SimpleNamespace(name="   ", username="sarahsmith", email="s@x.com")
        assert _resolve_actor_name(actor) == "sarahsmith"

    def test_falls_back_to_email_local_when_no_name_or_username(self):
        actor = SimpleNamespace(name=None, username=None, email="sarah@example.com")
        assert _resolve_actor_name(actor) == "sarah"

    def test_falls_back_to_someone_when_everything_missing(self):
        actor = SimpleNamespace(name=None, username=None, email=None)
        assert _resolve_actor_name(actor) == "Someone"

    def test_someone_when_actor_has_no_attrs(self):
        assert _resolve_actor_name(object()) == "Someone"

    def test_empty_email_local_falls_through(self):
        # Edge case: "@example.com" → local part is empty → skip to "Someone".
        actor = SimpleNamespace(name=None, username=None, email="@example.com")
        assert _resolve_actor_name(actor) == "Someone"


class TestTruncateNote:
    def test_short_note_unchanged(self):
        assert _truncate_note("hello") == "hello"

    def test_long_note_gets_ellipsis_and_fits_limit(self):
        note = "x" * 200
        truncated = _truncate_note(note, limit=120)
        assert len(truncated) == 120
        assert truncated.endswith("…")


class TestRecipeForked:
    def test_basic(self):
        title, body = recipe_forked(
            actor_name="Sarah",
            recipe_name="Sweet Potato Quiche",
            target_book_name="Sarah's Recipes",
        )
        assert "🔱" in title
        assert "Sarah forked your Sweet Potato Quiche" in title
        assert body == "They saved it to Sarah's Recipes."


class TestRecipeNoteAdded:
    def test_short_snippet_preserved(self):
        title, body = recipe_note_added(
            actor_name="Sarah",
            recipe_name="Sweet Potato Quiche",
            note_snippet="Add more cinnamon next time.",
        )
        assert "Sarah noted your Sweet Potato Quiche" in title
        assert "📝" in title
        assert body == 'Sarah: "Add more cinnamon next time."'

    def test_long_snippet_truncated_to_120_chars(self):
        long_note = "x" * 200
        _, body = recipe_note_added(
            actor_name="Sarah",
            recipe_name="Quiche",
            note_snippet=long_note,
        )
        # Body wraps the snippet in Sarah: "<snippet>" — the snippet piece
        # must be <=120 chars and end with an ellipsis.
        assert 'Sarah: "' in body
        start = body.index('"') + 1
        end = body.rindex('"')
        inner = body[start:end]
        assert len(inner) == 120
        assert inner.endswith("…")


class TestRecipeCookedByPartner:
    def test_basic(self):
        title, body = recipe_cooked_by_partner(
            actor_name="Sarah",
            recipe_name="Sweet Potato Quiche",
        )
        assert title == "🍳 Sarah cooked your Sweet Potato Quiche!"
        assert body == "Tap to see how it went."


class TestMealEventInviteAccepted:
    def test_accepted(self):
        title, body = meal_event_invite_accepted(
            actor_name="Sarah",
            event_title="Saturday brunch",
            status="accepted",
        )
        assert "🥞" in title
        assert "Sarah's coming to Saturday brunch" in title
        assert body == "They just RSVP'd yes."

    def test_declined(self):
        title, body = meal_event_invite_accepted(
            actor_name="Sarah",
            event_title="Saturday brunch",
            status="declined",
        )
        assert title == "Sarah can't make Saturday brunch"
        assert body == "Tap to swap recipes if needed."

    def test_maybe(self):
        title, body = meal_event_invite_accepted(
            actor_name="Sarah",
            event_title="Saturday brunch",
            status="maybe",
        )
        assert title == "Sarah might join Saturday brunch"
        assert body == "They marked themselves as a maybe."

    def test_unknown_status_treated_as_accepted(self):
        title, _ = meal_event_invite_accepted(
            actor_name="Sarah",
            event_title="Saturday brunch",
            status="tentative",
        )
        # Defensive default: future statuses route to the "yes" copy rather
        # than crashing — the inviter still gets a clear signal.
        assert "Sarah's coming to" in title


class TestCookFeedbackPrompt:
    def test_basic(self):
        title, body = cook_feedback_prompt(recipe_name="Sweet Potato Quiche")
        assert title == "How did your Sweet Potato Quiche turn out? 🍴"
        assert body == "Tap to add a quick rating + note."
