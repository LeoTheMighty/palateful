# cmrc-2 — QA walkthrough

Story: `cmrc-2-grep-gate-and-test-cleanup.md`
Predecessor: cmrc-1 (delivered the source deletion)

## Prerequisites

- Branch with cmrc-1 + cmrc-2 commits checked out.
- `cd app && flutter pub get`.

## Static checks

- [ ] `ls -l tools/no-cook-chat-check.sh` shows `-rwxr-xr-x` (executable).
- [ ] `bash tools/no-cook-chat-check.sh` exits `0` and prints `no-cook-chat-check: OK`.
- [ ] `.github/workflows/ci.yml` contains a step named `No cook-mode chat references (cmrc-2 grep guard)` immediately after `No silent catches (rp-5 grep guard)`.
- [ ] `grep -rE "chat_bubble|CookModeChatSheet|cook_mode_chat_sheet" app/lib/features/recipes/cook_mode/ app/test/` returns **zero lines** (exit code 1).

## Negative test for the grep gate

To convince yourself the gate actually trips on re-introduction:

```bash
# Temporarily add a forbidden string to a cook-mode file
echo '// CookModeChatSheet(' >> app/lib/features/recipes/cook_mode/cook_mode_screen.dart
bash tools/no-cook-chat-check.sh  # expect: exit 1 with "chat references found" message
git checkout -- app/lib/features/recipes/cook_mode/cook_mode_screen.dart
bash tools/no-cook-chat-check.sh  # expect: exit 0
```

- [ ] First run exits non-zero with the "deliberately removed" message.
- [ ] After `git checkout --`, second run is clean.

## Test suite

- [ ] `cd app && flutter test` — full suite passes with zero `-N` failures. Before cmrc-2, `cook_mode_test.dart` failed compilation; that's now resolved.
- [ ] `cd app && flutter test test/cook_mode_test.dart` shows 6 tests, all pass. Two of them are the new header regression assertions from cmrc-2 AC4.

## Manual QA (combined cmrc-1 + cmrc-2)

Same walkthrough as `cmrc-1-qa-walkthrough.md`:
- [ ] Open a recipe → Start Cooking → confirm header shows back, title, manual-timer, cooking-time, close. No chat anywhere.
- [ ] Toggle airplane mode → offline indicator appears; manual-timer stays visible.

## Epic completion check

- [ ] `_bmad-output/implementation-artifacts/sprint-status.yaml` shows:
  - `cmrc-1-delete-chat-sheet-button-and-route-wiring: done`
  - `cmrc-2-grep-gate-and-test-cleanup: done`
  - `epic-cook-mode-remove-chat: done`
