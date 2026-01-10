# Recipe Book App — Part 3: Recipe Feasibility & Cooking

## Recipe Feasibility Check

`src/lib/recipes/feasibility.ts`:

```typescript
import { prisma } from '../db/prisma';

export interface IngredientStatus {
  ingredientId: string;
  ingredientName: string;
  needed: number;
  have: number;
  unit: string;
  status: 'have' | 'partial' | 'missing';
  shortfall: number;
  isOptional: boolean;
}

export interface SubstituteOption {
  substituteId: string;
  substituteName: string;
  quality: string;
  ratio: number;
  notes: string | null;
  haveAmount: number;
  canFullySubstitute: boolean;
}

export interface IngredientWithSubstitutes extends IngredientStatus {
  substitutes: SubstituteOption[];
}

export interface RecipeFeasibility {
  recipeId: string;
  recipeName: string;
  canMake: boolean;
  canMakeWithSubstitutes: boolean;
  requirements: IngredientStatus[];
  missingWithSubstitutes: IngredientWithSubstitutes[];
  shoppingList: Array<{ ingredient: string; need: number; unit: string }>;
}

export async function checkRecipeFeasibility(
  recipeId: string,
  pantryId: string,
  scale = 1
): Promise<RecipeFeasibility> {
  const recipe = await prisma.recipe.findUnique({
    where: { id: recipeId },
    include: { ingredients: { include: { ingredient: true }, orderBy: { orderIndex: 'asc' } } },
  });

  if (!recipe) throw new Error('Recipe not found');

  const pantryIngredients = await prisma.pantryIngredient.findMany({
    where: { pantryId },
    include: { ingredient: true },
  });

  const pantryMap = new Map(
    pantryIngredients.map((pi) => [pi.ingredientId, { quantity: Number(pi.quantityNormalized), unit: pi.unitNormalized }])
  );

  const requirements: IngredientStatus[] = recipe.ingredients.map((ri) => {
    const needed = Number(ri.quantityNormalized) * scale;
    const have = pantryMap.get(ri.ingredientId)?.quantity || 0;
    const status = have >= needed ? 'have' : have > 0 ? 'partial' : 'missing';

    return {
      ingredientId: ri.ingredientId,
      ingredientName: ri.ingredient.canonicalName,
      needed,
      have,
      unit: ri.unitNormalized,
      status,
      shortfall: Math.max(0, needed - have),
      isOptional: ri.isOptional,
    };
  });

  const missing = requirements.filter((r) => r.status !== 'have' && !r.isOptional);

  const missingWithSubstitutes: IngredientWithSubstitutes[] = await Promise.all(
    missing.map(async (m) => {
      const subs = await prisma.ingredientSubstitution.findMany({
        where: { ingredientId: m.ingredientId },
        include: { substitute: true },
        orderBy: { quality: 'asc' },
      });

      const substitutes: SubstituteOption[] = subs
        .map((sub) => {
          const pantryItem = pantryMap.get(sub.substituteId);
          if (!pantryItem) return null;
          
          const neededWithRatio = m.shortfall * Number(sub.ratio);
          return {
            substituteId: sub.substituteId,
            substituteName: sub.substitute.canonicalName,
            quality: sub.quality,
            ratio: Number(sub.ratio),
            notes: sub.notes,
            haveAmount: pantryItem.quantity,
            canFullySubstitute: pantryItem.quantity >= neededWithRatio,
          };
        })
        .filter((s): s is SubstituteOption => s !== null);

      return { ...m, substitutes };
    })
  );

  const canMake = missing.length === 0;
  const canMakeWithSubstitutes = missingWithSubstitutes.every((m) => m.substitutes.some((s) => s.canFullySubstitute));

  const shoppingList = missingWithSubstitutes
    .filter((m) => !m.substitutes.some((s) => s.canFullySubstitute))
    .map((m) => ({ ingredient: m.ingredientName, need: m.shortfall, unit: m.unit }));

  return { recipeId, recipeName: recipe.name, canMake, canMakeWithSubstitutes, requirements, missingWithSubstitutes, shoppingList };
}
```

---

## Cook Recipe (Deduct Ingredients)

`src/lib/recipes/cooking.ts`:

```typescript
import { prisma } from '../db/prisma';
import { checkRecipeFeasibility } from './feasibility';

export interface CookRecipeResult {
  success: boolean;
  error?: string;
  deducted?: Array<{ ingredient: string; amountUsed: number; remaining: number; unit: string }>;
  cookingLogId?: string;
}

export interface SubstituteUsage {
  ingredientId: string;
  substituteId: string;
  quantity: number;
}

export async function cookRecipe(
  recipeId: string,
  pantryId: string,
  options: { scale?: number; substitutes?: SubstituteUsage[]; notes?: string } = {}
): Promise<CookRecipeResult> {
  const { scale = 1, substitutes = [], notes } = options;

  const feasibility = await checkRecipeFeasibility(recipeId, pantryId, scale);

  if (!feasibility.canMake && !feasibility.canMakeWithSubstitutes) {
    return { success: false, error: 'Missing ingredients with no available substitutes' };
  }

  const substituteMap = new Map(substitutes.map((s) => [s.ingredientId, s]));

  return prisma.$transaction(async (tx) => {
    const deducted: CookRecipeResult['deducted'] = [];

    for (const req of feasibility.requirements) {
      if (req.isOptional && req.status === 'missing') continue;

      const sub = substituteMap.get(req.ingredientId);
      const targetId = sub?.substituteId || req.ingredientId;
      const quantityToUse = sub?.quantity || req.needed;

      const pantryItem = await tx.pantryIngredient.findUnique({
        where: { pantryId_ingredientId: { pantryId, ingredientId: targetId } },
        include: { ingredient: true },
      });

      if (!pantryItem) throw new Error(`Missing pantry item: ${targetId}`);

      const currentAmount = Number(pantryItem.quantityNormalized);
      const newAmount = currentAmount - quantityToUse;

      if (newAmount < 0) {
        throw new Error(`Not enough ${pantryItem.ingredient.canonicalName}`);
      }

      if (newAmount === 0) {
        await tx.pantryIngredient.delete({ where: { id: pantryItem.id } });
      } else {
        await tx.pantryIngredient.update({
          where: { id: pantryItem.id },
          data: { quantityNormalized: newAmount, quantityDisplay: newAmount },
        });
      }

      deducted.push({
        ingredient: pantryItem.ingredient.canonicalName,
        amountUsed: quantityToUse,
        remaining: Math.max(0, newAmount),
        unit: pantryItem.unitNormalized,
      });
    }

    const cookingLog = await tx.cookingLog.create({
      data: { recipeId, pantryId, scaleFactor: scale, notes },
    });

    return { success: true, deducted, cookingLogId: cookingLog.id };
  });
}
```

---

## API Routes

### Ingredient Search

`src/app/api/ingredients/search/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { searchIngredients, createUserIngredient } from '@/lib/ingredients/search';

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const query = params.get('q');
  
  if (!query) return NextResponse.json({ error: 'Query required' }, { status: 400 });

  const result = await searchIngredients(query, {
    fuzzyThreshold: parseFloat(params.get('fuzzyThreshold') || '0.3'),
    semanticThreshold: parseFloat(params.get('semanticThreshold') || '0.7'),
    limit: parseInt(params.get('limit') || '10'),
    includeSemantic: params.get('semantic') !== 'false',
  });

  return NextResponse.json(result);
}

export async function POST(request: NextRequest) {
  const { name, userId, category, aliases } = await request.json();
  if (!name || !userId) return NextResponse.json({ error: 'name and userId required' }, { status: 400 });
  
  const result = await createUserIngredient(name, userId, { category, aliases });
  return NextResponse.json(result, { status: 201 });
}
```

### Recipe Feasibility

`src/app/api/recipes/[id]/feasibility/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { checkRecipeFeasibility } from '@/lib/recipes/feasibility';

export async function GET(request: NextRequest, { params }: { params: { id: string } }) {
  const pantryId = request.nextUrl.searchParams.get('pantryId');
  const scale = parseFloat(request.nextUrl.searchParams.get('scale') || '1');

  if (!pantryId) return NextResponse.json({ error: 'pantryId required' }, { status: 400 });

  const feasibility = await checkRecipeFeasibility(params.id, pantryId, scale);
  return NextResponse.json(feasibility);
}
```

### Cook Recipe

`src/app/api/recipes/[id]/cook/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { cookRecipe } from '@/lib/recipes/cooking';

export async function POST(request: NextRequest, { params }: { params: { id: string } }) {
  const { pantryId, scale, substitutes, notes } = await request.json();
  if (!pantryId) return NextResponse.json({ error: 'pantryId required' }, { status: 400 });

  const result = await cookRecipe(params.id, pantryId, { scale, substitutes, notes });
  
  if (!result.success) return NextResponse.json({ error: result.error }, { status: 400 });
  return NextResponse.json(result);
}
```
