# Recipe Book App — Part 2: Unit Conversion & Core Utilities

## File Structure

```
src/lib/
├── db/
│   ├── prisma.ts           # Prisma singleton
│   └── raw-queries.ts      # Vector/trigram raw SQL
├── units/
│   ├── constants.ts        # Unit definitions
│   └── conversion.ts       # Conversion logic
├── ingredients/
│   ├── embeddings.ts       # Generate embeddings
│   └── search.ts           # Fuzzy + semantic search
└── recipes/
    ├── feasibility.ts      # Can-I-make-this checker
    └── cooking.ts          # Deduct ingredients
```

---

## Prisma Client Singleton

`src/lib/db/prisma.ts`:

```typescript
import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === 'development' ? ['error', 'warn'] : ['error'],
  });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
```

---

## Raw Queries for Vector/Trigram

`src/lib/db/raw-queries.ts`:

```typescript
import { prisma } from './prisma';

export interface FuzzySearchResult {
  id: string;
  canonical_name: string;
  aliases: string[];
  category: string | null;
  best_similarity: number;
}

export interface SemanticSearchResult {
  id: string;
  canonical_name: string;
  category: string | null;
  similarity: number;
}

export async function searchIngredientsFuzzy(
  searchTerm: string,
  threshold = 0.3,
  limit = 10
): Promise<FuzzySearchResult[]> {
  return prisma.$queryRaw<FuzzySearchResult[]>`
    SELECT * FROM search_ingredients_fuzzy(${searchTerm}, ${threshold}, ${limit})
  `;
}

export async function searchIngredientsSemantic(
  embedding: number[],
  threshold = 0.7,
  limit = 10
): Promise<SemanticSearchResult[]> {
  const embeddingStr = `[${embedding.join(',')}]`;
  return prisma.$queryRaw<SemanticSearchResult[]>`
    SELECT * FROM search_ingredients_semantic(${embeddingStr}::vector, ${threshold}, ${limit})
  `;
}

export async function updateIngredientEmbedding(
  ingredientId: string,
  embedding: number[]
): Promise<void> {
  const embeddingStr = `[${embedding.join(',')}]`;
  await prisma.$executeRaw`
    UPDATE ingredients SET embedding = ${embeddingStr}::vector WHERE id = ${ingredientId}
  `;
}

export async function findSimilarIngredients(
  ingredientId: string,
  limit = 5
): Promise<SemanticSearchResult[]> {
  return prisma.$queryRaw<SemanticSearchResult[]>`
    SELECT b.id, b.canonical_name, b.category,
      (1 - (a.embedding <=> b.embedding))::FLOAT as similarity
    FROM ingredients a, ingredients b
    WHERE a.id = ${ingredientId} AND b.id != ${ingredientId}
      AND a.embedding IS NOT NULL AND b.embedding IS NOT NULL
    ORDER BY a.embedding <=> b.embedding LIMIT ${limit}
  `;
}
```

---

## Unit Definitions

`src/lib/units/constants.ts`:

```typescript
export type UnitType = 'volume' | 'weight' | 'count' | 'other';

export interface UnitDefinition {
  name: string;
  abbreviations: string[];
  type: UnitType;
  toBase: number;
  baseUnit: string;
}

export const VOLUME_UNITS: Record<string, UnitDefinition> = {
  ml: { name: 'milliliter', abbreviations: ['ml', 'milliliter'], type: 'volume', toBase: 1, baseUnit: 'ml' },
  l: { name: 'liter', abbreviations: ['l', 'liter'], type: 'volume', toBase: 1000, baseUnit: 'ml' },
  tsp: { name: 'teaspoon', abbreviations: ['tsp', 'teaspoon'], type: 'volume', toBase: 4.929, baseUnit: 'ml' },
  tbsp: { name: 'tablespoon', abbreviations: ['tbsp', 'tablespoon'], type: 'volume', toBase: 14.787, baseUnit: 'ml' },
  cup: { name: 'cup', abbreviations: ['c', 'cup', 'cups'], type: 'volume', toBase: 236.588, baseUnit: 'ml' },
  floz: { name: 'fluid ounce', abbreviations: ['fl oz', 'floz'], type: 'volume', toBase: 29.574, baseUnit: 'ml' },
  pint: { name: 'pint', abbreviations: ['pt', 'pint'], type: 'volume', toBase: 473.176, baseUnit: 'ml' },
  quart: { name: 'quart', abbreviations: ['qt', 'quart'], type: 'volume', toBase: 946.353, baseUnit: 'ml' },
  gallon: { name: 'gallon', abbreviations: ['gal', 'gallon'], type: 'volume', toBase: 3785.41, baseUnit: 'ml' },
};

export const WEIGHT_UNITS: Record<string, UnitDefinition> = {
  g: { name: 'gram', abbreviations: ['g', 'gram'], type: 'weight', toBase: 1, baseUnit: 'g' },
  kg: { name: 'kilogram', abbreviations: ['kg', 'kilogram'], type: 'weight', toBase: 1000, baseUnit: 'g' },
  oz: { name: 'ounce', abbreviations: ['oz', 'ounce'], type: 'weight', toBase: 28.3495, baseUnit: 'g' },
  lb: { name: 'pound', abbreviations: ['lb', 'lbs', 'pound'], type: 'weight', toBase: 453.592, baseUnit: 'g' },
};

export const COUNT_UNITS: Record<string, UnitDefinition> = {
  count: { name: 'count', abbreviations: ['', 'count', 'piece', 'each'], type: 'count', toBase: 1, baseUnit: 'count' },
  dozen: { name: 'dozen', abbreviations: ['dozen', 'doz'], type: 'count', toBase: 12, baseUnit: 'count' },
};

export const OTHER_UNITS: Record<string, UnitDefinition> = {
  pinch: { name: 'pinch', abbreviations: ['pinch'], type: 'other', toBase: 1, baseUnit: 'pinch' },
  bunch: { name: 'bunch', abbreviations: ['bunch'], type: 'other', toBase: 1, baseUnit: 'bunch' },
  clove: { name: 'clove', abbreviations: ['clove'], type: 'other', toBase: 1, baseUnit: 'clove' },
  sprig: { name: 'sprig', abbreviations: ['sprig'], type: 'other', toBase: 1, baseUnit: 'sprig' },
  slice: { name: 'slice', abbreviations: ['slice'], type: 'other', toBase: 1, baseUnit: 'slice' },
  can: { name: 'can', abbreviations: ['can'], type: 'other', toBase: 1, baseUnit: 'can' },
};

export const ALL_UNITS = { ...VOLUME_UNITS, ...WEIGHT_UNITS, ...COUNT_UNITS, ...OTHER_UNITS };
```

---

## Unit Conversion Logic

`src/lib/units/conversion.ts`:

```typescript
import { ALL_UNITS, UnitDefinition } from './constants';

export interface NormalizedQuantity {
  quantityNormalized: number;
  unitNormalized: string;
  quantityDisplay: number;
  unitDisplay: string;
}

function findUnit(input: string): UnitDefinition | null {
  const normalized = input.toLowerCase().trim();
  for (const [key, unit] of Object.entries(ALL_UNITS)) {
    if (key === normalized || unit.abbreviations.includes(normalized)) return unit;
  }
  return null;
}

export function normalizeQuantity(quantity: number, unit: string): NormalizedQuantity {
  const unitDef = findUnit(unit);
  
  if (!unitDef || unitDef.type === 'other') {
    return {
      quantityNormalized: quantity,
      unitNormalized: unitDef?.baseUnit || unit.toLowerCase(),
      quantityDisplay: quantity,
      unitDisplay: unit,
    };
  }
  
  return {
    quantityNormalized: quantity * unitDef.toBase,
    unitNormalized: unitDef.baseUnit,
    quantityDisplay: quantity,
    unitDisplay: unit,
  };
}

export function convertBetweenUnits(
  quantity: number,
  fromUnit: string,
  toUnit: string
): { success: boolean; result?: number; error?: string } {
  const fromDef = findUnit(fromUnit);
  const toDef = findUnit(toUnit);
  
  if (!fromDef || !toDef) return { success: false, error: 'Unknown unit' };
  if (fromDef.type !== toDef.type) return { success: false, error: `Cannot convert ${fromDef.type} to ${toDef.type}` };
  if (fromDef.type === 'other') return { success: false, error: 'Cannot convert non-standard units' };
  
  const inBase = quantity * fromDef.toBase;
  return { success: true, result: inBase / toDef.toBase };
}

export function canCompareUnits(unit1: string, unit2: string): boolean {
  const def1 = findUnit(unit1);
  const def2 = findUnit(unit2);
  if (!def1 || !def2) return false;
  if (def1.type === 'other' || def2.type === 'other') return false;
  return def1.type === def2.type;
}

export function formatQuantity(quantity: number, unit: string): string {
  const fractions: Record<number, string> = {
    0.25: '¼', 0.33: '⅓', 0.5: '½', 0.66: '⅔', 0.75: '¾'
  };
  
  const whole = Math.floor(quantity);
  const decimal = quantity - whole;
  
  for (const [value, fraction] of Object.entries(fractions)) {
    if (Math.abs(decimal - parseFloat(value)) < 0.05) {
      return whole === 0 ? `${fraction} ${unit}` : `${whole} ${fraction} ${unit}`;
    }
  }
  
  return `${Math.round(quantity * 100) / 100} ${unit}`;
}
```

---

## Embedding Generation

`src/lib/ingredients/embeddings.ts`:

```typescript
import { pipeline, Pipeline } from '@xenova/transformers';

let embedder: Pipeline | null = null;

async function getEmbedder(): Promise<Pipeline> {
  if (!embedder) {
    embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
  }
  return embedder;
}

export async function generateEmbedding(text: string): Promise<number[]> {
  const model = await getEmbedder();
  const result = await model(text, { pooling: 'mean', normalize: true });
  return Array.from(result.data as Float32Array);
}

export async function generateEmbeddings(texts: string[]): Promise<number[][]> {
  const model = await getEmbedder();
  return Promise.all(texts.map(async (text) => {
    const result = await model(text, { pooling: 'mean', normalize: true });
    return Array.from(result.data as Float32Array);
  }));
}
```

---

## Ingredient Search (Combined Fuzzy + Semantic)

`src/lib/ingredients/search.ts`:

```typescript
import { prisma } from '../db/prisma';
import { searchIngredientsFuzzy, searchIngredientsSemantic } from '../db/raw-queries';
import { generateEmbedding } from './embeddings';

export interface SearchResult {
  id: string;
  canonicalName: string;
  category: string | null;
  matchType: 'exact' | 'fuzzy' | 'semantic';
  similarity: number;
}

export interface SearchResponse {
  action: 'matched' | 'confirm' | 'create_new';
  ingredient?: SearchResult;
  suggestions?: SearchResult[];
  message?: string;
}

export async function searchIngredients(
  query: string,
  options: { fuzzyThreshold?: number; semanticThreshold?: number; limit?: number; includeSemantic?: boolean } = {}
): Promise<SearchResponse> {
  const { fuzzyThreshold = 0.3, semanticThreshold = 0.7, limit = 10, includeSemantic = true } = options;
  const normalized = query.toLowerCase().trim();

  // 1. Exact match
  const exact = await prisma.ingredient.findFirst({
    where: {
      OR: [{ canonicalName: normalized }, { aliases: { has: normalized } }],
      pendingReview: false,
    },
  });

  if (exact) {
    return {
      action: 'matched',
      ingredient: { id: exact.id, canonicalName: exact.canonicalName, category: exact.category, matchType: 'exact', similarity: 1.0 },
    };
  }

  // 2. Fuzzy search
  const fuzzy = await searchIngredientsFuzzy(normalized, fuzzyThreshold, limit);
  
  if (fuzzy.length > 0 && fuzzy[0].best_similarity > 0.8) {
    return {
      action: 'matched',
      ingredient: { id: fuzzy[0].id, canonicalName: fuzzy[0].canonical_name, category: fuzzy[0].category, matchType: 'fuzzy', similarity: fuzzy[0].best_similarity },
    };
  }

  // 3. Semantic search (if fuzzy didn't find great matches)
  let semantic: { id: string; canonical_name: string; category: string | null; similarity: number }[] = [];
  if (includeSemantic && (!fuzzy[0] || fuzzy[0].best_similarity < 0.6)) {
    const embedding = await generateEmbedding(normalized);
    semantic = await searchIngredientsSemantic(embedding, semanticThreshold, limit);
  }

  // Combine results
  const results: SearchResult[] = [];
  const seen = new Set<string>();

  for (const r of fuzzy) {
    if (!seen.has(r.id)) {
      seen.add(r.id);
      results.push({ id: r.id, canonicalName: r.canonical_name, category: r.category, matchType: 'fuzzy', similarity: r.best_similarity });
    }
  }

  for (const r of semantic) {
    if (!seen.has(r.id)) {
      seen.add(r.id);
      results.push({ id: r.id, canonicalName: r.canonical_name, category: r.category, matchType: 'semantic', similarity: r.similarity });
    }
  }

  results.sort((a, b) => b.similarity - a.similarity);

  if (results.length > 0) {
    return { action: 'confirm', suggestions: results.slice(0, limit), message: `Did you mean one of these?` };
  }

  return { action: 'create_new', message: `We don't have "${query}" yet. Add it?` };
}

export async function createUserIngredient(
  name: string,
  userId: string,
  options: { category?: string; aliases?: string[] } = {}
): Promise<{ id: string; canonicalName: string }> {
  const normalized = name.toLowerCase().trim();
  const embedding = await generateEmbedding(normalized);

  const ingredient = await prisma.ingredient.create({
    data: {
      canonicalName: normalized,
      aliases: options.aliases || [],
      category: options.category,
      isCanonical: false,
      pendingReview: true,
      submittedById: userId,
    },
  });

  const embeddingStr = `[${embedding.join(',')}]`;
  await prisma.$executeRaw`UPDATE ingredients SET embedding = ${embeddingStr}::vector WHERE id = ${ingredient.id}`;

  return { id: ingredient.id, canonicalName: ingredient.canonicalName };
}
```
