"""Centralized title/body copy for every push notification we send.

One function per `(NotificationType, variant)` pair. Each returns a
`(title, body)` tuple. Callsites pass data, get strings — never invent
inline copy. This keeps tone consistent and makes copy changes a
single-file diff.

Variants are encoded as keyword arguments; defaults are explicit.
Emoji palette is intentionally light: title-only, when it adds clarity
or warmth. Bodies stay plain text so they read clean on devices that
strip emoji.

When extending this module for new notification types (Epics B/C/D/E),
follow the existing shape: pure function, narrow keyword args, returns
the tuple. No state, no logging, no DB access.
"""

from __future__ import annotations

# Emoji palette — pick from this list so we don't drift across functions.
# Add sparingly; prefer no emoji over a stretched metaphor.
EMOJI_RECIPE = "🍳"
EMOJI_BOOK = "📖"
EMOJI_MEAL = "🍽️"
EMOJI_FORK = "🔱"
EMOJI_NOTE = "📝"
EMOJI_RSVP = "🥞"
EMOJI_FEEDBACK = "🍴"
EMOJI_CART = "🛒"
EMOJI_ERROR = "🛑"

# Longest hostname/source label rendered in a push title before we
# truncate to avoid iOS / Android banner clipping. 30 keeps the title
# under the typical clip boundary with the emoji + "Couldn't import
# from" prefix.
_SOURCE_LABEL_MAX = 30

# Max body length for partner-note snippets. Longer notes are truncated with
# a trailing ellipsis. 120 chars keeps the body under iOS banner limits
# while leaving room for the actor-name prefix.
_NOTE_SNIPPET_MAX = 120


def _resolve_actor_name(actor: object) -> str:
    """Best-effort first-name-ish label for a notification actor.

    Fallback chain (locked by epic-notifications-partner-activity):
        actor.name (first word) → actor.username → actor.email local part → "Someone".

    The User model doesn't have a first_name column; `name` is the closest
    proxy, so we slice off the first whitespace-separated word to approximate.
    Attributes are read defensively so this works for mocks / test doubles
    that only set a subset of the User fields.
    """
    name = getattr(actor, "name", None)
    if isinstance(name, str) and name.strip():
        first = name.strip().split()[0]
        if first:
            return first
    username = getattr(actor, "username", None)
    if isinstance(username, str) and username.strip():
        return username.strip()
    email = getattr(actor, "email", None)
    if isinstance(email, str) and "@" in email:
        local = email.split("@", 1)[0].strip()
        if local:
            return local
    return "Someone"


def _truncate_note(note: str, limit: int = _NOTE_SNIPPET_MAX) -> str:
    """Truncate a note snippet with an ellipsis when it exceeds `limit`."""
    if len(note) <= limit:
        return note
    # Reserve one char for the ellipsis so the visible body stays ≤ limit.
    return note[: limit - 1].rstrip() + "…"


def import_needs_review(
    *,
    recipe_name: str | None = None,
    count: int = 1,
) -> tuple[str, str]:
    """Push copy for `IMPORT_NEEDS_REVIEW`.

    Variants:
    - Single recipe with a name → "Your {recipe_name} is ready 🍳"
    - Single recipe without a name → generic "Your recipe is ready to review"
    - Bulk (count > 1) → count-aware variant; recipe_name ignored
    """
    if count > 1:
        return (
            "Your bulk import is ready",
            f"{count} recipes need a quick review.",
        )
    if recipe_name:
        return (
            f"Your {recipe_name} is ready {EMOJI_RECIPE}",
            "Tap to confirm the details we extracted.",
        )
    return (
        "Your recipe is ready to review",
        "Tap to confirm the details we extracted.",
    )


def recipe_added(
    *,
    actor_name: str,
    recipe_name: str,
    book_name: str,
) -> tuple[str, str]:
    """Push copy for `RECIPE_ADDED` (partner added a recipe to a shared book)."""
    return (
        f"{EMOJI_RECIPE} New in {book_name}",
        f"{actor_name} added {recipe_name}",
    )


def recipe_forked(
    *,
    actor_name: str,
    recipe_name: str,
    target_book_name: str,
) -> tuple[str, str]:
    """Push copy for `RECIPE_FORKED` (partner forked your recipe)."""
    return (
        f"{EMOJI_FORK} {actor_name} forked your {recipe_name}",
        f"They saved it to {target_book_name}.",
    )


def recipe_note_added(
    *,
    actor_name: str,
    recipe_name: str,
    note_snippet: str,
) -> tuple[str, str]:
    """Push copy for `RECIPE_NOTE_ADDED` (partner added a note to your recipe).

    The `note_snippet` is truncated to the module's standard 120-char
    limit; the recipe owner always has full-read access to the note on
    tap-through, so showing a snippet in the body is safe.
    """
    snippet = _truncate_note(note_snippet)
    return (
        f"{actor_name} noted your {recipe_name} {EMOJI_NOTE}",
        f'{actor_name}: "{snippet}"',
    )


def recipe_cooked_by_partner(
    *,
    actor_name: str,
    recipe_name: str,
) -> tuple[str, str]:
    """Push copy for `RECIPE_COOKED_BY_PARTNER` (partner cooked your recipe)."""
    return (
        f"{EMOJI_RECIPE} {actor_name} cooked your {recipe_name}!",
        "Tap to see how it went.",
    )


def meal_event_invite_accepted(
    *,
    actor_name: str,
    event_title: str,
    status: str,
) -> tuple[str, str]:
    """Push copy for `MEAL_EVENT_INVITE_ACCEPTED` (invitee responded).

    Branches on participant `status`:
        - "accepted" → RSVP-yes copy.
        - "declined" → RSVP-no copy.
        - "maybe"    → RSVP-maybe copy.

    An unknown status is treated as "accepted" so we never crash on a new
    status value the server starts accepting in the future.
    """
    normalized = (status or "").strip().lower()
    if normalized == "declined":
        return (
            f"{actor_name} can't make {event_title}",
            "Tap to swap recipes if needed.",
        )
    if normalized == "maybe":
        return (
            f"{actor_name} might join {event_title}",
            "They marked themselves as a maybe.",
        )
    return (
        f"{EMOJI_RSVP} {actor_name}'s coming to {event_title}!",
        "They just RSVP'd yes.",
    )


def cook_feedback_prompt(
    *,
    recipe_name: str,
) -> tuple[str, str]:
    """Push copy for `COOK_FEEDBACK_PROMPT` (2h post-cook nudge to the cooker)."""
    return (
        f"How did your {recipe_name} turn out? {EMOJI_FEEDBACK}",
        "Tap to add a quick rating + note.",
    )


def shopping_deadline_reminder(
    *,
    list_name: str,
    item_count: int,
) -> tuple[str, str]:
    """Push copy for `SHOPPING_DEADLINE_REMINDER` (morning-of summary).

    Singular / plural split on `item_count`. The body is intentionally
    generic ("Tap to see what's left") rather than naming items — the
    shopping list view covers per-item detail on tap-through.
    """
    if item_count == 1:
        title = f"{EMOJI_CART} 1 item on {list_name} is due today"
    else:
        title = f"{EMOJI_CART} {item_count} items on {list_name} are due today"
    return (title, "Tap to see what's left.")


def _truncate_source_label(label: str, limit: int = _SOURCE_LABEL_MAX) -> str:
    """Trim a source label (hostname / filename) for inline title use."""
    if len(label) <= limit:
        return label
    return label[: limit - 1].rstrip() + "…"


def import_failed(
    *,
    source_label: str,
    count: int = 1,
) -> tuple[str, str]:
    """Push copy for `IMPORT_FAILED` (terminal full-job-failure).

    - Single (count == 1) → names the source in the title.
    - Bulk (count > 1) → count-aware, generic title; source_label
      ignored (too much to cram into the banner).
    """
    if count > 1:
        return (
            f"{EMOJI_ERROR} Bulk import failed",
            f"We couldn't extract any of the {count} recipes. Tap to retry.",
        )
    trimmed = _truncate_source_label(source_label)
    return (
        f"{EMOJI_ERROR} Couldn't import from {trimmed}",
        "We couldn't extract a recipe. Tap to retry.",
    )


# Per-slot display label + emoji for meal-event reminders. Keep aligned
# with MealEvent.meal_type / Flutter MealType enum. `snack` gets its
# own emoji per the meal-3 epic spec; the others share the cooking pan.
_MEAL_SLOT_LABELS: dict[str, str] = {
    "breakfast": "Breakfast",
    "lunch": "Lunch",
    "dinner": "Dinner",
    "snack": "Snack",
}
_MEAL_SLOT_EMOJI: dict[str, str] = {
    "breakfast": EMOJI_RECIPE,
    "lunch": EMOJI_RECIPE,
    "dinner": EMOJI_RECIPE,
    "snack": "🥨",
}


def meal_event_reminder(
    *,
    meal_type: str,
    recipe_name: str | None = None,
    minutes_until: int = 0,
    is_shared: bool = False,
    partner_name: str | None = None,
) -> tuple[str, str]:
    """Push copy for `MEAL_EVENT_REMINDER` fired by the beat scheduler.

    `minutes_until` is the delta from the resolved reminder-time to the
    meal's `scheduled_at`, computed by the task. ≤0 means "now" — the
    title drops the "in Nmin" suffix.

    Variants:
    - Solo + recipe: "Lunch in 5 — Carbonara 🍳" + "Tap to open and
      start prepping."
    - Solo, no recipe: "Lunch time! 🍳" + "Tap to open the meal you
      planned."
    - Shared + partner_name: body becomes
      "{partner_name} is also cooking — tap to coordinate."
    - `snack` → emoji flips to 🥨.
    """
    slot_label = _MEAL_SLOT_LABELS.get(meal_type, "Meal")
    emoji = _MEAL_SLOT_EMOJI.get(meal_type, EMOJI_RECIPE)

    if recipe_name:
        if minutes_until >= 1:
            title = f"{slot_label} in {minutes_until} — {recipe_name} {emoji}"
        else:
            title = f"{slot_label} now — {recipe_name} {emoji}"
    else:
        title = f"{slot_label} time! {emoji}"

    if is_shared and partner_name:
        body = f"{partner_name} is also cooking — tap to coordinate."
    elif recipe_name:
        body = "Tap to open and start prepping."
    else:
        body = "Tap to open the meal you planned."

    return (title, body)


def meal_event_updated(
    *,
    actor_name: str,
    event_title: str,
    scheduled_at_changed: bool = False,
    new_time: str | None = None,
) -> tuple[str, str]:
    """Push copy for `MEAL_EVENT_UPDATED` (shared-meal edits fan-out).

    Two variants:
    - Only `scheduled_at` changed (with a formatted `new_time`) →
      "{event_title} moved to {new_time}" + "{actor_name} updated
      '{event_title}'".
    - Anything else → "{event_title} updated" + "{actor_name} made
      changes to '{event_title}'".

    Empty `actor_name` / `event_title` fall back to "Someone" / "Meal
    event" to match the long-standing update-stub shape.
    """
    actor = actor_name or "Someone"
    title_text = event_title or "Meal event"

    if scheduled_at_changed and new_time:
        return (
            f"{title_text} moved to {new_time}",
            f"{actor} updated '{title_text}'",
        )

    return (
        f"{title_text} updated",
        f"{actor} made changes to '{title_text}'",
    )
