#!/usr/bin/env bash
# cmrc-2 — CI guard against re-introduction of the cook-mode chat sheet.
#
# Rationale: the experimental CookModeChatSheet was deliberately removed
# in epic-cook-mode-remove-chat (2026-04-22). The user flagged the UX as
# wrong shape and wants to rethink AI-in-cook-mode from scratch. Without
# an automated gate, the next person touching cook mode would find the
# old widget in git history, think "oh this used to exist, let me add
# it back", and we'd be right back where we started.
#
# Scope is app/lib/features/recipes/cook_mode/ ONLY. The generic chat
# surface in app/lib/features/chat/ + app/lib/features/profile/ is
# unrelated and stays — its consumer (`ChatService`) is still wired up
# to the backend /chat/threads routes.
#
# To revive the sheet, remove this check AFTER a fresh UX discussion.
#
# Exit codes:
#   0 — clean
#   1 — chat reference found (list printed to stderr)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COOK_MODE_DIR="$ROOT/app/lib/features/recipes/cook_mode"

if [ ! -d "$COOK_MODE_DIR" ]; then
  echo "no-cook-chat-check: cook_mode directory not found at $COOK_MODE_DIR" >&2
  exit 1
fi

PATTERN='chat_bubble|ChatBubble|CookModeChatSheet|cook_mode_chat_sheet|_showAIChatSheet'

# `grep -RE --include='*.dart'` keeps the search to Dart source so the
# gate isn't tripped by a comment in a sibling markdown/story file.
if matches="$(grep -RnE --include='*.dart' "$PATTERN" "$COOK_MODE_DIR" 2>/dev/null)"; then
  echo "no-cook-chat-check: chat references found under app/lib/features/recipes/cook_mode/:" >&2
  echo "$matches" | sed 's/^/  /' >&2
  echo >&2
  echo "Chat sheet was deliberately removed in epic-cook-mode-remove-chat (2026-04-22);" >&2
  echo "reintroduce via a new UX discussion, not by reviving the old widget." >&2
  exit 1
fi

echo "no-cook-chat-check: OK"
exit 0
