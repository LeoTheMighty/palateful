# Story 5.3: Search Filters

Status: ready-for-dev

## Story

As a user,
I want to filter search results by recipe book, tags, prep time, and cook time,
So that I can narrow down results when I know what kind of recipe I want.

## Acceptance Criteria

1. Given I have search results displayed, When I tap a recipe book filter chip, Then only recipes from that book appear in results
2. Given I have search results displayed, When I tap a tag filter chip, Then only recipes with that tag appear in results
3. Given I have search results displayed, When I tap a time filter chip (e.g., ≤30 min), Then only recipes within that prep/cook time appear
4. Filters combine with AND logic — all active filters must match simultaneously
5. Results update immediately when any filter is toggled (no separate "Apply" button)
6. Active filters are displayed as filled/selected chips and can be individually removed by tapping again
7. Filtering by book does not show public recipes from other users — only narrows within the relevant section

## Tasks / Subtasks

- [ ] Task 1: Add filter query params to `unified_search.py` backend (AC: #1, #2, #3, #4, #7)
  - [ ] Open `services/api/src/api/v1/search/unified_search.py`
  - [ ] Add optional params to `execute()`: `book_id: str | None = None`, `tags: str | None = None` (comma-separated), `max_prep_time: int | None = None`, `max_cook_time: int | None = None`
  - [ ] Add `_filter_conditions()` method that returns a list of SQLAlchemy WHERE conditions from active filters
  - [ ] In `_filter_conditions()`:
    - If `book_id` set: `Recipe.recipe_book_id == book_id` (cast to UUID if needed)
    - If `tags` set: for each tag in `[t.strip() for t in tags.split(',')]` add `func.array_to_string(Recipe.tags, ',').ilike(f'%{tag}%')` — same NULL-safe pattern as `_recipe_matches()`
    - If `max_prep_time` set: `or_(Recipe.prep_time.is_(None), Recipe.prep_time <= max_prep_time)` — recipes with no prep time are included
    - If `max_cook_time` set: `or_(Recipe.cook_time.is_(None), Recipe.cook_time <= max_cook_time)`
  - [ ] Apply `_filter_conditions()` to `_search_my_recipes()` exact tier (add to `.where(...)`)
  - [ ] Apply `_filter_conditions()` to `_search_public_recipes()` exact tier
  - [ ] Apply `_filter_conditions()` to `_search_my_recipes_semantic()` and `_search_public_recipes_semantic()` (ORM, same `.where(...)` pattern)
  - [ ] For fuzzy tier `_search_my_recipes_fuzzy()` and `_search_public_recipes_fuzzy()`: add conditional f-string SQL clauses for each filter (same pattern as `exclude_clause`) — wrap in try/except already present
  - [ ] When `book_id` is set, `_search_my_recipes` and fuzzy/semantic variants should narrow to that specific book rather than all `my_book_ids`
  - [ ] Pass `filter_conditions` as a parameter to all `_search_*` helper methods OR extract them once in `execute()` and thread through

- [ ] Task 2: Backend filter tests (AC: #1, #2, #3)
  - [ ] Open `services/api/tests/test_search.py`
  - [ ] Add `test_search_filter_book_id()`: `GET /v1/search?q=pasta&book_id=some-uuid`, assert 200 + correct response shape
  - [ ] Add `test_search_filter_max_prep_time()`: `GET /v1/search?q=pasta&max_prep_time=30`, assert 200 + correct shape
  - [ ] Add `test_search_filter_tags()`: `GET /v1/search?q=pasta&tags=vegetarian`, assert 200 + correct shape
  - [ ] Note: same mock-DB pattern as `test_search_fuzzy_returns_200` — verifies no crash + shape

- [ ] Task 3: Update `ApiClient.search()` in Flutter (AC: #1-#6)
  - [ ] Open `app/lib/core/services/api_client.dart`
  - [ ] Update `search()` signature: `Future<Response> search(String query, {int limit = 20, String? bookId, List<String>? tags, int? maxPrepTime, int? maxCookTime})`
  - [ ] Add params to `queryParameters`: `if (bookId != null) 'book_id': bookId`, `if (tags != null && tags.isNotEmpty) 'tags': tags.join(',')`, `if (maxPrepTime != null) 'max_prep_time': maxPrepTime`, `if (maxCookTime != null) 'max_cook_time': maxCookTime`
  - [ ] The API sends tags as a single comma-separated string (e.g., `tags=vegetarian,quick`) matching the backend parser

- [ ] Task 4: Add filter chip UI to `SearchScreen` (AC: #1-#6)
  - [ ] Open `app/lib/features/search/search_screen.dart`
  - [ ] Add filter state fields to `_SearchScreenState`:
    ```dart
    String? _filterBookId;
    String? _filterBookName;        // for display
    Set<String> _filterTags = {};
    int? _maxTotalTime;             // sum of prep+cook displayed as "≤Xmin"
    ```
  - [ ] Add `_onFilterChanged()` method: calls `_performSearch(_searchController.text)` directly (no debounce — filter taps are intentional)
  - [ ] Update `_performSearch()` to pass filter params to `_apiClient.search()`:
    ```dart
    final response = await _apiClient.search(
      query,
      bookId: _filterBookId,
      tags: _filterTags.isEmpty ? null : _filterTags.toList(),
      maxPrepTime: _maxTotalTime,   // send as max_prep_time
      maxCookTime: _maxTotalTime,   // send same limit for cook time
    );
    ```
    Note: Use the same value for both `maxPrepTime` and `maxCookTime` since the chip label is "Total ≤Xmin"
  - [ ] Add `_buildFilterRow()` widget that appears in the body when `_hasSearched` is true:
    - Horizontally scrollable `SingleChildScrollView` with `Row` of `FilterChip` widgets
    - **Book chips**: extract unique `{id, name}` pairs from `_myRecipes` (not public — book filter is for personal collection); one chip per book found in results; use `FilterChip(label: Text(bookName), selected: _filterBookId == bookId, onSelected: ...)`
    - **Time chips**: preset options `[15, 30, 60]` minutes; `FilterChip(label: Text('≤${t}min'), selected: _maxTotalTime == t, onSelected: (sel) { setState(() { _maxTotalTime = sel ? t : null; }); _onFilterChanged(); })`
    - **Tag chips**: extract unique tags from ALL results (my + public); deduplicate; limit to first 10 most common tags; `FilterChip(label: Text('#$tag'), selected: _filterTags.contains(tag), onSelected: ...)`
    - Wrap `_buildFilterRow()` and results `ListView` in a `Column`
    - Padding: `EdgeInsets.symmetric(horizontal: 8, vertical: 4)` for the row
  - [ ] When a filter chip is deselected (tapped again while selected): clear that filter and re-run search
  - [ ] When the search query changes (`_onSearchChanged`): reset all filters (`_filterBookId = null; _filterTags.clear(); _maxTotalTime = null;`) before running new search — stale filters from previous queries should not carry over
  - [ ] Use `colorScheme.*` theming for `FilterChip` — do NOT use `AppColors`; selected chips use `colorScheme.primaryContainer` / `colorScheme.onPrimaryContainer` automatically via Material 3
  - [ ] Do NOT show filter row when `!_hasSearched` (empty state) or `_isLoading` is true

- [ ] Task 5: Flutter widget tests (AC: #5, #6)
  - [ ] Open (or create) `app/test/search_screen_test.dart`
  - [ ] Add test: `'filter chips render when results present'` — render a `FilterChip` widget with `selected: false`, verify it shows; render with `selected: true`, verify selected state
  - [ ] Follow the existing isolated widget test pattern (test the primitive components, not the full DI-wired SearchScreen)

## Dev Notes

### Read Before Touching Anything

**The search infrastructure exists end-to-end from Stories 5.1 and 5.2.** Story 5.3 adds filter parameters only — do NOT rewrite the endpoint, the three-tier pipeline, or the Flutter screen layout. Read these files first:

- `services/api/src/api/v1/search/unified_search.py` — current three-tier implementation (READ FIRST)
- `app/lib/features/search/search_screen.dart` — current working search screen (READ FIRST)
- `app/lib/core/services/api_client.dart:241` — current `search()` signature (READ FIRST)

### What Stories 5.1 & 5.2 Delivered (Do Not Rewrite)

- `GET /v1/search?q=...&limit=N` — fully working, returns `{query, my_recipes, public_recipes, users}`
- Three-tier pipeline: exact ILIKE → fuzzy pg_trgm → semantic pgvector, dedup by ID sets
- `_get_my_book_ids(user)` helper — cached at start of `execute()`
- `_recipe_matches(query)` — OR condition on name/description/ingredient/tag
- `SearchScreen` — working screen with debounce, photo-dominant recipe cards, section headers
- `_buildRecipeTile()` — Card layout with 100×100 image, chevron, ingredients line
- `ApiClient.search(String query, {int limit = 20})` — HTTP client method

### Backend: Adding Filters to All Tiers

#### Method Signature Update

```python
def execute(
    self,
    q: str,
    limit: int = 20,
    book_id: str | None = None,
    tags: str | None = None,        # comma-separated, e.g. "vegetarian,quick"
    max_prep_time: int | None = None,
    max_cook_time: int | None = None,
):
    filter_tags = [t.strip() for t in tags.split(",")] if tags else []
    # ... existing logic, pass filters to each tier
```

#### `_filter_conditions()` Helper

```python
def _filter_conditions(
    self,
    book_id: str | None,
    filter_tags: list[str],
    max_prep_time: int | None,
    max_cook_time: int | None,
) -> list:
    conditions = []
    if book_id:
        conditions.append(Recipe.recipe_book_id == book_id)
    for tag in filter_tags:
        conditions.append(func.array_to_string(Recipe.tags, ",").ilike(f"%{tag}%"))
    if max_prep_time is not None:
        conditions.append(or_(Recipe.prep_time.is_(None), Recipe.prep_time <= max_prep_time))
    if max_cook_time is not None:
        conditions.append(or_(Recipe.cook_time.is_(None), Recipe.cook_time <= max_cook_time))
    return conditions
```

Note: `or_` is already imported from sqlalchemy. The `func` import is already present.

#### Applying to ORM Tiers

For `_search_my_recipes()` and semantic equivalents, spread the conditions into `.where()`:
```python
.where(
    Recipe.recipe_book_id.in_(my_book_ids),
    Recipe.archived_at.is_(None),
    self._recipe_matches(query),
    *filter_conditions,   # unpack list
)
```

#### Applying to Fuzzy Raw SQL Tier

Add conditional f-string clauses inside the try/except (same pattern as `exclude_clause`):

```python
# Build dynamic WHERE clauses for filters
book_clause = "AND r.recipe_book_id = :filter_book_id" if book_id else ""
prep_clause = "AND (r.prep_time IS NULL OR r.prep_time <= :max_prep_time)" if max_prep_time else ""
cook_clause = "AND (r.cook_time IS NULL OR r.cook_time <= :max_cook_time)" if max_cook_time else ""
# For tags: add one clause per tag
tag_clauses = "\n".join(
    f"AND array_to_string(r.tags, ',') ILIKE :filter_tag_{i}"
    for i in range(len(filter_tags))
)

# Add to params dict:
if book_id:
    params["filter_book_id"] = book_id
if max_prep_time:
    params["max_prep_time"] = max_prep_time
if max_cook_time:
    params["max_cook_time"] = max_cook_time
for i, tag in enumerate(filter_tags):
    params[f"filter_tag_{i}"] = f"%{tag}%"
```

Then include in the f-string SQL:
```sql
WHERE r.recipe_book_id = ANY(:book_ids)
  AND r.archived_at IS NULL
  {exclude_clause}
  {book_clause}
  {prep_clause}
  {cook_clause}
  {tag_clauses}
  AND (similarity(r.name, :query) > 0.2 OR ...)
```

#### Book Filter in My Recipes Tier

When `book_id` is provided, restrict the my_book_ids check:
```python
# In execute():
effective_book_ids = [book_id] if book_id else my_book_ids
# Pass effective_book_ids to all _search_my_* methods
```

This prevents the `_get_my_book_ids()` result from being ignored when a book filter is active.

### Frontend: Filter Chip Row Design

#### State Management

```dart
// Filter state — reset when query text changes
String? _filterBookId;
String? _filterBookName;
Set<String> _filterTags = {};
int? _maxTotalTime;  // applied to both prep_time and cook_time

// Derived data extracted from current results
List<MapEntry<String, String>> _availableBooks() {
  final seen = <String>{};
  final books = <MapEntry<String, String>>[];
  for (final r in _myRecipes) {
    final id = r['recipe_book_id'] as String?;
    final name = r['recipe_book_name'] as String?;
    if (id != null && name != null && seen.add(id)) {
      books.add(MapEntry(id, name));
    }
  }
  return books;
}

List<String> _availableTags() {
  final tagCounts = <String, int>{};
  for (final r in [..._myRecipes, ..._publicRecipes]) {
    for (final tag in (r['ingredients'] as List? ?? [])) { /* skip — ingredients not tags */ }
    // Note: tags are not returned in RecipeResult — see below
  }
  return tagCounts.entries
    .toList()
    ..sort((a, b) => b.value.compareTo(a.value));
    .take(10).map((e) => e.key).toList();
}
```

**IMPORTANT**: `RecipeResult` currently does NOT return `tags` in the response (only: `id, name, description, image_url, prep_time, cook_time, recipe_book_id, recipe_book_name, ingredients`). Tags are NOT in the Flutter response model. Two options:
1. Add `tags: list[str] = []` to `UnifiedSearch.RecipeResult` and pass `recipe.tags or []` — simplest fix
2. Use only time + book filters in the UI (skip tag chips for now)

**Recommended**: Add `tags: list[str] = []` to `RecipeResult` model in `unified_search.py` and include `tags=recipe.tags or []` in the result construction. Then display tag chips in the Flutter UI. This is a 2-line change in the backend.

#### Layout Structure

```dart
@override
Widget build(BuildContext context) {
  return Scaffold(
    appBar: AppBar(... existing search bar ...),
    body: Column(children: [
      if (_hasSearched && !_isLoading && _anyResultsExist)
        _buildFilterRow(),
      Expanded(child: _buildBody()),
    ]),
  );
}
```

#### FilterChip Theming

Use Material 3 `FilterChip` — do NOT use `ChoiceChip` (wrong semantics). Use `colorScheme.*` only:
```dart
FilterChip(
  label: Text(bookName),
  selected: _filterBookId == bookId,
  onSelected: (selected) {
    setState(() {
      _filterBookId = selected ? bookId : null;
      _filterBookName = selected ? bookName : null;
    });
    _onFilterChanged();
  },
)
```

Selected state uses Material 3 defaults: filled with `colorScheme.secondaryContainer`, checkmark icon. No manual color overrides needed.

#### Filter Reset on Query Change

```dart
void _onSearchChanged(String query) {
  _debounce?.cancel();
  // Reset stale filters when user types a new query
  setState(() {
    _filterBookId = null;
    _filterBookName = null;
    _filterTags.clear();
    _maxTotalTime = null;
  });
  if (query.length < 2) { ... return; }
  _debounce = Timer(const Duration(milliseconds: 300), () {
    _performSearch(query);
  });
}
```

### RecipeResult Tags Field Addition

Add to `UnifiedSearch.RecipeResult` in `unified_search.py`:
```python
class RecipeResult(BaseModel):
    id: str
    name: str
    ...
    ingredients: list[str] = []
    tags: list[str] = []   # ADD THIS
```

And pass in `_search_my_recipes()` and `_search_my_recipes_semantic()`:
```python
tags=recipe.tags or [],
```

The fuzzy tier returns `tags=[]` (no ORM object available) — acceptable, same as `ingredients=[]`.

### What NOT To Do

- Do NOT change the response schema keys (`my_recipes`, `public_recipes`, `users`)
- Do NOT change the `/v1/search` endpoint path or minimum query length
- Do NOT add a new endpoint — add optional query params to the existing one
- Do NOT rewrite the three-tier pipeline — just add `.where(*filter_conditions)` to existing queries
- Do NOT use `AppColors` in the Flutter filter UI — use `colorScheme.*`
- Do NOT apply a debounce to filter chip taps — call `_performSearch` directly
- Do NOT show tags from the `ingredients` field — that field has ingredient names, not recipe tags
- Do NOT block the search if filters produce 0 results — empty state is fine

### Architecture Compliance

- Backend follows `Endpoint` class pattern ✓ (existing, extend only)
- Use `success()` helper for responses ✓ (no change)
- All Python: snake_case ✓
- Tests in `services/api/tests/test_search.py` ✓
- No response schema key changes ✓
- FilterChip uses `colorScheme.*` theming ✓

### References

- [Source: services/api/src/api/v1/search/unified_search.py] — base implementation to extend
- [Source: app/lib/features/search/search_screen.dart] — Flutter screen to extend
- [Source: app/lib/core/services/api_client.dart:241] — `search()` method to update
- [Source: libraries/utils/utils/models/recipe.py:31-35] — `prep_time`, `cook_time`, `tags` fields
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.3] — acceptance criteria
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — FilterChip component, warm palette theming
- [Source: _bmad-output/planning-artifacts/architecture.md] — Endpoint pattern, SQLAlchemy patterns, anti-patterns

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

### File List
