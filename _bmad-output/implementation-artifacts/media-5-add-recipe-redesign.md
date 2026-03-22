# Story Media.5: Add Recipe Sheet Redesign + Final Wiring

Status: done

## Story

As a user,
I want the Add Recipe sheet to show Quick Import options at the top with more options expandable below,
so that the most common import methods are one tap away and I'm not overwhelmed by choices.

## Acceptance Criteria

1. Add Recipe sheet shows "Quick Import" section with 3 options: From Link, From Photo, Paste Text
2. "From Link" subtitle reads "Any URL — websites, TikTok, Instagram, YouTube" (replaces old "From URL")
3. "More Options" expander section shows: PDF/Document, Voice Memo, Spreadsheet, Create Manually
4. Tapping "From Link" with a social media URL routes to video extraction (Story 1) automatically
5. All import types are functional (no "Coming soon" stubs remain)
6. Share sheet accepts all supported file types: URLs, images, PDFs, audio, video, spreadsheets
7. Share sheet routes shared files to the correct import screen based on MIME type
8. Video files shared via share sheet route to metadata extraction (same as URL)

## Tasks / Subtasks

- [x] Task 1: Redesign Add Recipe sheet layout (AC: #1, #2, #3)
  - [x] Modify `app/lib/features/recipes/add_recipe/add_recipe_sheet.dart`
  - [x] **Quick Import** section:
    - 🔗 **From Link** — "Any URL — websites, TikTok, Instagram, YouTube" → URL import screen
    - 📷 **From Photo** — "Snap or upload a photo" → photo capture screen
    - 📋 **Paste Text** — "Paste recipe from anywhere" → text paste screen
  - [x] **More Options** (collapsed by default, expand on tap):
    - 📄 **PDF / Document** — "Import from a cookbook PDF" → PDF import screen
    - 🎤 **Voice Memo** — "Record or import a voice recording" → audio import screen
    - 📊 **Spreadsheet** — "Import CSV or Excel file" → spreadsheet import screen
    - ✏️ **Create Manually** — "Build from scratch" → recipe wizard
  - [x] Expander: simple `ExpansionTile` or animated toggle with "More options ▼" / "Less options ▲"

- [x] Task 2: URL import — social media detection on frontend (AC: #4)
  - [x] In the URL import screen: when user pastes a URL, detect if it's a social media link
  - [x] Show platform-specific messaging: "TikTok video detected — extracting recipe from captions..."
  - [x] Backend handles the actual routing (from Story 1), frontend just shows appropriate progress messaging

- [x] Task 3: Remove all "Coming soon" stubs (AC: #5)
  - [x] Verify every option in the sheet navigates to a working screen
  - [x] Remove any remaining toast stubs for Paste Text, Spreadsheet
  - [x] Ensure PDF and Voice Memo navigate to their respective screens from Stories 3 and 4

- [x] Task 4: Share sheet — complete file type support (AC: #6, #7, #8)
  - [x] Verify `_handleSharedFiles` in main.dart handles all MIME types:
    - URLs → URL import (with social media detection)
    - Images (.jpg, .png, .heic) → photo import
    - PDFs → PDF import screen
    - Audio (.m4a, .mp3, .wav) → audio import screen
    - Video files → upload, extract metadata, process as video import
    - Spreadsheets (.csv, .xlsx) → spreadsheet import
    - Text → check for URL first, then text paste
  - [x] Update iOS Info.plist share extension to accept all file types
  - [x] Test each file type via share sheet

- [x] Task 5: Empty state + onboarding updates (AC: #1)
  - [x] Update empty recipe book state to match new import option names
  - [x] Verify onboarding "Import" path shows the new Add Recipe sheet

## Dev Notes

- This story ties together all previous import work — Media.1-4 + Import.4-8
- The "Quick Import" vs "More Options" split is based on usage frequency, not technical grouping
- "From Link" replaces "From URL" — friendlier language, and the subtitle calls out social media
- The expander should remember its state within the session (collapsed by default, stays open if expanded)
- No new backend work — this is purely frontend UI reorganization + wiring

### References

- [Investigation: 11-universal-media-import.md — Share-to-App section]
- [Epic: epic-media-import.md]
