# Story Vibes.3: Flutter — VibeChip Widget, Recipe Card + Detail Integration

Status: complete

## Story

As a user,
I want to see colored vibe pills on my recipe cards and detail screens,
so that I can instantly get a feel for what kind of meal each recipe is.

## Acceptance Criteria

1. `VibeChip` widget renders a colored pill with a dot and label (e.g., "● Comfort" in terracotta)
2. Recipe cards on the home screen show up to 2 vibe chips below the recipe image
3. Recipe detail screen shows vibe chips prominently near the title/metadata area
4. Vibe colors come from the API options endpoint (not hardcoded in Flutter)
5. Recipes without vibes show no chips (graceful absence, not empty placeholders)
6. Vibe chips work correctly in both light and dark mode
7. Tapping a vibe chip on the detail screen does nothing for now (override is Story 4)

## Tasks / Subtasks

- [x] Task 1: Fetch and cache vibe options (AC: #4)
  - [x] Call `GET /recipes/vibes/options` on app startup or first use
  - [x] Cache in a provider: `Map<String, VibeOption>` with id, name, color
  - [x] Expose via `vibeOptionsProvider` for widgets to consume

- [x] Task 2: Create VibeChip widget (AC: #1, #6)
  - [x] Create `app/lib/shared/widgets/vibe_chip.dart`
  - [x] Input: `vibeId` (e.g., "comfort") + `VibeOption` from provider
  - [x] Render: colored circle (8px) + label text in a rounded pill container
  - [x] Pill background: vibe color at 15% opacity
  - [x] Text + dot: vibe color at full opacity
  - [x] Ensure contrast in both light and dark mode (test all 7 colors)
  - [x] Compact sizing: fits alongside existing recipe card metadata

- [x] Task 3: Integrate into RecipeCard (AC: #2, #5)
  - [x] Modify `app/lib/features/home/widgets/recipe_card.dart`
  - [x] Show VibeChip(s) in the card — position below image, above or alongside existing tags
  - [x] Show primary vibe always, secondary vibe if it exists (max 2 chips)
  - [x] If recipe has no vibes (`primary_vibe == null`): show nothing, no empty space

- [x] Task 4: Integrate into RecipeDetailScreen (AC: #3, #5, #7)
  - [x] Modify `app/lib/features/recipes/recipe_detail_screen.dart`
  - [x] Show VibeChip(s) near the title area, after the recipe name or near the metadata strip
  - [x] Slightly larger chips than the card version for detail screen prominence
  - [x] If no vibes: show nothing

- [x] Task 5: Update recipe model in Flutter (AC: #2, #3)
  - [x] Add `primaryVibe` and `secondaryVibe` fields to the Flutter recipe model/DTO
  - [x] Parse from API responses

## Dev Notes

- The VibeChip is intentionally simple for V1: colored dot + text label. No custom icons
- Existing `RecipeCard` already shows tags as pills — VibeChip follows the same visual pattern but with vibe-specific colors
- The 15% opacity background ensures the pill is visible but not overwhelming on the card
- Colors from API: the provider fetches once and caches. If the API is unreachable, fall back to a hardcoded default map
- Dark mode: vibe colors should work as-is against dark backgrounds (the soft pastels have good contrast). Test to verify

### References

- [Investigation: 10-health-vibes-score.md — Display & Visualization section]
- [Epic: epic-vibes.md]
