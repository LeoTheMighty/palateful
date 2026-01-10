-- ============================================
-- Enable required PostgreSQL extensions
-- ============================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- CreateTable
CREATE TABLE "pantries" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "pantries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "pantry_users" (
    "id" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'member',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" TEXT NOT NULL,
    "pantry_id" TEXT NOT NULL,

    CONSTRAINT "pantry_users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "pantry_ingredients" (
    "id" TEXT NOT NULL,
    "quantity_display" DECIMAL(10,3) NOT NULL,
    "unit_display" TEXT NOT NULL,
    "quantity_normalized" DECIMAL(10,3) NOT NULL,
    "unit_normalized" TEXT NOT NULL,
    "added_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "expires_at" TIMESTAMP(3),
    "pantry_id" TEXT NOT NULL,
    "ingredient_id" TEXT NOT NULL,

    CONSTRAINT "pantry_ingredients_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recipe_books" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "is_public" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "recipe_books_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recipe_book_users" (
    "id" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'member',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" TEXT NOT NULL,
    "recipe_book_id" TEXT NOT NULL,

    CONSTRAINT "recipe_book_users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recipes" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "instructions" TEXT,
    "servings" INTEGER NOT NULL DEFAULT 1,
    "prep_time" INTEGER,
    "cook_time" INTEGER,
    "image_url" TEXT,
    "source_url" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "recipe_book_id" TEXT NOT NULL,

    CONSTRAINT "recipes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "recipe_ingredients" (
    "id" TEXT NOT NULL,
    "quantity_display" DECIMAL(10,3) NOT NULL,
    "unit_display" TEXT NOT NULL,
    "quantity_normalized" DECIMAL(10,3) NOT NULL,
    "unit_normalized" TEXT NOT NULL,
    "notes" TEXT,
    "is_optional" BOOLEAN NOT NULL DEFAULT false,
    "order_index" INTEGER NOT NULL DEFAULT 0,
    "recipe_id" TEXT NOT NULL,
    "ingredient_id" TEXT NOT NULL,

    CONSTRAINT "recipe_ingredients_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ingredients" (
    "id" TEXT NOT NULL,
    "canonical_name" TEXT NOT NULL,
    "aliases" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "category" TEXT,
    "flavor_profile" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "default_unit" TEXT,
    "is_canonical" BOOLEAN NOT NULL DEFAULT true,
    "pending_review" BOOLEAN NOT NULL DEFAULT false,
    "image_url" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "submitted_by_id" TEXT,
    "parent_id" TEXT,

    CONSTRAINT "ingredients_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ingredient_substitutions" (
    "id" TEXT NOT NULL,
    "context" TEXT,
    "quality" TEXT NOT NULL,
    "ratio" DECIMAL(5,2) NOT NULL DEFAULT 1.0,
    "notes" TEXT,
    "ingredient_id" TEXT NOT NULL,
    "substitute_id" TEXT NOT NULL,

    CONSTRAINT "ingredient_substitutions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "units" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "abbreviation" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "to_base_factor" DECIMAL(15,6) NOT NULL,
    "base_unit" TEXT NOT NULL,

    CONSTRAINT "units_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "cooking_logs" (
    "id" TEXT NOT NULL,
    "scale_factor" DECIMAL(5,2) NOT NULL DEFAULT 1.0,
    "notes" TEXT,
    "cooked_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recipe_id" TEXT NOT NULL,
    "pantry_id" TEXT NOT NULL,

    CONSTRAINT "cooking_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "pantry_users_user_id_pantry_id_key" ON "pantry_users"("user_id", "pantry_id");

-- CreateIndex
CREATE UNIQUE INDEX "pantry_ingredients_pantry_id_ingredient_id_key" ON "pantry_ingredients"("pantry_id", "ingredient_id");

-- CreateIndex
CREATE UNIQUE INDEX "recipe_book_users_user_id_recipe_book_id_key" ON "recipe_book_users"("user_id", "recipe_book_id");

-- CreateIndex
CREATE UNIQUE INDEX "recipe_ingredients_recipe_id_ingredient_id_key" ON "recipe_ingredients"("recipe_id", "ingredient_id");

-- CreateIndex
CREATE UNIQUE INDEX "ingredients_canonical_name_key" ON "ingredients"("canonical_name");

-- CreateIndex
CREATE UNIQUE INDEX "ingredient_substitutions_ingredient_id_substitute_id_contex_key" ON "ingredient_substitutions"("ingredient_id", "substitute_id", "context");

-- CreateIndex
CREATE UNIQUE INDEX "units_name_key" ON "units"("name");

-- AddForeignKey
ALTER TABLE "pantry_users" ADD CONSTRAINT "pantry_users_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "pantry_users" ADD CONSTRAINT "pantry_users_pantry_id_fkey" FOREIGN KEY ("pantry_id") REFERENCES "pantries"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "pantry_ingredients" ADD CONSTRAINT "pantry_ingredients_pantry_id_fkey" FOREIGN KEY ("pantry_id") REFERENCES "pantries"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "pantry_ingredients" ADD CONSTRAINT "pantry_ingredients_ingredient_id_fkey" FOREIGN KEY ("ingredient_id") REFERENCES "ingredients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recipe_book_users" ADD CONSTRAINT "recipe_book_users_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recipe_book_users" ADD CONSTRAINT "recipe_book_users_recipe_book_id_fkey" FOREIGN KEY ("recipe_book_id") REFERENCES "recipe_books"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recipes" ADD CONSTRAINT "recipes_recipe_book_id_fkey" FOREIGN KEY ("recipe_book_id") REFERENCES "recipe_books"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recipe_ingredients" ADD CONSTRAINT "recipe_ingredients_recipe_id_fkey" FOREIGN KEY ("recipe_id") REFERENCES "recipes"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "recipe_ingredients" ADD CONSTRAINT "recipe_ingredients_ingredient_id_fkey" FOREIGN KEY ("ingredient_id") REFERENCES "ingredients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ingredients" ADD CONSTRAINT "ingredients_submitted_by_id_fkey" FOREIGN KEY ("submitted_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ingredients" ADD CONSTRAINT "ingredients_parent_id_fkey" FOREIGN KEY ("parent_id") REFERENCES "ingredients"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ingredient_substitutions" ADD CONSTRAINT "ingredient_substitutions_ingredient_id_fkey" FOREIGN KEY ("ingredient_id") REFERENCES "ingredients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ingredient_substitutions" ADD CONSTRAINT "ingredient_substitutions_substitute_id_fkey" FOREIGN KEY ("substitute_id") REFERENCES "ingredients"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "cooking_logs" ADD CONSTRAINT "cooking_logs_recipe_id_fkey" FOREIGN KEY ("recipe_id") REFERENCES "recipes"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- ============================================
-- CUSTOM: Add embedding column for vector search
-- ============================================
ALTER TABLE "ingredients" ADD COLUMN IF NOT EXISTS "embedding" vector(384);

-- ============================================
-- CUSTOM: Trigram index for fuzzy text search
-- ============================================
CREATE INDEX IF NOT EXISTS "idx_ingredients_canonical_name_trgm"
ON "ingredients" USING gin ("canonical_name" gin_trgm_ops);

-- ============================================
-- CUSTOM: Vector index for semantic search
-- Note: ivfflat requires data to build, so we use HNSW which works on empty tables
-- ============================================
CREATE INDEX IF NOT EXISTS "idx_ingredients_embedding"
ON "ingredients" USING hnsw ("embedding" vector_cosine_ops);

-- ============================================
-- CUSTOM: Fuzzy search function
-- ============================================
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

-- ============================================
-- CUSTOM: Semantic search function
-- ============================================
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
