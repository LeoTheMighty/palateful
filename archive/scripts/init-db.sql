-- Enable required PostgreSQL extensions for Palateful
-- pg_trgm: Fuzzy text matching for ingredient search
-- vector: pgvector for semantic embeddings search

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
