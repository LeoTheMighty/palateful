# recipe-defaults-4 — Frontend + audit: share-import fallback uses default_recipe_book_id consistently

**Epic:** `epic-recipe-default-books`
**Status:** review
**Order in epic:** 4 of 4 (final story)

## Why

Stories 1–3 land the schema, the new-user provisioning hook, and the
switcher UI. Story 4 closes the loop on the user-facing share-import
flows: confirm every entry point that lets a user start an import
without specifying a destination book consults
`AuthService.defaultRecipeBookId`, AND patches the one place in the
share-import path that fell back to an arbitrary `books.first` when no
default was set.

## Audit findings

| Entry point | File | Status |
|---|---|---|
| Share-extension receiver (deep-link / share-sheet) | `receive_import_screen.dart:209` | ✅ already uses `widget.bookId ?? _authService.defaultRecipeBookId` |
| Share-import screen (URL paste from share extension) | `share_import_screen.dart:69` | ⚠️ uses `defaultId` but falls back to **`books.first`** when null — patched here |
| Photo capture | `photo_capture_screen.dart:109` | ✅ uses `getIt<AuthService>().defaultRecipeBookId` |
| URL paste | `url_import_screen.dart:69` | ✅ uses default |
| Recipe wizard | `recipe_wizard_screen.dart:82` | ✅ uses default |
| Bulk URL import | `bulk_url_import_screen.dart:117` | ✅ uses default |
| Text paste | `text_paste_import_screen.dart:34` | ✅ uses default |
| Audio import | `audio_import_screen.dart:44` | ✅ uses default |
| PDF import | `pdf_import_screen.dart:39` | ✅ uses default |
| Spreadsheet import | `spreadsheet_import_screen.dart:40` | ✅ uses default |
| Video file import | `video_file_import_screen.dart:33` | ✅ uses default |

The audit confirms the existing client surface area is already well
behaved. The single remaining gap was `share_import_screen.dart`'s
`books.first` fallback, which would have routed a user with no
`defaultRecipeBookId` into whatever recipe book happened to be first
in their list — a non-deterministic destination.

## Patch

`share_import_screen.dart`'s "no default set" path now prefers a
`is_system=true` book (Trying Out) over `books.first`. Story 1 has
back-filled every existing user with one Trying Out book; story 2's
auth-callback hook ensures every new user gets one. The cache might
not yet reflect the server-side default-set on the very first
request, but the system book is reliably present in the list, so
preferring it is a deterministic improvement.

```dart
Map<String, dynamic>? systemBook;
for (final b in books) {
  if (b['is_system'] == true) {
    systemBook = b as Map<String, dynamic>;
    break;
  }
}

if (defaultId != null) {
  targetBook = books.firstWhere(
    (b) => b['id']?.toString() == defaultId,
    orElse: () => systemBook ?? books.first,
  );
} else {
  targetBook = systemBook ?? books.first;
}
```

## Scope — files this story touches

**MODIFY**
- `app/lib/features/recipes/add_recipe/share_import_screen.dart` —
  prefer system book over `books.first` when no default is set.

**NEW**
- `_bmad-output/implementation-artifacts/recipe-defaults-4-...md` (this file).
- `_bmad-output/implementation-artifacts/recipe-defaults-4-...-qa-walkthrough.md` (QA).

**MODIFY (sprint flip)**
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Out of scope

- **No new tests for the share-import fallback path.** The existing
  13 tests in `share_import_test.dart` + `share_import_screen_nav_test.dart`
  exercise the success path. Adding a "no default + system-book preferred"
  test would require a mocked `AuthService`/`readRecipeBooks` chain that
  isn't currently in place; the patch is small + reviewable inline,
  and the next story-set's regression sweep
  (`recipe-bulk-org-5` / `recipe-list-org-6`) re-exercises the
  share-import path under realistic conditions.
- **No backend changes.** The audit covers client-side fallbacks only.

## Acceptance criteria

1. **Share-sheet, photo, URL, share-extension** all consult
   `defaultRecipeBookId`. Verified by audit table above.
2. **For new users** (post-defaults-2), that default is Trying Out.
3. **For existing users with an existing default**, behavior unchanged.
4. **For existing users with no default set**, the share-import screen
   now prefers Trying Out (system book) over `books.first`. The
   migration's back-fill (story 1) guarantees every existing user has
   the system book.
5. **Manual smoke** — fresh-account → share a recipe in → confirm it
   lands in Trying Out, visible in the switcher. Documented in the
   QA file as a checklist for the next runtime smoke session.
6. **Existing share-import widget tests** still green
   (13 tests in `share_import_test.dart` +
   `share_import_screen_nav_test.dart`).
7. **Sprint-status flipped** `recipe-defaults-4-...: backlog → done`.

## Definition of done

- [ ] Share-import fallback patched.
- [ ] Audit table documented.
- [ ] Existing tests still pass.
- [ ] Sprint-status flipped.
- [ ] QA walkthrough file present.
- [ ] Atomic commit.
