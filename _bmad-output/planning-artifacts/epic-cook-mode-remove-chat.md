<!-- refined via party-mode 2026-04-22 -->
# Epic: Cook Mode — Remove Chat Sheet (Flutter-only)

## Overview

`CookModeChatSheet` (`app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart`) is an experimental AI chat surface reachable from a chat bubble in the cook-mode header. The user has decided the UX isn't right and wants to rethink how AI assistance shows up in cook mode. Rather than let it rot in place — accumulating theme tokens, tests, and coupling — pull it cleanly now so future cook-mode work (`epic-cook-mode-meal`, `epic-cook-mode-resume`, `epic-cook-mode-polish`) doesn't have to carry it. Motivation is captured in PRD addendum 2026-04-22 FR-MCM-8: "messy there, want to come back to how we incorporate it." Documenting *why* in the epic prevents the next person (or future-Leo) from just reverting.

This is a pure-deletion epic. No replacement, no regression, no backend touch. The `/v1/recipes/{id}/chat` route on the API side stays intact (removing it is cheap but out of scope — it may be repurposed for a future AI surface). A code comment on the backend route will note that its frontend consumer was deliberately removed, so nobody assumes the endpoint is dead.

Grounded references (verified at refinement time):
- Chat import at `cook_mode_screen.dart:16`.
- `_showAIChatSheet` method at `cook_mode_screen.dart:494`.
- `CookModeChatSheet(...)` constructor call at `cook_mode_screen.dart:499`.
- Chat button (offline-gated) in `_buildHeader` at `cook_mode_screen.dart:736–741` (icon `Icons.chat_bubble_outline`, onPressed `_showAIChatSheet`).
- Chat test assertions inline in `app/test/cook_mode_test.dart:5, 209–220` (no dedicated `cook_mode_chat_sheet_test.dart` file exists — verified).
- No `GoRoute` for chat exists in `app/lib/core/router/app_router.dart` — chat opens as a `showModalBottomSheet`, not a route.

## Goal

Recipe cook mode no longer has a chat surface. The header is simpler — back / title / manual-timer / cooking-time badge — with no chat bubble. All cook-mode-chat-sheet code and tests are deleted. A CI grep gate prevents accidental re-introduction of the chat sheet under `app/lib/features/recipes/cook_mode/`.

## End-user flow

1. User taps **"Start Cooking"** on a recipe detail screen.
2. Cook mode opens — **no chat bubble** icon in the header. Just back, recipe name, manual-timer button, and the cooking-time badge. No awkward gap where chat used to live (header Row is rebalanced).
3. User cooks through the recipe as before — ingredient strip, steps, timers, navigation, offline indicator, and post-cook flow all identical.
4. User finishes cooking, rates via the post-cook sheet.
5. At no point did the user see, tap, or miss anything related to AI chat.

## Frontend changes

**Deleted files:**
- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` (entire file).
- No dedicated test file to delete — chat test assertions live inline in `cook_mode_test.dart:5, 209–220` and are pruned in cmrc-2.

**Modified:** `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- Remove the `import 'widgets/cook_mode_chat_sheet.dart';` line at `:16`.
- Remove the `IconButton` at `:736–741` (the chat bubble in `_buildHeader`) along with its surrounding offline-gate conditional (`if (!_isOffline) …`) if that conditional is only guarding chat. If the same offline-gate wraps other elements, preserve them but simplify the expression to drop chat.
- Remove the `_showAIChatSheet` method at `:494` and the `CookModeChatSheet(...)` constructor call at `:499`.
- Remove any state field (e.g., `_chatSheetController`, `_isChatOpen`) introduced for chat; remove any `recipeContext`-string builder whose only consumer was the chat sheet.
- **Rebalance the header `Row`**: after the chat IconButton is removed, inspect sibling `SizedBox` / `Spacer` / padding widgets that exist specifically to pad around it. Collapse those so the remaining four elements (back, title, manual-timer, cooking-time) sit with consistent spacing — no dead gap.

**Modified:** `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` — imports and no-longer-referenced private symbols are cleaned up so `npx nx run app:analyze` reports zero new warnings.

**Modified tests** (7 files in `app/test/`, swept via grep for `chat`, `Chat`, `chat_bubble`, `CookModeChatSheet`, `cook_mode_chat_sheet`, `_showAIChatSheet`):
- `cook_mode_test.dart` — remove import at `:5` and the `CookModeChatSheet` assertions at `:209–220`. Any header-icon-count assertion adjusts from N to N−1.
- `cook_mode_gesture_test.dart` — scan for chat references; prune.
- `cook_mode_timer_test.dart` — scan; prune.
- `offline_cook_mode_test.dart` — scan; the chat button's offline-gated visibility was one thing this test likely covered. Replace with a positive assertion that the manual-timer button remains visible offline (which is the meaningful offline check).
- `cook_mode_timers_integration_test.dart` — scan; prune.
- `post_cook_feedback_test.dart` — scan; unlikely to touch chat but verify.
- `cook_timer_notification_service_test.dart` — scan; unlikely but verify.

**Route/deep-link cleanup:** confirmed none exists. `app_router.dart` has no chat route; chat was always modal. No router change.

**New:** `tools/no-cook-chat-check.sh`
- Mirror the shape of `tools/no-silent-catch-check.sh` (plain bash, `set -euo pipefail`, exit 1 on match with an explanatory message).
- Scope: `grep -RE "chat_bubble|ChatBubble|CookModeChatSheet|cook_mode_chat_sheet|_showAIChatSheet" app/lib/features/recipes/cook_mode/` (note: `app/lib/` scope only — do NOT scan the whole repo; backend chat route + FastAPI server references are legitimate).
- Message on match: "Chat sheet was deliberately removed in epic-cook-mode-remove-chat (2026-04-22); reintroduce via a new UX discussion, not by reviving the old widget."

**Modified:** `.github/workflows/ci.yml`
- Add a new `run: bash tools/no-cook-chat-check.sh` step immediately after the existing `bash tools/no-silent-catch-check.sh` line at `:344`. Name the step "Check no cook-mode chat references".

## Backend changes

None. Rationale: the `/v1/recipes/{id}/chat` route is deliberately kept — its frontend consumer is deleted in this epic but the route may be repurposed for a future AI surface. To prevent future maintainers from pruning the route thinking it's dead:

- **Add a code comment** to the route handler file (find via grep `/chat` under `services/api/src/api/v1/recipe/`) stating: `"Flutter consumer deliberately removed in epic-cook-mode-remove-chat (2026-04-22). Route retained for potential future AI-assist surface. If reviving: see PRD addendum 2026-04-22 FR-MCM-8."`

No schema change, no auth change, no migration, no tests touched.

## Infrastructure changes

None beyond the new CI step (a single `bash` invocation in `.github/workflows/ci.yml`). Rationale: no new env var, no AWS resource, no Terraform, no Docker change. The grep script runs on the existing GitHub Actions runner via the existing CI workflow — zero new cost, zero new dependency.

## Design principles

- **Delete, don't dead-code.** Comment-out-the-widget is not acceptable; remove the file entirely. Future reviewers should not find a dormant chat sheet under `widgets/`.
- **No partial removal.** If the chat button is hidden but the sheet file stays, we gain nothing — the bytes ship and the coupling remains. All-or-nothing deletion on the client.
- **Backend route stays, commented.** The endpoint is cheap to retain and may be repurposed. A code comment links back to this epic so future maintainers have context.
- **Grep gate catches regressions.** Without CI enforcement, the next person doing cook-mode work will look at git history, think "oh this used to exist, let me add it back", and the cycle repeats. The gate is the contract.
- **Positive header assertion, not just negative.** Don't only assert chat icon is absent; assert the header contains exactly the four expected icons (back, title, manual-timer, cooking-time). Catches silent growth (new icon added without design discussion) in addition to regression.
- **Offline-mode visibility is still tested.** The chat button was offline-gated; that test coverage is repurposed, not lost — it becomes a positive assertion that manual-timer is visible offline.

## File structure

Anticipated touched paths:
- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` (DELETE)
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` (remove chat import, method, button, header rebalance)
- `app/test/cook_mode_test.dart` (prune `:5` import + `:209–220` assertions + any icon-count assertion)
- `app/test/cook_mode_gesture_test.dart` (grep-prune)
- `app/test/cook_mode_timer_test.dart` (grep-prune)
- `app/test/offline_cook_mode_test.dart` (grep-prune; replace chat-offline-gate assertion with manual-timer-offline-gate assertion)
- `app/test/cook_mode_timers_integration_test.dart` (grep-prune)
- `app/test/post_cook_feedback_test.dart` (grep-verify; prune if any match)
- `app/test/cook_timer_notification_service_test.dart` (grep-verify; prune if any match)
- `tools/no-cook-chat-check.sh` (NEW, executable)
- `.github/workflows/ci.yml` (add a step after `:344`)
- Backend chat-route handler file (find via grep `/chat` in `services/api/src/api/v1/recipe/`) — add code comment only

## Stories

### Story cmrc-1 — Delete chat sheet + header button + rebalance header

**AC1** — `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart` file is deleted from disk.
**AC2** — `cook_mode_screen.dart` has zero references to `CookModeChatSheet`, `cook_mode_chat_sheet`, `chat_bubble`, `_showAIChatSheet`, or any chat-related state / import / method. Verified via `grep -n "chat\|Chat" app/lib/features/recipes/cook_mode/cook_mode_screen.dart` returning zero lines (case-sensitive match is fine; no recipe-related usage of "chat" is expected).
**AC3** — The `IconButton(icon: Icon(Icons.chat_bubble_outline, …), onPressed: _showAIChatSheet)` at `:736–741` is removed from `_buildHeader`. The surrounding `if (!_isOffline) …` offline-gate conditional is either removed (if chat was its only conditional body) or simplified (if it gated multiple elements).
**AC4** — Header `Row` is rebalanced: any `SizedBox` / `Spacer` / padding whose sole purpose was to separate the chat button from its neighbors is removed or resized so remaining four elements (back, title, manual-timer, cooking-time) sit with consistent spacing. Manual visual QA: screenshot posted to the PR description confirms no dead gap.
**AC5** — Backend chat-route handler (located via `grep -l "/chat" services/api/src/api/v1/recipe/`) gains a code comment: `# Flutter consumer deliberately removed in epic-cook-mode-remove-chat (2026-04-22). Route retained for potential future AI-assist surface.` Route logic is unchanged.
**AC6** — `npx nx run app:build` compiles; `npx nx run app:analyze` reports zero new errors/warnings; `npx nx run app:test` passes (some tests will be updated in cmrc-2 — for this story, tests that reference chat may fail if they asserted on its presence; that's expected and cmrc-2 fixes them).
**AC7** — Widget test (new, added in `cook_mode_test.dart`): pump `CookModeScreen`, assert `find.byIcon(Icons.chat_bubble_outline)` is `findsNothing`. Assert `find.byIcon(Icons.timer_outlined)` (manual-timer) is `findsOneWidget` — positive assertion guards against accidental removal.
**AC8** — Widget test (new): pump `CookModeScreen` with `_isOffline = true`. Assert manual-timer icon is visible (positive offline-mode assertion replacing the prior chat-visibility offline-gate test).

### Story cmrc-2 — Grep gate in CI + test cleanup

**AC1** — New script `tools/no-cook-chat-check.sh` exists and is executable (`chmod +x`). Content mirrors `tools/no-silent-catch-check.sh` shape: `#!/usr/bin/env bash`, `set -euo pipefail`, a grep against `app/lib/features/recipes/cook_mode/` for `chat_bubble|ChatBubble|CookModeChatSheet|cook_mode_chat_sheet|_showAIChatSheet`. On match, print an explanatory message referencing this epic and `exit 1`.
**AC2** — `.github/workflows/ci.yml` gains a new step immediately after the `bash tools/no-silent-catch-check.sh` line at `:344`:
  ```yaml
  - name: Check no cook-mode chat references
    run: bash tools/no-cook-chat-check.sh
  ```
  (Or the appropriate YAML shape matching the existing step's indentation and structure.)
**AC3** — Test sweep across the 7 cook-mode-adjacent test files listed in "File structure" above. For each, `grep -n "chat\|Chat" <file>`: delete matching import lines, delete matching test case bodies, prune matching assertions inside other test bodies, remove comment references to chat. Specifically:
  - `cook_mode_test.dart:5` — delete the `import 'package:palateful/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart';`
  - `cook_mode_test.dart:209–220` — delete the `test('CookModeChatSheet class is importable', …)` and any sibling block that asserts `CookModeChatSheet` non-null.
  - Any header-icon-count assertion (e.g., `expect(find.byType(IconButton), findsNWidgets(N))`) adjusts from N to N−1.
**AC4** — `offline_cook_mode_test.dart`: any assertion about chat's offline visibility is replaced by a positive assertion that the manual-timer icon is visible with `_isOffline = true`. Net coverage: offline mode still has an icon-visibility test, just for the right icon.
**AC5** — `npx nx run app:test` is green after cmrc-1 + cmrc-2 land together.
**AC6** — Run the new CI script locally against HEAD to verify it passes: `bash tools/no-cook-chat-check.sh`. Run it against a pre-cmrc-1 branch snapshot (or stash the deletion temporarily) to verify it fails. Both outcomes logged in the PR description.
**AC7** — Manual grep sanity check in the PR description: `grep -rE "chat_bubble|CookModeChatSheet|cook_mode_chat_sheet" app/lib/features/recipes/cook_mode/ app/test/` returns zero lines.
**AC8** — Manual QA walkthrough: open cook mode from a recipe, verify the header visually shows exactly four elements in order: back arrow, recipe title (ellipsized), manual-timer icon, cooking-time badge. Screenshot posted to the PR description (complements AC4 on cmrc-1).

## Dependencies

- **Internal:** cmrc-1 blocks cmrc-2 (grep gate requires chat code to actually be gone; otherwise the gate fails on existing code). cmrc-1's test file changes (AC7, AC8) land together with cmrc-2's broader test sweep — consider combining into one PR for clean review.
- **Cross-epic:**
  - `epic-cook-mode-polish` (backlog): cmp-3 migrates chat-sheet tokens to `CookModeTheme`. If cmrc-1 ships first, cmp-3's chat-sheet stanza becomes a no-op — remove it from cmp-3's AC list when the story is picked up. If cmp-3 ships first, cmrc-1 deletes the now-migrated file; no semantic conflict, just slight churn.
  - `epic-cook-mode-resume` (planned): adds a `PopupMenuButton` (overflow) to the header after the cooking-time badge. Whoever ships second rebalances the Row to accommodate. Header-icon-count assertions in test files need a +1 update in the resume epic.
  - `epic-cook-mode-meal` (planned): meal cook mode inherits a chat-free baseline; no new chat surface is added there by construction. Ideally cmrc ships first so the shared-widget extraction in meal-cook's cmm-1 doesn't carry chat through the move.

## Open questions for the user

- **None outstanding.** Party-mode surfaced three questions (backend route archival, test-file-gutting strategy, grep-guard CI wiring); all three were resolved with the locked decision (route stays with a code comment), sensible default (prune assertions in-place rather than gut test files to zero content), and the concrete CI pattern (step in `.github/workflows/ci.yml`, not `npx nx run app:lint`).
