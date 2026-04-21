# QA walkthrough — pbq-7 list_meal_events eager load participants

## What shipped

`GET /v1/meal-events` attaches `selectinload(MealEvent.participants)`
as a sibling `.options(...)` entry alongside the existing
`meal.components.recipe` chain. The response loop's
`len(event.participants)` call now reads against an eager-loaded
collection instead of triggering a per-row lazy load.

## Before/after numbers

### Query count

| Page size | Pre-pbq-7 | Post-pbq-7 |
| --- | --- | --- |
| 20 events | 1 main + 1 `meal` chain + **20 lazy participants** | 1 main + 1 meal chain + **1 participants IN** |

### Latency (single-operator prod)

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --format csv --top 40 \
    | grep meal-events
```

Method: pin baseline → redeploy → 30-min follow-up. Single-operator
prod has few participants per event, so the pre-fix N lazy loads are
all single-row lookups via PK — fast per-hit but quickly dominate p95
as page size grows. Post-fix collapses to one `IN` batched fetch.

## How to verify

### 1. Local tests green

```bash
npx nx run api:test -- tests/test_meal_event.py::TestListMealEvents --no-cov
# 3 passed including pbq-7 assertion
```

### 2. Selectinload spy locks in the fix

`test_list_meal_events_eager_loads_participants_as_sibling_option`:

- Patches `api.v1.meal_event.list_meal_events.selectinload`.
- Asserts the outer-call attribute-key set contains both
  `"participants"` and `"meal"` — the sibling wiring is structural.
- Bounds `qc.query_count_for(MealEvent) <= 2`.

### 3. Response shape unchanged

```bash
curl -H "Authorization: Bearer <token>" \
     https://api.palateful.app/v1/meal-events
```

Each item carries `participant_count` as before — now fed from the
eager-loaded collection.

## Checklist

- [x] `selectinload(MealEvent.participants)` wired as a SIBLING
      option, not nested under `.meal`.
- [x] Test asserts both `"meal"` and `"participants"` in the outer
      selectinload attribute-key set.
- [x] Bounded query count on `MealEvent`.
- [x] Response shape byte-identical.

## Rollback

```bash
git revert <pbq-7-commit>
```

Drops the sibling option. No data migration.
