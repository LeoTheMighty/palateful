import { prisma } from '../src/lib/prisma';
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
  { name: 'jalapeno', aliases: ['jalapeno', 'jalapenos'], category: 'produce', flavor: ['spicy', 'vegetal'] },
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

seedIngredients()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
