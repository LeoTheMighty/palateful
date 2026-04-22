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
