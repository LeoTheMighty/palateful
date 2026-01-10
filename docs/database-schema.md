# Palateful Database Schema

## Overview

Palateful uses PostgreSQL with two extensions:
- **pgvector**: 384-dimensional vector embeddings for semantic search
- **pg_trgm**: Trigram-based fuzzy text matching

## Entity Relationship Diagram

```
User
  ├── Thread (1:N) → Chat (1:N)
  ├── PantryUser (N:M) → Pantry → PantryIngredient (N:M) → Ingredient
  ├── RecipeBookUser (N:M) → RecipeBook → Recipe → RecipeIngredient (N:M) → Ingredient
  └── Ingredient (submitted_by)

Ingredient
  ├── IngredientSubstitution (self-referential N:M)
  ├── embedding: Vector(384)
  └── parent/children (self-referential hierarchy)

Unit (standalone lookup table)
CookingLog → Recipe, Pantry
```

---

## Models

### User

Primary user model with Auth0 integration.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| auth0Id | String | Unique, Required | Auth0 subject ID |
| email | String | Unique, Required | User email |
| name | String | Nullable | Display name |
| picture | String | Nullable | Profile picture URL |
| emailVerified | Boolean | Default: false | Email verification status |
| hasCompletedOnboarding | Boolean | Default: false | Onboarding completion flag |
| createdAt | DateTime | Default: now() | Creation timestamp |
| updatedAt | DateTime | Auto-update | Last update timestamp |

**Relations:**
- `pantryMemberships` → PantryUser[]
- `recipeBookMemberships` → RecipeBookUser[]
- `submittedIngredients` → Ingredient[]
- `threads` → Thread[]

---

### Thread

AI conversation threads.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| title | String | Nullable | Conversation title (auto-generated) |
| createdAt | DateTime | Default: now() | Creation timestamp |
| updatedAt | DateTime | Auto-update | Last update timestamp |
| userId | String | FK → User, CASCADE | Owner user |

**Indexes:** `userId`

**Relations:**
- `user` → User
- `chats` → Chat[]

---

### Chat

Individual chat messages in a thread.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| role | String | Required | "user", "assistant", "system", "tool" |
| content | Text | Nullable | Message content |
| createdAt | DateTime | Default: now() | Creation timestamp |
| toolCalls | JSON | Nullable | OpenAI tool_calls array |
| toolCallId | String | Nullable | Tool call correlation ID |
| toolName | String | Nullable | Tool name for tool responses |
| promptTokens | Int | Nullable | Prompt token count |
| completionTokens | Int | Nullable | Completion token count |
| model | String | Nullable | Model identifier (e.g., "gpt-4o") |
| threadId | String | FK → Thread, CASCADE | Parent thread |

**Indexes:** `threadId`

**Relations:**
- `thread` → Thread

---

### Pantry

Container for user's ingredient inventory.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| name | String | Required | Pantry name |
| createdAt | DateTime | Default: now() | Creation timestamp |
| updatedAt | DateTime | Auto-update | Last update timestamp |

**Relations:**
- `members` → PantryUser[]
- `ingredients` → PantryIngredient[]
- `cookingLogs` → CookingLog[]

---

### PantryUser

Join table for pantry membership with roles.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| role | String | Default: "member" | "owner" or "member" |
| createdAt | DateTime | Default: now() | Creation timestamp |
| userId | String | FK → User, CASCADE | Member user |
| pantryId | String | FK → Pantry, CASCADE | Parent pantry |

**Unique Constraint:** `(userId, pantryId)`

**Relations:**
- `user` → User
- `pantry` → Pantry

---

### PantryIngredient

Ingredient inventory in a pantry.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| quantityDisplay | Decimal(10,3) | Required | User-entered quantity |
| unitDisplay | String | Required | User-entered unit |
| quantityNormalized | Decimal(10,3) | Required | Normalized quantity (base units) |
| unitNormalized | String | Required | Normalized unit name |
| addedAt | DateTime | Default: now() | When added |
| updatedAt | DateTime | Auto-update | Last update |
| expiresAt | DateTime | Nullable | Expiration date |
| pantryId | String | FK → Pantry, CASCADE | Parent pantry |
| ingredientId | String | FK → Ingredient, RESTRICT | Ingredient reference |

**Unique Constraint:** `(pantryId, ingredientId)`

**Relations:**
- `pantry` → Pantry
- `ingredient` → Ingredient

---

### RecipeBook

Collection of recipes.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| name | String | Required | Recipe book name |
| description | String | Nullable | Description |
| isPublic | Boolean | Default: false | Public visibility |
| createdAt | DateTime | Default: now() | Creation timestamp |
| updatedAt | DateTime | Auto-update | Last update timestamp |

**Relations:**
- `members` → RecipeBookUser[]
- `recipes` → Recipe[]

---

### RecipeBookUser

Join table for recipe book membership.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| role | String | Default: "member" | "owner", "editor", "viewer" |
| createdAt | DateTime | Default: now() | Creation timestamp |
| userId | String | FK → User, CASCADE | Member user |
| recipeBookId | String | FK → RecipeBook, CASCADE | Parent recipe book |

**Unique Constraint:** `(userId, recipeBookId)`

**Relations:**
- `user` → User
- `recipeBook` → RecipeBook

---

### Recipe

Individual recipe.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| name | String | Required | Recipe name |
| description | String | Nullable | Description/notes |
| instructions | Text | Nullable | Cooking instructions |
| servings | Int | Default: 1 | Number of servings |
| prepTime | Int | Nullable | Prep time in minutes |
| cookTime | Int | Nullable | Cook time in minutes |
| imageUrl | String | Nullable | Recipe image URL |
| sourceUrl | String | Nullable | Original source URL |
| createdAt | DateTime | Default: now() | Creation timestamp |
| updatedAt | DateTime | Auto-update | Last update timestamp |
| recipeBookId | String | FK → RecipeBook, CASCADE | Parent recipe book |

**Relations:**
- `recipeBook` → RecipeBook
- `ingredients` → RecipeIngredient[]
- `cookingLogs` → CookingLog[]

---

### RecipeIngredient

Ingredient requirements for a recipe.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| quantityDisplay | Decimal(10,3) | Required | Display quantity |
| unitDisplay | String | Required | Display unit |
| quantityNormalized | Decimal(10,3) | Required | Normalized quantity |
| unitNormalized | String | Required | Normalized unit |
| notes | String | Nullable | Prep notes ("finely chopped") |
| isOptional | Boolean | Default: false | Optional ingredient flag |
| orderIndex | Int | Default: 0 | Display order |
| recipeId | String | FK → Recipe, CASCADE | Parent recipe |
| ingredientId | String | FK → Ingredient, RESTRICT | Ingredient reference |

**Unique Constraint:** `(recipeId, ingredientId)`

**Relations:**
- `recipe` → Recipe
- `ingredient` → Ingredient

---

### Ingredient

Core ingredient with semantic search support.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| canonicalName | String | Unique, Required | Standard name ("tomato") |
| aliases | String[] | Default: [] | Alternative names |
| category | String | Nullable | "produce", "dairy", "protein", "pantry", "spice" |
| flavorProfile | String[] | Default: [] | Flavor tags ("acidic", "umami") |
| defaultUnit | String | Nullable | Suggested unit |
| isCanonical | Boolean | Default: true | Base ingredient flag |
| pendingReview | Boolean | Default: false | Community submission review |
| imageUrl | String | Nullable | Ingredient image |
| **embedding** | **Vector(384)** | Nullable | **Semantic search embedding** |
| submittedById | String | FK → User, SET NULL | Submitter |
| parentId | String | FK → Ingredient, SET NULL | Parent in hierarchy |
| createdAt | DateTime | Default: now() | Creation timestamp |
| updatedAt | DateTime | Auto-update | Last update timestamp |

**Indexes:**
- `idx_ingredients_canonical_name_trgm` - GIN trigram index for fuzzy search
- `idx_ingredients_embedding` - HNSW vector index for semantic search

**Relations:**
- `submittedBy` → User
- `parent` → Ingredient (self)
- `children` → Ingredient[]
- `pantryIngredients` → PantryIngredient[]
- `recipeIngredients` → RecipeIngredient[]
- `substitutesFor` → IngredientSubstitution[]
- `substitutedBy` → IngredientSubstitution[]

---

### IngredientSubstitution

Ingredient substitution relationships.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| context | String | Nullable | "baking", "cooking", "raw", "any" |
| quality | String | Required | "perfect", "good", "workable" |
| ratio | Decimal(5,2) | Default: 1.0 | Conversion ratio |
| notes | String | Nullable | Substitution advice |
| ingredientId | String | FK → Ingredient, CASCADE | Original ingredient |
| substituteId | String | FK → Ingredient, CASCADE | Substitute ingredient |

**Unique Constraint:** `(ingredientId, substituteId, context)`

**Relations:**
- `ingredient` → Ingredient
- `substitute` → Ingredient

---

### Unit

Unit conversion lookup table.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| name | String | Unique, Required | Full name ("teaspoon") |
| abbreviation | String | Required | Short form ("tsp") |
| type | String | Required | "volume", "weight", "count", "other" |
| toBaseFactor | Decimal(15,6) | Required | Conversion factor to base unit |
| baseUnit | String | Required | Reference base unit |

---

### CookingLog

Recipe cooking history.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | String | PK, CUID | Primary identifier |
| scaleFactor | Decimal(5,2) | Default: 1.0 | Recipe scale |
| notes | String | Nullable | Cooking notes |
| cookedAt | DateTime | Default: now() | When cooked |
| recipeId | String | FK → Recipe, RESTRICT | Recipe cooked |
| pantryId | String | Required | Pantry used |

**Relations:**
- `recipe` → Recipe
- `pantry` → Pantry

---

## Custom Database Functions

### search_ingredients_fuzzy

Fuzzy text search using trigram similarity.

```sql
search_ingredients_fuzzy(
  search_term TEXT,
  similarity_threshold FLOAT DEFAULT 0.3,
  result_limit INT DEFAULT 10
)
RETURNS TABLE (
  id TEXT,
  canonical_name TEXT,
  aliases TEXT[],
  category TEXT,
  name_similarity FLOAT,
  alias_similarity FLOAT,
  best_similarity FLOAT
)
```

**Usage:** Searches both `canonical_name` and `aliases` array, returning the best similarity score.

### search_ingredients_semantic

Vector similarity search using embeddings.

```sql
search_ingredients_semantic(
  query_embedding vector(384),
  similarity_threshold FLOAT DEFAULT 0.7,
  result_limit INT DEFAULT 10
)
RETURNS TABLE (
  id TEXT,
  canonical_name TEXT,
  category TEXT,
  similarity FLOAT
)
```

**Usage:** Uses HNSW index for efficient nearest-neighbor search on 384-dimensional vectors.

---

## Seeded Data

### Units (21 entries)

| Type | Units |
|------|-------|
| Volume | ml, l, tsp, tbsp, cup, fl oz, pint, quart, gallon |
| Weight | g, kg, oz, lb |
| Count | count, dozen |
| Other | pinch, bunch, clove, sprig, slice, can |

### Ingredients (58 entries)

| Category | Examples |
|----------|----------|
| Produce (16) | tomato, onion, garlic, carrot, lemon, basil, parsley, ginger |
| Dairy (10) | butter, milk, cream, cheese, egg, yogurt, sour cream |
| Protein (7) | chicken breast, beef, pork, salmon, shrimp, tofu, bacon |
| Pantry (14) | olive oil, flour, sugar, soy sauce, rice, pasta, honey |
| Spice (8) | cumin, paprika, cayenne, cinnamon, oregano, thyme |

### Substitutions (20+ entries)

| Original | Substitute | Quality | Context |
|----------|------------|---------|---------|
| butter | coconut oil | good | baking |
| sour cream | greek yogurt | perfect | any |
| lemon | lime | perfect | any |
| chicken breast | chicken thigh | perfect | cooking |
| milk | heavy cream (diluted) | good | cooking |

---

## Migration Files

- `20251231161517_init` - Core User model
- `20251231170000_add_recipe_pantry_ingredient_models` - Full schema with pgvector
- `20251231180000_add_thread_message_models` - AI chat system
- `20251231190000_rename_messages_to_chats` - Renamed messages to chats
