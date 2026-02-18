# Search Feature — Design Document

## Overview

Unified search across recipes and users, with results prioritized by relevance to the current user:

1. **Your recipes** (from recipe books you own or are a member of)
2. **Public recipes** (from public recipe books you don't have access to)
3. **Users** (friends first, then all other users)

Search is a single endpoint that returns all three categories in one response, letting the frontend render them in priority sections.

---

## API

### `GET /v1/search?q=<query>&limit=20`

Single unified search endpoint. The backend handles all prioritization logic.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | required | Search query (min 2 chars) |
| `limit` | int | 20 | Max results per category |

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "chicken",
    "my_recipes": [
      {
        "id": "uuid",
        "name": "Lemon Garlic Chicken",
        "image_url": "https://...",
        "meal_type": "dinner",
        "prep_time": 15,
        "cook_time": 30,
        "tags": ["easy", "weeknight"],
        "recipe_book_id": "uuid",
        "recipe_book_name": "Family Favorites",
        "ingredients": [
          { "canonical_name": "chicken breast" },
          { "canonical_name": "lemon" },
          { "canonical_name": "garlic" }
        ]
      }
    ],
    "public_recipes": [
      {
        "id": "uuid",
        "name": "Thai Chicken Curry",
        "image_url": "https://...",
        "meal_type": "dinner",
        "prep_time": 20,
        "cook_time": 25,
        "tags": ["thai", "spicy"],
        "recipe_book_id": "uuid",
        "recipe_book_name": "Asian Dishes",
        "owner": {
          "id": "uuid",
          "username": "chef_maya",
          "picture": "https://..."
        }
      }
    ],
    "users": [
      {
        "id": "uuid",
        "username": "chicken_lover42",
        "name": "Chris Chen",
        "picture": "https://...",
        "friendship_status": "friends"
      }
    ]
  }
}
```

### Backend Query Strategy

All three queries run concurrently (asyncio.gather) for a single fast response.

#### 1. My Recipes

```sql
SELECT r.*, rb.name AS recipe_book_name
FROM recipes r
JOIN recipe_books rb ON r.recipe_book_id = rb.id
JOIN recipe_book_users rbu ON rb.id = rbu.recipe_book_id
WHERE rbu.user_id = :current_user_id
  AND (
    r.name ILIKE '%' || :query || '%'
    OR r.description ILIKE '%' || :query || '%'
    OR EXISTS (
      SELECT 1 FROM recipe_ingredients ri
      JOIN ingredients i ON ri.ingredient_id = i.id
      WHERE ri.recipe_id = r.id
        AND i.canonical_name ILIKE '%' || :query || '%'
    )
    OR :query = ANY(r.tags)
  )
ORDER BY
  -- Exact name match first
  (r.name ILIKE :query) DESC,
  -- Name starts with query
  (r.name ILIKE :query || '%') DESC,
  -- Name contains query
  (r.name ILIKE '%' || :query || '%') DESC,
  r.updated_at DESC
LIMIT :limit;
```

Searches across recipe name, description, ingredient names, and tags. Prioritizes exact and prefix name matches.

#### 2. Public Recipes

```sql
SELECT r.*, rb.name AS recipe_book_name,
       u.id AS owner_id, u.username AS owner_username, u.picture AS owner_picture
FROM recipes r
JOIN recipe_books rb ON r.recipe_book_id = rb.id
JOIN recipe_book_users rbu ON rb.id = rbu.recipe_book_id AND rbu.role = 'owner'
JOIN users u ON rbu.user_id = u.id
WHERE rb.is_public = true
  AND rb.id NOT IN (
    SELECT recipe_book_id FROM recipe_book_users WHERE user_id = :current_user_id
  )
  AND (
    r.name ILIKE '%' || :query || '%'
    OR r.description ILIKE '%' || :query || '%'
    OR EXISTS (
      SELECT 1 FROM recipe_ingredients ri
      JOIN ingredients i ON ri.ingredient_id = i.id
      WHERE ri.recipe_id = r.id
        AND i.canonical_name ILIKE '%' || :query || '%'
    )
    OR :query = ANY(r.tags)
  )
ORDER BY
  (r.name ILIKE :query) DESC,
  (r.name ILIKE :query || '%') DESC,
  (r.name ILIKE '%' || :query || '%') DESC,
  r.updated_at DESC
LIMIT :limit;
```

Same search logic but scoped to public recipe books the user doesn't already have access to. Includes owner info so the frontend can show who the recipe belongs to.

#### 3. Users

Reuses the existing search_users logic with friends surfaced first:

```sql
SELECT u.id, u.username, u.name, u.picture,
  CASE
    WHEN f.friend_id IS NOT NULL THEN 'friends'
    WHEN fr_sent.id IS NOT NULL THEN 'request_sent'
    WHEN fr_recv.id IS NOT NULL THEN 'request_received'
    ELSE 'none'
  END AS friendship_status
FROM users u
LEFT JOIN friendships f ON f.user_id = :current_user_id AND f.friend_id = u.id
LEFT JOIN friend_requests fr_sent ON fr_sent.from_user_id = :current_user_id
  AND fr_sent.to_user_id = u.id AND fr_sent.status = 'pending'
LEFT JOIN friend_requests fr_recv ON fr_recv.from_user_id = u.id
  AND fr_recv.to_user_id = :current_user_id AND fr_recv.status = 'pending'
WHERE u.id != :current_user_id
  AND u.username IS NOT NULL
  AND (
    u.username ILIKE '%' || :query || '%'
    OR u.name ILIKE '%' || :query || '%'
  )
ORDER BY
  -- Friends first
  (f.friend_id IS NOT NULL) DESC,
  -- Then exact username match
  (u.username = :query) DESC,
  -- Then prefix match
  (u.username ILIKE :query || '%') DESC,
  u.username
LIMIT :limit;
```

---

## API Implementation

### File Structure

```
services/api/src/
├── routers/v1/
│   └── search_router.py          # Route definition
├── api/v1/search/
│   └── unified_search.py         # Search logic
└── schemas/
    └── search.py                 # Pydantic response models
```

### Router

```python
# search_router.py
router = APIRouter(prefix="/search", tags=["search"])

@router.get("")
async def search(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=50),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await UnifiedSearch(db, user).execute(q, limit)
```

Wire into `v1_router.py` alongside the other routers.

---

## Frontend

### Search Screen

New screen at route `/search`. Opened by tapping the existing "Search recipes..." bar on the home screen.

#### Layout

```
┌──────────────────────────────┐
│  ← Search                    │
│  ┌──────────────────────────┐│
│  │ 🔍  Search recipes...    ││  ← autofocused TextField
│  └──────────────────────────┘│
│                              │
│  MY RECIPES                  │  ← section header
│  ┌──────────────────────────┐│
│  │ 🍋 Lemon Garlic Chicken  ││  ← RecipeCard-style tiles
│  │   Family Favorites · 45m ││
│  ├──────────────────────────┤│
│  │ 🍗 Chicken Parmesan      ││
│  │   Weeknight Meals · 1h   ││
│  └──────────────────────────┘│
│                              │
│  PUBLIC RECIPES              │  ← section header
│  ┌──────────────────────────┐│
│  │ 🍛 Thai Chicken Curry    ││
│  │   by @chef_maya · 45m    ││  ← shows owner
│  └──────────────────────────┘│
│                              │
│  PEOPLE                      │  ← section header
│  ┌──────────────────────────┐│
│  │ 👤 chicken_lover42       ││
│  │   Chris Chen · Friends   ││  ← shows friendship status
│  └──────────────────────────┘│
└──────────────────────────────┘
```

#### Behavior

- **Autofocus** the search TextField on screen open
- **Debounce** input by 300ms before hitting the API
- Show a **loading shimmer** while waiting for results
- **Empty sections are hidden** — if no public recipes match, that section doesn't render
- **Empty state** before typing: show recent searches (stored locally) or nothing
- **No results state**: "No results for [query]"
- Tapping a recipe navigates to `/recipes/:id`
- Tapping a user navigates to their profile (or friend request flow)

### File Structure

```
app/lib/features/search/
└── search_screen.dart
```

### API Client Addition

```dart
// In api_client.dart
Future<Response> search(String query, {int limit = 20}) async {
  return _dio.get('/v1/search', queryParameters: {
    'q': query,
    'limit': limit,
  });
}
```

### Route Addition

```dart
// In app_router.dart
GoRoute(
  path: '/search',
  builder: (context, state) => const SearchScreen(),
),
```

### Home Screen Change

Replace the current TODO snackbar on the search bar tap with:

```dart
onTap: () => context.push('/search'),
```

Using `push` (not `go`) so the home screen stays on the navigation stack and the user can swipe/tap back.

---

## Future Enhancements (not in this iteration)

These are noted for awareness but **not built now**:

- **Semantic vector search** — use the existing pgvector embeddings on recipes/ingredients for "find me something like pasta with a creamy sauce" queries. Would add an optional `?semantic=true` param.
- **Search by ingredient list** — "what can I make with chicken, rice, and broccoli" using pantry matching logic.
- **Trending/popular recipes** — a "discover" section showing popular public recipes before the user types anything.
- **Search history** — persist recent searches server-side for cross-device sync.
- **Filters on search results** — meal type, max cook time, dietary tags within search results.
