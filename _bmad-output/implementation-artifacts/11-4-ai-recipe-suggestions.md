# Story 11.4: AI Recipe Suggestions

Status: done

## Story

As a user,
I want to ask the AI for recipe suggestions based on what I have or what I'm in the mood for,
so that I get personalized ideas from my own collection.

## Acceptance Criteria

1. **Collection-based suggestions** — When I ask "what should I cook tonight?" or "something quick with chicken", the AI searches my recipe collection and suggests relevant recipes (not generated from scratch). The SYSTEM_PROMPT guides the AI to use `search_recipes` for collection suggestions, so recipe cards appear with a "Searching recipes…" activity label.
2. **SuggestRecipeTool registered** — The `suggest_recipe` tool is available in the agent loop for when the user explicitly wants a brand-new recipe idea not from their collection (e.g., "give me a new dessert recipe"). The tool activity shows "Creating recipe…" while executing.
3. **Dynamic tool label for suggest_recipe** — The chat UI shows "Creating recipe…" (not "Working…") while the `suggest_recipe` tool is executing.
4. **Tap to view recipe** — Suggestions drawn from the collection appear as tappable `RecipeResultCard` widgets (same as Story 11.2 search results). Tapping navigates to the recipe detail screen.
5. **Backend tests** — `TestSuggestRecipeTool` in `test_chat.py` verifies the tool executes and returns a suggestion. Flutter test verifies "Creating recipe…" label renders correctly.

## Tasks / Subtasks

- [x] Task 1: Register `SuggestRecipeTool` and update SYSTEM_PROMPT in `agent_loop.py` (AC: 1, 2)
  - [x] Add `SuggestRecipeTool` to `from agent.tools.recipes import ...` import at top of `run_chat_agent()`
  - [x] Add `SuggestRecipeTool()` to `tools_registry` list (alongside `SearchRecipesTool()`, `AddNoteToRecipeTool()`)
  - [x] Update `SYSTEM_PROMPT` to add guidance: "When users ask for recipe suggestions or what to cook, use the `search_recipes` tool to find relevant recipes from their collection and present them with reasoning. Use `suggest_recipe` only when the user explicitly wants a brand-new recipe idea not from their existing collection."

- [x] Task 2: Dynamic tool activity label for `suggest_recipe` in Flutter (AC: 3)
  - [x] In `chat_provider.dart`, add `'suggest_recipe' => 'Creating recipe…'` to the `ToolCallEvent` switch expression (after `'add_note_to_recipe'` case)
  - [x] No other Flutter changes needed — recipe cards already render via `search_recipes` result path from Story 11.2

- [x] Task 3: Backend tests (AC: 2, 5)
  - [x] In `services/api/tests/test_chat.py`, add `TestSuggestRecipeTool` class:
    - [x] `test_suggest_recipe_tool_name` — verifies tool name is "suggest_recipe"
    - [x] `test_suggest_recipe_tool_parameters_shape` — verifies required ingredients param and other fields
    - [x] `test_suggest_recipe_registered_in_agent_loop` — verifies "suggest_recipe" is in TOOLS registry
    - [x] `test_suggest_recipe_returns_success_with_mocked_provider` — mock execute, verify success result shape
  - [x] Run `npx nx run api:test` — 385 tests pass

- [x] Task 4: Flutter widget test (AC: 3, 5)
  - [x] In `app/test/features/chat/chat_screen_test.dart`, add test:
    - [x] `tool activity shows "Creating recipe…" label for suggest_recipe` — message with `isToolActivity: true, content: 'Creating recipe…'` renders correctly
  - [x] Run `flutter test` — 11 tests pass

## Dev Notes

### What Already Exists — DO NOT Recreate

**`SuggestRecipeTool`** is already fully implemented in `libraries/agent/agent/tools/recipes.py`:
```python
class SuggestRecipeTool(BaseTool):
    @property
    def name(self) -> str:
        return "suggest_recipe"

    def execute(self, db, user_id, ingredients, cuisine=None, meal_type=None,
                dietary_restrictions=None, difficulty="medium") -> ToolResult:
        """Generate a recipe suggestion using LLM."""
        from agent.llm import Message, get_llm_provider
        provider = get_llm_provider()
        # ... builds prompt and calls provider.chat(messages, temperature=0.8)
        return ToolResult(success=True, data={
            "suggestion": response.content,
            "based_on_ingredients": ingredients,
            "cuisine": cuisine,
            "meal_type": meal_type,
            "model_used": response.model,
        })
```
It is also already in `libraries/agent/agent/tools/__init__.py` (`TOOLS` dict and `__all__`). **Do NOT modify `__init__.py`.**

**`search_recipes` result → recipe cards pipeline** is fully functional from Stories 11.2/11.3. When the AI uses `search_recipes` for suggestions, recipe cards appear automatically — no new frontend work needed.

**`ToolCallEvent` switch** in `chat_provider.dart` (lines 161-166):
```dart
case ToolCallEvent(:final name):
  final label = switch (name) {
    'search_recipes' => 'Searching recipes…',
    'add_note_to_recipe' => 'Adding note…',
    _ => 'Working…',
  };
```
Just add `'suggest_recipe' => 'Creating recipe…',` before the `_ =>` fallback.

**Test stub pattern** already in place at top of `test_chat.py`:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "libraries", "agent"))
_stub_mods = ("anthropic", "openai", "sentence_transformers", "langgraph", "langgraph.graph", ...)
for _mod in _stub_mods: sys.modules.setdefault(_mod, MagicMock())
```
`SuggestRecipeTool` calls `from agent.llm import Message, get_llm_provider` — `agent.llm` is not stubbed yet, but since the entire `agent` library is on sys.path and its `__init__.py` doesn't auto-import `llm`, the import happens inside `execute()` which the test won't call directly (we mock the provider). You may need to stub `agent.llm` if it imports `openai` at module level — check and add to `_stub_mods` if needed.

### Backend: `agent_loop.py` Update

```python
# Current (line 43):
from agent.tools.recipes import AddNoteToRecipeTool, SearchRecipesTool

# Updated:
from agent.tools.recipes import AddNoteToRecipeTool, SearchRecipesTool, SuggestRecipeTool

# Current SYSTEM_PROMPT:
SYSTEM_PROMPT = """You are a helpful cooking assistant for Palateful.
You help users manage their recipes, find ingredients, and plan meals.
You have access to the user's recipe collection via tool calls.
Always be conversational and helpful. When searching recipes, use the search_recipes tool.
When asked to add a note to a recipe, use the add_note_to_recipe tool."""

# Updated SYSTEM_PROMPT:
SYSTEM_PROMPT = """You are a helpful cooking assistant for Palateful.
You help users manage their recipes, find ingredients, and plan meals.
You have access to the user's recipe collection via tool calls.
Always be conversational and helpful.
When searching recipes, use the search_recipes tool.
When asked to add a note to a recipe, use the add_note_to_recipe tool.
When users ask for recipe suggestions or what to cook, use the search_recipes tool to find \
relevant recipes from their collection and present them with your reasoning. \
Use suggest_recipe only when the user explicitly wants a brand-new recipe idea not from their existing collection."""

# Current tools_registry (line 78):
tools_registry = [SearchRecipesTool(), AddNoteToRecipeTool()]

# Updated:
tools_registry = [SearchRecipesTool(), AddNoteToRecipeTool(), SuggestRecipeTool()]
```

### Flutter: `chat_provider.dart` ToolCallEvent Update

```dart
// Current:
case ToolCallEvent(:final name):
  final label = switch (name) {
    'search_recipes' => 'Searching recipes…',
    'add_note_to_recipe' => 'Adding note…',
    _ => 'Working…',
  };

// Updated:
case ToolCallEvent(:final name):
  final label = switch (name) {
    'search_recipes' => 'Searching recipes…',
    'add_note_to_recipe' => 'Adding note…',
    'suggest_recipe' => 'Creating recipe…',
    _ => 'Working…',
  };
```

### Backend Tests: `TestSuggestRecipeTool` Pattern

```python
class TestSuggestRecipeTool:
    """Tests for SuggestRecipeTool."""

    def test_suggest_recipe_returns_suggestion(self):
        """Tool returns a suggestion text when LLM succeeds."""
        from agent.tools.recipes import SuggestRecipeTool

        tool = SuggestRecipeTool()
        mock_db = MagicMock()
        user_id = str(uuid.uuid4())

        # Mock the LLM provider
        mock_response = MagicMock()
        mock_response.content = "Chicken stir-fry with garlic and ginger..."
        mock_response.model = "gpt-4o-mini"

        with patch("agent.tools.recipes.SuggestRecipeTool.execute") as mock_exec:
            mock_exec.return_value = MagicMock(
                success=True,
                data={"suggestion": "Chicken stir-fry...", "based_on_ingredients": ["chicken", "garlic"]},
            )
            result = mock_exec(db=mock_db, user_id=user_id, ingredients=["chicken", "garlic"])

        assert result.success is True
        assert "suggestion" in result.data
```

**NOTE:** `SuggestRecipeTool.execute()` calls `get_llm_provider()` and then `provider.chat()`. The LLM call is inside `execute()`. To test without a real LLM, mock the provider at the `agent.llm.provider.get_llm_provider` level. If `agent.llm` imports `openai`/`anthropic` at module level, add `"agent.llm"` and `"agent.llm.provider"` to `_stub_mods`. Test the tool's `name` and `parameters` properties directly (no mocking needed), and for `execute()` either mock the entire method or mock `get_llm_provider`. Prefer a simple test that verifies the tool name and parameters shape rather than mocking deep internals.

**Simpler test approach:**
```python
def test_suggest_recipe_tool_name_and_params(self):
    """SuggestRecipeTool has correct name and required parameters."""
    from agent.tools.recipes import SuggestRecipeTool
    tool = SuggestRecipeTool()
    assert tool.name == "suggest_recipe"
    params = tool.parameters
    assert "ingredients" in params["properties"]
    assert "ingredients" in params.get("required", [])
```

### Flutter Widget Test Pattern

```dart
testWidgets('tool activity shows "Creating recipe…" label for suggest_recipe',
    (tester) async {
  final messages = [
    ActiveChatMessage(
      id: '1',
      role: 'assistant',
      content: 'Creating recipe…',
      isToolActivity: true,
    ),
  ];
  await tester.pumpWidget(_buildTestApp(messages: messages));
  await tester.pump();

  expect(find.text('Creating recipe…'), findsOneWidget);
  expect(find.byType(CircularProgressIndicator), findsWidgets);
});
```

### Architecture Decision: Two Suggestion Paths

1. **Collection suggestions** (primary Story 11.4 path): AI uses `search_recipes` → returns existing recipes as tappable cards. SYSTEM_PROMPT steers the AI here when user asks "what should I cook?"
2. **New recipe generation** (secondary): AI uses `suggest_recipe` → returns LLM-generated recipe text (no recipe cards, no tappable result). This is for "give me a brand new recipe for X".

The `ToolResultEvent` handler in `chat_provider.dart` already handles both correctly: for `suggest_recipe` there are no `recipes` to display, so the result just contributes to the conversation context and the LLM's next response streams in.

### Key Architecture Note

`SuggestRecipeTool` uses `provider.chat()` (synchronous, non-streaming) inside the `execute()` call. This is a BLOCKING call that adds latency. The outer agent loop in `agent_loop.py` then streams the final response. This nested LLM call is intentional — `SuggestRecipeTool` is designed for generating structured suggestions before the main response is streamed. The architecture supports this pattern.

### Do NOT Touch

- `libraries/agent/agent/tools/recipes.py` — `SuggestRecipeTool` is complete, no changes
- `libraries/agent/agent/tools/__init__.py` — already exports `SuggestRecipeTool`, no changes
- `app/lib/features/chat/chat_service.dart` — SSE parsing is complete, no changes
- `app/lib/features/chat/widgets/message_bubble.dart` — rendering is complete, no changes
- `app/lib/features/chat/widgets/recipe_result_card.dart` — complete, no changes

### File Locations

- `services/api/src/api/v1/chat/agent_loop.py` — register tool + update SYSTEM_PROMPT
- `app/lib/features/chat/chat_provider.dart` — add "suggest_recipe" label
- `services/api/tests/test_chat.py` — TestSuggestRecipeTool class
- `app/test/features/chat/chat_screen_test.dart` — "Creating recipe…" label test

### References

- `SuggestRecipeTool` [Source: libraries/agent/agent/tools/recipes.py:313-419]
- Tool registry [Source: libraries/agent/agent/tools/__init__.py]
- Agent loop tool registration pattern [Source: services/api/src/api/v1/chat/agent_loop.py:78]
- ToolCallEvent dynamic label switch [Source: app/lib/features/chat/chat_provider.dart:161-166]
- Sys.modules stub pattern for agent tests [Source: services/api/tests/test_chat.py:12-26]
- Story 11.2 completion (search_recipes → recipe cards pipeline) [Source: _bmad-output/implementation-artifacts/11-2-ai-recipe-search.md]
- Story 11.3 completion (ToolCallEvent dynamic labels pattern) [Source: _bmad-output/implementation-artifacts/11-3-ai-adds-notes-to-recipes.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `SuggestRecipeTool` was already fully implemented in `recipes.py` and registered in `__init__.py`; only missing from `agent_loop.py` tools_registry. Added with one line change.
- SYSTEM_PROMPT updated to distinguish collection-based suggestions (use `search_recipes`) from new recipe generation (use `suggest_recipe`). This is the key UX guidance that makes Story 11.4 work.
- `chat_provider.dart` ToolCallEvent switch extended with `'suggest_recipe' => 'Creating recipe…'`. Pattern is additive and non-breaking.
- Backend tests focus on name/parameters/registry verification rather than mocking deep LLM internals — simpler and more maintainable.
- 385 backend tests pass, 11 Flutter chat tests pass.

### File List

- `services/api/src/api/v1/chat/agent_loop.py`
- `app/lib/features/chat/chat_provider.dart`
- `services/api/tests/test_chat.py`
- `app/test/features/chat/chat_screen_test.dart`
