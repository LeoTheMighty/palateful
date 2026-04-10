# Story 13.8: End-to-End Integration & Eval Gates

## Status: Complete

## What Was Done

### 1. New Eval Fixtures (4 recipes)

Added four new text fixture pairs to `services/eval/fixtures/`:

| Fixture | Ingredients | Steps | Prep | Cook | Servings |
|---|---|---|---|---|---|
| `chocolate_chip_cookies` | 10 | 8 | 15 min | 12 min | 36 |
| `chicken_tikka_masala` | 19 (incl. spices) | 8 | 20 min | 40 min | 4 |
| `simple_pasta` | 5 | 4 | 5 min | 15 min | 2 |
| `banana_bread` | 8 | 6 | 10 min | 60 min | 8 |

Each fixture consists of:
- `fixtures/text/<name>.txt` -- realistic recipe text (as if copy-pasted from a website)
- `fixtures/expected/<name>.json` -- ground truth JSON following the standard extraction schema

The fixtures cover a range of recipe types (cookies, Indian curry, simple weeknight meal, baking) and complexity levels (5-19 ingredients, 4-8 steps).

### 2. Eval Gate Script

**File:** `services/eval/src/gate.py`

A CI-ready gate script that:
- Runs the fixture-based eval suite via `fixture_runner.run_eval()`
- Reads the aggregate `overall_f1_avg` from results
- Compares against configurable thresholds per input type:
  - `text`: 0.80 (80% F1)
  - `image`: 0.70 (70% F1 -- more lenient for image extraction)
  - `url`: 0.85 (85% F1)
- Exits with code 0 on pass, code 1 on failure
- Accepts optional CLI arguments for fixtures directory and strategy

### 3. NX Target

Added `eval-gate` target to `services/eval/project.json`:
```json
"eval-gate": {
  "executor": "nx:run-commands",
  "options": {
    "command": "poetry run python -m src.gate",
    "cwd": "{projectRoot}"
  }
}
```

Run with: `npx nx run eval:eval-gate`

### 4. Sprint Status

Updated `_bmad-output/implementation-artifacts/sprint-status.yaml`:
- All Epic 13 stories marked as `done`
- `epic-13` marked as `done`

## Files Changed

- `services/eval/fixtures/text/chocolate_chip_cookies.txt` (new)
- `services/eval/fixtures/text/chicken_tikka_masala.txt` (new)
- `services/eval/fixtures/text/simple_pasta.txt` (new)
- `services/eval/fixtures/text/banana_bread.txt` (new)
- `services/eval/fixtures/expected/chocolate_chip_cookies.json` (new)
- `services/eval/fixtures/expected/chicken_tikka_masala.json` (new)
- `services/eval/fixtures/expected/simple_pasta.json` (new)
- `services/eval/fixtures/expected/banana_bread.json` (new)
- `services/eval/src/gate.py` (new)
- `services/eval/project.json` (modified -- added `eval-gate` target)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified -- Epic 13 done)
- `_bmad-output/implementation-artifacts/13-8-end-to-end-integration-and-eval-gates.md` (new -- this file)

## Acceptance Criteria

- [x] At least 4 new text fixtures with realistic recipe text and ground truth JSON
- [x] Fixtures cover diverse recipe types (cookies, curry, pasta, baking)
- [x] Eval gate script with configurable thresholds per input type
- [x] Gate exits non-zero on failure for CI integration
- [x] NX target `eval-gate` wired up in project.json
- [x] All Epic 13 stories marked done in sprint status
