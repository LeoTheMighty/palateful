# Story Polish.1: Serving Scaler

Status: done

## Story

As a user,
I want to adjust the serving size on a recipe and see all ingredient quantities update automatically,
so that I can cook for more or fewer people without doing math in my head.

## Acceptance Criteria

1. Recipe detail screen shows current servings (e.g., "Serves 4") as a tappable/adjustable control
2. User can increase or decrease servings with +/- buttons or a slider
3. All ingredient quantities update in real-time based on the scale factor (newServings / originalServings)
4. Original servings value is preserved — scaling is display-only, not persisted
5. Scaled quantities show clean values (e.g., 1.5 not 1.4999, "1/2" not "0.5" where appropriate)
6. Cook mode also reflects the scaled quantities
7. "Add to Cart" uses the scaled quantities
8. Reset button returns to original servings
9. Works correctly when original servings is null (hide scaler, show as-is)

## Tasks / Subtasks

- [x] Task 1: Serving scaler UI on recipe detail (AC: #1, #2, #8)
  - [x] Add serving scaler widget near the top of the recipe detail screen (near prep time, cook time metadata)
  - [x] Display: "Serves [−] 4 [+]" with tappable +/- buttons
  - [x] Track `_scaleFactor` in state (default 1.0)
  - [x] Reset button (circular arrow icon) appears when scale != 1.0
  - [x] If recipe has no servings value, hide the scaler entirely

- [x] Task 2: Scale ingredient quantities (AC: #3, #5)
  - [x] When displaying ingredients, multiply each quantity by `_scaleFactor`
  - [x] Smart rounding:
    - Round to nearest 0.25 for quantities > 1 (e.g., 1.25, 1.5, 1.75)
    - Round to nearest 0.125 (1/8) for quantities < 1
    - Show fractions where natural: 1/2, 1/3, 1/4, 3/4, 1/8
    - Avoid ugly decimals (1.333... → "1 1/3")
  - [x] Handle null/empty quantities gracefully (items like "salt to taste" have no quantity)

- [x] Task 3: Preserve original values (AC: #4)
  - [x] `_scaleFactor` is local state only — never sent to API
  - [x] Original recipe data is not modified
  - [x] Navigating away and back resets to original

- [x] Task 4: Cook mode integration (AC: #6)
  - [x] Pass `_scaleFactor` to cook mode screen when entering cook mode
  - [x] Cook mode ingredient strip shows scaled quantities
  - [x] Cook mode step text shows original (don't modify instruction text)

- [x] Task 5: Add to Cart with scaled quantities (AC: #7)
  - [x] When "Add to Cart" is tapped with a non-1.0 scale factor:
    - Use scaled quantities for shopping list items
    - Show snackbar: "Added ingredients for X servings to [List Name]"

## Dev Notes

- Check the recipe model for the `servings` field — it should be an integer or nullable
- Ingredient model has `quantity` (numeric) and `unit` (string) fields — multiply `quantity` only
- For fraction display, consider a small utility: `formatQuantity(double value) → String`
  - 0.125 → "1/8", 0.25 → "1/4", 0.333 → "1/3", 0.5 → "1/2", 0.75 → "3/4"
  - 1.5 → "1 1/2", 2.25 → "2 1/4", etc.
  - Fallback: round to 2 decimal places for unusual values
- This is purely frontend — no API changes needed
- Every competitor has this feature — it's table stakes

### References

- [Competitor Analysis: 07-competitor-analysis-recime.md — every competitor listed has serving scaler]
