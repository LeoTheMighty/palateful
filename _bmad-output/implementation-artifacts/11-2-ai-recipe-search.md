# Story 11.2: AI Recipe Search

Status: done

## Story

As a user,
I want to ask the AI to find recipes in my collection using natural language,
so that I can search conversationally ("what's that chicken dish I made last month?").

## Acceptance Criteria

1. **Natural language search** — When I ask the AI about recipes ("find pasta recipes", "what's that chicken dish?"), it calls the `search_recipes` tool and returns relevant results from my collection using the Epic 5 search infrastructure (semantic/pgvector search).
2. **Recipe details in results** — Results include the recipe name, recipe book name, and key details (prep+cook time, servings).
3. **Clickable recipe cards** — Recipe results are rendered as tappable cards in the chat UI. Tapping navigates to `/recipes/:id`.
4. **Scoped to user** — Search only returns recipes from the authenticated user's recipe books (no data leakage).
5. **Recipe book name included** — The tool result includes `recipe_book_name` alongside `recipe_id` and `recipe_name`.

## Tasks / Subtasks

- [x] Task 1: Enhance `SearchRecipesTool` to include recipe book name (AC: 2, 5)
  - [x] Add `selectinload(Recipe.recipe_book)` to the base_query in `recipes.py`
  - [x] Add `"recipe_book_name": recipe.recipe_book.name` to each recipe_data dict
  - [x] Remove the separate `RecipeBook` import if not already present (use loaded relation)

- [x] Task 2: Add structured recipe data to `tool_result` SSE event (AC: 2, 3)
  - [x] In `agent_loop.py`, after executing a `search_recipes` tool call, check if the result data contains `"recipes"` key
  - [x] When tool is `search_recipes`, add `"recipes"` list to the `tool_result` SSE event — each item: `{id, name, recipe_book_name, total_time, relevance_score}`
  - [x] Keep `content` field as the truncated string for LLM history (unchanged)
  - [x] SSE event shape: `{"type": "tool_result", "id": ..., "name": "search_recipes", "content": "...", "recipes": [...]}`

- [x] Task 3: Update Flutter `ToolResultEvent` to carry structured recipes (AC: 3)
  - [x] Add `recipes: List<RecipeResult>?` to `ToolResultEvent` class in `chat_service.dart`
  - [x] Add `RecipeResult` data class: `{id, name, recipeBookName, totalTime, relevanceScore}` with `fromJson` factory
  - [x] Update SSE parsing in `sendMessage()` to extract `recipes` array from `tool_result` events

- [x] Task 4: Update `ActiveChatMessage` and `ActiveChatNotifier` to carry recipe results (AC: 3)
  - [x] Add `recipeResults: List<RecipeResult>?` field to `ActiveChatMessage` in `chat_provider.dart`
  - [x] Add `recipeResults` to `ActiveChatMessage.copyWith()`
  - [x] In `sendMessage()` of `ActiveChatNotifier`, when a `ToolResultEvent` with recipes arrives, update the last assistant message's `recipeResults` field (set `isToolActivity: false` after tool result is received with recipes)

- [x] Task 5: Render recipe result cards in `MessageBubble` (AC: 3)
  - [x] Create `app/lib/features/chat/widgets/recipe_result_card.dart` — a tappable card showing recipe name, book name, total time
  - [x] In `MessageBubble._buildContent()`: when `message.recipeResults != null && message.recipeResults!.isNotEmpty`, render a `Column` of `RecipeResultCard` widgets below the message text
  - [x] `RecipeResultCard` tap handler: `context.push('/recipes/${result.id}')`
  - [x] Use `go_router` for navigation (import `package:go_router/go_router.dart`)

- [x] Task 6: Backend tests (AC: 1, 4)
  - [x] In `services/api/tests/test_chat.py`, add `TestSearchRecipesTool` class:
    - [x] Test that `recipe_book_name` is included in the search results
    - [x] Test that recipe search is scoped to user's recipe books (empty list for user with no books)
  - [x] Run `npx nx run api:test` — 374 tests pass

- [x] Task 7: Flutter widget tests (AC: 3)
  - [x] In `app/test/features/chat/chat_screen_test.dart`, add test:
    - [x] `ActiveChatMessage` with `recipeResults` renders `RecipeResultCard` widgets
    - [x] Verify tapping a `RecipeResultCard` would navigate (use mock router or verify the card widget exists)
  - [x] Run `flutter test` — all tests pass

## Dev Notes

### What Already Exists — DO NOT Recreate

**`SearchRecipesTool` is already registered in `agent_loop.py`:**
```python
# services/api/src/api/v1/chat/agent_loop.py
tools_registry = [SearchRecipesTool()]
tool_defs = [t.to_langchain_tool() for t in tools_registry]
```
The AI will automatically call `search_recipes` when the user asks for recipe lookups. **Do NOT add another registration.**

**`tool_result` SSE event already exists** in `agent_loop.py`:
```python
yield {
    "type": "tool_result",
    "id": tc["id"],
    "name": tool_name,
    "content": tool_content[:500],
}
```
Task 2 only adds `"recipes"` to this event when `tool_name == "search_recipes"` and the result has recipes.

**`/recipes/:id` route already exists** in `app/lib/core/router/app_router.dart`:
```dart
GoRoute(
  path: '/recipes/:id',
  parentNavigatorKey: _rootNavigatorKey,
  pageBuilder: (context, state) => buildReduceMotionPage(
    context: context, state: state,
    child: RecipeDetailScreen(recipeId: id),
  ),
),
```
`RecipeResultCard` can navigate directly to this route using `context.push('/recipes/${result.id}')`.

**`ChatEvent` sealed class and SSE parsing** already in `app/lib/features/chat/chat_service.dart`. The `ToolResultEvent` only has `name: String` right now — Task 3 adds the optional `recipes` field without breaking existing code.

### Backend: How to Add `recipe_book_name` to SearchRecipesTool

The `Recipe` model has a `recipe_book: Mapped["RecipeBook"]` relationship. The RecipeBook model has `name: Mapped[str]`. Currently the query uses:
```python
.options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient))
```
Add `selectinload(Recipe.recipe_book)` to eager-load the book:
```python
.options(
    selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
    selectinload(Recipe.recipe_book),
)
```
Then in the recipe_data dict:
```python
"recipe_book_name": recipe.recipe_book.name if recipe.recipe_book else None,
```

### Backend: How to Add Structured Data to `tool_result` SSE Event

In `agent_loop.py`, after calling `result = tool.execute(...)`, the result data is available:
```python
# In the for tc in response.tool_calls: loop
result = tool.execute(db=database.db, user_id=str(user.id), **tool_args)
tool_content = result.to_message()

tool_result_event = {
    "type": "tool_result",
    "id": tc["id"],
    "name": tool_name,
    "content": tool_content[:500],
}
# Add structured recipe data if this is a search_recipes tool call
if tool_name == "search_recipes" and result.success and isinstance(result.data, dict):
    raw_recipes = result.data.get("recipes", [])
    tool_result_event["recipes"] = [
        {
            "id": r["id"],
            "name": r["name"],
            "recipe_book_name": r.get("recipe_book_name"),
            "total_time": r.get("total_time"),
            "relevance_score": r.get("relevance_score"),
        }
        for r in raw_recipes
    ]
yield tool_result_event
```

### Flutter: `ToolResultEvent` and `RecipeResult` Data Classes

```dart
// In chat_service.dart
class RecipeResult {
  final String id;
  final String name;
  final String? recipeBookName;
  final int? totalTime;
  final double? relevanceScore;

  RecipeResult({
    required this.id,
    required this.name,
    this.recipeBookName,
    this.totalTime,
    this.relevanceScore,
  });

  factory RecipeResult.fromJson(Map<String, dynamic> json) => RecipeResult(
    id: json['id'] as String,
    name: json['name'] as String,
    recipeBookName: json['recipe_book_name'] as String?,
    totalTime: json['total_time'] as int?,
    relevanceScore: (json['relevance_score'] as num?)?.toDouble(),
  );
}

class ToolResultEvent extends ChatEvent {
  final String name;
  final List<RecipeResult>? recipes;  // NEW
  ToolResultEvent(this.name, {this.recipes});
}
```

Parse in `sendMessage()` SSE loop:
```dart
case 'tool_result':
  final recipesRaw = data['recipes'] as List<dynamic>?;
  final recipes = recipesRaw
      ?.map((e) => RecipeResult.fromJson(e as Map<String, dynamic>))
      .toList();
  yield ToolResultEvent(data['name'] as String, recipes: recipes);
```

### Flutter: `ActiveChatMessage` Update

```dart
// In chat_provider.dart — add to ActiveChatMessage
class ActiveChatMessage {
  ...
  final List<RecipeResult>? recipeResults;  // NEW

  const ActiveChatMessage({
    ...
    this.recipeResults,
  });

  ActiveChatMessage copyWith({
    ...
    List<RecipeResult>? recipeResults,
  }) => ActiveChatMessage(
    ...
    recipeResults: recipeResults ?? this.recipeResults,
  );
}
```

In `ActiveChatNotifier.sendMessage()`, handle `ToolResultEvent`:
```dart
case ToolResultEvent(:final name, :final recipes):
  if (recipes != null && recipes.isNotEmpty) {
    final updated = msgs.map((m) {
      if (m.id == assistantMsg.id) {
        return m.copyWith(
          recipeResults: recipes,
          isToolActivity: false,
        );
      }
      return m;
    }).toList();
    state = AsyncData((tid, updated));
  }
```

**Important:** Riverpod 3.0.3 uses `state.value` (NOT `state.valueOrNull`). The `ToolResultEvent` handler in `sendMessage()` is currently a `break` — replace it with the recipe card update logic.

### Flutter: `RecipeResultCard` Widget

```dart
// app/lib/features/chat/widgets/recipe_result_card.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../chat_service.dart';

class RecipeResultCard extends StatelessWidget {
  final RecipeResult recipe;
  const RecipeResultCard({super.key, required this.recipe});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(top: 6),
      color: colorScheme.surface,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => context.push('/recipes/${recipe.id}'),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(recipe.name,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            fontWeight: FontWeight.w600)),
                    if (recipe.recipeBookName != null)
                      Text(recipe.recipeBookName!,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant)),
                    if (recipe.totalTime != null && recipe.totalTime! > 0)
                      Text('${recipe.totalTime} min',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }
}
```

### Flutter: `MessageBubble` Update

In `message_bubble.dart` `_buildContent()`, after rendering the text content:
```dart
Widget _buildContent(BuildContext context, ColorScheme colorScheme) {
  // ... existing isToolActivity and isStreaming checks ...

  final isUser = message.role == 'user';

  // If there are recipe results, show them as tappable cards below the text
  if (!isUser && message.recipeResults != null && message.recipeResults!.isNotEmpty) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (message.content.isNotEmpty)
          Text(message.content, style: TextStyle(color: colorScheme.onSurface)),
        ...message.recipeResults!.map((r) => RecipeResultCard(recipe: r)),
      ],
    );
  }

  return Text(
    message.content,
    style: TextStyle(
      color: isUser ? colorScheme.onPrimaryContainer : colorScheme.onSurface,
    ),
  );
}
```

### Key Architecture Note: Search Infrastructure

`SearchRecipesTool` already uses the Epic 5 semantic search infrastructure:
- pgvector cosine distance on `Recipe.embedding` field
- `SentenceTransformer(settings.embedding_model)` for query embedding
- Exact/fuzzy/semantic search NOT done in parallel in this tool — pure semantic via pgvector
- The tool is already registered and working; Story 11.2 is purely about enriching the output and rendering the results in Flutter

### Do NOT Touch

- `services/api/src/api/v1/chat/agent_loop.py` tool registration (already has `SearchRecipesTool`) — only modify the `yield tool_result_event` block
- `services/api/src/api/v1/chat/send_message.py` — no changes needed
- `services/api/src/routers/v1/chat_router.py` — no changes needed
- `app/lib/core/router/app_router.dart` — `/recipes/:id` route already exists
- `app/lib/shared/widgets/scaffold_with_bottom_nav.dart` — do NOT add nav destinations
- `app/test/widget_test.dart` — existing nav tests must still pass (285 total)

### File Locations and Patterns

Backend test file: `services/api/tests/test_chat.py` (NOT `services/api/unittests/v1/test_chat.py`) — confirmed in Story 11.1 completion notes.

Import pattern for testing SearchRecipesTool:
```python
from unittest.mock import MagicMock, patch
from agent.tools.recipes import SearchRecipesTool
```

Flutter test file location: `app/test/features/chat/chat_screen_test.dart` (extend existing file).

### References

- SearchRecipesTool [Source: libraries/agent/agent/tools/recipes.py]
- BaseTool / ToolResult pattern [Source: libraries/agent/agent/tools/base.py]
- Chat agent loop — tool_result event [Source: services/api/src/api/v1/chat/agent_loop.py:111-116]
- Recipe model + recipe_book relationship [Source: libraries/utils/utils/models/recipe.py:48-53]
- RecipeBook model name field [Source: libraries/utils/utils/models/recipe_book.py:22]
- ActiveChatMessage + sendMessage [Source: app/lib/features/chat/chat_provider.dart]
- MessageBubble widget [Source: app/lib/features/chat/widgets/message_bubble.dart]
- /recipes/:id route [Source: app/lib/core/router/app_router.dart:150-162]
- Story 11.1 completion notes [Source: _bmad-output/implementation-artifacts/11-1-ai-chat-with-tool-calling.md#Completion Notes]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `services/api/tests/test_chat.py` stubs out `anthropic`, `openai`, `sentence_transformers`, `langgraph`, and `langgraph.graph` via `sys.modules` before importing the agent library, since those packages are not installed in the api test venv. This pattern must be used for any future tests that import from `libraries/agent/`.
- `ToolResultEvent` handler in `chat_provider.dart` uses `break` after the `if` block — without it Dart's `switch` would fall through.
- `RecipeResultCard` uses `go_router` `context.push()` for navigation; the `/recipes/:id` route is already registered in `app_router.dart`.

### File List

- `libraries/agent/agent/tools/recipes.py`
- `services/api/src/api/v1/chat/agent_loop.py`
- `services/api/tests/test_chat.py`
- `app/lib/features/chat/chat_service.dart`
- `app/lib/features/chat/chat_provider.dart`
- `app/lib/features/chat/widgets/recipe_result_card.dart`
- `app/lib/features/chat/widgets/message_bubble.dart`
- `app/test/features/chat/chat_screen_test.dart`
