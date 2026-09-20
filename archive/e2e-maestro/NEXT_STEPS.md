# E2E Test Suite — Status

All 7 E2E tests pass individually against the E2E backend stack.

## How to run

### 1. Start the E2E backend stack
```bash
npx nx run e2e:stack-up
# or: docker compose -f docker-compose.yml -f docker-compose.e2e.yml up --build -d
```

### 2. Run a single test
```bash
chromedriver --port=4444 &
cd app
flutter drive \
  --driver=test_driver/integration_test.dart \
  --target=integration_test/01_app_launch_test.dart \
  -d chrome \
  --dart-define=E2E_MODE=true
```

### 3. Run all tests sequentially
```bash
npx nx run e2e:test
# or: ./services/e2e/scripts/run_all.sh
# or: ./services/e2e/scripts/run_all.sh 01 03 07  (specific tests)
```

### 4. Tear down
```bash
npx nx run e2e:stack-down
```

---

## Test results (all passing)

| # | Test | What it covers |
|---|------|---------------|
| 01 | App launch | Auth bypass, bottom nav visible |
| 02 | Recipe books | Create recipe book, verify in list |
| 03 | Create recipe | Wizard flow (4 steps), save recipe |
| 04 | Shopping list | Create list, add items, check off item |
| 05 | Calendar | Week view renders day labels |
| 06 | Search | Navigate to search, enter query |
| 07 | AI chat | Open chat, send message, verify mocked response |

---

## Bugs fixed during E2E setup

| Bug | File | Fix |
|-----|------|-----|
| Recipe creation response UUID serialization | `services/api/src/api/v1/recipe/create_recipe.py` | `str()` on recipe.id, ingredient IDs |
| Recipe book creation UUID serialization | `services/api/src/api/v1/recipe_book/create_recipe_book.py` | `str()` on recipe_book.id |
| Recipe creation 422 when servings=null | `services/api/src/api/v1/recipe/create_recipe.py` | `servings: int \| None = 1` |
| Meal events DISTINCT ON SQL error (500) | `services/api/src/api/v1/meal_event/list_meal_events.py` | ORDER BY must start with DISTINCT ON column |
| Hero tag conflict on recipe book FAB | `app/lib/features/recipe_books/recipe_book_detail_screen.dart` | `heroTag: null` on FAB |
| Shopping list items not appearing (WebSocket only) | `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` | Also update local state after addItem API call |
| WebSocket crash in E2E mode | `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` | Skip WebSocket connect when `kE2EMode` |
| AI chat SSE event type mismatch | `services/api/src/api/v1/chat/agent_loop.py` | `"text"` → `"token"`, add `message_id` to done event |

---

## Known issues

- **ChromeDriver flakiness**: `flutter drive -d chrome` occasionally fails with `AppConnectionException` between consecutive tests. Workaround: kill stale Chrome processes between tests (handled in `run_all.sh`).
- **500 on home screen**: The meal events `DISTINCT ON` bug is fixed, but other home screen API calls may log non-blocking errors for a fresh E2E user (e.g., empty favorites).

---

## Files modified / created

### This session (test fixes)
```
app/integration_test/helpers.dart              — rewritten with waitFor(), robust settle()
app/integration_test/01_app_launch_test.dart   — use waitFor for reliable waiting
app/integration_test/02_recipe_books_test.dart — use waitFor
app/integration_test/03_create_recipe_test.dart — rewritten for wizard flow (4 steps)
app/integration_test/04_shopping_list_test.dart — use waitFor, fix item adding flow
app/integration_test/05_calendar_test.dart     — use waitFor
app/integration_test/06_search_test.dart       — fix: tap search area → navigate to SearchScreen
app/integration_test/07_ai_chat_test.dart      — fix hint text (Unicode ellipsis), send button
services/e2e/scripts/run_all.sh                — created, runs all tests sequentially
services/e2e/project.json                      — updated targets for flutter drive
```

### Codebase fixes
```
services/api/src/api/v1/recipe/create_recipe.py         — UUID str(), nullable servings
services/api/src/api/v1/recipe_book/create_recipe_book.py — UUID str()
services/api/src/api/v1/meal_event/list_meal_events.py   — DISTINCT ON ordering fix
services/api/src/api/v1/chat/agent_loop.py               — SSE event type fix
app/lib/features/recipe_books/recipe_book_detail_screen.dart — heroTag: null
app/lib/features/shopping_cart/screens/shopping_list_screen.dart — local state update, skip WS in E2E
```

### Previous session (E2E infrastructure)
```
services/api/src/config.py                     — e2e_test_mode: bool = False
services/api/src/dependencies.py               — E2E auth bypass
services/api/src/api/v1/chat/agent_loop.py     — AI mock for E2E
services/api/src/main.py (CORS)                — http://localhost regex
app/lib/main.dart                              — kE2EMode bypass
app/pubspec.yaml                               — integration_test added
app/test_driver/integration_test.dart
docker-compose.e2e.yml
```
