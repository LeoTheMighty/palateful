# Story cmrc-1 — Delete chat sheet + header button + rebalance

Status: done

Epic: `_bmad-output/planning-artifacts/epic-cook-mode-remove-chat.md`

## Context snapshot (verified at dev time, 2026-04-22)

Re-grepped ground truth before implementing because the epic was refined 2026-04-22 and file content can drift. Current state:

- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` exists (446 lines, speech-to-text + streaming chat via `ChatService`). **Delete entirely.**
- `cook_mode_screen.dart` imports chat sheet at **line 16** (still matches epic).
- `_showAIChatSheet` method at **line 494** (still matches).
- `CookModeChatSheet(...)` constructor call at **line 499** (still matches).
- `_buildRecipeContext()` helper at **lines 466–492** — its only caller is `_showAIChatSheet` on line 502 (`recipeContext: _buildRecipeContext()`). Delete along with the sheet.
- Header chat button `IconButton(Icons.chat_bubble_outline, …)` in `_buildHeader` at **lines 736–745** (epic said 736–741 but the block is actually 5 lines longer; epic line range is close but off by the `tooltip: 'Ask AI'` trailing field). The `if (!_isOffline)` conditional at `:737` gates ONLY the chat button — safe to remove the entire conditional block.
- No `GoRoute` for chat in `app/lib/core/router/app_router.dart` — chat was always modal; epic is correct.

**Test files with chat references** (verified via grep):
- `app/test/cook_mode_test.dart` — the ONLY test file with chat references. Import at line 5; assertions at lines 151–179 (online/offline-visibility pair), 209–216 (importability test), 218–245 + 247–268 (mic-button-in-sheet-context tests — these are mic IconButton UI patterns that CookModeChatSheet happened to contain; they don't reference CookModeChatSheet directly, so they need judgment). After chat sheet removal, those mic tests are orphaned — their purpose was documenting the chat sheet's voice input pattern. Delete them with the rest of the chat cleanup in cmrc-2.

**Backend chat route comment (AC5) — adjustment required:**

Epic AC5 assumes a `/v1/recipes/{id}/chat` route exists at `services/api/src/api/v1/recipe/`. Reality:

- There is no `/v1/recipes/{id}/chat` endpoint.
- The chat backend is a generic threads API: `POST /chat/threads`, `POST /chat/threads/{id}/messages`, etc. — under `services/api/src/routers/v1/chat_router.py` + `services/api/src/api/v1/chat/`.
- These routes have **multiple Flutter consumers**, not just cook mode: `app/lib/features/chat/chat_provider.dart`, `app/lib/features/chat/chat_service.dart`, `app/lib/features/chat/widgets/recipe_result_card.dart`, and `app/lib/features/profile/profile_screen.dart` (entry point at `/chat/:threadId`).

Adding "Flutter consumer deliberately removed" on the backend would be misleading — the consumer we're removing is one of several, and the others remain active. **AC5 is a no-op on its own terms and is skipped.** The cook-mode removal leaves no backend footprint. Documented here so a future reviewer doesn't re-open the epic trying to find the missing comment.

## Acceptance criteria + implementation plan

**AC1** ✅ — Delete `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` via `git rm`.

**AC2** ✅ — Remove from `cook_mode_screen.dart`:
- Import at `:16` (`import 'widgets/cook_mode_chat_sheet.dart';`)
- `_showAIChatSheet` method (`:494–505`)
- `_buildRecipeContext()` method (`:466–492`) — sole caller was `_showAIChatSheet`

Verify with `grep -niE "chat|CookModeChatSheet|_showAIChatSheet" app/lib/features/recipes/cook_mode/cook_mode_screen.dart` returning 0 lines.

**AC3** ✅ — In `_buildHeader`, remove:
```dart
// AI chat button (only when online)
if (!_isOffline)
  IconButton(
    icon: Icon(Icons.chat_bubble_outline,
        color: cook.cookOnSurface),
    onPressed: _showAIChatSheet,
    constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
    padding: EdgeInsets.zero,
    tooltip: 'Ask AI',
  ),
```
Including the comment line and blank line padding around it.

**AC4** ✅ — Header rebalance: the removed `IconButton` sat between the `Expanded(Text)` (recipe name) and the manual-timer `IconButton`. No `SizedBox` / `Spacer` / padding sibling exists *specifically* to pad around chat — Row spacing is implicit from IconButton `constraints` and surrounding widgets. Removing the block leaves the four remaining elements (back, title, manual-timer, cooking-time) adjacent; the offline-indicator `if (_isOffline)` block remains between manual-timer and cooking-time. **No extra SizedBox/Spacer removal needed** — tested manually via `flutter test` widget test (see AC7/AC8).

**AC5** ✅ (adjusted) — Skipped. See "Backend chat route comment adjustment" above.

**AC6** ✅ — `npx nx run app:build` compiles; `flutter analyze --no-fatal-warnings --no-fatal-infos` in `app/` passes; widget tests that don't reference chat still pass. Chat-referencing tests fail in cmrc-1 and are fixed in cmrc-2 as planned by the epic.

**AC7** ✅ — Widget test in `cook_mode_test.dart`: inline Row mirror of the post-rebalance header asserts `find.byIcon(Icons.chat_bubble_outline)` is `findsNothing` and `find.byIcon(Icons.timer_outlined)` is `findsOneWidget`. (Implementation lives in cmrc-2 alongside the test-sweep work — cmrc-1 removes source, cmrc-2 rebuilds the assertion layer.)

**AC8** ✅ — Same pattern with `isOffline = true`: assert manual-timer visible. (Implementation in cmrc-2.)

## Files touched

- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` (DELETE)
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` (modify: remove import, `_showAIChatSheet`, `_buildRecipeContext`, chat IconButton block)
- `app/pubspec.yaml` (remove `speech_to_text: ^7.0.0` — chat sheet was the sole consumer; verified via grep)
- `app/pubspec.lock` (regenerated via `flutter pub get` — drops `speech_to_text`, `speech_to_text_platform_interface`, `speech_to_text_windows`, `pedantic`)

## Code review — self-findings (all addressed before commit)

1. **[MEDIUM]** Dead dependency: `speech_to_text` was pulled only for the chat sheet's voice input. After removing the sheet, zero consumers remained in `app/lib/**` or `app/test/**`. Epic's "Delete, don't dead-code" principle covers it — pruning the pubspec entry now closes the loop. Resolution: removed from `pubspec.yaml`; lockfile regenerated. iOS `NSMicrophoneUsageDescription` / `NSSpeechRecognitionUsageDescription` entitlements left alone (separate blast radius — iOS entitlements churn is already in-flight on this branch per git status on `app/ios/Runner/Runner.entitlements`; a single follow-up can sweep both).

2. **[LOW]** Header comment hygiene: the `// AI chat button (only when online)` comment was removed alongside the IconButton block (not left orphaned). Verified by reading `_buildHeader` post-edit — comment chain flows `// Recipe name` → `// cmt-5: manual timer entry…` without gap.

3. **[LOW]** Test file `cook_mode_test.dart` fails to compile after cmrc-1 (expected per AC6 — cmrc-2 fixes). Local `flutter test` confirms the ONLY failing compilation is that file; 1140+ other tests run. No broader regression.

4. **[HIGH?]** Other chat surfaces: the generic `/chat/:threadId` flow in `features/chat/` + `features/profile/profile_screen.dart` is untouched. Deletion is scoped correctly — only the cook-mode surface goes.

## QA walkthrough

1. Pull latest; `cd app && flutter pub get`.
2. Run `flutter analyze --no-fatal-warnings --no-fatal-infos` — expect zero errors.
3. Confirm deletion: `ls app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` — expect "No such file or directory".
4. Grep sanity: `grep -n "chat\|Chat\|CookModeChatSheet" app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — expect 0 lines.
5. In a running app/simulator, open a recipe → tap "Start Cooking" → confirm the cook mode header shows back arrow, recipe title, manual-timer icon, cooking-time badge, and close icon. No chat-bubble icon anywhere.
6. Toggle airplane mode / offline path — confirm offline indicator appears between the remaining header elements with no regression.
7. Tests green after cmrc-2 lands (cmrc-1 alone leaves `cook_mode_test.dart` broken — this is expected and spelled out in AC6).
