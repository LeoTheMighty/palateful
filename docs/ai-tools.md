# Palateful AI Tools

## Overview

Palateful uses OpenAI's function calling (tools) to give the AI assistant access to user data and recipe management capabilities.

---

## System Prompt

```
You are Palateful, a friendly and knowledgeable cooking assistant.

## Your Capabilities
- Search and browse the user's recipe collection
- Suggest new recipes based on preferences or available ingredients
- Check what recipes can be made with pantry contents
- Help organize and manage recipes
- Provide cooking tips and substitution suggestions

## Guidelines
- Be conversational, warm, and helpful
- When suggesting recipes, consider any dietary preferences mentioned
- Use tools to access real data rather than making up recipes
- If you don't have enough information, ask clarifying questions
- Format recipes nicely when displaying them
- Keep responses concise but informative

## When Using Tools
- Always use the appropriate tool to get accurate data from the user's collection
- When searching, try multiple approaches if the first doesn't yield results
- Explain what you're doing when using tools (e.g., "Let me search your recipes...")
- If a tool returns no results, suggest alternatives or offer to help create something new

## Formatting
- Use markdown for formatting when helpful
- Use bullet points for ingredient lists
- Use numbered lists for recipe steps
- Bold important information like cooking times or temperatures
```

---

## Tool Definitions

### Recipe Tools

#### searchRecipes

Search for recipes by name, ingredients, or description.

```json
{
  "name": "searchRecipes",
  "description": "Search for recipes by name, ingredients, or description. Use this when the user asks to find a recipe.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search term (recipe name or keywords)"
      },
      "ingredients": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Filter by required ingredients"
      },
      "maxCookTime": {
        "type": "number",
        "description": "Maximum total cooking time in minutes"
      },
      "limit": {
        "type": "number",
        "description": "Maximum number of results (default 5)"
      }
    }
  }
}
```

**Example Usage:**
- "Find me a chicken recipe" → `searchRecipes({ query: "chicken" })`
- "What can I make in under 30 minutes?" → `searchRecipes({ maxCookTime: 30 })`
- "Search for recipes with garlic and lemon" → `searchRecipes({ ingredients: ["garlic", "lemon"] })`

**Response:**
```json
{
  "success": true,
  "data": {
    "count": 3,
    "recipes": [
      {
        "id": "clm123...",
        "name": "Lemon Garlic Chicken",
        "description": "Crispy pan-fried chicken...",
        "prepTime": 15,
        "cookTime": 25,
        "servings": 4,
        "ingredientCount": 8
      }
    ]
  }
}
```

---

#### listRecipes

Get a paginated list of all recipes with optional filters and sorting.

```json
{
  "name": "listRecipes",
  "description": "Get a list of all recipes with optional filters and sorting. Use this to browse the recipe collection.",
  "parameters": {
    "type": "object",
    "properties": {
      "limit": {
        "type": "number",
        "description": "Max results to return (default 10)"
      },
      "offset": {
        "type": "number",
        "description": "Pagination offset"
      },
      "sortBy": {
        "type": "string",
        "enum": ["name", "createdAt", "cookTime", "prepTime"],
        "description": "Field to sort by"
      },
      "sortOrder": {
        "type": "string",
        "enum": ["asc", "desc"],
        "description": "Sort direction"
      }
    }
  }
}
```

**Example Usage:**
- "Show me my recipes" → `listRecipes({ limit: 10 })`
- "What recipes did I add recently?" → `listRecipes({ sortBy: "createdAt", sortOrder: "desc" })`
- "List my quickest recipes" → `listRecipes({ sortBy: "cookTime", sortOrder: "asc" })`

**Response:**
```json
{
  "success": true,
  "data": {
    "recipes": [...],
    "total": 47,
    "limit": 10,
    "offset": 0
  }
}
```

---

#### getRecipeDetails

Get full details of a specific recipe including all ingredients and instructions.

```json
{
  "name": "getRecipeDetails",
  "description": "Get full details of a specific recipe including all ingredients and instructions.",
  "parameters": {
    "type": "object",
    "properties": {
      "recipeId": {
        "type": "string",
        "description": "The unique ID of the recipe"
      }
    },
    "required": ["recipeId"]
  }
}
```

**Example Usage:**
- "Tell me more about that chicken recipe" → `getRecipeDetails({ recipeId: "clm123..." })`

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "clm123...",
    "name": "Lemon Garlic Chicken",
    "description": "Crispy pan-fried chicken with bright lemon and garlic flavors",
    "instructions": "1. Season chicken with salt and pepper...",
    "prepTime": 15,
    "cookTime": 25,
    "servings": 4,
    "sourceUrl": "https://...",
    "ingredients": [
      {
        "name": "chicken breast",
        "quantity": 2,
        "unit": "lb",
        "notes": "boneless, skinless",
        "isOptional": false
      },
      {
        "name": "lemon",
        "quantity": 2,
        "unit": "count",
        "notes": "juiced",
        "isOptional": false
      }
    ]
  }
}
```

---

#### suggestRecipe

Generate a new recipe suggestion based on user preferences or available ingredients.

```json
{
  "name": "suggestRecipe",
  "description": "Generate a new recipe suggestion based on user preferences or available ingredients. The AI will create a recipe, not fetch from database.",
  "parameters": {
    "type": "object",
    "properties": {
      "preferences": {
        "type": "string",
        "description": "User preferences (cuisine, dietary restrictions, flavor profile)"
      },
      "availableIngredients": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Ingredients the user has available"
      },
      "mealType": {
        "type": "string",
        "enum": ["breakfast", "lunch", "dinner", "snack", "dessert"],
        "description": "Type of meal"
      },
      "difficulty": {
        "type": "string",
        "enum": ["easy", "medium", "hard"],
        "description": "Desired difficulty level"
      }
    }
  }
}
```

**Example Usage:**
- "Suggest a vegetarian dinner" → `suggestRecipe({ preferences: "vegetarian", mealType: "dinner" })`
- "What can I make with chicken, rice, and broccoli?" → `suggestRecipe({ availableIngredients: ["chicken", "rice", "broccoli"] })`

**Note:** This tool signals the AI to generate a recipe. The response is a prompt to generate, not database data.

**Response:**
```json
{
  "success": true,
  "data": {
    "instruction": "Generate a recipe based on these parameters",
    "parameters": {
      "preferences": "vegetarian",
      "mealType": "dinner",
      "difficulty": "easy"
    }
  }
}
```

The AI then generates a recipe in the following format:

```markdown
**Vegetarian Stir-Fry**

*A quick and healthy vegetable stir-fry with tofu*

**Prep Time:** 15 minutes | **Cook Time:** 10 minutes | **Servings:** 4

**Ingredients:**
- 1 block firm tofu, pressed and cubed
- 2 cups mixed vegetables
- 3 tbsp soy sauce
...

**Instructions:**
1. Press tofu for 15 minutes to remove excess moisture
2. Heat oil in a wok over high heat
...

**Tips:** For crispier tofu, freeze and thaw before pressing.
```

---

### Pantry Tools

#### getPantryContents

Get list of ingredients currently in the user's pantry.

```json
{
  "name": "getPantryContents",
  "description": "Get list of ingredients currently in the user's pantry.",
  "parameters": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "enum": ["produce", "dairy", "protein", "pantry", "spice"],
        "description": "Filter by ingredient category"
      }
    }
  }
}
```

**Example Usage:**
- "What's in my pantry?" → `getPantryContents({})`
- "What produce do I have?" → `getPantryContents({ category: "produce" })`

**Response:**
```json
{
  "success": true,
  "data": {
    "totalItems": 15,
    "byCategory": {
      "produce": [
        { "name": "tomato", "quantity": 4, "unit": "count", "pantry": "My Pantry" },
        { "name": "onion", "quantity": 2, "unit": "count", "pantry": "My Pantry" }
      ],
      "dairy": [
        { "name": "butter", "quantity": 1, "unit": "cup", "pantry": "My Pantry" }
      ],
      "protein": [
        { "name": "chicken breast", "quantity": 2, "unit": "lb", "pantry": "My Pantry" }
      ]
    }
  }
}
```

---

#### checkRecipeFeasibility

Check if a recipe can be made with current pantry contents.

```json
{
  "name": "checkRecipeFeasibility",
  "description": "Check if a recipe can be made with current pantry contents. Shows what ingredients are available, missing, or can be substituted.",
  "parameters": {
    "type": "object",
    "properties": {
      "recipeId": {
        "type": "string",
        "description": "The recipe ID to check"
      },
      "scale": {
        "type": "number",
        "description": "Scale factor for the recipe (default 1)"
      }
    },
    "required": ["recipeId"]
  }
}
```

**Example Usage:**
- "Can I make the chicken recipe?" → `checkRecipeFeasibility({ recipeId: "clm123..." })`
- "Can I make double the pasta recipe?" → `checkRecipeFeasibility({ recipeId: "clm456...", scale: 2 })`

**Response:**
```json
{
  "success": true,
  "data": {
    "recipeName": "Lemon Garlic Chicken",
    "canMake": false,
    "canMakeWithSubstitutes": true,
    "summary": {
      "have": 5,
      "partial": 1,
      "missing": 2
    },
    "missingIngredients": [
      { "ingredient": "lemon", "need": 2, "unit": "count" },
      { "ingredient": "fresh parsley", "need": 0.25, "unit": "cup" }
    ],
    "substitutionOptions": [
      {
        "ingredient": "lemon",
        "substitutes": [
          {
            "name": "lime",
            "quality": "perfect",
            "canFullySubstitute": true
          }
        ]
      }
    ]
  }
}
```

---

#### addToPantry

Add an ingredient to the user's pantry.

```json
{
  "name": "addToPantry",
  "description": "Add an ingredient to the user's pantry.",
  "parameters": {
    "type": "object",
    "properties": {
      "ingredientName": {
        "type": "string",
        "description": "Name of the ingredient to add"
      },
      "quantity": {
        "type": "number",
        "description": "Amount to add"
      },
      "unit": {
        "type": "string",
        "description": "Unit of measurement (cups, lbs, oz, etc.)"
      }
    },
    "required": ["ingredientName", "quantity", "unit"]
  }
}
```

**Example Usage:**
- "Add 2 pounds of chicken to my pantry" → `addToPantry({ ingredientName: "chicken", quantity: 2, unit: "lbs" })`
- "I bought a dozen eggs" → `addToPantry({ ingredientName: "eggs", quantity: 12, unit: "count" })`

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Added 2 lbs of chicken to your pantry"
  }
}
```

**Error Response (ingredient not found):**
```json
{
  "success": false,
  "error": "Ingredient \"xyz\" not found in our database. Please use a known ingredient name."
}
```

---

## Planned Tools (Future)

### Recipe Management

| Tool | Description |
|------|-------------|
| `createRecipe` | Add a new recipe to user's recipe book |
| `updateRecipe` | Modify an existing recipe |
| `deleteRecipe` | Remove a recipe |
| `importRecipeFromUrl` | Import recipe from a URL |

### Suggestion & Discovery

| Tool | Description |
|------|-------------|
| `suggestRecipeFromPantry` | "What can I make with what I have?" |
| `surpriseMe` | Random recipe based on taste profile |
| `suggestVariation` | "How could I change this recipe?" |
| `findSimilarRecipes` | Find recipes like a given one |

### Cooking & Logging

| Tool | Description |
|------|-------------|
| `logCooking` | Record that user cooked a recipe |
| `rateRecipe` | Rate a recipe after cooking |
| `addNoteToRecipe` | Add comment/note to a recipe |

### Meal Planning

| Tool | Description |
|------|-------------|
| `planMeals` | Create weekly meal plan |
| `generateShoppingList` | List from recipes minus pantry |

---

## Tool Execution Flow

### Sequence Diagram

```
User                    API                     OpenAI                  Tools
  │                      │                        │                       │
  │  "What's in my       │                        │                       │
  │   pantry?"           │                        │                       │
  ├─────────────────────▶│                        │                       │
  │                      │   Chat completion      │                       │
  │                      │   with tools           │                       │
  │                      ├───────────────────────▶│                       │
  │                      │                        │                       │
  │                      │   tool_calls:          │                       │
  │                      │   getPantryContents    │                       │
  │                      │◀───────────────────────┤                       │
  │                      │                        │                       │
  │                      │   Execute tool         │                       │
  │                      ├───────────────────────────────────────────────▶│
  │                      │                        │                       │
  │                      │   Tool result          │                       │
  │                      │◀───────────────────────────────────────────────┤
  │                      │                        │                       │
  │                      │   Continue with        │                       │
  │                      │   tool result          │                       │
  │                      ├───────────────────────▶│                       │
  │                      │                        │                       │
  │                      │   Final response       │                       │
  │                      │◀───────────────────────┤                       │
  │                      │                        │                       │
  │  Streamed response   │                        │                       │
  │◀─────────────────────┤                        │                       │
  │                      │                        │                       │
```

### Multiple Tool Calls

The AI may call multiple tools in sequence:

```
User: "Can I make any quick chicken recipes?"

1. searchRecipes({ query: "chicken", maxCookTime: 30 })
   → Returns 3 recipes

2. getPantryContents({})
   → Returns pantry items

3. checkRecipeFeasibility({ recipeId: "..." })  (for each recipe)
   → Returns feasibility for each

AI: "I found 3 chicken recipes under 30 minutes. Based on your pantry,
     you can make 'Lemon Garlic Chicken' right now! You're only missing
     parsley, but you could substitute with cilantro..."
```

---

## Error Handling

### Tool Error Response Format

```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

### Common Errors

| Error | Cause | AI Behavior |
|-------|-------|-------------|
| Recipe not found | Invalid recipeId | Inform user, offer to search |
| No pantry found | User hasn't set up pantry | Offer to create one |
| Ingredient not found | Unknown ingredient name | Suggest alternatives |
| Access denied | User doesn't own resource | Explain limitation |

### Max Iterations

Tools loop is limited to 10 iterations. If exceeded:
- Loop terminates
- AI responds: "I encountered an issue processing your request. Please try again."

---

## Configuration

### Environment Variables

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini  # or gpt-4o for smarter responses
```

### Model Options

| Model | Use Case | Cost |
|-------|----------|------|
| `gpt-4o-mini` | Default, fast, cheap | Lower |
| `gpt-4o` | Complex reasoning | Higher |

---

## Testing Tools

### Manual Testing

```bash
# Create a thread
curl -X POST http://localhost:3000/api/chat/threads \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Send a message (SSE response)
curl -N http://localhost:3000/api/chat/threads/$THREAD_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "What is in my pantry?"}'
```

### Expected Tool Calls

| User Message | Expected Tool |
|--------------|---------------|
| "What's in my pantry?" | `getPantryContents` |
| "Find pasta recipes" | `searchRecipes` |
| "Show me all my recipes" | `listRecipes` |
| "Can I make the carbonara?" | `checkRecipeFeasibility` |
| "I bought milk" | `addToPantry` |
| "Suggest a quick dinner" | `suggestRecipe` |
