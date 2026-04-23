#!/usr/bin/env bash
# ffm-1 — CI guard: `apiClient.getRecipeBooks()` (and service fallback
# `getRecipeBooks()` on `RecipeBookService`) must only live inside the
# shared Riverpod provider in
# `app/lib/features/recipe_books/providers/recipe_books_provider.dart`
# (via `RecipeBookService.listRecipeBooks()` which is itself a thin
# wrapper on `_api.getRecipeBooks`).
#
# Rationale: the frontend-fetch-minimization epic's AC #2 is "grep on
# `app/lib/features/` for `apiClient.getRecipeBooks()` and
# `recipeBookService.getRecipeBooks()` returns zero hits outside the
# provider file + generated mocks". Without a CI gate, the next person
# adding an add-recipe flow or a book picker would quietly reintroduce
# the duplicate round-trip.
#
# Allowed sites:
#   - app/lib/features/recipe_books/services/recipe_book_service.dart
#     (the service *IS* the legitimate wrapper; the provider reads via it)
#   - app/lib/core/services/api_client.dart
#     (the low-level API method itself)
#
# Exit codes:
#   0 — clean
#   1 — offending call site found (list printed to stderr)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_LIB="$ROOT/app/lib/features"

if [ ! -d "$APP_LIB" ]; then
  echo "no-direct-get-recipe-books-check: features dir not found at $APP_LIB" >&2
  exit 1
fi

# Pattern: `<anything>.getRecipeBooks(` — catches `apiClient.getRecipeBooks(`,
# `_apiClient.getRecipeBooks(`, `_api.getRecipeBooks(`. We allow only the
# service wrapper below.
PATTERN='[a-zA-Z_]+\.getRecipeBooks\('

violations=""
while IFS= read -r -d '' file; do
  case "$file" in
    */features/recipe_books/services/recipe_book_service.dart) continue ;;
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
  echo "no-direct-get-recipe-books-check: $count direct getRecipeBooks() call(s) found:" >&2
  printf '%s' "$violations" | sed 's/^/  /' >&2
  echo >&2
  echo "Recipe-book list must flow through recipeBooksProvider" >&2
  echo "(features/recipe_books/providers/recipe_books_provider.dart)." >&2
  echo "Non-Consumer StatefulWidget callers can use readRecipeBooks(context)." >&2
  exit 1
fi

echo "no-direct-get-recipe-books-check: OK"
exit 0
