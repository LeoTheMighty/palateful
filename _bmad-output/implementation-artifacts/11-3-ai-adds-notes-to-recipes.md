# Story 11.3: AI Adds Notes to Recipes

Status: done

## Story

As a user,
I want to tell the AI to add a note to a recipe on my behalf,
so that I can capture ideas without navigating to the recipe and typing manually.

## Acceptance Criteria

1. **Natural language note creation** — When I say "add a note to [recipe] — try adding more garlic next time", the AI calls the `add_note_to_recipe` tool, creates the note, and confirms: "Added note to [Recipe Name]".
2. **Recipe lookup by name** — The tool accepts either a recipe UUID or a natural language recipe name; when given a name it uses semantic search to find the best match in the user's collection.
3. **User-scoped access** — The tool only attaches notes to recipes the user has access to (membership in the recipe book). Attempting to add a note to an inaccessible recipe returns an error message, never creates data.
4. **Note persisted in DB** — The created `RecipeNote` row links to the correct `recipe_id` and `created_by = user.id`. The note is visible on the recipe detail screen and in version history.
5. **Dynamic tool label in chat** — The chat UI shows "Adding note…" (not "Searching recipes…") while the `add_note_to_recipe` tool is executing.

## Tasks / Subtasks

- [x] Task 1: Create `AddNoteToRecipeTool` in `recipes.py` (AC: 1, 2, 3, 4)
  - [x] Add `AddNoteToRecipeTool` class to `libraries/agent/agent/tools/recipes.py`
  - [x] `name` = `"add_note_to_recipe"`
  - [x] Parameters: `recipe_id` (string, optional UUID), `recipe_name` (string, optional), `note_body` (string, required). At least one of `recipe_id` / `recipe_name` is required.
  - [x] If only `recipe_name` provided: run a semantic search (same pgvector/SentenceTransformer approach as `SearchRecipesTool`) limited to 1 result — use the top match
  - [x] If only `recipe_id` provided: fetch recipe directly from DB
  - [x] Check user membership in `RecipeBookUser` (same pattern as `add_recipe_note.py`) — return error if not found
  - [x] Create `RecipeNote(recipe_id=..., body=note_body, created_by=user_id)` via `db.add(note); db.flush()`
  - [x] Return `ToolResult(success=True, data={"note_id": ..., "recipe_name": ..., "recipe_id": ..., "note_body": ...})`
  - [x] On any error (recipe not found, no access, empty body): return `ToolResult(success=False, error=...)`

- [x] Task 2: Register `AddNoteToRecipeTool` in registry and agent loop (AC: 1)
  - [x] In `libraries/agent/agent/tools/__init__.py`: import `AddNoteToRecipeTool` and add to `__all__` and `TOOLS` dict
  - [x] In `services/api/src/api/v1/chat/agent_loop.py`: add `AddNoteToRecipeTool()` to `tools_registry` list
  - [x] Update SYSTEM_PROMPT to mention the tool: add "When asked to add a note to a recipe, use the add_note_to_recipe tool."

- [x] Task 3: Dynamic tool activity label in Flutter chat UI (AC: 5)
  - [x] In `chat_provider.dart`, change the hardcoded `'Searching recipes…'` in `ToolCallEvent` handler to be dynamic based on tool name
  - [x] `add_note_to_recipe` → `'Adding note…'`
  - [x] `search_recipes` → `'Searching recipes…'`
  - [x] Any other tool → `'Working…'` (generic fallback)
  - [x] Update `ToolCallEvent` in `chat_service.dart` to carry the `name` field (it already has `final String name` — just use it in the provider)

- [x] Task 4: Backend tests (AC: 1, 2, 3, 4)
  - [x] In `services/api/tests/test_chat.py`, add `TestAddNoteToRecipeTool` class:
    - [x] `test_add_note_creates_note_with_recipe_id` — mock DB, verify `RecipeNote` is created with correct `recipe_id` and `body`
    - [x] `test_add_note_by_recipe_name_uses_search` — mock search returning a recipe, verify note is created on matched recipe
    - [x] `test_add_note_returns_error_for_inaccessible_recipe` — no `RecipeBookUser` membership → `success=False`
    - [x] `test_add_note_returns_error_for_missing_recipe` — recipe not found → `success=False`
  - [x] Run `npx nx run api:test` — 380 tests pass

- [x] Task 5: Flutter widget tests (AC: 5)
  - [x] In `app/test/features/chat/chat_screen_test.dart`, add test:
    - [x] `ToolCallEvent with add_note_to_recipe shows "Adding note…"` — message with `isToolActivity: true, content: 'Adding note…'` renders correctly
    - [x] `ToolCallEvent with unknown tool shows "Working…"` — message with `isToolActivity: true, content: 'Working…'` renders correctly
  - [x] Run `flutter test` — all tests pass

## Dev Notes

### What Already Exists — DO NOT Recreate

**`RecipeNote` model** is at `libraries/utils/utils/models/recipe_note.py`:
```python
class RecipeNote(JoinsBase):
    __tablename__ = "recipe_notes"
    id: Mapped[uuid.UUID]
    recipe_id: Mapped[uuid.UUID]  # FK → recipes.id CASCADE
    body: Mapped[str]              # Text, nullable=False
    created_by: Mapped[uuid.UUID | None]  # FK → users.id SET NULL
```

**`add_recipe_note.py`** REST endpoint already exists at `services/api/src/api/v1/recipe/add_recipe_note.py`. Do NOT call this via HTTP from the tool — use the DB session directly (same pattern as `SearchRecipesTool`).

**`SearchRecipesTool`** in `libraries/agent/agent/tools/recipes.py` has the full embedding/pgvector search pattern. Reuse the same approach for recipe lookup by name in `AddNoteToRecipeTool`. When searching by name, use `limit(1)` — take top match.

**`tools_registry`** in `agent_loop.py` currently has `[SearchRecipesTool()]`. Add `AddNoteToRecipeTool()` to this list.

**`ToolCallEvent`** in `chat_service.dart` already carries `final String name`. The `chat_provider.dart` `ToolCallEvent()` handler currently ignores the name and hardcodes `'Searching recipes…'`. Use the name to select the label.

**`/recipes/:id` route** already exists. The recipe detail screen (`recipe_detail_screen.dart`) already loads notes from the API response — no changes needed there.

**Test import pattern for agent library** (from Story 11.2 completion notes):
```python
# In services/api/tests/test_chat.py — already present at top of file:
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "libraries", "agent"))
# Also already stubs: anthropic, openai, sentence_transformers, langgraph, langgraph.graph
# Add to _stub_mods tuple if AddNoteToRecipeTool imports any new packages
```

### Backend: `AddNoteToRecipeTool` Implementation Pattern

```python
class AddNoteToRecipeTool(BaseTool):
    @property
    def name(self) -> str:
        return "add_note_to_recipe"

    @property
    def description(self) -> str:
        return """Add a note to a recipe in the user's collection. Use this when the user
        wants to record a tip, variation, or observation about a recipe.
        You can identify the recipe by its UUID or by name (natural language)."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recipe_id": {
                    "type": "string",
                    "description": "UUID of the recipe to add the note to",
                },
                "recipe_name": {
                    "type": "string",
                    "description": "Name of the recipe (used for search if recipe_id not provided)",
                },
                "note_body": {
                    "type": "string",
                    "description": "Content of the note to add",
                },
            },
            "required": ["note_body"],
        }

    def execute(self, db: Session, user_id: str, note_body: str,
                recipe_id: str | None = None, recipe_name: str | None = None) -> ToolResult:
        from utils.models import Recipe, RecipeBookUser
        from utils.models.recipe_note import RecipeNote

        try:
            if not note_body.strip():
                return ToolResult(success=False, error="Note body cannot be empty")

            # Resolve recipe
            recipe = None
            if recipe_id:
                recipe = db.get(Recipe, recipe_id)
            elif recipe_name:
                # Semantic search for best match
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer(settings.embedding_model)
                query_embedding = model.encode(recipe_name).tolist()

                # Get user's book IDs
                from sqlalchemy import select
                book_query = select(RecipeBookUser.recipe_book_id).where(
                    RecipeBookUser.user_id == user_id
                )
                book_ids = [row[0] for row in db.execute(book_query).fetchall()]
                if not book_ids:
                    return ToolResult(success=False, error="User has no recipe books")

                result = db.execute(
                    select(Recipe, Recipe.embedding.cosine_distance(query_embedding).label("distance"))
                    .where(Recipe.recipe_book_id.in_(book_ids))
                    .where(Recipe.archived_at.is_(None))
                    .where(Recipe.embedding.is_not(None))
                    .order_by("distance")
                    .limit(1)
                ).fetchone()
                if result:
                    recipe = result[0]
            else:
                return ToolResult(success=False, error="Either recipe_id or recipe_name is required")

            if not recipe:
                return ToolResult(success=False, error=f"Recipe not found")

            # Verify access
            from sqlalchemy import select as sel
            membership = db.execute(
                sel(RecipeBookUser).where(
                    RecipeBookUser.user_id == user_id,
                    RecipeBookUser.recipe_book_id == recipe.recipe_book_id,
                )
            ).scalar_one_or_none()
            if not membership:
                return ToolResult(success=False, error="Recipe not found or access denied")

            # Create note
            note = RecipeNote(recipe_id=recipe.id, body=note_body.strip(), created_by=user_id)
            db.add(note)
            db.flush()

            return ToolResult(
                success=True,
                data={
                    "note_id": str(note.id),
                    "recipe_id": str(recipe.id),
                    "recipe_name": recipe.name,
                    "note_body": note_body.strip(),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

**Note**: Use `db.get(Recipe, recipe_id)` for UUID lookup and `db.add(note); db.flush()` for creation — matches the pattern in `add_recipe_note.py` which calls `self.database.create(note)` (same effect).

### Backend: `__init__.py` Update

```python
from agent.tools.recipes import AddNoteToRecipeTool, SearchRecipesTool, SuggestRecipeTool

__all__ = [
    "BaseTool", "ToolResult",
    "GetPantryTool",
    "SearchRecipesTool", "SuggestRecipeTool", "AddNoteToRecipeTool",
    "GetUserPreferencesTool",
]

TOOLS = {
    "get_pantry": GetPantryTool,
    "search_recipes": SearchRecipesTool,
    "suggest_recipe": SuggestRecipeTool,
    "add_note_to_recipe": AddNoteToRecipeTool,
    "get_user_preferences": GetUserPreferencesTool,
}
```

### Backend: `agent_loop.py` Update

```python
from agent.tools.recipes import AddNoteToRecipeTool, SearchRecipesTool

SYSTEM_PROMPT = """You are a helpful cooking assistant for Palateful.
You help users manage their recipes, find ingredients, and plan meals.
You have access to the user's recipe collection via tool calls.
Always be conversational and helpful. When searching recipes, use the search_recipes tool.
When asked to add a note to a recipe, use the add_note_to_recipe tool."""

# In run_chat_agent():
tools_registry = [SearchRecipesTool(), AddNoteToRecipeTool()]
```

### Flutter: Dynamic Tool Activity Label

In `chat_provider.dart`, the `ToolCallEvent` handler:

```dart
case ToolCallEvent(:final name):
  final label = switch (name) {
    'search_recipes' => 'Searching recipes…',
    'add_note_to_recipe' => 'Adding note…',
    _ => 'Working…',
  };
  final updated = msgs.map((m) {
    if (m.id == assistantMsg.id) {
      return m.copyWith(
        content: label,
        isToolActivity: true,
      );
    }
    return m;
  }).toList();
  state = AsyncData((tid, updated));
```

**Note**: `ToolCallEvent` already carries `final String name` (see `chat_service.dart`). The current handler pattern-matches `ToolCallEvent()` (no field binding) — change to `ToolCallEvent(:final name)` to extract the name.

### Flutter: Test Pattern for ToolCallEvent Label

```dart
testWidgets('ToolCallEvent with add_note_to_recipe shows "Adding note…"', (tester) async {
  await tester.pumpWidget(_buildTestApp());
  await tester.pump();
  // Simulate a ToolCallEvent with add_note_to_recipe through the notifier
  // The _FakeActiveChatNotifier doesn't have sendMessage wired to real events
  // — test the MessageBubble directly with isToolActivity state
  final messages = [
    ActiveChatMessage(
      id: '1',
      role: 'assistant',
      content: 'Adding note…',
      isToolActivity: true,
    ),
  ];
  await tester.pumpWidget(_buildTestApp(messages: messages));
  await tester.pump();
  expect(find.text('Adding note…'), findsOneWidget);
  expect(find.byType(CircularProgressIndicator), findsWidgets);
});
```

### Key Architecture Note

`AddNoteToRecipeTool` uses the DB session directly (not HTTP). This means:
- No HTTP request overhead
- Participates in the same transaction as the rest of the agent loop
- `db.flush()` makes the note visible within the transaction without committing
- The agent loop commits in step 7 (`database.db.commit()`)

### Do NOT Touch

- `services/api/src/api/v1/recipe/add_recipe_note.py` — REST endpoint is unchanged
- `services/api/src/api/v1/chat/send_message.py` — no changes needed
- `app/lib/features/recipe/` — recipe detail screen already loads notes from `GET /v1/recipes/:id`; no changes needed
- `app/lib/features/chat/chat_service.dart` — `ToolCallEvent` already has `name` field; no changes

### File Locations

- `libraries/agent/agent/tools/recipes.py` — add `AddNoteToRecipeTool`
- `libraries/agent/agent/tools/__init__.py` — register tool
- `services/api/src/api/v1/chat/agent_loop.py` — add to registry + update SYSTEM_PROMPT
- `app/lib/features/chat/chat_provider.dart` — dynamic tool label
- `services/api/tests/test_chat.py` — backend tests
- `app/test/features/chat/chat_screen_test.dart` — Flutter tests

### References

- `RecipeNote` model [Source: libraries/utils/utils/models/recipe_note.py]
- `AddRecipeNote` endpoint pattern [Source: services/api/src/api/v1/recipe/add_recipe_note.py]
- `SearchRecipesTool` embedding search pattern [Source: libraries/agent/agent/tools/recipes.py]
- Tool registry [Source: libraries/agent/agent/tools/__init__.py]
- Agent loop tool registration [Source: services/api/src/api/v1/chat/agent_loop.py:77]
- `ToolCallEvent` name field [Source: app/lib/features/chat/chat_service.dart:12-15]
- `chat_provider.dart` ToolCallEvent handler [Source: app/lib/features/chat/chat_provider.dart:161-171]
- Story 11.2 completion notes (agent library import pattern for tests) [Source: _bmad-output/implementation-artifacts/11-2-ai-recipe-search.md#Completion Notes]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `AddNoteToRecipeTool` uses `db.get(Recipe, recipe_id)` for UUID lookup and `db.add(note); db.flush()` for creation — matches `add_recipe_note.py` endpoint pattern, no HTTP call overhead.
- When looking up by `recipe_name`, uses same pgvector/SentenceTransformer embedding approach as `SearchRecipesTool` with `limit(1)` to get the best match.
- `chat_provider.dart` now uses Dart `switch` expression for tool label selection — `ToolCallEvent(:final name)` pattern-matches the name field.
- Backend tests for `AddNoteToRecipeTool` follow the same `sys.modules` stub pattern established in Story 11.2 for importing the agent library.

### File List

- `libraries/agent/agent/tools/recipes.py`
- `libraries/agent/agent/tools/__init__.py`
- `services/api/src/api/v1/chat/agent_loop.py`
- `app/lib/features/chat/chat_provider.dart`
- `services/api/tests/test_chat.py`
- `app/test/features/chat/chat_screen_test.dart`
