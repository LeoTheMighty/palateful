# Palateful E2E Tests

End-to-end tests: the real Flutter web app, driven in Chrome by
`flutter drive`, against the real API and a real Postgres.

```
flutter drive (Chrome, via chromedriver)
    ↓ drives
Flutter web (built with E2E_MODE=true — Auth0 bypassed)
    ↓ real HTTP to http://localhost:8000
FastAPI (E2E_TEST_MODE=true, ENVIRONMENT=development — Auth0 bypassed)
    ↓ real SQL
PostgreSQL — the `test` database, real migrations
```

**Mocked:** OpenAI/AI calls (canned response returned server-side).
**Not mocked:** API business logic, DB, WebSockets, CORS.

## Prerequisites

Docker Desktop running, Flutter on `PATH`, and — the fiddly one — a
**chromedriver whose major version matches your Chrome**. `flutter drive`
attaches through it, and a mismatch fails the run.

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version
npx @puppeteer/browsers install chromedriver@<that exact version>
export PATH="<install dir>/chromedriver-mac-arm64:$PATH"
```

Do **not** use `brew install chromedriver`: the cask is deprecated (it
fails the macOS Gatekeeper check and is scheduled for removal), and it
tracks a different version line than stable Chrome — as of this writing it
ships 151 while stable Chrome is 150.

Chrome auto-updates, so this breaks periodically. The suite preflights the
pair and tells you the exact command to run when they drift — it fails in
under a second rather than after a full app build.

## Running the suite

```bash
npx nx run e2e:test
```

That is the whole lifecycle: stack up (`--build`) → wait for
`http://localhost:8000/v1/health` → run every flow in
`app/integration_test/0*_test.dart` → tear the stack down in a `trap`
(teardown survives a failed flow or a Ctrl-C). Exits 0 **iff** every flow
passed.

The wrapper owns the whole `palateful` compose project for the duration of
the run — teardown stops your local dev stack too, and it pins
`COMPOSE_PROJECT_NAME=palateful` so the containers are the same ones
`e2e:stack-down` and `docker kill palateful-api` address, even when the
suite is invoked from a git worktree.

Useful overrides:

| Var | Default | Why |
|-----|---------|-----|
| `E2E_KEEP_STACK=1` | `0` | Skip teardown so you can poke at a failure. |
| `E2E_HEALTH_TIMEOUT` | `180` | Seconds to wait for the API. Raise it on a cold first build. |
| `E2E_HEALTH_URL` | `http://localhost:8000/v1/health` | Non-default port. |

### A subset of flows

```bash
bash services/e2e/scripts/e2e_lifecycle.sh 01 03   # by number, still full lifecycle
```

### A single flow against a stack you manage

```bash
npx nx run e2e:stack-up
npx nx run e2e:test-single --test=integration_test/04_shopping_list_test.dart
npx nx run e2e:stack-down
```

`scripts/run_all.sh` is the inner runner and assumes the stack is already
up — reach for it only when you are managing the stack yourself.

## Flows

| File | What it covers |
|------|----------------|
| `01_app_launch_test.dart` | App launches, bottom nav visible (auth bypass works) |
| `02_recipe_books_test.dart` | Create a recipe book, verify it appears |
| `03_create_recipe_test.dart` | Recipe wizard end to end, save |
| `04_shopping_list_test.dart` | Create list, add items, check one off |
| `05_calendar_test.dart` | Calendar loads, current week renders |
| `06_search_test.dart` | Search accepts input, no crash |
| `07_ai_chat_test.dart` | AI assistant opens, responds (mocked) |
| `08_meals_home_promotion_test.dart` | Home long-press → Create Meal → meal appears in grid |

The population is the `integration_test/0*_test.dart` glob — a new flow
joins the suite by being numbered. `integration_test/perf_audit/` is a
subdirectory and stays out by construction.

## Gotcha: `API_BASE_URL` defaults to production

`app/lib/core/config/environment.dart` defaults `API_BASE_URL` to
`https://api.palateful.app`. A build without an explicit define talks to
**production** — with the fixed e2e token. Every invocation in this
directory (and the `test-single` / `test-headless` nx targets) pins
`--dart-define=API_BASE_URL=http://localhost:8000`. If you hand-roll a
`flutter drive`, pass it yourself.

## Gotcha: ChromeDriver flake

`flutter drive -d chrome` intermittently fails to attach to the freshly
launched Chrome device between consecutive flows
(`AppConnectionException`). `run_all.sh` kills stale
`flutter_tools_chrome_device` processes before every attempt and retries a
flow **exactly once**, and **only** on that signature. Any other failure
fails immediately — a blanket retry would mask real regressions.

## How the auth bypass works

The app is built with `--dart-define=E2E_MODE=true`, which sets
`kE2EMode = true` in `main.dart`: Auth0 is skipped and the fixed token
`e2e-test-token` is injected.

The API is started with `E2E_TEST_MODE=true` **and**
`ENVIRONMENT=development` (`docker-compose.e2e.yml`) — the gate in
`services/api/src/dependencies.py` requires both, plus the matching token,
before it returns the seeded test user (`e2e@palateful.test`) without
calling Auth0. The user is lazy-created on first request, so there is no
SQL seed step.

The overlay also repoints the API at `postgresql://…/test`, the database
`migrator-test` migrates. E2E writes never touch your local dev data.

## Writing a flow

`app/integration_test/helpers.dart` carries the primitives every existing
flow uses — prefer them over raw `pumpAndSettle()`, which never settles on
a screen with a shimmer loader:

- `waitFor(tester, finder)` — pump until a specific widget proves the
  screen is ready. This is how you wait for navigation or data loading.
- `settle(tester)` — a `pumpAndSettle` that tolerates perpetual animations.
- `tapText(tester, 'Save')` — find by visible text, ensure visible, tap.

Number the file (`09_…_test.dart`) or it will not join the glob.

## Not in CI

`.github/workflows/ci.yml` runs with `--exclude=e2e`. This suite is a
local/manual gate; wiring it into CI is deliberately out of scope for now.
