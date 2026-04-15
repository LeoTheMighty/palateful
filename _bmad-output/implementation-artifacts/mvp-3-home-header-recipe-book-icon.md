# Story MVP.3: Home Header — Add Recipe Book Icon, Remove Redundant "See All" Link

Status: ready-for-dev

## Story

As a user on the home screen,
I want a first-class Recipe Book icon in the top header next to Chat,
so that I can jump into my books from the main surface without hunting for a hidden "See All" text link.

## Context

The home screen header at `app/lib/features/home/home_screen.dart` inside `_buildSearchHeader()` (lines 508–559) currently contains:

- Search bar
- `CircleIconButton` with `Icons.chat_bubble_outline` at lines 541–545 (Chat)
- `CircleIconButton` for Photo Import at lines 549–555

The Recipe Books screen already exists (`app/lib/features/recipe_books/recipe_books_screen.dart`, route `/recipe-books` registered at `app/lib/core/router/app_router.dart:373`). The only current path to it from the home screen is a "See All" text link at line 581 which is easy to miss.

This story promotes Recipe Books to a first-class header icon and removes the redundant text link. Per Sally's UX note from Party Mode, the icons should be visually grouped to reflect their verbs: **navigation** (Books, Chat) vs **action** (Import).

## Acceptance Criteria

1. A new `CircleIconButton` for Recipe Books appears in `_buildSearchHeader()` using a book icon (recommend `Icons.menu_book_outlined` for consistency with the outlined icon style already used by Chat).
2. Icon order in the header: `[Search bar] [📖 Books] [💬 Chat] [📷 Import]`.
3. Tapping the Books icon navigates to `/recipe-books` via `context.push('/recipe-books')`.
4. The icons are visually grouped as navigation (Books + Chat) vs action (Import) — use a small spacing gap or subtle divider between Chat and Import so the eye reads two groups, not three equal items.
5. The "See All" text link at `home_screen.dart:581-590` is **removed**.
6. The existing Chat and Import icons behave exactly as before — this story only adds one icon and removes one text link.
7. Widget test: tapping the Books icon navigates to the `/recipe-books` route.
8. The same `CircleIconButton` component is reused — do not introduce a new icon-button style.

## Tasks / Subtasks

- [ ] Task 1: Add the Recipe Books icon to the header (AC: #1, #2, #3, #8)
  - [ ] Modify `app/lib/features/home/home_screen.dart` `_buildSearchHeader()` (around line 541)
  - [ ] Add a `CircleIconButton` **before** the Chat icon with `Icons.menu_book_outlined`
  - [ ] `onTap`: `context.push('/recipe-books')`
  - [ ] Reuse the exact same `CircleIconButton` component already used by Chat at line 541 — no new styling

- [ ] Task 2: Visually group navigation vs action icons (AC: #4)
  - [ ] Between the Chat icon and the Import icon, insert a small horizontal spacer (e.g. `SizedBox(width: 8)` or whatever matches the existing theme spacing scale)
  - [ ] Keep Books and Chat tightly grouped (standard spacing, no spacer between them)
  - [ ] Do not add a visible divider line unless the spacing gap alone doesn't read clearly — prefer whitespace over chrome

- [ ] Task 3: Remove the redundant "See All" text link (AC: #5)
  - [ ] Delete the text link widget at `home_screen.dart:581-590`
  - [ ] Audit the surrounding section — if the "See All" was inside a `Row` with a section title, clean up any now-orphaned alignment or spacing
  - [ ] Do not remove the section title itself; only the text link

- [ ] Task 4: Widget test (AC: #7)
  - [ ] Test location: `app/test/features/home/home_screen_test.dart` (create if missing)
  - [ ] Pump `HomeScreen` with a test router, find the Books icon by its icon data or semantic label, tap it, assert navigation to `/recipe-books`
  - [ ] Also assert the "See All" text link is absent (regression test for the removal)

## Dev Notes

- **Do not introduce a new icon-button widget** — the existing `CircleIconButton` at line 541 is the styled component. Reuse it directly.
- Icon choice: `Icons.menu_book_outlined` matches the `_outlined` suffix already used by Chat (`Icons.chat_bubble_outline`). If Leo has a preference for a different book icon, update at implementation time.
- The home screen file is large — do not attempt to refactor unrelated sections. This story touches `_buildSearchHeader()` and the "See All" link only.
- Semantic labels: add `semanticLabel: 'Recipe Books'` on the icon button for accessibility (match the pattern of existing icons if they set labels).
- This story has **no backend changes** and **no model changes**. Pure Flutter.
- This story and MVP.4 both touch `home_screen.dart`. Land this one first to avoid merge conflicts; MVP.4 removes widgets further down the file.

### Project Structure Notes

- Flutter test directory convention: `app/test/features/...` mirrors `app/lib/features/...`.
- `CircleIconButton` is the existing header icon component — grep for its definition to verify signature before use.

### References

- Header implementation: `app/lib/features/home/home_screen.dart:508-559`
- Chat icon reference: `home_screen.dart:541-545`
- "See All" link to remove: `home_screen.dart:581-590`
- Recipe books screen: `app/lib/features/recipe_books/recipe_books_screen.dart`
- Route registration: `app/lib/core/router/app_router.dart:373`
- [Epic: epic-mvp-finalization.md]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
