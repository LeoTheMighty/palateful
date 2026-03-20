# Story Perf.2: Flutter Network & Caching

Status: done

## Story

As a user,
I want the app to load fast and not waste my mobile data,
so that I can use Palateful smoothly even on slow connections.

## Acceptance Criteria

1. **Parallel recipe loading** — Home screen loads recipes from all books in parallel using `Future.wait()` instead of sequential API calls. Load time reduces from O(n) to O(1) where n is number of books.
2. **Local state persistence** — Home screen does NOT refetch all recipes when returning from recipe detail. State persists across navigation. Only refetches on explicit pull-to-refresh or when a mutation occurs.
3. **Meal filter is client-side** — Meal type filter on home screen filters locally on cached data instead of triggering a full API refetch.
4. **Tests pass** — All Flutter tests pass.

## Tasks / Subtasks

- [ ] Task 1: Parallel recipe loading on home screen (AC: 1)
  - [ ] In `home_screen.dart` `_loadAllRecipesFromBooks()`: replace sequential `for` loop with `Future.wait()` to fetch all books in parallel
  - [ ] Keep error handling per-book (one failure doesn't block others)

- [ ] Task 2: Remove refetch on navigation return (AC: 2)
  - [ ] Remove `_loadRecipes()` call after `context.push('/recipes/...')` returns
  - [ ] Keep `_loadRecipes()` on `initState()` and pull-to-refresh
  - [ ] After mutations (edit, delete, archive), only refetch if the mutation changed the data

- [ ] Task 3: Client-side meal filter (AC: 3)
  - [ ] In `_onMealFilterChanged()`: remove `_loadRecipes()` call
  - [ ] Filter `_recipes` list locally based on `_mealFilter` value
  - [ ] Keep a separate `_allRecipes` master list; `_filteredRecipes` derived from it

- [ ] Task 4: Tests (AC: 4)
  - [ ] Run `flutter test` — all tests pass

## Dev Notes

### File Locations

- `app/lib/features/home/home_screen.dart` — all changes in this file

### References

- Performance audit findings (session context)
- Home screen sequential loading [Source: app/lib/features/home/home_screen.dart:99-111]
- Navigation refetch pattern [Source: app/lib/features/home/home_screen.dart:838-841]
- Meal filter refetch [Source: app/lib/features/home/home_screen.dart:216-222]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
