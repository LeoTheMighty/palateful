import { prisma } from '../src/lib/prisma';

const SUBS = [
  // Dairy
  { from: 'butter', to: 'coconut milk', context: 'baking', quality: 'good', ratio: 1.0, notes: 'Slight coconut flavor' },
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

  // Herbs
  { from: 'parsley', to: 'cilantro', context: 'any', quality: 'workable', ratio: 1.0, notes: 'Very different flavor' },
  { from: 'thyme', to: 'oregano', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Similar earthy flavor' },

  // Oils
  { from: 'olive oil', to: 'vegetable oil', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Less flavor' },
  { from: 'vegetable oil', to: 'olive oil', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Adds flavor' },

  // Proteins
  { from: 'chicken breast', to: 'chicken thigh', context: 'cooking', quality: 'perfect', ratio: 1.0, notes: 'Juicier' },
  { from: 'chicken thigh', to: 'chicken breast', context: 'cooking', quality: 'good', ratio: 1.0, notes: 'Leaner' },

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
      where: {
        ingredientId_substituteId_context: {
          ingredientId: ingredient.id,
          substituteId: substitute.id,
          context: sub.context,
        },
      },
      update: { quality: sub.quality, ratio: sub.ratio, notes: sub.notes },
      create: {
        ingredientId: ingredient.id,
        substituteId: substitute.id,
        context: sub.context,
        quality: sub.quality,
        ratio: sub.ratio,
        notes: sub.notes,
      },
    });
    count++;
  }

  console.log(`Seeded ${count} substitutions`);
}

seedSubstitutions()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
