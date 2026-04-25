"""Duplicate-detection helper for import items.

Story `import-dup-1` of `epic-import-duplicate-detection`. Finds existing
recipes in the user's library that match a parsed-but-not-yet-imported
recipe, by exact title or by source URL. The Approve-Import GET endpoint
embeds the result so the Flutter screen can render the
"you already have this" banner before the user taps Approve.

Match scope is intentionally tight in v1:
  - **title**: case-insensitive, trim-normalised exact match on
    `recipes.name`. Backed by ``ix_recipes_book_lower_name`` so the
    query is an index seek across the user's books, not a table scan.
  - **source_url**: exact equality on `recipes.source_url`, both
    non-null. Catches the "I already imported this URL six months ago"
    case even when the title was edited later.

The user's library = every `recipe_book` they have membership in
(``recipe_book_users.user_id = :me``). The helper does not enforce role
— a viewer-on-shared-book recipe is still a duplicate from the user's
perspective.

Returns 0+ ``DuplicateMatch`` dicts, each with enough fields for the
banner: recipe id, name, current book id+name, archived_at, last_cooked
(MAX of `cooking_logs.cooked_at` for the recipe), and `match_kind`
(``"title"`` or ``"source_url"``). The same recipe can match on both
keys — we de-dupe on recipe id and prefer ``"title"`` (the more
intentional "I named this the same thing" match).
"""

from datetime import datetime
from typing import TypedDict

from sqlalchemy import func, or_, select
from utils.models.cooking_log import CookingLog
from utils.models.recipe import Recipe
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser


class DuplicateMatch(TypedDict):
    recipe_id: str
    title: str
    current_book_id: str
    current_book_name: str
    archived_at: datetime | None
    last_cooked: datetime | None
    match_kind: str  # "title" | "source_url"


def _normalised_title(raw: str | None) -> str | None:
    """Return the lower-cased, stripped title or None for empty input.

    Mirrors the SQL `lower(trim(name))` predicate so caller-side
    short-circuiting matches the index. An empty / whitespace-only
    title produces no matches (no point hammering the DB).
    """
    if not raw:
        return None
    cleaned = raw.strip().lower()
    return cleaned or None


async def find_duplicate_recipes(
    database,
    user_id: str,
    parsed_title: str | None,
    parsed_source_url: str | None,
) -> list[DuplicateMatch]:
    """Find existing recipes in the user's library that match either key.

    Args:
        database: AsyncDatabase instance (the endpoint's `self.database`).
        user_id: The calling user's UUID (string form).
        parsed_title: Title from the import item's parsed_recipe (or
            user_edits if the user already edited the form). May be None
            or whitespace-only — both short-circuit to no title match.
        parsed_source_url: URL from the import item. May be None — both
            sides of the match must be non-null for URL matching.

    Returns:
        List of `DuplicateMatch` dicts, sorted by `archived_at IS NULL`
        first (active matches above archived ones), then by the recipe's
        most recent activity (last_cooked desc, then created_at desc).
        Empty list when no match.
    """
    norm_title = _normalised_title(parsed_title)
    norm_url = parsed_source_url.strip() if parsed_source_url else None
    if not norm_title and not norm_url:
        return []

    # Books the user can see — duplicate scope = the user's library.
    memberships = await database.where(
        RecipeBookUser, user_id=user_id
    ).all()
    book_ids = [m.recipe_book_id for m in memberships]
    if not book_ids:
        return []

    # Predicate: title match OR source_url match. Both already
    # short-circuit when their input is None (so a URL-only import
    # without a title still works, and vice-versa).
    or_clauses = []
    if norm_title:
        or_clauses.append(func.lower(func.trim(Recipe.name)) == norm_title)
    if norm_url:
        or_clauses.append(
            (Recipe.source_url.isnot(None)) & (Recipe.source_url == norm_url)
        )

    # Last-cooked subquery: MAX(cooked_at) per recipe. Soft dep on the
    # recipe-list-organization helper — we ship our own thin version
    # rather than cross-importing across epic boundaries.
    last_cooked_sq = (
        select(
            CookingLog.recipe_id.label("recipe_id"),
            func.max(CookingLog.cooked_at).label("last_cooked"),
        )
        .where(CookingLog.recipe_id.isnot(None))
        .group_by(CookingLog.recipe_id)
        .subquery()
    )

    stmt = (
        select(
            Recipe.id,
            Recipe.name,
            Recipe.source_url,
            Recipe.recipe_book_id,
            Recipe.archived_at,
            RecipeBook.name.label("book_name"),
            last_cooked_sq.c.last_cooked,
        )
        .join(RecipeBook, RecipeBook.id == Recipe.recipe_book_id)
        .outerjoin(
            last_cooked_sq, last_cooked_sq.c.recipe_id == Recipe.id
        )
        .where(
            Recipe.recipe_book_id.in_(book_ids),
            or_(*or_clauses),
        )
    )

    result = await database.db.execute(stmt)
    rows = list(result.all())

    matches: list[DuplicateMatch] = []
    for row in rows:
        # Determine match_kind. A recipe can match both title and URL;
        # title wins because it's the more intentional "same name"
        # judgment. URL-only matches surface the "I already imported
        # this internet recipe" case where the title may have drifted.
        kind = "title" if (
            norm_title
            and row.name
            and row.name.strip().lower() == norm_title
        ) else "source_url"
        matches.append({
            "recipe_id": str(row.id),
            "title": row.name,
            "current_book_id": str(row.recipe_book_id),
            "current_book_name": row.book_name,
            "archived_at": row.archived_at,
            "last_cooked": row.last_cooked,
            "match_kind": kind,
        })

    # Stable sort: active matches first (so the banner picks an active
    # one when both exist for the same title), then by most recent
    # activity. Python's sort is stable so the multi-key composition
    # works as written.
    matches.sort(
        key=lambda m: (
            m["archived_at"] is not None,  # False (active) sorts first
            -(m["last_cooked"].timestamp() if m["last_cooked"] else 0),
        )
    )
    return matches
