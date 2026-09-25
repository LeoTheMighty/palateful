#!/usr/bin/env bash
# pantrysync — CI guard: pantry *mutations* must go through
# `PantryService`, never straight to `ApiClient`.
#
# Rationale. `PantryService.{add,update,delete}PantryIngredient` each
# emit a `PantryItem*` event on the MutationBus
# (app/lib/features/pantry/services/pantry_service.dart), and
# `defaultPantryProvider` / `pantryIngredientsProvider` invalidate
# themselves on those events
# (app/lib/features/pantry/providers/pantry_provider.dart). A call that
# goes directly to `ApiClient` mutates the server and emits nothing, so
# an open pantry list keeps showing the pre-mutation state — bounded
# only by that provider's 10-minute TTL backstop.
#
# That is not hypothetical: `shopping_list_screen.dart`'s pantry-undo
# called `getIt<ApiClient>().deletePantryIngredient(...)` directly, and
# an open pantry view kept the phantom row for up to ten minutes with
# nothing on screen saying so. This guard exists so the next person
# wiring a pantry mutation from another feature cannot reintroduce it
# without tripping CI.
#
# Note this guard catches the *client-initiated* half only. A mutation
# the SERVER performs (the shopping-list check-off auto-add) has no
# client call to catch — that path must emit
# `PantryChangedExternally` by hand. Grep-able rule of thumb: client
# performed it → PantryService; server performed it →
# PantryChangedExternally.
#
# Allowed sites:
#   - app/lib/features/pantry/services/pantry_service.dart
#     (the service IS the legitimate wrapper — it emits the events; it
#     holds the only legitimate `_api.<mutation>PantryIngredient` calls)
#   - app/lib/core/services/api_client.dart
#     (the low-level API methods themselves; not under features/)
#
# Reads are deliberately NOT guarded: `getDefaultPantry` /
# `estimatePantryExpiry` change nothing, so a direct read cannot
# desynchronise a view.
#
# Exit codes:
#   0 — clean
#   1 — offending call site found (list printed to stderr)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_LIB="$ROOT/app/lib/features"

if [ ! -d "$APP_LIB" ]; then
  echo "no-direct-pantry-mutation-check: features dir not found at $APP_LIB" >&2
  exit 1
fi

# Matches on the RECEIVER, not just the method name: an ApiClient-shaped
# receiver calling a pantry mutation. `_service.addPantryIngredient(` and
# `getIt<PantryService>().delete…(` are the CORRECT calls and must not
# match — a guard that fires on the fix as loudly as on the bug gets
# switched off within a week.
PATTERN='(getIt<ApiClient>\(\)|\b_?api(Client)?)\.(add|update|delete)PantryIngredient\('

violations=""
while IFS= read -r -d '' file; do
  case "$file" in
    */features/pantry/services/pantry_service.dart) continue ;;
  esac

  if hits="$(grep -nE "$PATTERN" "$file" 2>/dev/null)"; then
    while IFS=: read -r lineno rest; do
      [ -z "$lineno" ] && continue
      violations="${violations}${file}:${lineno}:${rest}"$'\n'
    done <<< "$hits"
  fi
done < <(find "$APP_LIB" -type f -name '*.dart' -print0)

if [ -n "$violations" ]; then
  count=$(printf '%s' "$violations" | grep -c '^' || true)
  echo "no-direct-pantry-mutation-check: $count direct pantry mutation(s) found:" >&2
  printf '%s' "$violations" | sed 's/^/  /' >&2
  echo >&2
  echo "Pantry mutations must go through PantryService so the MutationBus" >&2
  echo "event fires and an open pantry list invalidates. Calling ApiClient" >&2
  echo "directly leaves that list wrong for up to 10 minutes (the provider's" >&2
  echo "TTL backstop) with nothing on screen indicating it." >&2
  echo >&2
  echo "If the SERVER performed the mutation and this client has no payload" >&2
  echo "to assert, emit PantryChangedExternally(pantryId:, reason:) instead." >&2
  exit 1
fi

echo "no-direct-pantry-mutation-check: OK"
exit 0
