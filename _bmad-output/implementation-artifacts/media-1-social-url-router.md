# Story Media.1: Social Media URL Router + Video Metadata Extraction

Status: done

## Story

As a user,
I want to share a TikTok, Instagram, or YouTube link and have the app extract the recipe from the video's captions and description,
so that I can save recipes from social media as easily as from a regular website.

## Acceptance Criteria

1. Social media URLs (TikTok, Instagram, YouTube, Pinterest, Facebook) are detected and routed to the video extraction pipeline instead of standard web scraping
2. Video metadata (captions, description, subtitles) is extracted via yt-dlp without downloading the video
3. Extracted text is fed to the existing `extract_recipe_from_text()` for AI structuring
4. If metadata contains recipe-like content (≥2 recipe indicators), extraction proceeds automatically
5. If metadata contains no recipe content, import item is flagged with a message "No written recipe found in this video" and suggests audio transcription (Story 2) or text paste
6. Processing shows staged progress: "Fetching video info..." → "Reading captions..." → "Extracting recipe..." → "Recipe ready!"
7. Works for all major platforms: TikTok, Instagram Reels, YouTube (including Shorts), Pinterest, Facebook
8. Pinterest URLs that link to a source website are redirected to standard web extraction
9. Activity entry created for video imports

## Tasks / Subtasks

- [x] Task 1: Backend — URL classifier (AC: #1, #7, #8)
  - [x] Create `libraries/utils/utils/services/url_classifier.py`
  - [x] Implement `detect_platform(url)` with regex patterns for:
    - TikTok: `tiktok.com/@*/video/*`, `vm.tiktok.com/*`, `tiktok.com/t/*`
    - Instagram: `instagram.com/(p|reel|reels)/*`, `instagr.am/*`
    - YouTube: `youtube.com/watch?v=*`, `youtu.be/*`, `youtube.com/shorts/*`
    - Pinterest: `pinterest.com/pin/*`, `pin.it/*`
    - Facebook: `facebook.com/*/videos/*`, `fb.watch/*`
  - [x] Returns `SocialPlatform` enum (tiktok, instagram, youtube, pinterest, facebook, web)
  - [x] Pinterest special handling: extract source URL from pin data, redirect to web pipeline if available

- [x] Task 2: Backend — Video metadata extractor (AC: #2, #3, #4)
  - [x] Create `libraries/utils/utils/services/recipe_extractors/video_extractor.py`
  - [x] `VideoMetadataExtractor.extract_metadata(url)` using yt-dlp:
    - `skip_download: True` (never download video)
    - Extract: title, description, subtitles (auto-generated + manual), duration, platform, uploader, thumbnail
  - [x] `has_recipe_content(metadata)` — check for recipe indicators (ingredient, recipe, tbsp, preheat, etc.)
  - [x] Compose extracted text: `f"{title}\n{description}\n{subtitles}"` → feed to existing TextExtractor
  - [x] Add `yt-dlp` to worker service dependencies

- [x] Task 3: Backend — Integrate into ExtractRecipeTask (AC: #1, #4, #5)
  - [x] Modify `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`
  - [x] In `_extract_single_item`: if source URL is detected as social media platform:
    - Call `VideoMetadataExtractor.extract_metadata(url)`
    - If `has_recipe_content()` → feed text to `extract_recipe_from_text()`
    - If no recipe content → set item status to "needs_audio_fallback" or flag for review with helpful message
  - [x] Track `extractor_used: "video_metadata"` on the ImportItem

- [x] Task 4: Backend — Update StartImport for video URLs (AC: #9)
  - [x] When URL is detected as social media: set `source_type: "video"` on ImportJob
  - [x] Create activity entry: "Importing recipe from [platform] video..."

- [x] Task 5: Flutter — Staged progress UX for video imports (AC: #6)
  - [x] Modify URL import screen or create video-specific progress view
  - [x] Show stages: "Fetching video info..." → "Reading captions..." → "Extracting recipe..."
  - [x] On success: navigate to review or auto-approve (existing behavior)
  - [x] On "no recipe content": show message "No written recipe found" with options:
    - "Try audio transcription" (disabled until Story 2)
    - "Paste recipe text instead" → navigate to text paste screen

- [x] Task 6: Add yt-dlp dependency (AC: #2)
  - [x] Add `yt-dlp` to worker service `pyproject.toml`
  - [x] Ensure `ffmpeg` is available in worker Docker container (needed by yt-dlp for some operations)
  - [x] Pin yt-dlp version for stability

## Dev Notes

- `yt-dlp` is the backbone — supports 1700+ sites, actively maintained. Use `skip_download: True` to only fetch metadata
- The URL classifier runs before any extraction attempt — if it detects TikTok/Instagram, it skips the standard HTML fetch entirely
- Recipe indicator detection: count occurrences of cooking keywords in combined text, threshold ≥2 matches
- yt-dlp may need user-agent rotation for some platforms — handle gracefully with retries
- Risk: platforms change APIs frequently. Mitigation: pin yt-dlp version, test before upgrading, have fallback message
- Cost: metadata extraction is FREE (no AI calls). Only the `extract_recipe_from_text()` call costs ~$0.001-0.002

### References

- [Investigation: 11-universal-media-import.md — Video URL section]
- [Epic: epic-media-import.md]
