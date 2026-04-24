<!-- refined via party-mode 2026-04-17 -->
# Epic: Home Header Polish + Post-Add Navigation Fix

## Overview

Two small dogfood bugs cluster on the home screen / add-recipe path. Neither individually justifies an epic; together they finish the header-declutter work started in `epic-bugs-home-and-foundations` and close the "after add, back where I was" gap.

**Goal:** After this epic, (a) the home header has no photo-batch shortcut icon — the sole discoverable path to photo import is the Add Recipe sheet → From Photo, and (b) every add-recipe flow that currently hard-navs to `/` returns the user to the screen they launched from whenever a prior screen exists. "Add another" from the same context is a first-class, non-jarring action.

## Design Principles (refined via party-mode 2026-04-17)

1. **Delete, don't restyle** — same as the prior AI-chat removal. No replacement icon, no tooltip adjustments on surviving icons, no icon reshuffling.
2. **Respect the nav stack** — `context.pop()` over `context.go('/')`. Hard navs to home are the exception (cold launch), not the default.
3. **"Add another" is the success state** (PM lens) — the nav fix is not just about landing in the right place; it's about keeping the `+` FAB on the destination screen so the user can immediately queue another add. Integration tests assert `+` is tappable on the landing screen post-return.
4. **GoRouter routes have no `name:` in this codebase** (frontend lens) — route identification is by path string. The matcher uses `GoRouterState.of(context).matchedLocation` captured at push time, not `settings.name`. `popUntil` matches on a stashed path string or falls back to `r.isFirst`.
5. **Matcher must survive `pushReplacement` origins** (UX + frontend lens) — text/PDF/spreadsheet/audio entry points `pushReplacement` to review-list, so the entry-point screen is gone from the stack by the time terminal actions fire. "Originating route" for review-list means **the route below the entry-point screen at push time** — captured from the router state at pushReplacement time, not the ephemeral entry-point path.
6. **Cold-launch guard uses GoRouter, not raw Navigator** (frontend lens) — `GoRouter.of(context).canPop()` is the correct check; raw `Navigator.of(context).canPop()` can be fooled by any intermediate shell route on the stack.
7. **Mid-review errors still respect the nav stack** (UX lens) — if extractor errors after push to review-list, the error state's Close button uses the same pop-or-home helper as the success terminals; no separate "error goes to home" path.
8. **The review-list hub stays** — it's a real user action surface. Only its terminal transitions change.
9. **No new abstraction** — two inline fixes are cheaper than a centralized `RecipeCreationNavigator` for this surface area. Revisit only if a fourth post-create behavior appears.
10. **Tests follow the user** — integration tests assert "user is on expected screen after Approve" for each entry point, not "screen X's internals work." Hardware back-button behavior is a named regression target, not left implicit.

## Locked Decisions (carry forward to notifications workshop)

- **Route matching uses GoRouter's `matchedLocation` (path string), not `RouteSettings.name`.** Named-route conventions are not in use here; do not introduce them for one feature.
- **Cold-launch detection uses `GoRouter.of(context).canPop()`**, not `Navigator.of(context).canPop()`. Any future "pop-or-home" helper should mirror this.
- **When a flow uses `pushReplacement` mid-funnel, the "caller" that matters is the stack entry below the replaced screen**, captured at push time. Never rely on the replaced screen's own route being on the stack after replacement.
- **Mid-flow error terminals reuse the success terminal's nav helper** — error paths are not a separate nav surface.
- **Hardware back button is a named test target** on any story that touches terminal nav — don't leave it implicit.
- Match the prior epic's carry-forward: no feature flags, no backwards-compat shims, audit-log admin mutations (inherited — not exercised in this epic), delete-don't-restyle, inline fixes over new abstractions.

## End-user flow

### Flow A — Header cleanup

1. User opens Palateful; home screen loads.
2. The top row shows: Recipe Books icon, search bar, Pantry icon, Sort/Filter funnel. No camera/image icon.
3. User taps the `+` FAB → Add Recipe sheet → "From Photo" to reach the photo-import flow. That entry point is unchanged.
4. If the user has an in-flight photo batch from before (or started from somewhere else), the `BatchImportStatusWidget` on the home grid still shows progress and is tappable — batch monitoring is not affected.

### Flow B — Post-add navigation (share-sheet)

1. User is reading an article in Safari. They hit Share → Palateful.
2. Palateful opens into the Share Import screen (cold launch or warm). The screen processes the URL, extracts the recipe, shows it for approval.
3. User taps Approve (or Dismiss, or Close).
4. **Warm launch** (Palateful was already open): the screen pops and the user is returned to wherever they were before the share-sheet took over.
5. **Cold launch** (Palateful was closed): there is no prior screen to return to, so the user lands on home.
6. User never sees a jarring hard nav to home when they had a prior context.
7. **Add another:** on return the `+` FAB is tappable; a second share→approve round-trip lands on the same origin, not on a stale intermediate.

### Flow C — Post-add navigation (text paste from recipe book detail)

1. User is on the "Weeknight Dinners" recipe book detail.
2. User taps `+` → Add Recipe sheet → "Paste Text" → pastes → submits.
3. The app `pushReplacement`s to review-list (`/recipes/import/review-list/$jobId`). Because this is a replacement, the text-paste screen leaves the stack; the book detail remains one below.
4. User approves or dismisses and taps Close.
5. User is returned to "Weeknight Dinners" (reloaded), NOT home.
6. User taps `+` again from the same book to add another — continuity preserved.

### Flow D — Mid-review error

1. User pushes to review-list via any entry point.
2. Extractor errors partway (bad input, backend 5xx, etc.). The screen renders its error state with a Close action.
3. Close uses the same pop-or-home helper as the success terminals. Warm launches return to caller; cold launches land on home.

## Frontend changes

- `app/lib/features/home/home_screen.dart`
  - DELETE the `CircleIconButton` for `Icons.add_photo_alternate_outlined` (lines ~556–561).
  - DELETE `_pickMultiplePhotos()` (lines ~379–399) and `_showBatchConfirmDialog()` (lines ~401–438).
  - DELETE unused `image_picker` import (line ~5) and `_imagePicker` member (line ~32) if no remaining usages.
  - Adjust the header row's `SizedBox` spacing so the grid sits flush under the remaining icons (no gap where the button was).
- `app/lib/features/recipes/import/share_import_screen.dart`
  - Replace the three `context.go('/')` calls at lines ~216, ~237, ~250 with:
    ```dart
    GoRouter.of(context).canPop() ? context.pop() : context.go('/');
    ```
  - Inline; no new file.
- `app/lib/features/recipes/add_recipe/import_review_list_screen.dart` (canonical path)
  - Accept an optional `callerLocation` string via route `extra` at push time — the caller's `GoRouterState.matchedLocation` captured just before navigation.
  - For terminal actions (Approve-all, Dismiss-all, Close, and the error-state Close), invoke:
    ```dart
    final router = GoRouter.of(context);
    if (callerLocation != null && router.canPop()) {
      Navigator.of(context).popUntil((r) =>
        (r.settings.name == callerLocation) || r.isFirst);
      // If caller not found in the stack, r.isFirst halts the popUntil safely.
    } else if (router.canPop()) {
      context.pop();
    } else {
      context.go('/');
    }
    ```
  - The `r.settings.name == callerLocation` clause works because GoRouter stores the matched location string in `RouteSettings.name`. Verify this during dev with a single print statement before relying on it; if it doesn't hold, fall back to popping to the stack entry where `ModalRoute.of(context)?.settings.name` equals `callerLocation` via a local route introspection. Do NOT add `name:` attributes to `GoRoute` declarations — the codebase deliberately doesn't use them.
- Entry-point screens that `pushReplacement` to review-list (`text_paste_import_screen.dart`, `pdf_import_screen.dart`, `spreadsheet_import_screen.dart`, `audio_import_screen.dart`):
  - At push time, capture the **pre-entry-point** location — the route the user was on before they pushed the entry-point screen — by reading it from GoRouter's router delegate BEFORE the entry point was pushed. In practice this means: the entry-point screen receives `callerLocation` from its own push site, then forwards it to review-list in `extra`. For entry points launched from the Add Recipe sheet, capture `GoRouterState.of(context).matchedLocation` inside the sheet's onTap just before `context.push(...)`.
  - No behavioral change beyond threading `callerLocation` through `extra`. Their `pushReplacement` stays.
- `app/lib/features/recipes/add_recipe/bulk_url_import_screen.dart:614` uses `context.push` (not replacement) for review-list. Same `extra: {'callerLocation': ...}` payload; nothing else changes.
- `app/lib/features/activity/import_history_screen.dart:795` also pushes to review-list. Same payload.
- `app/lib/features/home/widgets/batch_import_status_widget.dart` — no change. It reads batch state from the provider, not from the home icon; confirmed no backend coupling to the removed icon.

## Backend changes

None. Architect lens confirms `BatchImportStatusWidget` reads from the batch-status provider, which subscribes to the existing `/v1/import/batches` endpoint. Removing the header icon does not orphan any backend surface.

## Infrastructure changes

None. No migrations, no env vars, no Terraform. No deploy ordering constraints.

## File structure (expected)

```
app/lib/features/home/
└── home_screen.dart                              # MODIFIED — remove batch-photo icon + handlers + image_picker import

app/lib/features/recipes/import/
└── share_import_screen.dart                      # MODIFIED — 3 context.go('/') → GoRouter canPop guard

app/lib/features/recipes/add_recipe/
├── import_review_list_screen.dart                # MODIFIED — accept callerLocation via extra; terminal actions popUntil
├── text_paste_import_screen.dart                 # MODIFIED — thread callerLocation in extra
├── pdf_import_screen.dart                        # MODIFIED — thread callerLocation in extra
├── spreadsheet_import_screen.dart                # MODIFIED — thread callerLocation in extra
├── audio_import_screen.dart                      # MODIFIED — thread callerLocation in extra
└── bulk_url_import_screen.dart                   # MODIFIED — thread callerLocation in extra

app/lib/features/activity/
└── import_history_screen.dart                    # MODIFIED — thread callerLocation in extra on review-list push

app/integration_test/
├── home_no_batch_photo_icon_test.dart            # NEW — asserts home header shape post-cleanup
└── post_add_recipe_nav_test.dart                 # NEW — per-entry-point landing + add-another + back-button assertions
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| home-polish-1 | Remove add-image icon from home header | 🟡 P1 | 0.25 d | None |
| home-polish-2 | Fix post-add-recipe navigation (share-sheet + review-list terminal) | 🟡 P1 | 0.5–1 d | None (parallel) |

**Total estimated effort: 0.75–1.25 days**

---

## Story home-polish-1: Remove add-image icon from home header

As Leo,
I want the multi-photo batch-import shortcut icon removed from the home screen header,
so that the header stops offering a redundant entry to a flow that already lives behind the `+` FAB's Add Recipe sheet.

### Acceptance Criteria

1. The `CircleIconButton` rendering `Icons.add_photo_alternate_outlined` at `home_screen.dart:556-561` is removed.
2. The helper methods `_pickMultiplePhotos()` and `_showBatchConfirmDialog()` are removed.
3. The `package:image_picker/image_picker.dart` import and the `_imagePicker = ImagePicker()` field are removed if and only if they have no remaining usages in `home_screen.dart` (grep first).
4. The header row's visual rhythm is preserved — the recipe grid sits flush under the remaining three header controls (books, search, pantry) plus the sort/filter funnel, with no empty gap.
5. `BatchImportStatusWidget` on the home grid is not touched. It continues to render in-flight batch progress for batches kicked off from any remaining entry point (Add Recipe sheet → From Photo). Confirmed no backend coupling to the removed icon (the widget reads from its own provider).
6. The Add Recipe sheet's "From Photo" entry (`add_recipe_sheet.dart:91-100`) is unchanged and remains the sole discoverable entry to the photo-import flow.
7. No feature flag, no analytics cleanup.
8. Integration test: a widget test loads the home screen and asserts that no descendant has `icon == Icons.add_photo_alternate_outlined`.

### Key Files
- Modify: `app/lib/features/home/home_screen.dart`
- Preserve: `app/lib/features/home/widgets/batch_import_status_widget.dart`, `app/lib/features/recipes/add_recipe_sheet.dart`, the whole photo-capture flow.
- Test: `app/integration_test/home_no_batch_photo_icon_test.dart` (or the project-standard test path).

---

## Story home-polish-2: Fix post-add-recipe navigation

As Leo,
I want to land back on the page I launched the add-recipe flow from, not on the home screen,
so that adding a recipe from a book keeps me in that book, adding via share-sheet keeps me where I came from, and I can queue up another add without losing context.

### Acceptance Criteria

1. **Share-sheet terminals (warm/cold launch split).** `share_import_screen.dart` — the three `context.go('/')` calls at lines ~216, ~237, ~250 (Approve, Dismiss, Close) are each replaced with:
   ```dart
   GoRouter.of(context).canPop() ? context.pop() : context.go('/');
   ```
   Warm-launch users pop back to their prior screen; cold-launch users (no nav stack under the share-import route) still land on home. Use `GoRouter.of(context).canPop()` specifically — not `Navigator.of(context).canPop()` — to avoid being fooled by any intermediate shell route.

2. **Review-list terminals return to the originating screen.** The review-list screen (`app/lib/features/recipes/add_recipe/import_review_list_screen.dart`) accepts an optional `callerLocation: String?` via route `extra`. Terminal actions (Approve-all, Dismiss-all, Close, and the error-state Close button) invoke a helper that:
   - If `callerLocation` is non-null and the stack contains a route whose `settings.name` equals it, `popUntil` to that route (with `r.isFirst` as the terminal fallback so we never dead-end).
   - Else if the router can pop, `context.pop()`.
   - Else `context.go('/')` (cold-launch safety).

   The `settings.name` match works because GoRouter writes the matched location string into `RouteSettings.name`. Dev verifies this with one print statement on first-run; if the behavior differs, fall back to `r.isFirst`-only pop semantics rather than introducing named-route declarations.

3. **`callerLocation` is threaded through `extra` from every review-list push site.** Files touched: `text_paste_import_screen.dart:57`, `pdf_import_screen.dart:81`, `spreadsheet_import_screen.dart:84`, `audio_import_screen.dart:136`, `bulk_url_import_screen.dart:614`, `import_history_screen.dart:795`. At each site, read `GoRouterState.of(context).matchedLocation` **before** the `pushReplacement`/`push` and include it as `extra: {..., 'callerLocation': callerLocation}`. For entry-point screens that use `pushReplacement`, the `callerLocation` they forward is the one they themselves received from their own push site (i.e., the route below the entry-point screen) — not their own path, which is about to leave the stack.

4. **Add Recipe sheet and in-screen push sites capture and forward `callerLocation`.** Every place that pushes a review-list-bound entry-point screen (Add Recipe sheet items, recipe-book detail, etc.) captures `GoRouterState.of(context).matchedLocation` at onTap time and forwards it.

5. **Photo flow and recipe-book-detail flow are unchanged.** `photo_capture_screen.dart:381` `context.pop(true)` is the exemplar. The recipe-book-detail flow's `context.push` → `context.pop` → `_loadRecipeBook()` is unchanged.

6. **Mid-review error terminals use the same helper.** If the review-list extractor errors mid-flow, its error-state Close button uses the same pop-or-home helper — no separate nav path for errors.

7. **Hardware back button** on the review-list screen is routed through the same helper via `PopScope` / `WillPopScope` `onPopInvoked` (Flutter's newer `PopScope` preferred if on Flutter 3.12+). The back button lands the user in the same place as the Close action.

8. **Integration tests:**
   - Home → `+` → Share Import (warm launch simulation) → Approve → back on home. ✓
   - Recipe-book-detail → `+` → Paste Text → mock submit → review-list → Approve-all → back on recipe-book-detail (book reloaded). ✓
   - Share-sheet cold-launch (nav stack empty under share-import) → Approve → on home (fallback path). ✓
   - Home → `+` → Photo → pop → back on home (baseline regression guard). ✓
   - **"Add another"** — recipe-book-detail → `+` → Paste Text → Approve-all → back on book → `+` tappable → Paste Text again → Approve-all → back on book (no stack accumulation, no popUntil overshoot). ✓
   - **Hardware back button** — review-list reached via text-paste from book detail → press Android back → lands on book detail. ✓
   - **Mid-review error** — review-list extractor forced-error → tap Close → lands on origin (or home on cold launch). ✓

9. **No new service, no `RecipeCreationNavigator` abstraction.** Inline helper in review-list screen file; 3-line guard at each share-sheet callsite.

10. **Manual dogfood check:** run the app, add a recipe from within a recipe book via text paste, approve the extracted item, verify the book detail is back on screen with the new recipe visible; then immediately tap `+` again and add a second one to confirm the "add another" path.

### Key Files
- Modify: `app/lib/features/recipes/import/share_import_screen.dart`
- Modify: `app/lib/features/recipes/add_recipe/import_review_list_screen.dart` (accept `callerLocation`; helper for terminal actions; `PopScope` wiring for hardware back)
- Modify push sites to thread `callerLocation` via `extra`:
  - `app/lib/features/recipes/add_recipe/text_paste_import_screen.dart`
  - `app/lib/features/recipes/add_recipe/pdf_import_screen.dart`
  - `app/lib/features/recipes/add_recipe/spreadsheet_import_screen.dart`
  - `app/lib/features/recipes/add_recipe/audio_import_screen.dart`
  - `app/lib/features/recipes/add_recipe/bulk_url_import_screen.dart`
  - `app/lib/features/activity/import_history_screen.dart`
  - Plus any Add Recipe sheet / recipe-book-detail push sites that launch the entry-point screens (capture `matchedLocation` at onTap).
- Test: `app/integration_test/post_add_recipe_nav_test.dart`

### Risks / open considerations (folded into the story during party-mode)

- **`settings.name` match on GoRouter.** Routes in `app_router.dart` have no `name:` attribute — identification is by path. GoRouter sets `RouteSettings.name` to the matched location string, so the matcher should work, but dev verifies with one `print` before committing. Fallback: drop the matcher clause and rely on `r.isFirst` + plain `pop()` semantics.
- **`pushReplacement` swallows the origin.** Text/PDF/spreadsheet/audio entry points use `pushReplacement` to reach review-list; by then the entry-point screen is gone. The `callerLocation` forwarded from review-list must be the route **below** the entry-point screen, not the entry-point itself. Each push site captures `matchedLocation` from its own caller before navigating.
- **Cold-launch detection.** Using `GoRouter.of(context).canPop()` correctly ignores shell-level routes that raw `Navigator.of(context).canPop()` would count as poppable.
- **`popUntil` overshoot on rapid "add another".** After a successful pop-to-caller, the caller is once again the top of the stack. A subsequent add-recipe push is a fresh push; `popUntil` from the next review-list terminal still matches the freshly-captured `callerLocation`. Test #5 above guards this explicitly.
- **Hardware back button.** `PopScope` is wired so Android back matches in-screen Close behavior. Not left implicit.

## Dependencies

- No dependencies on other epics.
- home-polish-1 and home-polish-2 are independent; can be implemented in either order and in parallel.

## Open questions for the user

None. User's 2026-04-17 batch locked all scope decisions: home-polish-1 is a straight delete; home-polish-2 fixes only share-sheet + review-list terminal, not every `pushReplacement`. Party-mode confirmed the scope pins and surfaced only implementation details (route-naming convention, `pushReplacement` origin capture, hardware back, mid-review errors) which are baked into ACs.

## Definition of Done (Epic Level)

- Home screen header has no `Icons.add_photo_alternate_outlined` button. Confirmed by widget test.
- Add Recipe sheet → From Photo still works end-to-end.
- `BatchImportStatusWidget` still renders in-flight batches on the home grid.
- Share-sheet Approve/Dismiss/Close from a warm launch returns the user to their prior screen; cold launch returns to home.
- Review-list terminal actions (including error-state Close and hardware back) return the user to the originating screen (home or recipe book detail), not to `/`.
- "Add another" round-trip works: the `+` FAB is tappable on the landing screen after a successful return, and a second add-recipe round-trip lands on the same origin.
- Photo-capture and recipe-book-detail flows remain unchanged; integration tests guard against regression.
