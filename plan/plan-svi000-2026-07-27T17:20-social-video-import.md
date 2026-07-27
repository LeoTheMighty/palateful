---
hash: svi000
type: plan
created: 2026-07-27T17:20:00-06:00
title: Social-media video import — TikTok / Instagram / YouTube via Whisper + AI extractor
from: _bmad-output/planning-artifacts/epic-social-video-import.md
status: ready
mode: YOLO
---

## Scope
Close Recime's #1 growth-feature gap: share a TikTok / Instagram Reel / YouTube Short via the OS share sheet and the recipe just appears. The share-extension flow routes social-video URLs to a new worker pipeline that combines platform caption/description scraping (per-platform scrapers with official-API best path and oEmbed/audio-only fallback), OpenAI Whisper audio transcription via a shared `audio_transcription.py` service, and the existing AI extractor. Recipes land in `Trying Out` with attribution preserved ("From @chefname on TikTok") and the import surfaces as an Activity Hub row (toast + Hub row per party-mode — the standalone landing screen was cut), with MutationBus events on every `import_item.status` transition. Cost discipline is a design constraint: 10-minute video hard cap, $5/user rolling-30-day budget enforced with idempotency keys and concurrency-safe budget accounting, all logged via the `error_logs` audit pattern. No new AWS resources; reuses existing S3 imports bucket, worker capacity, and `OPENAI_API_KEY`.

## Pre-split stories (BMAD)
- social-vid-1 — Backend: `audio_transcription.py` Whisper wrapper with 10-min duration cap, per-user rolling-30-day $5 budget (concurrency-safe via SELECT FOR UPDATE or Redis counter), idempotency key, cost audit rows, friendly over-budget error copy
- social-vid-2 — Backend: TikTok / Instagram / YouTube scrapers with best-path + fallback, per-platform circuit-breaker, respx/vcrpy cassette fixtures committed as blocking AC
- social-vid-3 — Backend: `social_video_extractor.py` orchestrator + Alembic migration extending `import_items.source_type` with `social_video` (with working downgrade), dedupe-on-`recipes.source_url` check, attribution metadata on import_items
- social-vid-4 — Backend: `extract_recipe_from_video_task` worker task + push notification on success/failure, deep-link payload `{type: 'video_import_ready', import_item_id}`, MutationBus emission spec for status transitions
- social-vid-5 — Frontend: share-routing URL detection + toast + Activity Hub row with "extracting" status (rewritten ~40% smaller after party-mode cut of `VideoImportLandingScreen`)
- social-vid-6 — Frontend: attribution badge on Approve-Import, failure/budget-paused/duplicate states as Activity Hub row states with inline CTAs, e2e sweep share→notify→approve→`Trying Out`
- social-vid-7 — Cost observability: extend `audit_errors.py` with `--cost-summary` flag aggregating `WhisperTranscription` audit rows by user + month (added by party-mode; script flag only, no new infra)

## Dependencies / notes
- No hard dependencies — share-sheet infrastructure (`epic-share-ios-extension`, `epic-share-android-entrypoint`, `epic-share-receiving-ux`) already shipped; `epic-recipe-default-books` `Trying Out` destination already shipped.
- Should ship before `epic-nutrition-auto-calc` so freshly-extracted recipes pick up nutrition immediately.
- Cost/ops: Whisper hosted-vs-local, 10-min duration cap, and rolling-30-day cap cadence are epic open questions with recommended defaults (OpenAI hosted, 10 min, rolling-30-day); social-vid-7 provides the ops visibility.
- Optional env vars `INSTAGRAM_API_TOKEN` / `YOUTUBE_API_KEY` improve scraping; graceful degradation to oEmbed/audio-only paths when absent. TOS-scraping fragility mitigated by circuit-breakers + always-on transcription fallback.
- Locked cross-epic decisions to honor: Activity Hub is the canonical surface for async ops; MutationBus events on `import_item.status` are contract; per-user cost-cap via `error_logs` aggregation is the paid-API convention; `audio_transcription.py` is the shared Whisper wrapper.
- When /devx-plan picks this up it should emit dev specs from the pre-split stories rather than re-chunking from scratch.

## Status log
- 2026-07-27T17:20 — imported from BMAD (epic file + sprint-status.yaml) during BMAD→devx migration; no implementation commits on main as of import
