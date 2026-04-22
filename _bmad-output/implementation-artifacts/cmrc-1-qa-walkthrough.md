# cmrc-1 — QA walkthrough

Story: `cmrc-1-delete-chat-sheet-button-and-route-wiring.md`

## Prerequisites

- Branch with cmrc-1 commit checked out.
- `cd app && flutter pub get` (lockfile changed — new deps resolution needed).

## Static checks

- [ ] `flutter analyze --no-fatal-warnings --no-fatal-infos` from `app/` reports **zero new errors** relative to `origin/main`. (Pre-existing warnings on `cook_mode_screen.dart` for `dart:ui` and `error_banner.dart` are unchanged.)
- [ ] `ls app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` returns `No such file or directory`.
- [ ] `grep -n "chat\|Chat\|CookModeChatSheet" app/lib/features/recipes/cook_mode/cook_mode_screen.dart` returns **zero lines**.
- [ ] `grep -n "speech_to_text" app/pubspec.yaml` returns **zero lines**.
- [ ] `grep -n "speech_to_text" app/pubspec.lock` returns **zero lines**.

## Test checks

- [ ] `flutter test` runs from `app/`. Every test file compiles **except** `test/cook_mode_test.dart`, which fails compilation with `Error when reading 'lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart': No such file or directory`. This is expected and scheduled to be fixed by cmrc-2.

## Manual QA (once cmrc-2 also lands, combined QA recommended)

- [ ] Launch the app (debug build) on iOS or Android simulator.
- [ ] Navigate to any recipe → tap **Start Cooking**.
- [ ] Confirm the cook mode header shows, left-to-right: back arrow → recipe title (ellipsized) → manual-timer icon → cooking-time badge → close icon. No chat-bubble icon anywhere.
- [ ] Enable airplane mode (or disable wifi + cell data). Wait a few seconds for the offline indicator to appear between manual-timer and cooking-time. Confirm manual-timer icon remains visible.
- [ ] Re-enable connectivity; offline indicator disappears.
- [ ] Scroll through a few recipe steps, start a manual timer, let it complete — confirm all core cook-mode flows (ingredient strip, step navigation, timer notification) work unchanged.
- [ ] Finish cooking → rate via post-cook sheet. Nothing related to AI or chat appears at any point.

## Known out-of-scope (documented in story file)

- Epic AC5 ("add backend code comment noting Flutter consumer removed") skipped — backend `/chat/threads` routes have other active Flutter consumers (`features/chat/`, `features/profile/profile_screen.dart`), so the comment would be misleading.
- iOS `NSMicrophoneUsageDescription` / `NSSpeechRecognitionUsageDescription` entitlements/Info.plist not cleaned up — left for a single follow-up sweep alongside the in-flight iOS entitlement changes on this branch.
