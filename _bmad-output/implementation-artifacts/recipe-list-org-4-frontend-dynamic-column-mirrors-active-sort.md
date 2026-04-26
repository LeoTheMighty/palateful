# recipe-list-org-4 — Frontend: dynamic column mirrors active sort

**Epic:** `epic-recipe-list-organization`
**Status:** done
**Order in epic:** 4 of 6

## Goal

Make the table-view's right-edge column work as the user's
*lens-by-sort* — its label and per-row values change as the user picks
a sort option, and tapping the column header flips sort direction.
This is the central UX bet of the epic ("the sort is the lens").

## Scope — files this story touches

**NEW**
- `app/lib/features/home/widgets/dynamic_column.dart` —
  `DynamicColumnSpec` value object + `dynamicColumnFor(SortOption)`
  helper. Also exports `formatDynamicColumnRelativeDate(DateTime?)`
  so the book-detail surface can read identically.
- `app/test/features/home/dynamic_column_test.dart` — exhaustive
  helper coverage (each SortOption + bucket boundaries +
  null/future/unparseable defenses).

**MODIFY**
- `app/lib/features/home/widgets/filter_bottom_sheet.dart` — add
  `SortOption.lastCooked` to the enum + the radio list
  (Icons.restaurant_rounded, label "Last cooked").
- `app/lib/features/home/home_screen.dart` —
  - Add `_sortReversed: false` to state.
  - Extend `_applySorting` with the `lastCooked` case (NULLS LAST
    on natural / NULLS FIRST when reversed) + tail-reverse for
    the deterministic-direction sorts when `_sortReversed`.
  - Reset `_sortReversed` to false when the bottom sheet picks a
    different sort.
  - Render `_DynamicColumnHeader` above the table view; tap fires
    `setState(() { _sortReversed = !_sortReversed; ... })`.
  - Populate each row's `RecipeTableTile.trailing` slot with the
    column-spec value. Meals fall back to the chevron (no
    last_cooked / cook_time / etc to resolve).
- `app/lib/features/recipe_books/recipe_book_detail_screen.dart` —
  Render a non-tappable `_BookDetailColumnHeader` ("Updated" + ↓)
  above the table view; populate each row's trailing with the
  shared `formatDynamicColumnRelativeDate(updatedAt)`.

## Acceptance criteria

1. **Helper contract.** `dynamicColumnFor(SortOption)` returns a
   `DynamicColumnSpec` with a label + value resolver per sort:
   - `lastCooked` → "Last cooked", relative date from `last_cooked`
     ("3d ago" / "Just now" / "—").
   - `quickest` → "Cook time", `prep_time + cook_time` minutes.
   - `newest` → "Added", relative date from `created_at`.
   - `best` → "Cooked", `times_cooked` count ("7×" / "—").
   - `popular` → "Popular", `popularity` score (one decimal).
   - `random` → falls back to "Last cooked" (no meaningful per-row
     value for shuffle).
2. **Atomic re-render.** When the user picks a new sort via the
   bottom sheet, the header label + every row value updates in the
   same frame as the row order changes. Implemented by re-running
   `_applySorting` inside the same `setState` that updates
   `_sortOption`.
3. **Header tap flips direction.** Tapping `_DynamicColumnHeader`
   toggles `_sortReversed` and re-runs `_applySorting`. Arrow icon
   swaps between ↓ (descending / natural) and ↑ (ascending /
   reversed).
4. **NULLS LAST on `lastCooked` desc.** Recipes with `last_cooked =
   null` sort to the bottom on descending, to the top on ascending.
   Cell renders "—".
5. **Direction reset on sort change.** Picking a different sort via
   the bottom sheet resets `_sortReversed = false` so the new sort
   shows in its natural direction. Re-applying the same sort keeps
   the user's chosen direction.
6. **Future / unparseable date defense.** The relative-date
   formatter returns "—" for null, future, and unparseable values
   instead of negative-time gibberish.
7. **Book-detail parity.** The book-detail table renders an
   informational "Updated ↓" header (no tap — book detail has no
   sort menu) and per-row relative dates from `updated_at`,
   identical vocabulary to the home column.

## Implementation notes

- **No new sort surface — extending the existing one.** The bottom
  sheet's `_SortRadioList._entries` gets one new row for "Last
  cooked"; everything else is unchanged. The dynamic column reads
  the same `_sortOption` state the bottom sheet writes to.
- **Direction lives on the screen, not in `HomeFilterState`.** The
  bottom sheet doesn't surface direction — it would be redundant
  with the column-header tap, and the epic explicitly avoids
  duplicating sort UI. So `_sortReversed` is a private home-screen
  field, not part of the apply payload.
- **`lastCooked` comparator handles direction internally.** The other
  sorts are descending-first; reversal happens via
  `sorted.reversed.toList()` at the end. `lastCooked` needs
  direction-aware NULL anchoring (NULLS LAST on desc, NULLS FIRST
  on asc) so the comparator itself reads `_sortReversed` and
  short-circuits the tail reverse for that case.
- **Meals don't get a dynamic column.** Meals don't carry
  `last_cooked` / `cook_time` / `created_at` in the home payload
  shape — passing one through `dynamicColumnFor` would produce
  "—" for every meal. Cleaner to render the chevron for meals
  instead, signalling "this row is a Meal, no per-sort value."
- **Book-detail header is non-tappable.** Book detail has no sort
  menu, so flipping direction has no UX surface. The header is
  informational ("here's the lens this list is sorted by"). If a
  book-detail sort menu lands later, this becomes a one-line
  refactor to make the header tappable.

## Tests added

`test/features/home/dynamic_column_test.dart` — 10 cases:
- each `SortOption` → correct label + value-shape on a sample row
- "Just now" / minutes / hours / yesterday / days / weeks / months
  / years buckets
- future date → "—"
- unparseable date → "—"

## File list

- NEW `app/lib/features/home/widgets/dynamic_column.dart`
- MODIFY `app/lib/features/home/widgets/filter_bottom_sheet.dart`
- MODIFY `app/lib/features/home/home_screen.dart`
- MODIFY `app/lib/features/recipe_books/recipe_book_detail_screen.dart`
- NEW `app/test/features/home/dynamic_column_test.dart`
- MODIFY `_bmad-output/implementation-artifacts/sprint-status.yaml`
