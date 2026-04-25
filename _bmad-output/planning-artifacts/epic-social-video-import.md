<!-- draft: pre-party-mode -->
# Epic: Social-Media Video Import — TikTok / Instagram / YouTube via Whisper + AI

## Overview

Close Recime's #1 growth feature gap. The user shares a TikTok / Instagram Reel / YouTube Short URL or video file via the OS share sheet → Palateful detects it's social-media content → routes to a video-extraction pipeline that combines audio transcription (OpenAI Whisper), platform caption / description scraping (where APIs allow), and the existing AI extractor → recipe lands in `Trying Out` (per `epic-recipe-default-books`) with attribution preserved (`From @chefname on TikTok`).

## Goal

Match Recime's flagship "share from TikTok and recipe just appears" UX. Deliver it on top of the existing share-extension + worker infra without new AWS resources. Keep cost bounded by per-import + per-user-per-month caps.

## End-user flow

1. User watches a recipe TikTok / Instagram Reel / YouTube Short on phone.
2. Taps native Share → Palateful icon (already pinned by users via existing share-extension flow).
3. Share extension uploads the URL or video file to Palateful's S3 imports bucket via the existing presigned-PUT pattern.
4. App immediately shows a non-blocking "Extracting recipe from your video — we'll notify you when ready" sheet that auto-dismisses after 2 seconds.
5. Backend `extract_recipe_from_video_task` worker task fires: detects platform, scrapes caption / description if URL is platform-specific, downloads or accesses video audio track, transcribes via Whisper (rejecting > 10 min videos with a friendly error), feeds combined caption + transcript text to existing AI extractor with `source_type=social_video` context.
6. ~30-60 seconds later push notification arrives: "Your recipe from TikTok is ready! Tap to review."
7. User taps → opens Approve-Import screen with the extracted recipe, a "From @chefname on TikTok" attribution badge, a small video thumbnail, and a "Source: tiktok.com/@chef/video/..." link.
8. User reviews/corrects fields, taps Approve → recipe lands in `Trying Out` per `epic-recipe-default-books`.
9. Extraction failure path: push notification "We couldn't extract a recipe from this video — try sharing a screenshot of the recipe text instead." Tap opens a friendly empty-state screen with a one-tap fallback to manual entry or screenshot import.

## Frontend changes

- `app/lib/features/sharing/share_receiving_handler.dart` — extend URL detection to recognize `tiktok.com`, `instagram.com/(reel|p)`, `youtube.com/(shorts|watch)`, `youtu.be` patterns. When matched, route to `VideoImportLandingScreen` instead of the generic file/URL flow.
- New screen `app/lib/features/recipes/add_recipe/video_import_landing_screen.dart` — non-blocking "Extracting recipe from your video" sheet with per-platform thumbnail (TikTok logo, Instagram Reel icon, YouTube logo), platform name, and a 2-second auto-dismiss timer. Includes a "Cancel" button that aborts the upload + cleans up the import_item row.
- `app/lib/features/recipes/add_recipe/approve_import_screen.dart` — render attribution badge widget when `import_item.source_type == 'social_video'`. Badge shows platform icon + creator handle + "Source: <truncated URL>" link.
- New widget `app/lib/features/recipes/add_recipe/video_extraction_failure_screen.dart` — empty state with "We couldn't extract a recipe from this video" + two CTAs: "Try a screenshot instead" (opens existing photo-import flow) and "Enter manually" (opens recipe-create flow with title pre-filled from the video title if available).

## Backend changes

- New `services/api/src/services/audio_transcription.py` — wraps OpenAI Whisper API (reuses existing `OPENAI_API_KEY`). Per-call cost cap: reject if estimated audio duration > 10 minutes (computed from video metadata before download). Per-call cost logged via existing `error_logs` audit pattern with `service="audit"`, `error_type="WhisperTranscription"`, payload includes user_id + duration_seconds + estimated_cost_usd.
- New platform-specific scrapers in `services/api/src/api/v1/recipe_extractors/`:
  - `tiktok_scraper.py` — fetches video metadata via TikTok's oEmbed endpoint or unofficial API; extracts caption text, creator handle, video duration. Graceful degradation: if metadata fetch fails, fall back to audio-transcription-only path.
  - `instagram_scraper.py` — fetches Reel caption + creator handle via Instagram Graph API (if `INSTAGRAM_API_TOKEN` env var present) or oEmbed fallback. Same graceful degradation.
  - `youtube_scraper.py` — fetches captions via YouTube Data API (if `YOUTUBE_API_KEY` present), description text, creator handle. Best degradation path of the three (YouTube has stable captions API).
- New `services/api/src/api/v1/recipe_extractors/social_video_extractor.py` orchestrator — given an import_item with `source_type='social_video'`, route to the right scraper, transcribe audio if scraper returned insufficient text, combine caption + transcript, feed to existing `ai_extractor.extract_recipe_from_text(...)` with `source_context={'platform': 'tiktok', 'creator': '@chef', 'video_url': '...'}`.
- **Schema additions** (Alembic migration):
  - `import_items.source_type` enum extension to include `social_video`.
  - `import_items.metadata` JSON column expansion (already JSON; just document the new keys): `platform`, `creator_handle`, `caption_text`, `video_duration_seconds`, `thumbnail_url`, `transcription_cost_usd`.
- New `services/api/src/tasks/extract_recipe_from_video_task.py` worker task — queued from share-sheet upload completion when source matches social-video patterns. Picks up the import_item, calls `social_video_extractor`, writes back the extracted recipe + attribution metadata, fires push notification on completion (success or failure) via existing notification system.
- `import_jobs` row creation: existing pattern; no new endpoint surface — share-extension flow already creates import_items and queues tasks; we're just extending the source-type branching.
- New `error_logs` audit entries for cost / failure tracking — query via existing `audit_errors.py --drill api:WhisperTranscription`.

## Infrastructure changes

- **Worker container ffmpeg** — already present per `sbf-4` (FFmpeg in worker for video file source type).
- **Reuses existing `OPENAI_API_KEY`** — Whisper uses the same key.
- **Optional new env vars** with degraded paths if absent:
  - `INSTAGRAM_API_TOKEN` — improves Instagram caption extraction; without it, falls back to oEmbed.
  - `YOUTUBE_API_KEY` — improves YouTube caption + metadata fetch; without it, audio-transcription-only path.
- **Per-import cost logging** via existing `error_logs` audit — no new ingest pipeline.
- **Per-user per-month cost cap** enforced in `audio_transcription.py` — query `error_logs` for the user's prior 30-day Whisper cost; reject with friendly error if > $5/user/month.
- **No new AWS resources.** S3 imports bucket reused. ECS worker capacity already sized for the existing video-file path.

## Initial design principles (from research; party-mode TBD)

- **Defensive close, not offensive launch.** Recime is winning installs daily on this. Ship to parity, not to leapfrog.
- **Cost discipline as a design constraint.** $5/user/month cap is non-negotiable; videos > 10 min rejected outright. The friendly error matters more than the threshold (users stay engaged via the screenshot fallback).
- **Graceful degradation for every platform.** Platform APIs are flaky / change frequently. Audio-transcription-only is the always-available baseline; caption scraping is the cheap-when-it-works enhancement.
- **Attribution preserved.** Creators get visible credit. Source URL preserved on the recipe forever (per existing `recipes.source_url` pattern). Reduces moral / legal friction with content creators.
- **Sandboxed transcription.** Source video file never persists beyond the transient transcription window. Only the structured recipe + attribution metadata land in DB. Reduces storage cost + privacy footprint.

## File structure (anticipated)

```
app/lib/features/
  sharing/share_receiving_handler.dart                            # extend URL detection
  recipes/add_recipe/
    video_import_landing_screen.dart                              # NEW
    approve_import_screen.dart                                    # render attribution badge
    video_extraction_failure_screen.dart                          # NEW

services/api/src/
  api/v1/recipe_extractors/
    tiktok_scraper.py                                             # NEW
    instagram_scraper.py                                          # NEW
    youtube_scraper.py                                            # NEW
    social_video_extractor.py                                     # NEW
    ai_extractor.py                                               # accept source_context kwarg
  services/audio_transcription.py                                 # NEW (Whisper wrapper)
  tasks/extract_recipe_from_video_task.py                         # NEW worker task

services/migrator/migrations/versions/
  20260426010000_extend_import_items_source_type_social_video.py  # NEW migration

_bmad-output/implementation-artifacts/
  social-vid-1-backend-audio-transcription-service.md
  social-vid-2-backend-platform-scrapers.md
  social-vid-3-backend-orchestrator-and-schema.md
  social-vid-4-backend-worker-task-and-notification.md
  social-vid-5-frontend-share-routing-and-landing-screen.md
  social-vid-6-frontend-attribution-badge-and-failure-state.md
```

## Story list

- **social-vid-1 — Backend: audio_transcription service + Whisper wrapper.** New `services/api/src/services/audio_transcription.py` with `transcribe_audio(audio_url, max_duration_seconds=600) -> TranscriptionResult`. Per-call cost cap (10 min hard limit). Per-call cost logged via `error_logs` audit. Per-user 30-day cost cap query (return `BudgetExceededError` if over $5). Unit tests cover happy path + over-duration rejection + over-budget rejection + Whisper API error handling. **AC:** service callable from a worker task; cost logging works (verified via `audit_errors.py --drill api:WhisperTranscription`); 100% test coverage.
- **social-vid-2 — Backend: platform scrapers (TikTok + Instagram + YouTube).** Three modules in `recipe_extractors/`. Each exposes `fetch_metadata(url) -> ScrapedMetadata` returning caption / creator / duration / thumbnail. Graceful degradation: every scraper has a "best path" (official API) and a fallback path (oEmbed or pure HTML scrape); both paths covered in tests. **AC:** each scraper handles a known good URL + a malformed URL + an API-failure URL; returns partial data when one signal is missing; unit tests cover all three platforms.
- **social-vid-3 — Backend: orchestrator + import_items schema extension.** New `social_video_extractor.py` calls scraper + transcription + AI extractor. Alembic migration extends `import_items.source_type` enum to include `social_video`. Endpoint surface for testing: extend existing `POST /v1/imports/start` to accept `source_type='social_video'`. **AC:** extractor produces a structured `ExtractedRecipe` from a real TikTok URL fixture (recorded HTTP cassettes); migration runs cleanly + reverses cleanly; `import_items` row carries the attribution metadata after extraction.
- **social-vid-4 — Backend: worker task + push notification.** New `extract_recipe_from_video_task` queued from share-sheet upload completion (the existing share-extension flow already triggers a task; we extend the routing logic to pick this task when `source_type='social_video'`). Fires push notification on success ("Your recipe from TikTok is ready!") and on failure ("We couldn't extract a recipe from this video"). **AC:** worker picks up tasks reliably; push notification fires on both outcomes; failure-path push includes a deep-link to the failure-state screen.
- **social-vid-5 — Frontend: share-routing + VideoImportLandingScreen.** Extend `share_receiving_handler.dart` URL detection. New `VideoImportLandingScreen` with per-platform thumbnail + auto-dismiss + Cancel button. **AC:** sharing a TikTok URL routes to the new screen; Cancel aborts the upload + cleans up the import_item row; widget tests cover all three platforms.
- **social-vid-6 — Frontend: attribution badge + failure-state screen + e2e regression sweep.** Approve-Import attribution badge widget (platform icon + creator handle + source link). New `VideoExtractionFailureScreen` with two CTAs (screenshot import / manual entry). End-to-end sweep: share a TikTok URL → see notification → tap → see Approve-Import with attribution → approve → see recipe in `Trying Out`. **AC:** badge renders correctly for all three platforms; failure screen reachable + both CTAs work; e2e flow passes on iOS + Android.

## Dependencies

- **No hard dependencies** beyond shipped share-sheet infrastructure (`epic-share-ios-extension`, `epic-share-android-entrypoint`, `epic-share-receiving-ux`).
- **Soft dependency:** recipes land in `Trying Out`, so `epic-recipe-default-books` should be done (it is — Stories 1 + 2 already shipped per recent /dev commits).
- **Should ship before:** `epic-nutrition-auto-calc` (so freshly-extracted recipes pick up nutrition immediately).

## Open questions for the user

- **Whisper deployment choice — OpenAI hosted vs whisper.cpp local.** Default: OpenAI hosted Whisper ($0.006/min, no infra). Alternative: whisper.cpp running in-worker ($0 marginal, ~2GB image bloat, slower for large videos). Hosted is simpler for v1; local is the cost-optimization story when volume grows.
- **Instagram API token sourcing.** Instagram's Graph API requires a Facebook developer app + Page connection. If we don't want to maintain that, oEmbed fallback covers ~80% of cases but loses creator handle. Acceptable for v1?
- **Video duration cap — 10 min vs other.** 10 min covers ~95% of recipe TikToks/Reels/Shorts and bounds Whisper cost at ~$0.06 per longest-allowed import. Higher cap = better coverage of YouTube long-form recipe videos; lower cap = tighter cost control. Confirm 10 min before story `social-vid-1`.
