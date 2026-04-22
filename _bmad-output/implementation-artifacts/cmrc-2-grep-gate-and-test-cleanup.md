# Story cmrc-2 — Grep gate in CI + test cleanup

Status: done

Epic: `_bmad-output/planning-artifacts/epic-cook-mode-remove-chat.md`
Predecessor: cmrc-1 (done — commit 1675837)

## Context snapshot (verified at dev time, 2026-04-22)

- After cmrc-1: `app/test/cook_mode_test.dart` fails to compile — import at line 5 points at the deleted chat sheet; `CookModeChatSheet` usage at line 215 is undefined. Everything else in the suite compiles.
- `tools/no-silent-catch-check.sh` exists and is the shape to mirror — `#!/usr/bin/env bash`, `set -eu`, early exit on match with explanatory message.
- `.github/workflows/ci.yml:344` is the line with `run: bash tools/no-silent-catch-check.sh`. Add a new step after it.
- Only `cook_mode_test.dart` has chat references in `app/test/`. The epic named 7 cook-mode-adjacent test files to sweep, but `grep -l chat` confirmed the other 6 are already clean. We verify with a post-cmrc-2 grep in AC7.

## Acceptance criteria + implementation plan

**AC1** — `tools/no-cook-chat-check.sh` exists, executable, mirrors `no-silent-catch-check.sh` shape. Scope: `grep -RE` against `app/lib/features/recipes/cook_mode/` for pattern union `chat_bubble|ChatBubble|CookModeChatSheet|cook_mode_chat_sheet|_showAIChatSheet`. On match → exit 1 with a message pointing at this epic.

**AC2** — `.github/workflows/ci.yml` gains a step with `run: bash tools/no-cook-chat-check.sh` immediately after the existing silent-catch-check step. YAML shape matches its sibling.

**AC3** — `cook_mode_test.dart` cleanup:
- Remove import at `:5` (`import 'package:palateful/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart';`).
- Remove the entire `testWidgets('AI chat button shows when online (not offline)', …)` and `testWidgets('AI chat button hidden when offline', …)` pair (lines 151–207). These tested a header pattern that no longer exists.
- Remove the `test('CookModeChatSheet class is importable', …)` block at lines 209–216.
- Remove the two mic-IconButton tests (lines 218–268): `testWidgets('mic button renders in voice input row pattern', …)` and `testWidgets('active mic button shows filled icon pattern', …)`. Their sole purpose was documenting the chat sheet's voice input; with the sheet gone, they're orphaned. `speech_to_text` dep is also gone.

**AC4** — Add two new widget tests to `cook_mode_test.dart` that mirror the header post-cmrc-1:
- Test 1: pump a `MaterialApp` containing a `Row` with the five post-cmrc-1 header elements (back, title, manual-timer, cooking-time, close). Assert `find.byIcon(Icons.chat_bubble_outline)` is `findsNothing` and `find.byIcon(Icons.timer_outlined)` is `findsOneWidget`.
- Test 2: pump the same scaffold but with `isOffline = true` gating the offline indicator. Assert manual-timer icon remains visible (positive offline-mode assertion replacing the old chat-offline-gate test).

**AC5** — `flutter test` passes cleanly (every test file compiles; no `-1` in the `+N -M` tally).

**AC6** — Run `bash tools/no-cook-chat-check.sh` locally on HEAD → exit 0. (Running it against pre-cmrc-1 would fail; not repeating that here — cmrc-1 already landed.)

**AC7** — `grep -rE "chat_bubble|CookModeChatSheet|cook_mode_chat_sheet" app/lib/features/recipes/cook_mode/ app/test/` returns zero lines. **Adjusted during dev**: the AC4 negative-assertion test initially used `find.byIcon(Icons.chat_bubble_outline)` which matched the grep. Rewrote the assertion to `find.byTooltip('Ask AI')` (same semantic — chat sheet's entry button used that tooltip) so the grep stays clean and the widget-level guard remains.

**AC8** — Manual QA deferred to the combined cmrc-1 + cmrc-2 walkthrough file; no new per-story walkthrough steps beyond AC5/AC6/AC7.

## Files touched

- `tools/no-cook-chat-check.sh` (NEW, chmod +x)
- `.github/workflows/ci.yml` (new CI step after line 344)
- `app/test/cook_mode_test.dart` (prune chat assertions, add header assertions)

## Story-level sprint-status update

- `cmrc-2-grep-gate-and-test-cleanup: done`
- `epic-cook-mode-remove-chat: done`
