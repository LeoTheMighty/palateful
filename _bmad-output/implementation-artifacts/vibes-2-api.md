# Story Vibes.2: API — Vibe Fields, Vibe Filter, Import Pipeline Integration

Status: complete

## Story

As a user,
I want the API to return vibe data on recipes and support filtering by vibe,
so that the frontend can display vibes and let me browse by mood.

## Acceptance Criteria

1. `GET /recipes` and `GET /recipe-books/{id}/recipes` responses include `primary_vibe` and `secondary_vibe` fields
2. `GET /recipes?vibe=comfort` filters recipes by primary OR secondary vibe
3. `PUT /recipes/{id}` accepts `primary_vibe` and `secondary_vibe` for user overrides
4. `GET /recipes/vibes/options` returns the list of valid vibes with display names and colors (for frontend rendering)
5. Import pipeline automatically populates vibes — no separate step needed
6. Vibe is included in recipe embedding text for improved semantic search

## Tasks / Subtasks

- [x] Task 1: Update recipe response schemas (AC: #1)
  - [x] Add `primary_vibe: str | None` and `secondary_vibe: str | None` to `RecipeResponse` and `RecipeListItem`
  - [x] Ensure all recipe list endpoints return vibe fields

- [x] Task 2: Add vibe filter to recipe queries (AC: #2)
  - [x] Add optional `vibe` query parameter to recipe list endpoints
  - [x] Filter: `WHERE primary_vibe = :vibe OR secondary_vibe = :vibe`
  - [x] Works alongside existing filters (meal type, search, tags)

- [x] Task 3: Allow vibe updates (AC: #3)
  - [x] Add `primary_vibe` and `secondary_vibe` to `RecipeUpdate` schema
  - [x] Validate against the allowed vibe values
  - [x] Allow setting to `null` to clear vibes

- [x] Task 4: Vibe options endpoint (AC: #4)
  - [x] Create `GET /recipes/vibes/options` returning:
    ```json
    [
      {"id": "light_fresh", "name": "Light & Fresh", "color": "#A8D8A8"},
      {"id": "hearty", "name": "Hearty & Filling", "color": "#D4A853"},
      {"id": "comfort", "name": "Comfort", "color": "#CB8B73"},
      {"id": "energizing", "name": "Energizing", "color": "#8FA882"},
      {"id": "carb_load", "name": "Carb-Load", "color": "#C8A96E"},
      {"id": "indulgent", "name": "Indulgent", "color": "#8B6B8B"},
      {"id": "warming", "name": "Warming", "color": "#A0522D"}
    ]
    ```
  - [x] This lets the frontend stay in sync without hardcoding vibe metadata

- [x] Task 5: Include vibes in embedding text (AC: #6)
  - [x] Modify `generate_recipe_embedding` to include vibe in the input text:
    ```python
    input_text = f"{name}. {description}. Tags: {tags}. Vibe: {primary_vibe}"
    ```
  - [x] This improves semantic search: "light fresh salad" will better match Light & Fresh recipes

- [x] Task 6: Verify import pipeline integration (AC: #5)
  - [x] Verify that ImportItem → Recipe creation copies vibes from parsed_recipe
  - [x] Test: import a recipe via URL → confirm vibes are populated on the created recipe
  - [x] Test: import via text paste → confirm vibes
  - [x] Test: import via spreadsheet → confirm vibes

## Dev Notes

- The vibe filter is additive to existing filters — it doesn't replace them
- The options endpoint is a static list for now — could become dynamic if we add custom vibes later
- Colors are sent from the API so the frontend doesn't need to hardcode them — makes it easy to adjust
- Embedding text modification is a one-line change in the existing function

### References

- [Investigation: 10-health-vibes-score.md — API Changes section]
- [Epic: epic-vibes.md]
