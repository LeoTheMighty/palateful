# Recipe Book App — Part 1: Prisma Schema

## Prerequisites

### Required Postgres Extensions
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- Fuzzy text matching
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector for embeddings
```

### Required Dependencies
```bash
npm install @prisma/client prisma
npm install @xenova/transformers  # For generating embeddings locally
npm install zod                   # For validation
```

---

## Complete Prisma Schema

`prisma/schema.prisma`:

```prisma
generator client {
  provider        = "prisma-client-js"
  previewFeatures = ["postgresqlExtensions"]
}

datasource db {
  provider   = "postgresql"
  url        = env("DATABASE_URL")
  extensions = [pg_trgm, vector]
}

// ============================================
// USER & AUTH
// ============================================

model User {
  id        String   @id @default(cuid())
  name      String
  email     String   @unique
  auth0Id   String   @unique @map("auth0_id")
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  pantryMemberships    PantryUser[]
  recipeBookMemberships RecipeBookUser[]
  submittedIngredients Ingredient[]      @relation("SubmittedBy")

  @@map("users")
}

// ============================================
// PANTRY SYSTEM
// ============================================

model Pantry {
  id        String   @id @default(cuid())
  name      String
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  members     PantryUser[]
  ingredients PantryIngredient[]

  @@map("pantries")
}

model PantryUser {
  id        String   @id @default(cuid())
  role      String   @default("member") // "owner" | "member"
  createdAt DateTime @default(now()) @map("created_at")

  userId   String  @map("user_id")
  user     User    @relation(fields: [userId], references: [id], onDelete: Cascade)
  pantryId String  @map("pantry_id")
  pantry   Pantry  @relation(fields: [pantryId], references: [id], onDelete: Cascade)

  @@unique([userId, pantryId])
  @@map("pantry_users")
}

model PantryIngredient {
  id                 String    @id @default(cuid())
  quantityDisplay    Decimal   @map("quantity_display") @db.Decimal(10, 3)
  unitDisplay        String    @map("unit_display")
  quantityNormalized Decimal   @map("quantity_normalized") @db.Decimal(10, 3)
  unitNormalized     String    @map("unit_normalized")
  addedAt            DateTime  @default(now()) @map("added_at")
  updatedAt          DateTime  @updatedAt @map("updated_at")
  expiresAt          DateTime? @map("expires_at")

  pantryId     String     @map("pantry_id")
  pantry       Pantry     @relation(fields: [pantryId], references: [id], onDelete: Cascade)
  ingredientId String     @map("ingredient_id")
  ingredient   Ingredient @relation(fields: [ingredientId], references: [id])

  @@unique([pantryId, ingredientId])
  @@map("pantry_ingredients")
}

// ============================================
// RECIPE SYSTEM
// ============================================

model RecipeBook {
  id          String   @id @default(cuid())
  name        String
  description String?
  isPublic    Boolean  @default(false) @map("is_public")
  createdAt   DateTime @default(now()) @map("created_at")
  updatedAt   DateTime @updatedAt @map("updated_at")

  members RecipeBookUser[]
  recipes Recipe[]

  @@map("recipe_books")
}

model RecipeBookUser {
  id        String   @id @default(cuid())
  role      String   @default("member") // "owner" | "editor" | "viewer"
  createdAt DateTime @default(now()) @map("created_at")

  userId       String     @map("user_id")
  user         User       @relation(fields: [userId], references: [id], onDelete: Cascade)
  recipeBookId String     @map("recipe_book_id")
  recipeBook   RecipeBook @relation(fields: [recipeBookId], references: [id], onDelete: Cascade)

  @@unique([userId, recipeBookId])
  @@map("recipe_book_users")
}

model Recipe {
  id           String   @id @default(cuid())
  name         String
  description  String?
  instructions String?  @db.Text
  servings     Int      @default(1)
  prepTime     Int?     @map("prep_time")  // minutes
  cookTime     Int?     @map("cook_time")  // minutes
  imageUrl     String?  @map("image_url")
  sourceUrl    String?  @map("source_url")
  createdAt    DateTime @default(now()) @map("created_at")
  updatedAt    DateTime @updatedAt @map("updated_at")

  recipeBookId String             @map("recipe_book_id")
  recipeBook   RecipeBook         @relation(fields: [recipeBookId], references: [id], onDelete: Cascade)
  ingredients  RecipeIngredient[]
  cookingLogs  CookingLog[]

  @@map("recipes")
}

model RecipeIngredient {
  id                 String  @id @default(cuid())
  quantityDisplay    Decimal @map("quantity_display") @db.Decimal(10, 3)
  unitDisplay        String  @map("unit_display")
  quantityNormalized Decimal @map("quantity_normalized") @db.Decimal(10, 3)
  unitNormalized     String  @map("unit_normalized")
  notes              String? // "finely chopped", "room temperature"
  isOptional         Boolean @default(false) @map("is_optional")
  orderIndex         Int     @default(0) @map("order_index")

  recipeId     String     @map("recipe_id")
  recipe       Recipe     @relation(fields: [recipeId], references: [id], onDelete: Cascade)
  ingredientId String     @map("ingredient_id")
  ingredient   Ingredient @relation(fields: [ingredientId], references: [id])

  @@unique([recipeId, ingredientId])
  @@map("recipe_ingredients")
}

// ============================================
// INGREDIENT SYSTEM
// ============================================

model Ingredient {
  id             String   @id @default(cuid())
  canonicalName  String   @unique @map("canonical_name")
  aliases        String[] @default([])
  category       String?  // "produce", "dairy", "protein", "pantry", "spice"
  flavorProfile  String[] @default([]) @map("flavor_profile")
  defaultUnit    String?  @map("default_unit")
  isCanonical    Boolean  @default(true) @map("is_canonical")
  pendingReview  Boolean  @default(false) @map("pending_review")
  imageUrl       String?  @map("image_url")
  createdAt      DateTime @default(now()) @map("created_at")
  updatedAt      DateTime @updatedAt @map("updated_at")

  // NOTE: embedding column added via raw SQL (vector(384))

  submittedById      String?                  @map("submitted_by_id")
  submittedBy        User?                    @relation("SubmittedBy", fields: [submittedById], references: [id])
  pantryIngredients  PantryIngredient[]
  recipeIngredients  RecipeIngredient[]
  substitutesFor     IngredientSubstitution[] @relation("SubstituteFor")
  substitutedBy      IngredientSubstitution[] @relation("SubstitutedBy")
  parentId           String?                  @map("parent_id")
  parent             Ingredient?              @relation("IngredientHierarchy", fields: [parentId], references: [id])
  children           Ingredient[]             @relation("IngredientHierarchy")

  @@map("ingredients")
}

model IngredientSubstitution {
  id       String  @id @default(cuid())
  context  String? // "baking", "cooking", "raw", "any"
  quality  String  // "perfect", "good", "workable"
  ratio    Decimal @default(1.0) @db.Decimal(5, 2)
  notes    String?

  ingredientId  String     @map("ingredient_id")
  ingredient    Ingredient @relation("SubstituteFor", fields: [ingredientId], references: [id], onDelete: Cascade)
  substituteId  String     @map("substitute_id")
  substitute    Ingredient @relation("SubstitutedBy", fields: [substituteId], references: [id], onDelete: Cascade)

  @@unique([ingredientId, substituteId, context])
  @@map("ingredient_substitutions")
}

// ============================================
// UNIT CONVERSION
// ============================================

model Unit {
  id           String  @id @default(cuid())
  name         String  @unique
  abbreviation String
  type         String  // "volume", "weight", "count", "other"
  toBaseFactor Decimal @map("to_base_factor") @db.Decimal(15, 6)
  baseUnit     String  @map("base_unit")

  @@map("units")
}

// ============================================
// COOKING HISTORY
// ============================================

model CookingLog {
  id          String   @id @default(cuid())
  scaleFactor Decimal  @default(1.0) @map("scale_factor") @db.Decimal(5, 2)
  notes       String?
  cookedAt    DateTime @default(now()) @map("cooked_at")

  recipeId String @map("recipe_id")
  recipe   Recipe @relation(fields: [recipeId], references: [id])
  pantryId String @map("pantry_id")

  @@map("cooking_logs")
}
```

---

## Post-Migration SQL

Run after `npx prisma migrate dev`:

```sql
-- Add embedding column
ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS embedding vector(384);

-- Trigram indexes for fuzzy search
CREATE INDEX IF NOT EXISTS idx_ingredients_canonical_name_trgm 
ON ingredients USING gin (canonical_name gin_trgm_ops);

-- Vector index for semantic search
CREATE INDEX IF NOT EXISTS idx_ingredients_embedding 
ON ingredients USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Fuzzy search function
CREATE OR REPLACE FUNCTION search_ingredients_fuzzy(
  search_term TEXT,
  similarity_threshold FLOAT DEFAULT 0.3,
  result_limit INT DEFAULT 10
)
RETURNS TABLE (
  id TEXT, canonical_name TEXT, aliases TEXT[], category TEXT,
  name_similarity FLOAT, alias_similarity FLOAT, best_similarity FLOAT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    i.id, i.canonical_name, i.aliases, i.category,
    similarity(i.canonical_name, search_term)::FLOAT,
    COALESCE((SELECT MAX(similarity(a, search_term)) FROM unnest(i.aliases) a), 0)::FLOAT,
    GREATEST(
      similarity(i.canonical_name, search_term),
      COALESCE((SELECT MAX(similarity(a, search_term)) FROM unnest(i.aliases) a), 0)
    )::FLOAT
  FROM ingredients i
  WHERE i.pending_review = false AND (
    similarity(i.canonical_name, search_term) > similarity_threshold
    OR EXISTS (SELECT 1 FROM unnest(i.aliases) a WHERE similarity(a, search_term) > similarity_threshold)
  )
  ORDER BY 7 DESC LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- Semantic search function
CREATE OR REPLACE FUNCTION search_ingredients_semantic(
  query_embedding vector(384),
  similarity_threshold FLOAT DEFAULT 0.7,
  result_limit INT DEFAULT 10
)
RETURNS TABLE (id TEXT, canonical_name TEXT, category TEXT, similarity FLOAT) AS $$
BEGIN
  RETURN QUERY
  SELECT i.id, i.canonical_name, i.category,
    (1 - (i.embedding <=> query_embedding))::FLOAT
  FROM ingredients i
  WHERE i.embedding IS NOT NULL AND i.pending_review = false
    AND (1 - (i.embedding <=> query_embedding)) > similarity_threshold
  ORDER BY i.embedding <=> query_embedding
  LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;
```
