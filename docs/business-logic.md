# Palateful Business Logic

## Overview

Core algorithms and business rules that power Palateful's recipe management and cooking assistance features.

---

## 1. Unit Conversion System

### Unit Types

| Type | Base Unit | Examples |
|------|-----------|----------|
| Volume | milliliter (ml) | tsp, tbsp, cup, fl oz, pint, quart, gallon, liter |
| Weight | gram (g) | oz, lb, kg |
| Count | count | dozen |
| Other | (not convertible) | pinch, bunch, clove, sprig, slice, can |

### Unit Definitions

```typescript
interface UnitDefinition {
  name: string;           // "teaspoon"
  abbreviations: string[]; // ["tsp", "teaspoon"]
  type: "volume" | "weight" | "count" | "other";
  toBase: number;         // Conversion factor to base unit
  baseUnit: string;       // "ml" for volume, "g" for weight
}
```

### Conversion Factors

#### Volume (to ml)
| Unit | Factor |
|------|--------|
| ml | 1 |
| tsp | 4.929 |
| tbsp | 14.787 |
| cup | 236.588 |
| fl oz | 29.574 |
| pint | 473.176 |
| quart | 946.353 |
| gallon | 3785.41 |
| liter | 1000 |

#### Weight (to g)
| Unit | Factor |
|------|--------|
| g | 1 |
| kg | 1000 |
| oz | 28.3495 |
| lb | 453.592 |

### Core Functions

#### `normalizeQuantity(quantity, unit)`

Converts user input to normalized base units for storage and comparison.

```typescript
function normalizeQuantity(quantity: number, unit: string): NormalizedQuantity {
  const unitDef = findUnit(unit);

  if (!unitDef || unitDef.type === "other") {
    // Non-convertible units stored as-is
    return {
      quantityNormalized: quantity,
      unitNormalized: unitDef?.baseUnit || unit.toLowerCase(),
      quantityDisplay: quantity,
      unitDisplay: unit
    };
  }

  return {
    quantityNormalized: quantity * unitDef.toBase,
    unitNormalized: unitDef.baseUnit,
    quantityDisplay: quantity,
    unitDisplay: unit
  };
}
```

**Example:**
- Input: `2 cups`
- Output: `{ quantityNormalized: 473.176, unitNormalized: "ml", quantityDisplay: 2, unitDisplay: "cups" }`

#### `convertBetweenUnits(quantity, fromUnit, toUnit)`

Converts between compatible units.

**Rules:**
- Units must be same type (volume→volume, weight→weight)
- "Other" type units cannot be converted
- Returns error if units incompatible

**Algorithm:**
1. Convert to base unit: `inBase = quantity * fromDef.toBase`
2. Convert from base to target: `result = inBase / toDef.toBase`

#### `formatQuantity(quantity, unit)`

Formats decimal quantities as fractions for display.

| Decimal | Fraction |
|---------|----------|
| 0.25 | 1/4 |
| 0.33 | 1/3 |
| 0.5 | 1/2 |
| 0.66 | 2/3 |
| 0.75 | 3/4 |

Tolerance: 0.05 for matching.

---

## 2. Ingredient Search

### Three-Tier Search Cascade

The ingredient search uses a cascading strategy for best results:

```
┌─────────────────────────────────────────────────────────────┐
│                    Search Algorithm                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. EXACT MATCH (fastest)                                   │
│     ├── Check canonical_name (case-insensitive)             │
│     └── Check aliases array                                 │
│     ↓ If found → Return immediately (confidence: 1.0)       │
│                                                              │
│  2. FUZZY MATCH (pg_trgm trigrams)                          │
│     ├── Uses search_ingredients_fuzzy() DB function         │
│     ├── Searches canonical_name AND aliases                 │
│     └── Returns similarity score (0-1)                      │
│     ↓ If best_similarity > 0.8 → Return as matched          │
│                                                              │
│  3. SEMANTIC MATCH (pgvector embeddings)                    │
│     ├── Only runs if fuzzy best < 0.6                       │
│     ├── Generates embedding for query                       │
│     ├── Uses search_ingredients_semantic() DB function      │
│     └── Vector cosine similarity (0-1)                      │
│     ↓ Filter by threshold (default 0.7)                     │
│                                                              │
│  4. COMBINE & RETURN                                         │
│     ├── Merge fuzzy + semantic results                      │
│     ├── Deduplicate by ID                                   │
│     ├── Sort by similarity descending                       │
│     └── Return top N results                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Search Options

```typescript
interface SearchOptions {
  fuzzyThreshold: number;     // Default: 0.3
  semanticThreshold: number;  // Default: 0.7
  limit: number;              // Default: 10
  includeSemantic: boolean;   // Default: true
}
```

### Response Types

| Action | Meaning | Condition |
|--------|---------|-----------|
| `matched` | Single confident match | Exact match OR fuzzy > 0.8 |
| `confirm` | Multiple suggestions | Multiple results, need user choice |
| `create_new` | No matches | No results above threshold |

### Embedding Generation

- **Model**: `Xenova/all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Normalization**: Mean pooling, L2 normalized
- **Storage**: pgvector Vector(384) column

---

## 3. Recipe Feasibility Checking

### Purpose

Determine if a recipe can be made with current pantry contents, and suggest substitutions for missing ingredients.

### Data Structures

```typescript
interface IngredientStatus {
  ingredientId: string;
  ingredientName: string;
  needed: number;        // Required amount (normalized)
  have: number;          // Available amount (normalized)
  unit: string;          // Normalized unit
  status: "have" | "partial" | "missing";
  shortfall: number;     // max(0, needed - have)
  isOptional: boolean;
}

interface SubstituteOption {
  substituteId: string;
  substituteName: string;
  quality: "perfect" | "good" | "workable";
  ratio: number;         // e.g., 0.75 = use 75% as much
  notes: string | null;
  haveAmount: number;    // Available substitute amount
  canFullySubstitute: boolean;
}

interface RecipeFeasibility {
  recipeId: string;
  recipeName: string;
  canMake: boolean;
  canMakeWithSubstitutes: boolean;
  requirements: IngredientStatus[];
  missingWithSubstitutes: (IngredientStatus & { substitutes: SubstituteOption[] })[];
  shoppingList: { ingredient: string; need: number; unit: string }[];
}
```

### Algorithm

```
checkRecipeFeasibility(recipeId, pantryId, scale = 1.0)

1. FETCH DATA
   ├── Get recipe with all ingredients
   └── Get pantry contents, build lookup map: ingredientId → {quantity, unit}

2. CALCULATE REQUIREMENTS
   For each recipe ingredient:
   ├── needed = quantityNormalized * scale
   ├── have = pantryMap[ingredientId]?.quantity || 0
   ├── status = (have >= needed) ? "have" : (have > 0) ? "partial" : "missing"
   └── shortfall = max(0, needed - have)

3. FIND MISSING (non-optional)
   missing = requirements.filter(r => r.status !== "have" && !r.isOptional)

4. CHECK SUBSTITUTES
   For each missing ingredient:
   ├── Query IngredientSubstitution table
   ├── For each substitute:
   │   ├── Check if available in pantry
   │   ├── Calculate needed_with_ratio = shortfall * ratio
   │   └── canFullySubstitute = pantry_amount >= needed_with_ratio
   └── Collect substitutes with availability info

5. DETERMINE FEASIBILITY
   ├── canMake = (missing.length === 0)
   └── canMakeWithSubstitutes = all missing have at least one full substitute

6. BUILD SHOPPING LIST
   shoppingList = missing ingredients without any full substitutes

7. RETURN RecipeFeasibility
```

### Business Rules

1. **Optional ingredients**: Can always be skipped - don't affect feasibility
2. **Partial availability**: "partial" status when some but not enough
3. **Substitution quality**: "perfect" > "good" > "workable"
4. **Substitution ratio**: Adjusts required amount (e.g., 0.75 = need less)
5. **Unit compatibility**: Only compare within same normalized unit

---

## 4. Cooking Logic

### Purpose

Execute a recipe cook, deducting ingredients from pantry and logging the event.

### Algorithm

```
cookRecipe(recipeId, pantryId, options)

Options:
  - scale: number (default 1.0)
  - substitutes: { ingredientId: substituteId, quantity: number }[]
  - notes: string | null

1. CHECK FEASIBILITY
   ├── Call checkRecipeFeasibility(recipeId, pantryId, scale)
   └── If !canMake && !canMakeWithSubstitutes → Return error

2. BUILD SUBSTITUTE MAP
   substituteMap = Map<originalIngredientId, {substituteId, quantity}>

3. BEGIN TRANSACTION

4. FOR EACH REQUIREMENT:
   ├── Skip if optional AND status === "missing"
   ├── Determine target ingredient:
   │   └── substituteMap.has(id) ? substituteMap.get(id).substituteId : id
   ├── Get quantity to deduct:
   │   └── substituteMap.has(id) ? substituteMap.get(id).quantity : needed
   ├── Fetch pantry ingredient record
   ├── Calculate new amount = current - deducted
   ├── If new_amount === 0:
   │   └── DELETE pantry ingredient record
   ├── Else:
   │   └── UPDATE pantry ingredient with new amount
   └── Track: { ingredient, amountUsed, amountRemaining }

5. CREATE COOKING LOG
   CookingLog {
     recipeId,
     pantryId,
     scaleFactor: scale,
     notes,
     cookedAt: now()
   }

6. COMMIT TRANSACTION

7. RETURN
   {
     success: true,
     deducted: [{ ingredient, amountUsed, amountRemaining }],
     cookingLogId
   }
```

### Atomicity

All ingredient deductions happen in a **single database transaction**. If any step fails, the entire operation rolls back - no partial deductions.

### Substitution Handling

When cooking with substitutes:
1. User specifies which substitutes to use via `substitutes` array
2. Deduction targets the substitute ingredient, not the original
3. Quantity may differ based on substitution ratio

---

## 5. Substitution System

### Quality Ratings

| Quality | Description | Use Case |
|---------|-------------|----------|
| perfect | Indistinguishable result | lemon ↔ lime |
| good | Minor flavor/texture difference | butter → coconut oil (baking) |
| workable | Noticeable difference but acceptable | milk → diluted cream |

### Context-Aware Substitutions

| Context | Description |
|---------|-------------|
| baking | Substitution works in baked goods |
| cooking | Substitution works in cooked dishes |
| raw | Substitution works uncooked |
| any | Works in all contexts |

### Ratio System

Substitution ratio adjusts required quantity:
- **1.0**: Use same amount
- **0.75**: Use 75% as much (substitute is stronger)
- **1.25**: Use 25% more (substitute is weaker)

**Example:**
- Recipe needs 1 cup butter
- Substitute: coconut oil, ratio 0.9
- Use: 0.9 cups coconut oil

---

## 6. Access Control

### Resource Ownership Model

```
User
  ├── owns → Pantry (via PantryUser.role = "owner")
  ├── member of → Pantry (via PantryUser.role = "member")
  ├── owns → RecipeBook (via RecipeBookUser.role = "owner")
  └── member of → RecipeBook (via RecipeBookUser.role = "editor" | "viewer")
```

### Permission Checks

| Operation | Required Role |
|-----------|---------------|
| View pantry contents | member or owner |
| Add/remove pantry items | member or owner |
| Delete pantry | owner |
| View recipes | viewer, editor, or owner |
| Edit recipes | editor or owner |
| Delete recipe book | owner |

### Query Patterns

Always filter by user membership:

```sql
-- Get user's pantries
SELECT p.* FROM pantries p
JOIN pantry_users pu ON p.id = pu.pantry_id
WHERE pu.user_id = :userId

-- Get user's recipes
SELECT r.* FROM recipes r
JOIN recipe_books rb ON r.recipe_book_id = rb.id
JOIN recipe_book_users rbu ON rb.id = rbu.recipe_book_id
WHERE rbu.user_id = :userId
```

---

## 7. AI Agent Tool Execution

### Execution Loop

```
MAX_ITERATIONS = 10

while (iterations < MAX_ITERATIONS):
    1. Call OpenAI with messages + tools
    2. If response has tool_calls:
       ├── For each tool_call:
       │   ├── Parse arguments JSON
       │   ├── Execute tool with context (userId, threadId)
       │   └── Append tool result to messages
       └── Continue loop
    3. If no tool_calls (finish_reason = "stop"):
       └── Return final response
```

### Tool Context

Every tool executor receives:

```typescript
interface ToolContext {
  userId: string;    // For access control
  threadId: string;  // For conversation context
}
```

### Tool Result Format

```typescript
interface ToolResult {
  success: boolean;
  data?: any;        // Tool-specific response
  error?: string;    // Error message if failed
}
```

### Iteration Limit

Maximum 10 tool call iterations to prevent infinite loops. If reached, returns error message.

---

## 8. Streaming Response Handling

### Server-Sent Events (SSE) Protocol

```
Event Types:
  - text: Partial assistant response
  - tool_call_start: Tool invocation beginning
  - tool_call_args: Incremental tool arguments
  - tool_call_complete: Tool call finished
  - tool_result: Tool execution result
  - done: Response complete
  - title: Auto-generated thread title
  - error: Error occurred
```

### Event Flow Example

```
→ User: "What's in my pantry?"

← data: {"type":"tool_call_start","toolCall":{"id":"call_123","name":"getPantryContents"}}
← data: {"type":"tool_call_args","toolCallId":"call_123","args":"{}"}
← data: {"type":"tool_call_complete","toolCallId":"call_123"}
← data: {"type":"tool_result","toolCallId":"call_123","result":{"success":true,"data":{...}}}
← data: {"type":"text","content":"You have "}
← data: {"type":"text","content":"15 items "}
← data: {"type":"text","content":"in your pantry..."}
← data: {"type":"done"}
```

---

## Summary: Critical Business Rules

1. **Quantities always stored in both display and normalized form**
2. **Unit conversion only within same type** (volume↔volume, weight↔weight)
3. **"Other" units (pinch, bunch) are not convertible**
4. **Recipe feasibility excludes optional ingredients from blocking**
5. **Cooking deductions are atomic** (all-or-nothing transaction)
6. **Substitution ratio adjusts required quantity**
7. **Ingredient search cascades: exact → fuzzy → semantic**
8. **Tool execution limited to 10 iterations**
9. **All data access filtered by user membership**
