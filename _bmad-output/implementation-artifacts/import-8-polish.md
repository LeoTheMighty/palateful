# Story Import.8: Import Polish — Auto-Approve, Shared Files

Status: done

## Story

As a user,
I want high-confidence URL imports to save automatically without requiring my review, and I want to be able to share files to Palateful from other apps,
so that importing feels seamless whether I'm saving a single link or uploading a file from my Files app.

## Acceptance Criteria

1. URL imports using JSON-LD extraction (structured data) with all ingredients matched at >85% confidence auto-approve without showing review screen
2. Auto-approved imports show a snackbar: "Recipe saved! [View]" instead of opening review
3. Auto-approve can be toggled off in Profile > Settings (default: on)
4. iOS share sheet accepts file types (CSV, XLSX, PDF, images) in addition to URLs
5. Shared files route to the appropriate import screen (spreadsheet → spreadsheet import, images → photo import)
6. User preference for auto-approve persists via API (notification preferences or user settings)

## Tasks / Subtasks

- [x] Task 1: Backend — Auto-approve logic (AC: #1, #6)
  - [x] In `ExtractRecipeTask` or after `MatchIngredientsTask`:
    - Check extraction method: was it JSON-LD? (structured, high-confidence)
    - Check ingredient match scores: all >0.85?
    - If both: set ImportItem status directly to "approved", trigger CreateRecipeTask
  - [x] Add `auto_approve_imports` boolean to user preferences (default: true)
  - [x] Check user preference before auto-approving
  - [x] Create activity: "Recipe '[Name]' saved automatically from [URL]"

- [x] Task 2: Flutter — Auto-approve UX (AC: #2, #3)
  - [x] In URL import flow: after submitting, poll for result
  - [x] If result comes back as auto-approved: show snackbar "Recipe saved! [View]" and navigate back
  - [x] If result needs review: navigate to review screen (existing behavior)
  - [x] Add toggle in Profile > Settings: "Auto-save high-confidence imports" with explanatory subtitle

- [x] Task 3: Extend share sheet to accept files (AC: #4, #5)
  - [x] Modify `ReceiveSharingIntent` handler in `app/lib/main.dart`
  - [x] Currently handles: `SharedMediaType.url`
  - [x] Add handling for: `SharedMediaType.file`
  - [x] Route by file extension:
    - `.csv`, `.xlsx`, `.xls` → spreadsheet import screen (from Story 7)
    - `.jpg`, `.jpeg`, `.png`, `.heic`, `.webp` → photo import screen (existing)
    - `.pdf` → photo import screen (treat as image for now, or show "PDF support coming soon")
    - Unknown → show error "Unsupported file type"
  - [x] Pass file path to the appropriate import screen

- [x] Task 4: Activity entries for auto-approved imports (AC: #1)
  - [x] Create activity when recipe is auto-approved
  - [x] Activity shows: "✅ [Recipe Name] saved from [source URL domain]"
  - [x] Tappable → navigates to recipe detail

## Dev Notes

- JSON-LD extraction is identified in `ExtractRecipeTask` by the extraction method used — check the `ExtractionResult.source` or similar field
- Ingredient matching confidence is available in `MatchIngredientsTask` results
- `ReceiveSharingIntent` package already handles files — just need to add the `SharedMediaType.file` case
- Auto-approve is a user preference, not a system-wide setting — some users want to review everything
- The auto-approve preference could live in the existing notification_preferences table or a new user_preferences table
- For MVP, auto-approve only applies to URL imports (JSON-LD). Spreadsheet and text imports always go through review.

### References

- [Investigation: 06-import-flow-overhaul.md — Auto-Approve section, Shared Files section]
- [Epic: epic-import-activity-nav.md]
