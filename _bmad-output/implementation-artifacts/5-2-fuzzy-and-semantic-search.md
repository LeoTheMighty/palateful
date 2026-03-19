# Story 5.2: Fuzzy & Semantic Search

Status: ready-for-dev

## Story

As a user,
I want search to be forgiving of typos and understand what I mean even when I don't use exact words,
So that I always find what I'm looking for.

## Acceptance Criteria

1. Given I enter a search query, When exact matches exist, Then they appear first in results
2. Fuzzy matches (typos, partial words) via pg_trgm appear after exact matches
3. Semantic matches (conceptually similar) via pgvector appear after fuzzy matches
4. The search pipeline runs exact → fuzzy → semantic in sequence, combining results without duplicates
5. Searching "chicken pasta" finds recipes titled "Creamy Garlic Chicken Penne" (semantic)
6. Searching "chiken" (typo) still returns chicken recipes (fuzzy)

## Tasks / Subtasks

- [ ] Task 1: Alembic migration — add pg_trgm GIN indexes on recipes (AC: #2, #6)
  - [ ] Create new migration in `services/migrator/migrations/versions/`
  - [ ] Add GIN trgm index on `recipes.name`: `CREATE INDEX IF NOT EXISTS idx_recipes_name_trgm ON recipes USING gin (name gin_trgm_ops)`
  - [ ] Add GIN trgm index on `recipes.description`: `CREATE INDEX IF NOT EXISTS idx_recipes_description_trgm ON recipes USING gin (description gin_trgm_ops)`
  - [ ] pg_trgm extension is already installed (initial migration) — do NOT re-add it
  - [ ] Set minimum pg_trgm similarity threshold in migration: `SET pg_trgm.similarity_threshold = 0.2` (via `op.execute("ALTER DATABASE ... SET ...")`  — or just leave as app-level setting)

- [ ] Task 2: Add fuzzy search tier to `unified_search.py` (AC: #1, #2, #4, #6)
  - [ ] Open `services/api/src/api/v1/search/unified_search.py`
  - [ ] Add `text` to the `sqlalchemy` imports: `from sqlalchemy import exists, func, or_, select, text`
  - [ ] Add `_fuzzy_recipe_filter()` method using raw SQL `similarity(name, :query) > 0.2 OR name % :query`
  - [ ] Update `_search_my_recipes()` to:
    1. Run exact ILIKE query (existing), collect result IDs
    2. If fewer than `limit` results, run fuzzy pg_trgm query excluding already-found IDs
    3. Combine and return up to `limit` results (exact first, then fuzzy)
  - [ ] Apply same two-pass pattern to `_search_public_recipes()`
  - [ ] Use raw SQL `text(...)` for pg_trgm (same pattern as `search_ingredients.py`)
  - [ ] Wrap pg_trgm pass in try/except with ILIKE fallback (extension might not be available in some environments)

- [ ] Task 3: Add semantic search tier to `unified_search.py` (AC: #3, #4, #5)
  - [ ] Add `_generate_query_embedding(query: str) -> list[float] | None` method:
    - Call `openai.OpenAI().embeddings.create(model="text-embedding-3-small", input=query, dimensions=384)`
    - Return `list[float]` or `None` if OpenAI unavailable/fails
    - Wrap entire call in try/except — semantic tier degrades gracefully
  - [ ] After exact + fuzzy passes, call `_generate_query_embedding(query)` once
  - [ ] If embedding is not None, run semantic pass:
    - Query `Recipe.embedding.cosine_distance(query_embedding)` ordered ascending (lower = more similar)
    - Filter: `Recipe.embedding.is_not(None)`, `Recipe.id.notin_(already_found_ids)`, `archived_at.is_(None)`
    - Threshold: cosine distance < 0.7 (similarity > 0.3) — tune as needed
    - Limit: append up to `limit` more results (not already in exact/fuzzy)
  - [ ] Use `pgvector.sqlalchemy` `Vector` for the cosine_distance call (already imported in recipe model)
    - Pattern from `libraries/agent/agent/tools/recipes.py:92`: `Recipe.embedding.cosine_distance(query_embedding).label("distance")`
  - [ ] Do NOT fail the entire search if semantic tier fails — catch exceptions and continue

- [ ] Task 4: Add recipe embedding generation on create/update (AC: #5)
  - [ ] Open `services/api/src/config.py`
  - [ ] Add `openai_api_key: str = ""` to `Settings` (reads from `OPENAI_API_KEY` env var)
  - [ ] Create `services/api/src/api/v1/search/generate_recipe_embedding.py` helper:
    ```python
    def generate_recipe_embedding(recipe_name: str, description: str | None, tags: list[str] | None) -> list[float] | None:
        """Generate 384-dim embedding for a recipe via OpenAI text-embedding-3-small."""
        text = f"{recipe_name}. {description or ''}. Tags: {', '.join(tags or [])}"
        try:
            from openai import OpenAI
            client = OpenAI()
            resp = client.embeddings.create(model="text-embedding-3-small", input=text, dimensions=384)
            return resp.data[0].embedding
        except Exception:
            return None
    ```
  - [ ] In `services/api/src/api/v1/recipe/create_recipe.py`:
    - After `db.refresh(recipe)`, call `generate_recipe_embedding()`
    - If not None, set `recipe.embedding = embedding` and `db.commit()` (or just set before commit)
  - [ ] In `services/api/src/api/v1/recipe/update_recipe.py`:
    - After saving recipe changes, regenerate embedding if name, description, or tags changed
    - Same pattern: call helper, set `recipe.embedding`, commit

- [ ] Task 5: Backend tests (AC: #2, #3, #6)
  - [ ] Add `test_search_fuzzy_returns_200()` to `services/api/tests/test_search.py`:
    - Mock DB, call `GET /v1/search?q=chiken`, assert 200 + response shape
  - [ ] Verify existing `test_search_by_tag` still passes
  - [ ] Note: pg_trgm try/except fallback means tests pass even without real pg_trgm

## Dev Notes

### Read Before Touching Anything

**The search infrastructure exists end-to-end from Story 5.1.** Story 5.2 enhances `unified_search.py` only — do NOT rewrite the endpoint, router, frontend, or response schema. Read these files first:

- `services/api/src/api/v1/search/unified_search.py` — current implementation (READ FIRST)
- `services/api/src/api/v1/ingredient/search_ingredients.py` — exact pg_trgm pattern to follow
- `libraries/agent/agent/tools/recipes.py:55-110` — exact pgvector cosine_distance pattern to follow
- `libraries/utils/utils/models/recipe.py` — Recipe model with `embedding: Vector(384)`

### What Story 5.1 Delivered (Do Not Rewrite)

- `GET /v1/search?q=...` endpoint — working, returns `{my_recipes, public_recipes, users}`
- `_recipe_matches()` — OR condition on name/description/ingredient/tag via ILIKE
- `SearchScreen` in Flutter — fully working, no changes needed in 5.2
- `ApiClient.search()` — no changes needed
- Photo-dominant recipe cards — no changes needed

### pg_trgm — Exact Implementation Pattern

The existing `search_ingredients.py` uses this proven pattern:

```python
from sqlalchemy import text

# In _search_my_recipes_fuzzy() — raw SQL for pg_trgm
result = self.db.execute(
    text("""
        SELECT r.id, r.name, rb.name AS book_name, ...
        FROM recipes r
        JOIN recipe_books rb ON r.recipe_book_id = rb.id
        JOIN recipe_book_users rbu ON rb.id = rbu.recipe_book_id
        WHERE rbu.user_id = :user_id
          AND r.archived_at IS NULL
          AND r.id != ALL(:exclude_ids)
          AND (
            similarity(r.name, :query) > 0.2
            OR r.name % :query
          )
        ORDER BY similarity(r.name, :query) DESC
        LIMIT :limit
    """),
    {"user_id": str(user.id), "query": query, "exclude_ids": exclude_ids, "limit": remaining}
)
```

The `%` operator uses `pg_trgm.similarity_threshold` (default 0.3). `similarity() > 0.2` catches more marginal matches. Wrap in try/except for environments without pg_trgm.

### pg_trgm Index Migration

File: `services/migrator/migrations/versions/<timestamp>_recipe_trgm_indexes.py`

```python
def upgrade():
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_recipes_name_trgm
        ON recipes USING gin (name gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_recipes_description_trgm
        ON recipes USING gin (description gin_trgm_ops)
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_recipes_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_recipes_description_trgm")
```

**IMPORTANT**: pg_trgm extension is already created in the initial migration (`2026011704109_5b51adc124d5_initial_models_for_recipe_books.py`). Do NOT re-add `CREATE EXTENSION pg_trgm` — it will fail if already exists.

### pgvector Semantic Search — Pattern from Agent Tools

From `libraries/agent/agent/tools/recipes.py:88-110`:

```python
from sqlalchemy import select

# Pattern for cosine distance query
query = (
    select(
        Recipe,
        Recipe.embedding.cosine_distance(query_embedding).label("distance"),
    )
    .where(Recipe.recipe_book_id.in_(book_ids))
    .where(Recipe.archived_at.is_(None))
    .where(Recipe.embedding.is_not(None))
    .where(Recipe.id.notin_(already_found_ids))
    .order_by("distance")
    .limit(limit)
)
result = self.db.execute(query)
```

`Recipe.embedding.cosine_distance(query_embedding)` is provided by `pgvector.sqlalchemy` (already installed). The `embedding` attribute has `.cosine_distance()`, `.l2_distance()`, `.max_inner_product()` methods.

### OpenAI Embedding Generation

The API service has `openai = "^2.8"` in `pyproject.toml`. Use `text-embedding-3-small` with `dimensions=384` to stay compatible with the existing `Vector(384)` column and `ix_recipe_embedding_hnsw` HNSW index:

```python
from openai import OpenAI

def generate_recipe_embedding(text: str) -> list[float] | None:
    try:
        client = OpenAI()  # Reads OPENAI_API_KEY from env
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=384
        )
        return resp.data[0].embedding
    except Exception:
        return None
```

**Why `dimensions=384`?** OpenAI text-embedding-3-* models support custom output dimensions. Setting 384 matches the existing `Vector(384)` column and HNSW index. Using a different dimension would require a schema migration.

**Graceful degradation**: If `OPENAI_API_KEY` is not set or call fails, return `None`. The semantic search tier then silently returns no results. Exact and fuzzy search still work.

### Existing Recipe Embeddings

Currently: **all `recipe.embedding` values are NULL** — the column exists (from migration `20260117041822_suggestion_and_notification`) but no code generates recipe embeddings yet. This means:
- Semantic search (AC#5) will return empty results until recipes are re-saved
- AC#5 ("chicken pasta" → "Creamy Garlic Chicken Penne") requires embeddings to exist
- Task 4 fixes this going forward; a separate backfill is out of scope

**What this means for testing**: The semantic tier's graceful degradation is essential. All existing tests pass with no embeddings.

### Alembic Migration File Naming

Look at existing migration files in `services/migrator/migrations/versions/` for the naming convention:
- Format: `{YYYYMMDDHHMMSS}_{random_hex}_{description}.py`
- Example: `2026011704109_5b51adc124d5_initial_models_for_recipe_books.py`
- Use current date for timestamp prefix

Generate a new Alembic revision:
```bash
# From services/migrator/ directory
npx nx run migrator:migrate -- revision --autogenerate -m "recipe_trgm_indexes"
# OR manually create the file with the correct naming pattern
```

The migration must have a `revision`, `down_revision` (pointing to latest), `branch_labels`, and `depends_on` header.

### Three-Pass Deduplication Strategy

The `execute()` method should follow this flow:

```python
def execute(self, q: str, limit: int = 20):
    query = q.strip()
    # Tier 1: Exact ILIKE search (existing logic)
    my_recipes_exact = self._search_my_recipes(query, limit, user)
    public_recipes_exact = self._search_public_recipes(query, limit, user)
    users = self._search_users(query, limit, user)

    # Collect IDs for dedup
    my_exact_ids = {r.id for r in my_recipes_exact}
    pub_exact_ids = {r.id for r in public_recipes_exact}

    # Tier 2: Fuzzy pg_trgm (only if needed)
    my_recipes_fuzzy = []
    if len(my_recipes_exact) < limit:
        my_recipes_fuzzy = self._search_my_recipes_fuzzy(query, limit - len(my_recipes_exact), user, exclude_ids=my_exact_ids)

    pub_recipes_fuzzy = []
    if len(public_recipes_exact) < limit:
        pub_recipes_fuzzy = self._search_public_recipes_fuzzy(query, limit - len(public_recipes_exact), user, exclude_ids=pub_exact_ids)

    # Tier 3: Semantic pgvector
    query_embedding = self._generate_query_embedding(query)
    all_my_ids = my_exact_ids | {r.id for r in my_recipes_fuzzy}
    my_recipes_semantic = []
    if query_embedding and len(my_recipes_exact) + len(my_recipes_fuzzy) < limit:
        my_recipes_semantic = self._search_my_recipes_semantic(query_embedding, limit - len(my_recipes_exact) - len(my_recipes_fuzzy), user, exclude_ids=all_my_ids)

    # Same for public_recipes_semantic...

    return success(data=UnifiedSearch.Response(
        query=query,
        my_recipes=my_recipes_exact + my_recipes_fuzzy + my_recipes_semantic,
        public_recipes=public_recipes_exact + pub_recipes_fuzzy + pub_recipes_semantic,
        users=users,
    ))
```

### What NOT To Do

- Do NOT change the response schema (`my_recipes`, `public_recipes`, `users` keys stay identical)
- Do NOT change the `/v1/search` endpoint signature
- Do NOT modify `SearchScreen` in Flutter — it already works
- Do NOT block recipe save on embedding generation failure — always return None gracefully
- Do NOT add `CREATE EXTENSION pg_trgm` to the migration — already exists
- Do NOT use `sentence_transformers` — it's not installed in the API service (that's the agent service only)
- Do NOT change the embedding column dimension (384) — the HNSW index was built for it
- Do NOT run `autogenerate` Alembic migration if it picks up unrelated model changes — write the migration manually

### Performance Notes

- pg_trgm GIN index makes `name % query` fast (index scan not table scan)
- Fuzzy pass only runs when exact pass returns fewer than `limit` results
- Semantic pass only runs if fuzzy pass still has room AND OpenAI call succeeds
- At current scale (< 1000 recipes per user), all three tiers run in < 500ms
- `ix_recipe_embedding_hnsw` HNSW index (m=16, ef_construction=64) makes cosine distance fast

### Architecture Compliance

- Backend follows `Endpoint` class pattern ✓ (existing, extend only)
- Use `success()` helper for responses ✓ (existing, no change)
- All Python: snake_case ✓
- Tests in `services/api/tests/test_search.py` ✓
- No schema changes to response format ✓
- OpenAI key reads from env (`OPENAI_API_KEY`) ✓

### References

- [Source: services/api/src/api/v1/search/unified_search.py] — base implementation to enhance
- [Source: services/api/src/api/v1/ingredient/search_ingredients.py] — pg_trgm pattern (use this!)
- [Source: libraries/agent/agent/tools/recipes.py:55-110] — pgvector cosine_distance pattern
- [Source: libraries/utils/utils/models/recipe.py] — Recipe model with Vector(384) embedding
- [Source: services/migrator/migrations/versions/2026011704109_5b51adc124d5_initial_models_for_recipe_books.py] — pg_trgm extension already installed here
- [Source: services/migrator/migrations/versions/20260117041822_525891f38d8b_suggestion_and_notification_models.py] — HNSW index on recipe embeddings created here
- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.2] — acceptance criteria
- [Source: docs/search-design.md] — search design document (note: semantic search marked "future" there but is in AC for 5.2)
- [Source: _bmad-output/planning-artifacts/architecture.md#Enforcement Guidelines] — Endpoint pattern, success() helper, anti-patterns

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

### Completion Notes List

### File List
