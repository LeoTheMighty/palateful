# Story 11.5: AI in Cooking Mode — Questions & Answers

Status: done

## Story

As a user,
I want to ask the AI questions about my recipe's ingredients, steps, or history while I'm cooking,
so that I get instant answers without leaving cooking mode.

## Acceptance Criteria

1. **AI entry point in cooking mode** — A chat icon button is visible in the cooking mode header. Tapping it opens a bottom sheet chat overlay. The button is hidden when offline (`_isOffline == true`).
2. **Recipe context injection** — When sending a message from cooking mode, the full recipe context (name, ingredients with quantities, all steps with numbers, current step index) is included. The backend appends this to the system prompt so the AI can reference specific recipe details.
3. **Chat bottom sheet** — The `CookModeChatSheet` bottom sheet shows a scrollable message list and a text input. It manages its own thread (creates one on first message) and SSE streaming. Uses the dark cooking mode theme (chocolate background, warm ivory text).
4. **Non-disruptive interaction** — The bottom sheet overlays on top of cooking mode. Dismissing it returns to cooking mode without navigating away. Step navigation and timers continue running behind the sheet.
5. **Backend recipe_context support** — `SendMessageParams` accepts an optional `recipe_context` field. `run_chat_agent()` appends it to the system prompt when present. The SYSTEM_PROMPT is updated to mention cooking mode context.
6. **Tests** — Backend tests verify `recipe_context` is appended to system messages. Flutter widget tests verify the AI button renders in cooking mode header and is hidden when offline.

## Tasks / Subtasks

- [x] Task 1: Backend — Add `recipe_context` to `SendMessageParams` and `run_chat_agent()` (AC: 2, 5)
  - [x]In `services/api/src/api/v1/chat/send_message.py`: add `recipe_context: str | None = Field(None, max_length=5000)` to `SendMessageParams`
  - [x]In `services/api/src/api/v1/chat/send_message.py`: pass `params.recipe_context` to `run_chat_agent()` as new kwarg `recipe_context`
  - [x]In `services/api/src/api/v1/chat/agent_loop.py`: add `recipe_context: str | None = None` parameter to `run_chat_agent()` signature
  - [x]In `run_chat_agent()`: when building messages, if `recipe_context` is not None, construct `system_content = SYSTEM_PROMPT + "\n\n--- Current Recipe Context ---\n" + recipe_context`; otherwise use `SYSTEM_PROMPT` alone. Use this as the system message content.
  - [x]Update `SYSTEM_PROMPT` to add: "When the user is cooking and asks questions about the current recipe, use the recipe context provided to answer. Reference specific ingredients, steps, and quantities."

- [x] Task 2: Flutter — Add `recipeContext` parameter to `ChatService.sendMessage()` (AC: 2)
  - [x]In `app/lib/features/chat/chat_service.dart`: update `sendMessage(String threadId, String text)` signature to `sendMessage(String threadId, String text, {String? recipeContext})`
  - [x]In the `_dio.post` data map: add `if (recipeContext != null) 'recipe_context': recipeContext`
  - [x]In `app/lib/features/chat/chat_provider.dart`: update `sendMessage(String text)` call to pass through (no recipeContext — default null for non-cooking-mode usage)

- [x] Task 3: Flutter — Create `CookModeChatSheet` widget (AC: 3, 4)
  - [x]Create `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart`
  - [x]StatefulWidget that accepts `recipeId`, `recipeName`, `recipeContext` (the context string)
  - [x]Internal state: `_threadId` (null until first message), `_messages` (list of simple message objects), `_isLoading`, `_controller` (TextEditingController)
  - [x]On first `_sendMessage()`: call `ChatService.createThread(title: 'Cooking: $recipeName')` to get threadId, then call `ChatService.sendMessage(threadId, text, recipeContext: recipeContext)`
  - [x]Stream SSE events: `TokenEvent` appends to assistant message content, `DoneEvent` finalizes, `ErrorEvent` shows error. `ToolCallEvent` / `ToolResultEvent` handled same as `ActiveChatNotifier` pattern (tool activity label, recipe cards).
  - [x]UI: Dark theme matching cooking mode — `AppColors.chocolateDark` background, `AppColors.warmIvory` text, `AppColors.terracotta` accent. Drag handle at top, scrollable message list, TextField + send button at bottom.
  - [x]Sheet height: 70% of screen (`isScrollControlled: true`, `DraggableScrollableSheet` or fixed height via `FractionallySizedBox`)
  - [x]Dismissible by swiping down or tapping outside

- [x] Task 4: Flutter — Add AI button to cooking mode header (AC: 1, 4)
  - [x]In `cook_mode_screen.dart` `_buildHeader()`: add an AI chat `IconButton` (use `Icons.smart_toy` or `Icons.chat_bubble_outline`) between the recipe name and the offline indicator
  - [x]Only show when `!_isOffline` (AI requires network)
  - [x]On tap: call `_showAIChatSheet()` method
  - [x]`_showAIChatSheet()` opens `showModalBottomSheet` with `CookModeChatSheet` passing recipe context
  - [x]Build recipe context string from `_recipe`, `_ingredients`, `_steps`, `_currentStep`: format as "Recipe: {name}\nIngredients:\n- {qty} {unit} {name}\n...\nSteps:\n1. {instruction}\n...\nCurrently on step {n} of {total}."

- [x] Task 5: Backend tests (AC: 5, 6)
  - [x]In `services/api/tests/test_chat.py`: add `TestRecipeContext` class:
    - [x]`test_send_message_params_accepts_recipe_context` — verify `SendMessageParams(message="test", recipe_context="ctx")` is valid
    - [x]`test_send_message_params_works_without_recipe_context` — verify `SendMessageParams(message="test")` is valid (backward compatible)
  - [x]Run `npx nx run api:test` — all tests pass

- [x] Task 6: Flutter widget tests (AC: 1, 6)
  - [x]In `app/test/features/chat/chat_screen_test.dart` or a new test file: add tests:
    - [x]Test that CookModeScreen header shows AI button when online (mock recipe loaded)
    - [x]Test that CookModeScreen header hides AI button when offline
  - [x]Run `flutter test` — all tests pass

## Dev Notes

### What Already Exists — DO NOT Recreate

**`ChatService`** at `app/lib/features/chat/chat_service.dart` — complete SSE streaming client. `sendMessage()` returns `Stream<ChatEvent>`. All event types (Token, ToolCall, ToolResult, Done, Error) are parsed. Just add `recipeContext` optional param.

**`SendMessageParams`** at `services/api/src/api/v1/chat/send_message.py`:
```python
class SendMessageParams(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
```
Add `recipe_context: str | None = Field(None, max_length=5_000)`.

**`run_chat_agent()`** at `services/api/src/api/v1/chat/agent_loop.py`:
```python
async def run_chat_agent(
    thread_id: str,
    user_message: str,
    user,
    database,
) -> AsyncGenerator[dict[str, Any]]:
```
Add `recipe_context: str | None = None` parameter. When building the system message:
```python
system_content = SYSTEM_PROMPT
if recipe_context:
    system_content += "\n\n--- Current Recipe Context ---\n" + recipe_context
messages = [Message(role="system", content=system_content)]
```

**`send_message_stream()`** at `services/api/src/api/v1/chat/send_message.py`:
```python
async def send_message_stream(thread_id, params, user, database):
    ...
    async for event in run_chat_agent(
        thread_id=thread_id,
        user_message=params.message,
        user=user,
        database=database,
    ):
```
Add `recipe_context=params.recipe_context` to the call.

**`CookModeScreen._buildHeader()`** at `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` (line 507):
```dart
Widget _buildHeader() {
  return Container(
    child: Row(children: [
      // Back button
      IconButton(icon: const Icon(Icons.arrow_back, ...), ...),
      // Recipe name
      Expanded(child: Text(_recipe?['name'] ?? 'Recipe', ...)),
      // Offline indicator
      if (_isOffline) ...[/* wifi_off icon */],
      // Cooking time
      Container(/* timer display */),
      // Close button
      IconButton(icon: const Icon(Icons.close, ...), ...),
    ]),
  );
}
```
Add AI button between recipe name Expanded and offline indicator:
```dart
// AI chat button (only when online)
if (!_isOffline)
  IconButton(
    icon: const Icon(Icons.chat_bubble_outline, color: AppColors.warmIvory),
    onPressed: _showAIChatSheet,
    constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
    padding: EdgeInsets.zero,
  ),
```

**PostCookFeedbackSheet pattern** at `app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart` — existing bottom sheet in cooking mode. Use the same `showModalBottomSheet` pattern with `AppColors.chocolateDark` background.

**Cooking mode theme** — `AppColors.chocolate` (#4A3728) background, `AppColors.warmIvory` (#F5ECD7) text, `AppColors.terracotta` accent, `AppColors.chocolateDark` for cards/sheets. 64dp minimum touch targets.

**CookModeScreen state** — `_recipe` (Map<String, dynamic>?), `_ingredients` (List<dynamic>), `_steps` (List<String>), `_currentStep` (int), `_isOffline` (bool). All available for building recipe context string.

### Backend: Recipe Context Format

The client builds a text string from recipe data:
```
Recipe: Chicken Pasta
Servings: 4

Ingredients:
- 2 chicken breasts, diced
- 3 cloves garlic, minced
- 200g penne pasta
- 2 tbsp olive oil

Steps:
1. Cook pasta according to package directions
2. Heat olive oil in a large skillet over medium-high heat
3. Add chicken and cook until golden, about 5 minutes
4. Add garlic and sautee for 1 minute
5. Combine pasta with chicken and serve

Currently on step 3 of 5.
```

### Backend: SYSTEM_PROMPT Update

```python
SYSTEM_PROMPT = (
    "You are a helpful cooking assistant for Palateful. "
    "You help users manage their recipes, find ingredients, and plan meals. "
    "You have access to the user's recipe collection via tool calls. "
    "Always be conversational and helpful. "
    "When searching recipes, use the search_recipes tool. "
    "When asked to add a note to a recipe, use the add_note_to_recipe tool. "
    "When users ask for recipe suggestions or what to cook, use the search_recipes tool "
    "to find relevant recipes from their collection and present them with your reasoning. "
    "Use suggest_recipe only when the user explicitly wants a brand-new recipe idea "
    "not from their existing collection. "
    "When the user is cooking and asks questions about the current recipe, "
    "use the recipe context provided to answer. Reference specific ingredients, "
    "steps, and quantities. Keep answers concise and practical."
)
```

### Flutter: CookModeChatSheet Design

```dart
class CookModeChatSheet extends StatefulWidget {
  final String recipeId;
  final String recipeName;
  final String recipeContext;

  const CookModeChatSheet({
    super.key,
    required this.recipeId,
    required this.recipeName,
    required this.recipeContext,
  });

  @override
  State<CookModeChatSheet> createState() => _CookModeChatSheetState();
}

class _CookModeChatSheetState extends State<CookModeChatSheet> {
  final _chatService = ChatService(getIt<ApiClient>().dio);
  final _controller = TextEditingController();
  final _scrollController = ScrollController();

  String? _threadId;
  final List<_SheetMessage> _messages = [];
  bool _isSending = false;

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isSending) return;
    _controller.clear();

    // Create thread on first message
    _threadId ??= (await _chatService.createThread(
      title: 'Cooking: ${widget.recipeName}',
    )).id;

    setState(() {
      _messages.add(_SheetMessage(role: 'user', content: text));
      _messages.add(_SheetMessage(role: 'assistant', content: '', isStreaming: true));
      _isSending = true;
    });
    _scrollToBottom();

    try {
      await for (final event in _chatService.sendMessage(
        _threadId!, text, recipeContext: widget.recipeContext,
      )) {
        if (!mounted) break;
        switch (event) {
          case TokenEvent(:final content):
            setState(() => _messages.last.content += content);
          case ToolCallEvent(:final name):
            // Show tool activity (optional for cooking mode)
            break;
          case ToolResultEvent():
            break;
          case DoneEvent():
            setState(() => _messages.last.isStreaming = false);
          case ErrorEvent(:final message):
            setState(() {
              _messages.last.content = 'Error: $message';
              _messages.last.isStreaming = false;
            });
        }
      }
    } catch (e) {
      if (mounted) setState(() {
        _messages.last.content = 'Error: $e';
        _messages.last.isStreaming = false;
      });
    }
    if (mounted) setState(() => _isSending = false);
  }
  // ... build() renders dark-themed message list + input field
}
```

### Flutter: Building Recipe Context String

In `_CookModeScreenState`:
```dart
String _buildRecipeContext() {
  final buf = StringBuffer();
  buf.writeln('Recipe: ${_recipe?['name'] ?? 'Unknown'}');
  if (_recipe?['servings'] != null) buf.writeln('Servings: ${_recipe!['servings']}');
  buf.writeln();
  buf.writeln('Ingredients:');
  for (final ing in _ingredients) {
    final qty = ing['quantity_display'] ?? '';
    final unit = ing['unit_display'] ?? '';
    final name = ing['name'] ?? ing['original_text'] ?? '';
    final notes = ing['notes'] ?? '';
    buf.writeln('- $qty $unit $name${notes.isNotEmpty ? ' ($notes)' : ''}'.trim());
  }
  buf.writeln();
  buf.writeln('Steps:');
  for (var i = 0; i < _steps.length; i++) {
    buf.writeln('${i + 1}. ${_steps[i]}');
  }
  buf.writeln();
  buf.writeln('Currently on step ${_currentStep + 1} of ${_steps.length}.');
  return buf.toString();
}
```

### Do NOT Touch

- `libraries/agent/agent/tools/recipes.py` — no new tools needed
- `libraries/agent/agent/tools/__init__.py` — no changes
- `app/lib/features/chat/chat_provider.dart` — ActiveChatNotifier unchanged (CookModeChatSheet manages its own state)
- `app/lib/features/chat/widgets/message_bubble.dart` — unchanged
- `app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart` — reference only
- `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart` — unchanged
- `app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart` — unchanged

### File Locations

- `services/api/src/api/v1/chat/send_message.py` — add recipe_context param
- `services/api/src/api/v1/chat/agent_loop.py` — add recipe_context to run_chat_agent + SYSTEM_PROMPT update
- `app/lib/features/chat/chat_service.dart` — add recipeContext to sendMessage()
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — add AI button + _showAIChatSheet + _buildRecipeContext
- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` — NEW: bottom sheet chat widget
- `services/api/tests/test_chat.py` — TestRecipeContext tests
- `app/test/features/recipes/cook_mode/cook_mode_screen_test.dart` — Flutter widget tests (may need new file)

### References

- `CookModeScreen` header and state [Source: app/lib/features/recipes/cook_mode/cook_mode_screen.dart:507-584]
- `PostCookFeedbackSheet` bottom sheet pattern [Source: app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart]
- `ChatService.sendMessage()` SSE streaming [Source: app/lib/features/chat/chat_service.dart:138-186]
- `SendMessageParams` [Source: services/api/src/api/v1/chat/send_message.py:12-13]
- `run_chat_agent()` [Source: services/api/src/api/v1/chat/agent_loop.py:39-185]
- `send_message_stream()` [Source: services/api/src/api/v1/chat/send_message.py:16-40]
- `SYSTEM_PROMPT` [Source: services/api/src/api/v1/chat/agent_loop.py:12-21]
- Chat router endpoint [Source: services/api/src/routers/v1/chat_router.py:60-68]
- Recipe model fields [Source: libraries/utils/utils/models/recipe.py]
- Recipe step model [Source: libraries/utils/utils/models/recipe_step.py]
- Story 11.4 completion (tool label pattern) [Source: _bmad-output/implementation-artifacts/11-4-ai-recipe-suggestions.md]
- Story 6.5 PostCookFeedbackSheet pattern [Source: _bmad-output/implementation-artifacts/6-5-post-cook-feedback-flow.md]
- Cooking mode dark theme [Source: app/lib/core/theme/app_colors.dart]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `recipe_context` added to `SendMessageParams` as optional field (max 5000 chars). Backward compatible — existing clients unaffected.
- `run_chat_agent()` appends recipe context to SYSTEM_PROMPT when provided, creating cooking-mode-aware system message.
- `ChatService.sendMessage()` accepts optional `recipeContext` parameter, included in POST body only when non-null.
- `CookModeChatSheet` is self-contained StatefulWidget managing its own thread and message state. Uses `ChatService` directly (not Riverpod ActiveChatNotifier) to avoid mixing state management patterns with StatefulWidget-based CookModeScreen.
- AI button in cook mode header uses `Icons.chat_bubble_outline` with 64dp touch target (matching cooking mode gesture requirements from Story 6.2).
- Recipe context string built from `_recipe`, `_ingredients`, `_steps`, `_currentStep` — includes all ingredients with quantities and all steps with numbers.
- 388 backend tests pass, 7 cook mode tests + 11 chat tests pass.

### File List

- `services/api/src/api/v1/chat/send_message.py`
- `services/api/src/api/v1/chat/agent_loop.py`
- `app/lib/features/chat/chat_service.dart`
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` (NEW)
- `services/api/tests/test_chat.py`
- `app/test/cook_mode_test.dart`
