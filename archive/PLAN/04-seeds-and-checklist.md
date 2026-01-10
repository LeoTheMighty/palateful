# Recipe Book App — Part 4: Seed Scripts & Checklist

## Seed Units

`scripts/seed-units.ts`:

```typescript
import { prisma } from '../src/lib/db/prisma';
import { ALL_UNITS } from '../src/lib/units/constants';

async function seedUnits() {
  console.log('Seeding units...');
  for (const [key, unit] of Object.entries(ALL_UNITS)) {
    await prisma.unit.upsert({
      where: { name: key },
      update: {},
      create: { name: key, abbreviation: unit.abbreviations[0], type: unit.type, toBaseFactor: unit.toBase, baseUnit: unit.baseUnit },
    });
  }
  console.log('Done!');
}

seedUnits().finally(() => prisma.$disconnect());
```

---

## Seed Ingredients

`scripts/seed-ingredients.ts`:

```typescript
import { prisma } from '../src/lib/db/prisma';
import { generateEmbedding } from '../src/lib/ingredients/embeddings';

const INGREDIENTS = [
  // Produce
  { name: 'tomato', aliases: ['tomatoes', 'roma tomato'], category: 'produce', flavor: ['acidic', 'umami', 'sweet'] },
  { name: 'onion', aliases: ['onions', 'yellow onion', 'white onion'], category: 'produce', flavor: ['pungent', 'sweet'] },
  { name: 'garlic', aliases: ['garlic cloves', 'fresh garlic'], category: 'produce', flavor: ['pungent', 'savory'] },
  { name: 'carrot', aliases: ['carrots'], category: 'produce', flavor: ['sweet', 'earthy'] },
  { name: 'potato', aliases: ['potatoes', 'russet potato'], category: 'produce', flavor: ['starchy', 'mild'] },
  { name: 'lemon', aliases: ['lemons', 'lemon juice'], category: 'produce', flavor: ['acidic', 'citrus', 'bright'] },
  { name: 'lime', aliases: ['limes', 'lime juice'], category: 'produce', flavor: ['acidic', 'citrus'] },
  { name: 'scallion', aliases: ['scallions', 'green onion', 'green onions'], category: 'produce', flavor: ['mild', 'oniony'] },
  { name: 'ginger', aliases: ['fresh ginger', 'ginger root'], category: 'produce', flavor: ['spicy', 'warm'] },
  { name: 'bell pepper', aliases: ['bell peppers', 'red pepper', 'capsicum'], category: 'produce', flavor: ['sweet', 'vegetal'] },
  { name: 'jalapeño', aliases: ['jalapeno', 'jalapeños'], category: 'produce', flavor: ['spicy', 'vegetal'] },
  { name: 'cilantro', aliases: ['fresh cilantro', 'coriander leaves'], category: 'produce', flavor: ['bright', 'citrusy'] },
  { name: 'parsley', aliases: ['fresh parsley', 'flat leaf parsley'], category: 'produce', flavor: ['fresh', 'herbaceous'] },
  { name: 'basil', aliases: ['fresh basil', 'sweet basil'], category: 'produce', flavor: ['sweet', 'aromatic'] },
  { name: 'spinach', aliases: ['baby spinach', 'fresh spinach'], category: 'produce', flavor: ['mild', 'earthy'] },
  { name: 'mushroom', aliases: ['mushrooms', 'cremini', 'button mushrooms'], category: 'produce', flavor: ['earthy', 'umami'] },

  // Dairy
  { name: 'butter', aliases: ['unsalted butter', 'salted butter'], category: 'dairy', flavor: ['rich', 'creamy'] },
  { name: 'milk', aliases: ['whole milk', '2% milk'], category: 'dairy', flavor: ['creamy', 'mild'] },
  { name: 'heavy cream', aliases: ['whipping cream', 'cream'], category: 'dairy', flavor: ['rich', 'fatty'] },
  { name: 'sour cream', aliases: [], category: 'dairy', flavor: ['tangy', 'creamy'] },
  { name: 'cream cheese', aliases: [], category: 'dairy', flavor: ['tangy', 'creamy'] },
  { name: 'cheddar cheese', aliases: ['cheddar', 'sharp cheddar'], category: 'dairy', flavor: ['sharp', 'tangy'] },
  { name: 'parmesan cheese', aliases: ['parmesan', 'parmigiano reggiano'], category: 'dairy', flavor: ['nutty', 'salty', 'umami'] },
  { name: 'mozzarella', aliases: ['mozzarella cheese'], category: 'dairy', flavor: ['mild', 'milky'] },
  { name: 'egg', aliases: ['eggs', 'large egg'], category: 'dairy', flavor: ['rich', 'binding'] },
  { name: 'greek yogurt', aliases: ['plain yogurt', 'yogurt'], category: 'dairy', flavor: ['tangy', 'creamy'] },

  // Proteins
  { name: 'chicken breast', aliases: ['boneless chicken breast'], category: 'protein', flavor: ['mild', 'lean'] },
  { name: 'chicken thigh', aliases: ['chicken thighs'], category: 'protein', flavor: ['rich', 'juicy'] },
  { name: 'ground beef', aliases: ['beef mince', 'hamburger meat'], category: 'protein', flavor: ['beefy', 'rich'] },
  { name: 'bacon', aliases: ['bacon strips'], category: 'protein', flavor: ['smoky', 'salty'] },
  { name: 'salmon', aliases: ['salmon fillet'], category: 'protein', flavor: ['rich', 'fatty'] },
  { name: 'shrimp', aliases: ['prawns'], category: 'protein', flavor: ['sweet', 'briny'] },
  { name: 'tofu', aliases: ['firm tofu', 'bean curd'], category: 'protein', flavor: ['mild', 'neutral'] },

  // Pantry
  { name: 'olive oil', aliases: ['extra virgin olive oil', 'evoo'], category: 'pantry', flavor: ['fruity', 'peppery'] },
  { name: 'vegetable oil', aliases: ['canola oil', 'neutral oil'], category: 'pantry', flavor: ['neutral'] },
  { name: 'sesame oil', aliases: ['toasted sesame oil'], category: 'pantry', flavor: ['nutty', 'aromatic'] },
  { name: 'all-purpose flour', aliases: ['flour', 'ap flour'], category: 'pantry', flavor: ['neutral'] },
  { name: 'sugar', aliases: ['white sugar', 'granulated sugar'], category: 'pantry', flavor: ['sweet'] },
  { name: 'brown sugar', aliases: ['light brown sugar'], category: 'pantry', flavor: ['sweet', 'molasses'] },
  { name: 'salt', aliases: ['table salt', 'kosher salt'], category: 'pantry', flavor: ['salty'] },
  { name: 'black pepper', aliases: ['pepper', 'ground pepper'], category: 'pantry', flavor: ['spicy', 'sharp'] },
  { name: 'soy sauce', aliases: ['shoyu', 'tamari'], category: 'pantry', flavor: ['salty', 'umami'] },
  { name: 'rice vinegar', aliases: ['rice wine vinegar'], category: 'pantry', flavor: ['mild', 'acidic'] },
  { name: 'chicken broth', aliases: ['chicken stock'], category: 'pantry', flavor: ['savory', 'rich'] },
  { name: 'tomato paste', aliases: [], category: 'pantry', flavor: ['concentrated', 'umami'] },
  { name: 'canned tomatoes', aliases: ['diced tomatoes', 'crushed tomatoes'], category: 'pantry', flavor: ['acidic', 'sweet'] },
  { name: 'coconut milk', aliases: ['canned coconut milk'], category: 'pantry', flavor: ['rich', 'sweet'] },
  { name: 'rice', aliases: ['white rice', 'jasmine rice'], category: 'pantry', flavor: ['neutral', 'starchy'] },
  { name: 'pasta', aliases: ['spaghetti', 'penne'], category: 'pantry', flavor: ['neutral'] },
  { name: 'honey', aliases: [], category: 'pantry', flavor: ['sweet', 'floral'] },

  // Spices
  { name: 'cumin', aliases: ['ground cumin'], category: 'spice', flavor: ['earthy', 'warm'] },
  { name: 'paprika', aliases: ['sweet paprika'], category: 'spice', flavor: ['sweet', 'mild'] },
  { name: 'smoked paprika', aliases: ['pimenton'], category: 'spice', flavor: ['smoky', 'sweet'] },
  { name: 'cayenne pepper', aliases: ['cayenne'], category: 'spice', flavor: ['hot', 'spicy'] },
  { name: 'cinnamon', aliases: ['ground cinnamon'], category: 'spice', flavor: ['sweet', 'warm'] },
  { name: 'oregano', aliases: ['dried oregano'], category: 'spice', flavor: ['earthy', 'pungent'] },
  { name: 'thyme', aliases: ['dried thyme'], category: 'spice', flavor: ['earthy', 'floral'] },
  { name: 'red pepper flakes', aliases: ['crushed red pepper'], category: 'spice', flavor: ['spicy', 'hot'] },
];

async function seedIngredients() {
  console.log('Seeding ingredients (this takes a while for embeddings)...');
  
  for (let i = 0; i < INGREDIENTS.length; i++) {
    const ing = INGREDIENTS[i];
    process.stdout.write(`\r${i + 1}/${INGREDIENTS.length}: ${ing.name}...`);

    const existing = await prisma.ingredient.findUnique({ where: { canonicalName: ing.name } });
    if (existing) continue;

    const embedding = await generateEmbedding(ing.name);
    const ingredient = await prisma.ingredient.create({
      data: {
        canonicalName: ing.name,
        aliases: ing.aliases,
        category: ing.category,
        flavorProfile: ing.flavor,
        isCanonical: true,
        pendingReview: false,
      },
    });

    const embeddingStr = `[${embedding.join(',')}]`;
    await prisma.$executeRaw`UPDATE ingredients SET embedding = ${embeddingStr}::vector WHERE id = ${ingredient.id}`;
  }
  
  console.log('\nDone!');
}

seedIngredients().finally(() => prisma.$disconnect());
```

---

## Seed Substitutions

`scripts/seed-substitutions.ts`:

```typescript
import { prisma } from '../src/lib/db/prisma';

const SUBS = [
  // Dairy
  { from: 'butter', to: 'coconut oil', context: 'baking', quality: 'good', ratio: 1.0, notes: 'Slight coconut flavor' },
  { from: 'butter', to: 'vegetable oil', context: 'baking', quality: 'workable', ratio: 0.75, notes: 'Use 3/4 amount' },
  { from: 'milk', to: 'coconut milk', context: 'any', quality: 'good', ratio: 1.0, notes: 'Adds coconut flavor' },
  { from: 'heavy cream', to: 'coconut milk', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Use full-fat' },
  { from: 'sour cream', to: 'greek yogurt', context: 'any', quality: 'perfect', ratio: 1.0, notes: 'Nearly identical' },
  { from: 'cream cheese', to: 'greek yogurt', context: 'any', quality: 'good', ratio: 1.0, notes: 'Tangier' },

  // Alliums
  { from: 'onion', to: 'scallion', context: 'cooking', quality: 'good', ratio: 1.5, notes: 'Milder, use more' },
  { from: 'scallion', to: 'onion', context: 'cooking', quality: 'good', ratio: 0.5, notes: 'Stronger, use less' },

  // Acids
  { from: 'lemon', to: 'lime', context: 'any', quality: 'perfect', ratio: 1.0, notes: 'Nearly identical' },
  { from: 'lime', to: 'lemon', context: 'any', quality: 'perfect', ratio: 1.0, notes: 'Nearly identical' },
  { from: 'rice vinegar', to: 'white wine vinegar', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Slightly sharper' },

  // Herbs
  { from: 'parsley', to: 'cilantro', context: 'any', quality: 'workable', ratio: 1.0, notes: 'Very different flavor' },
  { from: 'thyme', to: 'oregano', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Similar earthy flavor' },

  // Oils
  { from: 'olive oil', to: 'vegetable oil', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Less flavor' },
  { from: 'vegetable oil', to: 'olive oil', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Adds flavor' },

  // Proteins
  { from: 'chicken breast', to: 'chicken thigh', context: 'cooking', quality: 'perfect', ratio: 1.0, notes: 'Juicier' },
  { from: 'chicken thigh', to: 'chicken breast', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Leaner' },
  { from: 'ground beef', to: 'ground turkey', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Leaner' },

  // Sugars
  { from: 'sugar', to: 'honey', context: 'baking', quality: 'good', ratio: 0.75, notes: 'Use 3/4, reduce liquid' },
  { from: 'brown sugar', to: 'sugar', context: 'baking', quality: 'workable', ratio: 1.0, notes: 'Missing molasses' },

  // Spices
  { from: 'paprika', to: 'smoked paprika', context: 'cooking', quality: 'good', ratio: 0.5, notes: 'Adds smokiness' },
  { from: 'cayenne pepper', to: 'red pepper flakes', context: 'cooking', quality: 'good', ratio: 2.0, notes: 'Double amount' },
];

async function seedSubstitutions() {
  console.log('Seeding substitutions...');
  let count = 0;

  for (const sub of SUBS) {
    const ingredient = await prisma.ingredient.findUnique({ where: { canonicalName: sub.from } });
    const substitute = await prisma.ingredient.findUnique({ where: { canonicalName: sub.to } });

    if (!ingredient || !substitute) {
      console.log(`Skipping: ${sub.from} -> ${sub.to}`);
      continue;
    }

    await prisma.ingredientSubstitution.upsert({
      where: { ingredientId_substituteId_context: { ingredientId: ingredient.id, substituteId: substitute.id, context: sub.context } },
      update: { quality: sub.quality, ratio: sub.ratio, notes: sub.notes },
      create: { ingredientId: ingredient.id, substituteId: substitute.id, context: sub.context, quality: sub.quality, ratio: sub.ratio, notes: sub.notes },
    });
    count++;
  }

  console.log(`Seeded ${count} substitutions`);
}

seedSubstitutions().finally(() => prisma.$disconnect());
```

---

## Implementation Checklist

### Phase 1: Database Setup
- [ ] Add `pg_trgm` and `vector` extensions to Postgres
- [ ] Create Prisma schema from Part 1
- [ ] Run `npx prisma migrate dev`
- [ ] Run post-migration SQL for indexes and functions

### Phase 2: Core Utilities
- [ ] Create `src/lib/db/prisma.ts`
- [ ] Create `src/lib/db/raw-queries.ts`
- [ ] Create `src/lib/units/constants.ts`
- [ ] Create `src/lib/units/conversion.ts`

### Phase 3: Ingredient System
- [ ] Create `src/lib/ingredients/embeddings.ts`
- [ ] Create `src/lib/ingredients/search.ts`

### Phase 4: Recipe Logic
- [ ] Create `src/lib/recipes/feasibility.ts`
- [ ] Create `src/lib/recipes/cooking.ts`

### Phase 5: Seed Scripts
- [ ] Run `npx ts-node scripts/seed-units.ts`
- [ ] Run `npx ts-node scripts/seed-ingredients.ts`
- [ ] Run `npx ts-node scripts/seed-substitutions.ts`

### Phase 6: API Routes
- [ ] Create `src/app/api/ingredients/search/route.ts`
- [ ] Create `src/app/api/recipes/[id]/feasibility/route.ts`
- [ ] Create `src/app/api/recipes/[id]/cook/route.ts`

### Phase 7: Testing
- [ ] Test fuzzy search with typos
- [ ] Test semantic search with synonyms
- [ ] Test feasibility check
- [ ] Test ingredient deduction
- [ ] Test substitution suggestions

---

## Notes for Claude Code

1. **pgvector**: Prisma doesn't natively support `vector` type. Use raw SQL for embedding operations.

2. **Embedding model**: Uses `Xenova/all-MiniLM-L6-v2` locally (~80MB download on first run).

3. **Vercel Postgres**: Check that `pg_trgm` and `vector` extensions are available.

4. **Transaction safety**: `cookRecipe` uses transactions for atomic deduction.

5. **Unit edge cases**: "1 bunch cilantro" vs "2 tbsp cilantro" can't be compared automatically.
