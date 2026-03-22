# Palateful E2E Tests

End-to-end tests using [Maestro](https://maestro.dev/) against the Flutter web app.

## Architecture

```
Maestro (browser automation)
    ↓ interacts with
Flutter web (built with E2E_MODE=true — Auth0 bypassed)
    ↓ real HTTP
FastAPI (E2E_TEST_MODE=true — Auth0 validation bypassed)
    ↓ real SQL
PostgreSQL (test database, real migrations)
```

**Mocked:** OpenAI/AI calls (canned response returned server-side)
**Not mocked:** API business logic, DB, WebSockets, CORS

## Prerequisites

```bash
# Install Maestro
brew install maestro

# Verify install
maestro --version
```

## Running the tests

### 1. Start the backend

```bash
# From the repo root
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up --build -d
```

### 2. Build and serve the Flutter web app

```bash
cd app

# Option A — dev server with hot reload (recommended for development)
flutter run -d web-server --web-port=8888 --dart-define=E2E_MODE=true

# Option B — production build + static server
flutter build web --dart-define=E2E_MODE=true
python3 -m http.server 8888 -d build/web
```

### 3. Run all flows

```bash
# Via NX (recommended)
npx nx run e2e:test

# Run a single flow
npx nx run e2e:test-single --flow=services/e2e/flows/04_shopping_list.yaml

# Or directly with Maestro (from repo root)
maestro test services/e2e/flows/
```

## Test Flows

| Flow | Description |
|------|-------------|
| `01_app_launch.yaml` | App loads, bottom nav visible |
| `02_recipe_books.yaml` | Create a recipe book |
| `03_create_recipe.yaml` | Create a recipe with steps |
| `04_shopping_list.yaml` | Create list, add items, check off |
| `05_meal_calendar.yaml` | Open calendar, verify loads |
| `06_search.yaml` | Search from home screen |
| `07_ai_chat.yaml` | Open AI assistant, send message |
| `08_recipe_cook_mode.yaml` | Start cook mode on a recipe |
| `09_invitations.yaml` | Navigate to invitations |

## How the auth bypass works

Flutter is built with `--dart-define=E2E_MODE=true`, which sets `kE2EMode = true` in
`main.dart`. This skips Auth0 and injects the fixed token `e2e-test-token`.

The API is started with `E2E_TEST_MODE=true`. When it sees `Authorization: Bearer e2e-test-token`
it returns a seeded test user (`e2e@palateful.test`) without calling Auth0.

## Adding Semantics IDs

For more stable selectors, add `Semantics(identifier: 'my-id', child: ...)` wrappers
to key widgets and reference them in flows with:

```yaml
- tapOn:
    id: "my-id"
```
