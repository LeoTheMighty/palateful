# Database UML Diagram (Tables & Relationships Only)

Use this to recreate in LucidChart. Arrows show foreign key direction (child -> parent).

---

## Tables by Domain

### Core
- User
- Unit

### Recipes & Ingredients
- RecipeBook
- RecipeBookUser _(join)_
- Recipe
- RecipeIngredient _(join)_
- RecipeStep
- Ingredient
- IngredientSubstitution _(join)_

### Pantry & Inventory
- Pantry
- PantryUser _(join)_
- PantryIngredient _(join)_
- CookingLog

### Calendar & Meal Planning
- MealEvent
- MealEventParticipant _(join)_
- PrepStep

### Shopping Lists
- ShoppingList
- ShoppingListItem
- ShoppingListUser _(join)_
- ShoppingListEvent

### AI & Chat
- Thread
- Chat
- Suggestion
- Notification

### Import System
- ImportJob
- ImportItem
- IngredientMatch

### OCR
- ParserJob

### Collaboration
- Invitation
- InviteLink
- Activity

### Social
- Friendship _(join)_
- FriendRequest

### Timers
- ActiveTimer

---

## Relationships

```
User ──────────< RecipeBookUser >────────── RecipeBook
                                                │
User.default_recipe_book_id ──────────> RecipeBook
                                                │
                                           Recipe ──< RecipeStep
                                                │
                                    RecipeIngredient >──── Ingredient
                                                              │
                                                     Ingredient.parent ──> Ingredient  (self-ref)
                                                              │
                                              IngredientSubstitution (ingredient, substitute)

User ──────────< PantryUser >──────────── Pantry
                                              │
                                     PantryIngredient >──── Ingredient

CookingLog ────> Recipe
CookingLog ────> Pantry

User ──────────< MealEventParticipant >──── MealEvent
MealEvent ────> Recipe
MealEvent ────> User (owner)
MealEvent ────> Pantry
MealEvent.parent_event ──> MealEvent  (self-ref, recurring)
MealEvent ──< PrepStep
PrepStep ────> Recipe

MealEvent ──< ShoppingList
ShoppingList ────> Pantry
ShoppingList ────> User (owner)
ShoppingList ──< ShoppingListItem
ShoppingList ──< ShoppingListEvent
User ──────< ShoppingListUser >────── ShoppingList

ShoppingListItem ────> Ingredient
ShoppingListItem ────> Recipe
ShoppingListItem ────> MealEvent
ShoppingListItem ────> User (checked_by)
ShoppingListItem ────> User (added_by)
ShoppingListItem ────> User (assigned_to)

ShoppingListEvent ────> User

User ──< Thread ──< Chat

User ──< Suggestion ────> Recipe
User ──< Notification ────> Suggestion

User ──< ImportJob ────> RecipeBook
ImportJob ──< ImportItem ────> Recipe (created_recipe)
IngredientMatch ────> Ingredient
IngredientMatch ────> User

User ──< ParserJob

Invitation (from_user ──── to_user)  both FK > User
Invitation ────> resource (polymorphic: recipe_book, pantry, shopping_list, meal_event)
Notification ────> Invitation (optional)
Notification ────> User (source_user, optional)

InviteLink ────> User (created_by)
InviteLink ────> resource (polymorphic: recipe_book, pantry, shopping_list, meal_event)

Activity ────> User (optional)
Activity ────> resource (polymorphic: resource_type + resource_id)

RecipeBookUser.invited_by ────> User
PantryUser.invited_by ────> User
ShoppingListUser.invited_by ────> User
MealEventParticipant.invited_by ────> User

Friendship (user ──── friend)  both FK > User
FriendRequest (from_user ──── to_user)  both FK > User

ActiveTimer ────> User
ActiveTimer ────> MealEvent
ActiveTimer ────> RecipeStep
Ingredient.submitted_by ────> User
```

---

## Visual Layout Suggestion (for LucidChart)

```
                    ┌──────────────────────────────────┐
                    │           USER (center)           │
                    └──────────────────────────────────┘
                       │      │      │      │      │
          ┌────────────┘      │      │      │      └────────────┐
          ▼                   ▼      ▼      ▼                   ▼
   ┌─────────────┐    ┌─────────┐  ┌────────┐  ┌──────────┐  ┌───────────┐
   │ RecipeBook  │    │ Pantry  │  │Thread  │  │ImportJob │  │ Social    │
   │  User(join) │    │User(jn) │  │  Chat  │  │ImportItem│  │Friendship │
   │  Recipe     │    │PantryIng│  └────────┘  │IngMatch  │  │FriendReq  │
   │  RecipeIng  │    └─────────┘              └──────────┘  └───────────┘
   │  RecipeStep │         │
   └─────────────┘         │
         │                 │
         ▼                 ▼
   ┌───────────┐    ┌────────────┐
   │Ingredient │    │CookingLog  │
   │  Substit. │    └────────────┘
   └───────────┘
         │
   ┌─────────────────────────────────────────┐
   │           MEAL PLANNING                  │
   │  MealEvent ── Participant(join)          │
   │     │                                    │
   │  PrepStep    ShoppingList                │
   │              ShoppingListItem            │
   │              ShoppingListUser(join)       │
   │              ShoppingListEvent            │
   └─────────────────────────────────────────┘

   ┌────────────────────┐    ┌──────┐
   │ Suggestion         │    │ Unit │  (standalone lookup)
   │  Notification      │    └──────┘
   └────────────────────┘

   ┌─────────────────────────────┐
   │       COLLABORATION         │
   │  Invitation                 │
   │  InviteLink                 │
   │  Activity                   │
   └─────────────────────────────┘

   ┌──────────┐   ┌─────────────┐
   │ParserJob │   │ ActiveTimer │
   └──────────┘   └─────────────┘
```

### Arrow Legend
- `──<` = one-to-many (parent ──< children)
- `──>` = foreign key points to (child ──> parent)
- `>────<` = many-to-many via join table
