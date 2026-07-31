# Eval Fixtures

This directory contains test fixtures for evaluating recipe extraction strategies,
plus the conversational tool-trace fixtures for the Meal agent (`meal_*.json`).

## Directory Structure

```
fixtures/
  text/                # Plain text inputs (e.g. OCR output)
  images/              # Image inputs (photos of recipes)
  urls/                # URL test configs (JSON with url field)
  expected/            # Ground truth JSON files
  ingredient_fidelity/ # eri-5 ingredient field-completeness cases (YAML)
  meal_*.json          # msa-4 Meal-agent tool-trace fixtures (see below)
```

## Naming Convention

Fixtures are matched by filename stem. For example:

- `text/potato_quiche.txt` matches `expected/potato_quiche.json`
- `images/banana_bread.jpg` matches `expected/banana_bread.json`
- `urls/allrecipes_pasta.json` matches `expected/allrecipes_pasta.json`

## Adding a New Fixture

1. Place the input file in the appropriate subdirectory (`text/`, `images/`, or `urls/`).
2. Create a matching expected JSON file in `expected/` with the same stem name.
3. The expected JSON should follow the standard recipe extraction schema:

```json
{
  "name": "Recipe Name",
  "description": "Brief description",
  "prep_time_minutes": 15,
  "cook_time_minutes": 30,
  "servings": 4,
  "ingredients": [
    {
      "text": "2 cups all-purpose flour",
      "quantity": 2,
      "unit": "cups",
      "name": "all-purpose flour"
    }
  ],
  "instructions": "Step-by-step instructions as a single string."
}
```

## Running Evals

```bash
# Run text extraction eval against all text fixtures
npx nx run eval:run-fixtures

# Run with a specific strategy
npx nx run eval:run-fixtures -- --strategy text_extractor

# Compare multiple strategies
npx nx run eval:run-fixtures -- --compare text_extractor,ocr_then_text
```

## URL Fixture Format

URL fixtures are JSON files with the following structure:

```json
{
  "url": "https://example.com/recipe",
  "description": "Optional description of what this tests"
}
```

## Meal-agent tool-trace fixtures (`meal_*.json`, msa-4)

Seven fixtures describe conversational traces over the Meal MCP tool surface:
what the user says, which tools the AI is expected to call, in what order, with
which arguments, and what each tool handed back. They exist because the AI
performs **mutations the user didn't double-check** — a silent regression in
tool dispatch or parameter parsing is a data-integrity bug on a real Meal
library, so every mutating tool and every ambiguity path gets a fixture.

| File | Covers |
|---|---|
| `meal_create_from_explicit_ids.json` | Unambiguous names → one `create_meal` with 2 components |
| `meal_create_from_fuzzy_names.json` | Ambiguous "kale one" → clarify **before** writing |
| `meal_create_with_clarification_needed.json` | No signal → list candidates, commit nothing at all |
| `meal_update_name.json` | Rename only → one `update_meal`, no component churn |
| `meal_add_and_remove_component.json` | Add then remove, both silent; variation drives the degenerate-remove gate → `archive_meal` |
| `meal_archive_with_references.json` | Live references → `CONFIRMATION_REQUIRED`, then `archive_meal(confirmed=True)` |
| `meal_event_with_meal_id.json` | "Schedule the Summer Lunch Meal for Monday dinner" → `create_meal_event(meal_id=…, recipe_id=null)` |

### Format

```jsonc
{
  "id": "<must equal the filename stem>",
  "epic_fixture": 1,          // 1-7, unique across the set
  "story": "msa-4",
  "title": "...",
  "description": "...",
  "tags": ["meals", "mcp"],
  "context": {                 // starting state the AI is allowed to know
    "recipe_book_id": "<uuid>",
    "recipes": [{"id": "<uuid>", "name": "Kale Salad"}],
    "meals":   [{"id": "<uuid>", "name": "...", "component_recipe_ids": ["<uuid>"]}],
    "calendar_id": "<uuid>",   // only where the trace schedules something
    "meal_events": [], "recurrence_rules": []
  },
  "turns": [{
    "user": "what the user typed",
    "expected_tool_calls": [{
      "name": "create_meal",   // must be a real MCP tool
      "optional": false,       // true = the AI may skip this read
      "arguments": {...},      // must match the tool's real signature
      "tool_result": {...}     // what came back; drives the next turn
    }],
    "expect_clarifying_question": false,
    "expect_response_contains": ["substrings the reply must mention"]
  }],
  "assertions": {
    "committed_write_calls": 1,   // write calls that actually mutated
    "blocked_write_calls": 0,     // write calls answered CONFIRMATION_REQUIRED
    "required_tools": ["create_meal"],
    "forbidden_tools": ["archive_meal"]
  },
  "variations": [ /* optional: full scenarios with their own context/turns/assertions */ ]
}
```

A tool call counts as **blocked** when its `tool_result.error` is
`CONFIRMATION_REQUIRED` — the gate fired and nothing was written.

### Rules the fixtures must satisfy

Enforced by `src/meal_agent_fixtures.py::validate_fixture`:

- A turn with `expect_clarifying_question: true` must commit **zero** writes
  (a blocked write is fine — that's how the AI learns it needs to ask).
- A gated tool may only commit on a **later** turn, after the user answered.
  `archive_meal(confirmed=True)` without a prior `CONFIRMATION_REQUIRED` is a
  failure: the AI must not pre-confirm on the user's behalf.
- `create_meal_event` must state both `recipe_id` and `meal_id` explicitly and
  set exactly one of them (`ck_meal_events_recipe_xor_meal`), plus a
  `calendar_id`.
- `create_meal` needs ≥ 2 distinct `component_recipe_ids`.
- Every id passed as an argument must have come from `context` or from an
  earlier `tool_result` — no ids from nowhere.
- Ids must be valid lowercase-hex UUIDs (PostgreSQL rejects anything else).
- The declared write counts must match the trace they describe.

### Running the gate

```bash
npx nx run eval:meal-agent-gate     # the 7 fixtures + validator (no OpenAI calls)
npx nx run eval:test                # whole eval suite, includes the above
npx nx run api:test                 # cross-checks fixtures vs. real MCP signatures
```

Both halves run in CI via `nx affected -t test`. The eval-side test checks the
fixtures' internal consistency; `services/api/tests/mcp_server/test_meal_agent_eval_fixtures.py`
checks that every tool name and argument key still exists on the real
`@mcp.tool()` signatures. One failure blocks ship.
