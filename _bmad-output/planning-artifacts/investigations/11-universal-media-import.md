# Investigation 11: Universal Media-to-Recipe Import

> **Date:** March 2026
> **Goal:** Design a universal import pipeline that can accept ANY piece of media -- video, audio, PDF, social media links, images, text -- and produce a structured recipe.
> **Scope:** Technical feasibility, architecture, cost analysis, and prioritized implementation plan.

---

## Executive Summary

Palateful's import system currently handles two media types well (URLs via JSON-LD + AI fallback, and photos via HunyuanOCR + GPT-4o-mini structuring) and has text paste working. The vision is to accept literally any media that contains a recipe and turn it into structured data. This investigation covers the five missing media categories -- video URLs, audio files, PDFs, enhanced share-to-app for files, and social media URL intelligence -- and designs a unified architecture that routes any input through the appropriate extraction pipeline before converging into the existing ExtractRecipeTask -> MatchIngredientsTask -> Review -> CreateRecipeTask flow.

**Key findings:**

1. **Video URL import (TikTok/Instagram/YouTube)** is the highest-impact gap. Pestle does this on-device in <1 second by reading text metadata (captions, descriptions). Recime does it via cloud AI in 10-15 seconds by also transcribing audio. The metadata-first approach is dramatically cheaper ($0.00 per extraction) and covers 70-80% of cases. Audio transcription via Whisper ($0.003-0.006/min) is the fallback for the remaining 20-30%.

2. **PDF import** is straightforward with a dual-path approach: PyMuPDF for text-based PDFs (free, fast) and HunyuanOCR for scanned PDFs (existing infrastructure). Recipe boundary detection within multi-recipe PDFs is the hardest sub-problem.

3. **Audio import** (voice memos, podcast clips) is a simple Whisper transcription -> text extraction pipeline. Cost is $0.003-0.006/min, latency 5-15 seconds for typical clips.

4. **Share-to-app for files** requires configuring `receive_sharing_intent` to accept additional MIME types (images, PDFs, video files) and routing to the appropriate pipeline. This is a small Flutter change.

5. **Social media URL detection** is a URL pattern-matching router that identifies TikTok/Instagram/YouTube URLs and routes them to the video pipeline instead of standard web scraping.

**Estimated total cost per extraction at scale:**

| Media Type | Cost per Extraction | Latency |
|------------|-------------------|---------|
| URL (JSON-LD) | $0.000 | 1-3s |
| URL (AI fallback) | $0.002 | 3-8s |
| Photo/OCR | $0.001-0.003 | 5-30s |
| Video (metadata only) | $0.000-0.002 | 2-5s |
| Video (with audio transcription) | $0.01-0.05 | 10-30s |
| Audio (voice memo) | $0.003-0.03 | 5-15s |
| PDF (text-based) | $0.001-0.002 | 2-5s |
| PDF (scanned/OCR) | $0.003-0.005 | 10-60s |
| Text paste | $0.001-0.002 | 2-5s |

---

## Media Type Analysis

### 1. Video URL Import (TikTok, Instagram Reels, YouTube)

#### Current State in Palateful

Not supported. When a user shares a TikTok or Instagram URL, the existing pipeline attempts standard web scraping, which fails because these pages are JavaScript-rendered SPAs with no JSON-LD recipe data. The AI extractor receives garbage HTML and either produces a bad extraction or fails outright.

#### What Competitors Do

**Pestle (best-in-class for speed):**
- Uses on-device machine learning to process video metadata (captions, descriptions, subtitles)
- Reads text-based data: YouTube descriptions, TikTok captions, Instagram text overlays (when available as metadata)
- Processes in approximately 0.1 seconds (one-tenth of a second)
- The slowest part is fetching the caption from the platform API
- Does NOT actually "watch" or transcribe the video -- only reads text metadata
- Limitation: fails when recipe is spoken aloud without written instructions

**Recime (best-in-class for comprehensiveness):**
- Cloud-based AI that attempts to extract from video audio first
- If audio extraction finds nothing, falls back to finding the original recipe website
- Takes 10-15 seconds per extraction
- Handles cases where ingredients are spoken but not written
- More expensive (cloud processing) but higher success rate for narration-only recipes

**Pluck:**
- Similar metadata-first approach to Pestle
- Supports YouTube, TikTok, Instagram
- Web-based (not on-device)

#### Proposed Pipeline

```
Video URL received
    |
    v
[1. Platform Detection] -- Identify TikTok/Instagram/YouTube/Pinterest/Facebook
    |
    v
[2. Metadata Extraction] -- Fetch caption, description, subtitles (FREE)
    |                        Use yt-dlp or platform APIs
    |
    +--- Text found? -----> [3a. Text Recipe Extraction] -- GPT-4o-mini structures text
    |                        Cost: $0.001-0.002
    |
    +--- No text? --------> [3b. Audio Download] -- yt-dlp downloads audio track only
    |                        |
    |                        v
    |                        [4. Audio Transcription] -- Whisper API or GPT-4o-mini Transcribe
    |                        Cost: $0.003-0.006/min
    |                        |
    |                        v
    |                        [5. Text Recipe Extraction] -- GPT-4o-mini structures transcript
    |                        Cost: $0.001-0.002
    |
    v
[6. Standard Pipeline] -- MatchIngredientsTask -> Review -> CreateRecipeTask
```

**Tier 1: Metadata-first (free/near-free, <5 seconds)**
- Use `yt-dlp` (Python library, open source, supports 1700+ sites) to extract:
  - Video description/caption text
  - Auto-generated subtitles (YouTube, TikTok)
  - Manual subtitles/captions
  - Video title
  - Creator info
- Feed extracted text to the existing `extract_recipe_from_text()` function
- This covers ~70-80% of recipe videos (most creators write ingredients in the caption)

**Tier 2: Audio transcription fallback ($0.01-0.05, 10-30 seconds)**
- When metadata contains no recipe-like content:
  - Download audio only using `yt-dlp` (not the full video -- saves bandwidth)
  - Transcribe via OpenAI Whisper API ($0.006/min) or GPT-4o-mini Transcribe ($0.003/min)
  - Feed transcript to `extract_recipe_from_text()`
- Typical cooking video is 1-5 minutes -> cost $0.003-0.03

**Tier 3: Visual frame analysis (expensive, last resort)**
- For recipes shown only as text overlays in the video (not in caption, not spoken):
  - Extract keyframes from video at intervals (e.g., every 5 seconds)
  - Send frames to GPT-4o-mini vision API
  - Cost: ~$0.002 per frame x 10-60 frames = $0.02-0.12
- This is expensive and should only be used when Tier 1 and Tier 2 fail
- Consider: offer this as a premium feature or skip it entirely for MVP

#### Required Services/APIs

| Service | Purpose | Cost |
|---------|---------|------|
| `yt-dlp` (Python lib) | Download metadata, subtitles, audio | Free (open source) |
| OpenAI Whisper API | Audio transcription | $0.006/min |
| GPT-4o-mini Transcribe | Audio transcription (cheaper) | $0.003/min |
| GPT-4o-mini (text) | Structure extracted text into recipe | $0.001-0.002/call |
| GPT-4o-mini (vision) | Frame analysis (Tier 3 only) | ~$0.002/frame |
| TikTok Research API | Caption extraction (optional) | Free (rate-limited) |
| Supadata API | TikTok/YouTube transcript extraction | Free tier + paid |

#### Cost Per Extraction

| Scenario | Cost | Frequency |
|----------|------|-----------|
| Metadata extraction succeeds | $0.001-0.002 | ~70-80% of videos |
| Audio transcription needed (2-min video) | $0.007-0.014 | ~15-25% of videos |
| Audio transcription needed (5-min video) | $0.016-0.032 | ~5% of videos |
| Visual frame analysis needed | $0.02-0.12 | <5% (or skip for MVP) |
| **Weighted average** | **~$0.005** | |

#### Latency Expectations

| Step | Duration |
|------|----------|
| Platform detection + metadata fetch | 1-3 seconds |
| Text structuring (GPT-4o-mini) | 2-4 seconds |
| Audio download (if needed) | 3-10 seconds |
| Audio transcription (if needed) | 5-15 seconds |
| **Total (metadata path)** | **3-7 seconds** |
| **Total (audio path)** | **10-30 seconds** |

---

### 2. Audio Import (Voice Memos, Podcast Clips)

#### Current State in Palateful

Not supported. The app has `speech_to_text` integrated for voice input in cook mode chat, but there is no pipeline to accept an audio file and extract a recipe from it.

#### What Competitors Do

No major recipe app explicitly supports audio file import. This is a genuinely novel feature. The use cases are:
- Grandma dictating her recipe into a voice memo
- Podcast clip where a chef shares a recipe
- Audio message from a friend with a recipe
- Recording from a cooking class

#### Proposed Pipeline

```
Audio file received (m4a, mp3, wav, aac, ogg)
    |
    v
[1. Upload to S3] -- Store in imports bucket
    |
    v
[2. Transcribe] -- OpenAI Whisper API or GPT-4o-mini Transcribe
    |               $0.003-0.006/min
    v
[3. Extract Recipe] -- GPT-4o-mini structures transcript
    |                   $0.001-0.002
    v
[4. Standard Pipeline] -- MatchIngredientsTask -> Review -> Create
```

The pipeline is simple because it reuses the existing text extraction path. The only new component is the transcription step.

#### Required Services/APIs

| Service | Purpose | Cost |
|---------|---------|------|
| OpenAI Whisper API | Audio transcription | $0.006/min |
| GPT-4o-mini Transcribe | Audio transcription (budget option) | $0.003/min |
| GPT-4o-mini (text) | Structure transcript into recipe | $0.001-0.002/call |
| S3 | Temporary audio storage | ~$0.0001/file |

#### Cost Per Extraction

| Audio Length | Transcription | Structuring | Total |
|-------------|--------------|-------------|-------|
| 1 minute | $0.003-0.006 | $0.002 | $0.005-0.008 |
| 3 minutes | $0.009-0.018 | $0.002 | $0.011-0.020 |
| 5 minutes | $0.015-0.030 | $0.002 | $0.017-0.032 |
| 10 minutes | $0.030-0.060 | $0.002 | $0.032-0.062 |

**Recommendation:** Set a max audio length of 10 minutes (covers any reasonable recipe dictation). Use GPT-4o-mini Transcribe ($0.003/min) for cost optimization.

#### Latency Expectations

| Audio Length | Transcription | Structuring | Total |
|-------------|--------------|-------------|-------|
| 1 minute | 3-5 seconds | 2-4 seconds | 5-9 seconds |
| 5 minutes | 8-15 seconds | 2-4 seconds | 10-19 seconds |
| 10 minutes | 15-30 seconds | 3-5 seconds | 18-35 seconds |

---

### 3. PDF Import

#### Current State in Palateful

The `source_type` field on ImportJob already includes "pdf" as a valid value, but there is no implementation. The `ParseSourceTask` does not handle the "pdf" source type (returns "Unsupported source type"). The schema `StartImportRequest` includes "pdf" in its pattern regex.

The existing HunyuanOCR infrastructure can handle scanned PDF pages (convert page to image, run OCR), and the text extractor can handle OCR output.

#### What Competitors Do

- **Paprika:** Supports PDF import but primarily for Paprika's own export format
- **No major competitor** handles multi-recipe PDF extraction well (e.g., importing an entire cookbook PDF)
- This is an underserved area with high user value for cookbook digitization

#### Proposed Pipeline

```
PDF file received
    |
    v
[1. Upload to S3]
    |
    v
[2. Classify PDF] -- Text-based or scanned (image-based)?
    |                 Use PyMuPDF: if text extraction yields >100 chars/page, it's text-based
    |
    +--- Text-based PDF -----> [3a. Extract text per page] -- PyMuPDF (FREE)
    |                           |
    |                           v
    |                           [4a. Detect recipe boundaries] -- GPT-4o-mini
    |                           |   Identify where one recipe ends and another begins
    |                           |   Cost: $0.001-0.003
    |                           v
    |                           [5a. Extract each recipe] -- GPT-4o-mini per recipe
    |                               Cost: $0.001-0.002 per recipe
    |
    +--- Scanned PDF --------> [3b. Convert pages to images] -- PyMuPDF renders pages
    |                           |
    |                           v
    |                           [4b. OCR each page] -- HunyuanOCR (existing) OR GPT-4o-mini vision
    |                           |   Cost: $0.001/page (HunyuanOCR) or $0.002/page (GPT-4o-mini)
    |                           v
    |                           [5b. Merge + detect boundaries + extract] -- Same as 4a/5a
    |
    v
[6. Create ImportItems] -- One per detected recipe
    |
    v
[7. Standard Pipeline] -- MatchIngredientsTask -> Review -> Create
```

**Key sub-problem: Recipe boundary detection in multi-recipe PDFs**

When a PDF contains multiple recipes (e.g., a cookbook chapter), we need to detect where one recipe ends and another begins. Approaches:

1. **Page-based heuristic:** Assume one recipe per page (works for many cookbooks)
2. **Heading detection:** Look for large/bold text that signals a new recipe title
3. **AI boundary detection:** Send a few pages of text to GPT-4o-mini and ask it to identify recipe boundaries
4. **User-assisted:** Let the user specify page ranges per recipe

**Recommendation:** Start with AI boundary detection (most robust), fall back to page-based heuristic for very large PDFs to control costs.

#### Required Services/APIs

| Service | Purpose | Cost |
|---------|---------|------|
| PyMuPDF (Python lib) | PDF text extraction, page rendering | Free (open source) |
| HunyuanOCR | OCR for scanned PDFs | ~$0.001/page (Spot GPU) |
| GPT-4o-mini (text) | Recipe boundary detection + structuring | $0.001-0.003/call |
| GPT-4o-mini (vision) | Alternative to HunyuanOCR for scanned pages | ~$0.002/page |
| S3 | PDF storage + page image storage | ~$0.001/PDF |

#### Cost Per Extraction

| PDF Type | Pages | Cost |
|----------|-------|------|
| Single recipe, text-based | 1-2 | $0.002-0.004 |
| Single recipe, scanned | 1-2 | $0.004-0.008 |
| Multi-recipe chapter (10 recipes, text) | 10-20 | $0.01-0.03 |
| Full cookbook (50 recipes, scanned) | 100-200 | $0.10-0.30 |

#### Latency Expectations

| PDF Type | Duration |
|----------|----------|
| Single recipe, text-based | 2-5 seconds |
| Single recipe, scanned | 10-30 seconds (OCR) |
| Multi-recipe (10 recipes, text) | 5-15 seconds |
| Full cookbook (50 recipes, scanned) | 5-30 minutes (batch) |

**Full cookbook imports should be treated as batch jobs** with push notification on completion, not synchronous operations.

---

### 4. Enhanced Image Import (GPT-4o Vision as Alternative to HunyuanOCR)

#### Current State in Palateful

Working well. Photos go through HunyuanOCR (self-hosted on AWS Batch with Spot GPU) for OCR, then GPT-4o-mini structures the OCR text into a recipe. This is a two-step pipeline: OCR -> AI structuring.

#### Proposed Enhancement: GPT-4o-mini Vision Direct Path

Instead of the two-step HunyuanOCR -> GPT-4o-mini pipeline, send the image directly to GPT-4o-mini with vision capabilities and ask it to extract the recipe in one step.

```
Current:  Image -> HunyuanOCR (OCR text) -> GPT-4o-mini (structure) -> Recipe
Proposed: Image -> GPT-4o-mini Vision (OCR + structure in one) -> Recipe
```

**Advantages of the direct vision path:**
- Single API call instead of two
- No need to maintain/run HunyuanOCR infrastructure
- GPT-4o-mini vision can understand context, not just text (e.g., ingredient photos, step illustrations)
- Lower latency (skip GPU cold start for Batch jobs)

**Advantages of keeping HunyuanOCR:**
- ~10x cheaper per image ($0.001 vs $0.002-0.003)
- On-premises / no external API dependency for OCR step
- Better for batch processing (hundreds of images)
- HunyuanOCR may be more accurate for pure text extraction from complex layouts

**Recommendation:** Offer both paths:
- **Default:** GPT-4o-mini vision (simpler, faster for single images)
- **Batch/bulk:** HunyuanOCR + GPT-4o-mini text (cheaper at scale)

#### Cost Comparison

| Approach | Cost per Image | Latency |
|----------|---------------|---------|
| HunyuanOCR + GPT-4o-mini text | $0.002-0.003 | 10-30s (includes GPU spin-up) |
| GPT-4o-mini vision direct | $0.002-0.004 | 3-8s |
| GPT-4o vision (full model) | $0.005-0.010 | 3-8s |

---

### 5. Social Media URL Intelligence (Detection + Routing)

#### Current State in Palateful

All URLs go through the same pipeline: fetch HTML -> try JSON-LD -> AI fallback on HTML. This fails for social media URLs because:
- TikTok/Instagram serve JavaScript-rendered SPAs, not static HTML
- No JSON-LD recipe data is present
- The AI extractor gets minimal/garbage content from these pages

#### What Competitors Do

Both Recime and Pestle detect the URL platform and route to specialized extraction. The share sheet integration is the primary entry point.

#### Proposed URL Router

```python
# URL Pattern Detection
SOCIAL_MEDIA_PATTERNS = {
    "tiktok": [
        r"tiktok\.com/@[\w.]+/video/\d+",
        r"vm\.tiktok\.com/\w+",
        r"tiktok\.com/t/\w+",
    ],
    "instagram": [
        r"instagram\.com/(p|reel|reels)/[\w-]+",
        r"instagr\.am/p/[\w-]+",
    ],
    "youtube": [
        r"youtube\.com/watch\?v=[\w-]+",
        r"youtu\.be/[\w-]+",
        r"youtube\.com/shorts/[\w-]+",
    ],
    "pinterest": [
        r"pinterest\.com/pin/\d+",
        r"pin\.it/\w+",
    ],
    "facebook": [
        r"facebook\.com/.+/videos/\d+",
        r"fb\.watch/\w+",
    ],
}

def detect_url_type(url: str) -> str:
    """Detect if URL is a social media video or standard web page."""
    for platform, patterns in SOCIAL_MEDIA_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url):
                return platform
    return "web"  # Standard web page
```

**Routing logic in `ExtractRecipeTask`:**

```
URL received
    |
    v
[detect_url_type(url)]
    |
    +--- "web" ---------> Existing pipeline (fetch HTML -> JSON-LD -> AI fallback)
    |
    +--- "tiktok" ------> Video pipeline (metadata -> audio transcription -> frame analysis)
    +--- "instagram" ---> Video pipeline (same)
    +--- "youtube" -----> Video pipeline (same, YouTube has better subtitle support)
    +--- "pinterest" ---> Pinterest pipeline (fetch pin data, may link to source URL)
    +--- "facebook" ----> Video pipeline (same)
```

**Pinterest special case:** Pinterest pins often link to the original recipe source URL. The pipeline should:
1. Extract the pin's source URL
2. If source URL exists, route to the standard web pipeline
3. If no source URL, extract from pin description + image

#### Implementation Complexity

This is primarily a routing layer -- it detects URL type and dispatches to the correct extraction pipeline. The URL detection itself is simple regex matching. The main work is building the video extraction pipeline (covered in section 1).

---

## Universal Media Pipeline Architecture

### Unified Entry Point

All media imports should funnel through a single API entry point with media-type detection:

```
POST /v1/recipe-books/{book_id}/import
{
    "source_type": "url" | "url_list" | "photo" | "text" | "pdf" | "audio" | "video" | "file",

    // For URL-based imports:
    "url": "https://...",
    "urls": ["https://...", ...],

    // For text imports:
    "raw_text": "...",

    // For file imports (photo, pdf, audio, video):
    "ocr_texts": ["..."],           // Photo OCR (existing)
    "file_s3_key": "uploads/...",   // Pre-uploaded file reference
    "file_type": "pdf" | "audio" | "video" | "csv" | "image",
}
```

### Media Type Router

```
                        StartImport API
                             |
                             v
                    [Media Type Router]
                    /    |    |    |    \
                  URL  Photo  PDF  Audio  Video/File
                   |     |     |     |      |
                   v     v     v     v      v
              URL     Photo   PDF  Audio  Video
              Router  OCR    Parse Trans  Meta+
              |       |       |     |     Audio
              |       |       |     |      |
              v       v       v     v      v
         +-----------------------------------------+
         |     Text Recipe Extraction (AI)          |
         |   (GPT-4o-mini structures any text       |
         |    into recipe JSON format)              |
         +-----------------------------------------+
                             |
                             v
                    MatchIngredientsTask
                             |
                             v
                    Review (if needed)
                             |
                             v
                    CreateRecipeTask
```

### Architecture Principles

1. **All roads lead to text.** Every media type eventually produces text (OCR text, transcript, caption, raw text, extracted HTML). The existing `extract_recipe_from_text()` function is the universal structuring layer.

2. **The pipeline is a DAG, not a chain.** Different media types may skip steps or take different paths, but they all converge at the text structuring step.

3. **Cost optimization through tiered extraction.** Always try the cheapest method first (metadata, JSON-LD) before falling back to expensive methods (audio transcription, visual analysis).

4. **Async by default.** All extraction beyond the simplest cases runs as Celery tasks with polling/notification for completion.

5. **Source type tracking.** Every ImportItem tracks its `source_type` and `extractor_used` for analytics and debugging. New source types: `video_metadata`, `video_audio`, `video_frames`, `pdf_text`, `pdf_ocr`, `audio_transcript`.

### New Task: MediaPreprocessTask

Add a new task between `ParseSourceTask` and `ExtractRecipeTask` that handles media-specific preprocessing:

```python
class MediaPreprocessTask(BaseTask):
    """Preprocesses media files into text for recipe extraction.

    Handles:
    - Video URLs: metadata extraction, audio download + transcription
    - Audio files: transcription
    - PDF files: text extraction or OCR
    - Images: OCR (existing) or GPT-4o-mini vision (new)
    """

    name = "media_preprocess_task"

    def execute(self, item_id: str):
        item = self.database.find_by(ImportItem, id=item_id)

        if item.source_type in ("video", "video_url"):
            text = self._process_video(item)
        elif item.source_type == "audio":
            text = self._process_audio(item)
        elif item.source_type == "pdf_page":
            text = self._process_pdf_page(item)
        elif item.source_type == "photo" and not item.raw_data.get("text"):
            text = self._process_image(item)
        else:
            return  # Already has text, skip preprocessing

        # Store preprocessed text and dispatch to extraction
        item.raw_data = {**(item.raw_data or {}), "text": text}
        item.source_type = f"{item.source_type}_preprocessed"
        self.database.db.commit()

        # Dispatch to ExtractRecipeTask
        extract_task.delay(item_ids=[str(item.id)], user_id=str(self.user_id))
```

### New Extractor: VideoMetadataExtractor

```python
class VideoMetadataExtractor:
    """Extracts recipe text from video URL metadata using yt-dlp."""

    def extract_metadata(self, url: str) -> dict:
        """Extract video metadata without downloading the video."""
        import yt_dlp

        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitlesformat': 'json3',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'subtitles': self._extract_subtitles(info),
            'duration': info.get('duration', 0),
            'platform': info.get('extractor_key', ''),
            'uploader': info.get('uploader', ''),
            'thumbnail': info.get('thumbnail', ''),
        }

    def has_recipe_content(self, metadata: dict) -> bool:
        """Check if metadata contains recipe-like content."""
        text = f"{metadata['title']} {metadata['description']} {metadata.get('subtitles', '')}"
        recipe_indicators = [
            'ingredient', 'recipe', 'tbsp', 'tsp', 'cup', 'oz',
            'tablespoon', 'teaspoon', 'preheat', 'bake', 'cook',
            'stir', 'mix', 'chop', 'dice', 'mince', 'saute',
        ]
        text_lower = text.lower()
        return sum(1 for indicator in recipe_indicators if indicator in text_lower) >= 2

    def download_audio(self, url: str, output_path: str) -> str:
        """Download only the audio track from a video."""
        import yt_dlp

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
            'outtmpl': output_path,
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return f"{output_path}.mp3"
```

---

## Share-to-App Enhancement

### Current State

The Flutter app uses `receive_sharing_intent` to handle shared content. Currently, only URLs are processed:

```dart
// In main.dart _handleSharedFiles():
void _handleSharedFiles(List<SharedMediaFile> files) {
    for (final file in files) {
        final path = file.path.trim();
        if (path.startsWith('http://') || path.startsWith('https://')) {
            // Route to ShareImportScreen with URL
        }
        // Try to extract URL from text
        // ...
        // Non-URL files are silently ignored
    }
}
```

### Proposed Enhancement

Extend the share handler to accept images, videos, PDFs, and text:

```dart
void _handleSharedFiles(List<SharedMediaFile> files) {
    for (final file in files) {
        final path = file.path.trim();
        final mimeType = file.mimeType ?? '';
        final type = file.type; // SharedMediaType enum

        if (path.startsWith('http://') || path.startsWith('https://')) {
            // Existing: route URL to share import
            _routeToShareImport(url: path);
        } else if (type == SharedMediaType.image || mimeType.startsWith('image/')) {
            // NEW: route image to photo import
            _routeToPhotoImport(filePath: path);
        } else if (mimeType == 'application/pdf') {
            // NEW: route PDF to PDF import
            _routeToPdfImport(filePath: path);
        } else if (type == SharedMediaType.video || mimeType.startsWith('video/')) {
            // NEW: route video file to video import
            _routeToVideoImport(filePath: path);
        } else if (mimeType.startsWith('audio/')) {
            // NEW: route audio to audio import
            _routeToAudioImport(filePath: path);
        } else if (mimeType == 'text/csv' ||
                   mimeType == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
            // NEW: route spreadsheet to file import
            _routeToSpreadsheetImport(filePath: path);
        } else {
            // Try to extract URL from text content
            final urlMatch = RegExp(r'https?://\S+').firstMatch(path);
            if (urlMatch != null) {
                _routeToShareImport(url: urlMatch.group(0)!);
            }
        }
    }
}
```

### iOS Configuration Changes

In the iOS share extension's `Info.plist`, add supported types:

```xml
<key>NSExtensionActivationRule</key>
<dict>
    <key>NSExtensionActivationSupportsWebURLWithMaxCount</key>
    <integer>1</integer>
    <key>NSExtensionActivationSupportsImageWithMaxCount</key>
    <integer>10</integer>
    <key>NSExtensionActivationSupportsFileWithMaxCount</key>
    <integer>5</integer>
    <key>NSExtensionActivationSupportsText</key>
    <true/>
    <key>NSExtensionActivationSupportsMovieWithMaxCount</key>
    <integer>1</integer>
</dict>
```

### Implementation Effort

| Change | Effort |
|--------|--------|
| Update `_handleSharedFiles` in `main.dart` | S (half day) |
| Create routing functions for each media type | S (half day) |
| Update iOS share extension plist for file types | XS (1 hour) |
| Create "Shared File Import" screen (progress + result) | M (1-2 days) |
| File upload to S3 from share context | S (half day) |
| **Total** | **M (2-3 days)** |

---

## Social Media URL Detection & Routing

### Detection Patterns

```python
import re
from enum import Enum

class SocialPlatform(Enum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    PINTEREST = "pinterest"
    FACEBOOK = "facebook"
    WEB = "web"  # Standard website

# Compiled patterns for performance
PLATFORM_PATTERNS: dict[SocialPlatform, list[re.Pattern]] = {
    SocialPlatform.TIKTOK: [
        re.compile(r"(?:www\.)?tiktok\.com/@[\w.]+/video/\d+"),
        re.compile(r"vm\.tiktok\.com/\w+"),
        re.compile(r"(?:www\.)?tiktok\.com/t/\w+"),
    ],
    SocialPlatform.INSTAGRAM: [
        re.compile(r"(?:www\.)?instagram\.com/(p|reel|reels)/[\w-]+"),
        re.compile(r"instagr\.am/(p|reel)/[\w-]+"),
    ],
    SocialPlatform.YOUTUBE: [
        re.compile(r"(?:www\.)?youtube\.com/watch\?v=[\w-]+"),
        re.compile(r"youtu\.be/[\w-]+"),
        re.compile(r"(?:www\.)?youtube\.com/shorts/[\w-]+"),
        re.compile(r"(?:www\.)?youtube\.com/embed/[\w-]+"),
    ],
    SocialPlatform.PINTEREST: [
        re.compile(r"(?:www\.)?pinterest\.com/pin/\d+"),
        re.compile(r"pin\.it/\w+"),
    ],
    SocialPlatform.FACEBOOK: [
        re.compile(r"(?:www\.)?facebook\.com/.+/videos/\d+"),
        re.compile(r"fb\.watch/\w+"),
        re.compile(r"(?:www\.)?facebook\.com/watch/?\?v=\d+"),
    ],
}

def detect_platform(url: str) -> SocialPlatform:
    """Detect which social media platform a URL belongs to."""
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(url):
                return platform
    return SocialPlatform.WEB
```

### Integration with ExtractRecipeTask

Modify `_extract_single_item` in `ExtractRecipeTask` to use the URL router:

```python
def _extract_single_item(self, item_id: str) -> dict:
    item = self.database.find_by(ImportItem, id=item_id)

    if item.source_type == "photo":
        # Existing photo path
        ...
    elif item.source_url:
        platform = detect_platform(item.source_url)

        if platform == SocialPlatform.WEB:
            # Existing web extraction path
            result = asyncio.run(extract_recipe_from_url(item.source_url))
        else:
            # NEW: video/social media extraction
            result = self._extract_from_video_url(item, platform)
    ...
```

---

## Priority Recommendations

### Phase 1: Social Media URL Detection + Video Metadata (HIGH IMPACT, MEDIUM EFFORT)

**Why first:** This is the #1 requested feature and the biggest gap vs. Recime/Pestle. The metadata-only path covers 70-80% of video recipes at near-zero cost.

**Scope:**
- URL pattern detection for TikTok, Instagram, YouTube, Pinterest, Facebook
- `yt-dlp` integration for metadata/caption extraction
- Route extracted text to existing `extract_recipe_from_text()`
- Update `ExtractRecipeTask` to handle video URLs
- No audio transcription yet (Tier 1 only)

**Effort:** M (5-7 days backend, 1-2 days frontend for status messaging)

**Cost impact:** Near zero per extraction ($0.001-0.002 for AI structuring)

### Phase 2: Audio Transcription Fallback for Videos (MEDIUM IMPACT, LOW EFFORT)

**Why second:** Builds on Phase 1 to handle the 20-30% of videos where metadata has no recipe content.

**Scope:**
- Audio download via `yt-dlp` (audio-only, not full video)
- OpenAI Whisper/GPT-4o-mini Transcribe integration
- Fallback logic: try metadata first, if no recipe content detected, download and transcribe audio
- Max audio length: 10 minutes

**Effort:** S-M (3-4 days)

**Cost impact:** $0.003-0.03 per transcription

### Phase 3: PDF Import (MEDIUM IMPACT, MEDIUM EFFORT)

**Why third:** Common user request, especially for cookbook digitization. Backend model already has "pdf" as a source type.

**Scope:**
- PyMuPDF integration for text-based PDFs
- Page-to-image conversion for scanned PDFs -> existing OCR pipeline
- AI-based recipe boundary detection for multi-recipe PDFs
- File upload endpoint + S3 storage
- Flutter screen for PDF import (file picker, page preview)

**Effort:** M-L (5-8 days)

**Cost impact:** $0.002-0.005 per recipe (text-based), $0.005-0.010 per recipe (scanned)

### Phase 4: Share-to-App File Support (LOW-MEDIUM IMPACT, LOW EFFORT)

**Why fourth:** Quick win that makes the share sheet accept images, PDFs, and other files, not just URLs.

**Scope:**
- Update `_handleSharedFiles` in `main.dart` to detect file types
- Route to appropriate import screen based on MIME type
- Update iOS share extension configuration for file types
- File upload flow for shared files

**Effort:** S-M (2-3 days)

**Cost impact:** None (uses existing pipelines)

### Phase 5: Audio File Import (LOW IMPACT, LOW EFFORT)

**Why fifth:** Novel feature with a niche but loyal audience (grandma's recipes). Very low effort since Whisper integration exists from Phase 2.

**Scope:**
- Audio file picker in Flutter
- Upload to S3
- Whisper transcription (reuse Phase 2 infrastructure)
- Text extraction (reuse existing)
- New Flutter screen for audio import

**Effort:** S (2-3 days, mostly frontend)

**Cost impact:** $0.005-0.032 per recording

### Phase 6: GPT-4o-mini Vision Direct Path for Images (LOW IMPACT, LOW EFFORT)

**Why last:** HunyuanOCR already works. This is an optimization, not a new capability.

**Scope:**
- New extractor that sends image directly to GPT-4o-mini vision
- Use as default for single-image imports (faster, simpler)
- Keep HunyuanOCR for batch operations (cheaper at scale)

**Effort:** S (1-2 days)

**Cost impact:** Slightly higher per image ($0.003 vs $0.002) but faster and simpler

---

## Estimated Complexity Summary

| Media Type | Frontend | Backend | Total | Dependencies |
|-----------|----------|---------|-------|-------------|
| Video URL (metadata only) | S (2d) | M (5d) | **M (7d)** | yt-dlp |
| Video URL (+ audio) | XS (1d) | S-M (3d) | **S-M (4d)** | Phase 1 + Whisper API |
| PDF import | M (3d) | M (5d) | **M-L (8d)** | PyMuPDF |
| Share-to-app files | S (2d) | XS (1d) | **S (3d)** | None |
| Audio file import | S (2d) | S (1d) | **S (3d)** | Phase 2 (Whisper) |
| GPT-4o vision for images | XS (0.5d) | S (1.5d) | **S (2d)** | None |
| Social URL detection | XS (0.5d) | S (1d) | **XS-S (1.5d)** | None (included in Phase 1) |

**Total estimated effort for full universal media import: 6-8 weeks of engineering time**

---

## Cost Analysis at Scale

### Per-Extraction Cost by Media Type

| Media Type | Cost per Extraction |
|-----------|-------------------|
| URL (JSON-LD) | $0.000 |
| URL (AI fallback) | $0.002 |
| Photo (HunyuanOCR + AI) | $0.003 |
| Photo (GPT-4o-mini vision) | $0.003 |
| Video (metadata path) | $0.002 |
| Video (audio path, 3min avg) | $0.013 |
| Audio (3min avg) | $0.011 |
| PDF (text, single recipe) | $0.003 |
| PDF (scanned, single recipe) | $0.006 |
| Text paste | $0.002 |

### Monthly Cost Projections

Assumptions for usage mix:
- 50% URL imports (70% JSON-LD success, 30% AI fallback)
- 20% photo imports
- 15% video imports (75% metadata success, 25% need audio)
- 5% text paste
- 5% PDF imports (80% text-based, 20% scanned)
- 3% audio imports
- 2% other

**Weighted average cost per extraction: ~$0.004**

| Scale | Extractions/Month | AI/Processing Cost | S3 Storage | Total Monthly |
|-------|-------------------|-------------------|------------|---------------|
| 100 users (light) | 500 | $2.00 | $0.10 | **$2.10** |
| 100 users (heavy) | 2,000 | $8.00 | $0.50 | **$8.50** |
| 1,000 users | 5,000 | $20.00 | $2.00 | **$22.00** |
| 1,000 users (heavy) | 20,000 | $80.00 | $5.00 | **$85.00** |
| 10,000 users | 50,000 | $200.00 | $15.00 | **$215.00** |
| 10,000 users (heavy) | 200,000 | $800.00 | $50.00 | **$850.00** |

### Cost Optimization Strategies

1. **Metadata-first for videos:** Saves ~$0.01-0.05 per extraction vs. always transcribing audio
2. **JSON-LD first for URLs:** Saves $0.002 per extraction vs. always using AI
3. **Text-based PDF detection:** Saves $0.003-0.005 per page vs. always using OCR
4. **GPT-4o-mini Transcribe ($0.003/min) over Whisper ($0.006/min):** 50% savings on audio
5. **Batch API for non-urgent extractions:** OpenAI Batch API is 50% cheaper for both input and output tokens
6. **Cache ingredient matches:** Already implemented, reduces per-recipe AI calls over time
7. **Max audio length cap (10 min):** Prevents runaway costs from long podcast clips

### Break-Even: Self-Hosted Whisper

At what scale does self-hosting Whisper make sense?

| Self-Hosted Option | Monthly Cost | Break-Even |
|-------------------|-------------|------------|
| Modal.com (A10G on-demand) | $0.76/hour | ~2,500 min/month of transcription |
| Hetzner GPU server | ~$200/month | ~33,000 min/month of transcription |

At 10,000 users with 15% video imports needing audio: ~3,000 transcription minutes/month. Self-hosting on Modal begins to make sense at this scale. Dedicated GPU server not until 50,000+ users.

---

## New Dependencies Required

### Python Packages (Backend)

| Package | Purpose | Size/Notes |
|---------|---------|------------|
| `yt-dlp` | Video metadata + audio download | Large but well-maintained; 1700+ site support |
| `pymupdf` (fitz) | PDF text extraction + page rendering | Lightweight, C-based, fast |
| `openai` (already installed) | Whisper API + GPT-4o-mini vision | Already in use |

### Flutter Packages (Frontend)

| Package | Purpose | Notes |
|---------|---------|-------|
| `file_picker` (already installed) | Pick PDF, audio, video files | Already used for file import stub |
| `receive_sharing_intent` (already installed) | Accept shared files from other apps | Needs config update for new file types |

### Infrastructure

| Service | Purpose | Cost |
|---------|---------|------|
| S3 (existing) | Temporary storage for uploaded files | Minimal |
| Celery (existing) | Async task processing | No change |
| `ffmpeg` (on worker) | Audio extraction from video files | Free, needs to be installed in worker container |

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| yt-dlp breaks with platform changes | Medium | High | Pin versions, monitor yt-dlp releases, have fallback extraction |
| TikTok/Instagram block automated access | Medium | High | Use official APIs where available, respect rate limits, rotate user agents |
| Whisper API latency spikes | Low | Medium | Set timeouts, offer retry, consider self-hosted fallback |
| PDF recipe boundary detection fails | Medium | Low | Default to one-recipe-per-page, let user correct |
| HunyuanOCR GPU cold start too slow | Low | Low | Already handled by Spot instances; GPT-4o-mini vision as alternative |

### Legal/Compliance Risks

| Risk | Mitigation |
|------|------------|
| Video download may violate ToS | Only download metadata + audio (not full video); delete after processing |
| Copyright on recipe content | Users are importing for personal use; recipes themselves are not copyrightable (only the expression/photos) |
| Rate limiting by social platforms | Implement request throttling; use official APIs where possible; cache results |

### User Experience Risks

| Risk | Mitigation |
|------|------------|
| Long wait for audio transcription | Show progress stages ("Downloading audio...", "Transcribing...", "Extracting recipe...") |
| Poor extraction quality from videos | Show confidence score; make it easy to edit; allow re-extraction with different method |
| PDF import produces too many recipes | Let user select page range before processing; show preview |

---

## Appendix: Competitor Feature Matrix (Media Import)

| Media Type | Palateful (Current) | Palateful (Proposed) | Recime | Pestle | Mela | Paprika |
|-----------|-------------------|---------------------|--------|--------|------|---------|
| URL (web) | Yes (JSON-LD + AI) | Yes | Yes | Yes | Yes | Yes |
| URL (TikTok) | No | Yes (metadata + audio) | Yes (AI) | Yes (on-device) | No | No |
| URL (Instagram) | No | Yes | Yes (AI) | Yes (on-device) | No | No |
| URL (YouTube) | No | Yes | Yes | Yes | No | No |
| URL (Pinterest) | No | Yes (via source URL) | Yes | No | No | No |
| Photo/OCR | Yes (HunyuanOCR) | Yes + GPT-4o-mini vision | Yes | Yes | Yes | No |
| Multi-photo | Yes | Yes | Yes | Yes | No | No |
| Text paste | Yes | Yes | Yes | Yes | Yes | Yes |
| PDF (text) | No | Yes | No | No | No | Partial |
| PDF (scanned) | No | Yes (OCR) | No | No | No | No |
| Audio file | No | Yes (Whisper) | No | No | No | No |
| Video file (shared) | No | Yes | No | No | No | No |
| Spreadsheet (CSV) | No (stub) | Planned | No | No | No | Yes |
| Cross-app migration | No | Planned | Paprika, Notes | Paprika, Crouton | Paprika | Various |
| Share sheet (URLs) | Yes | Yes | Yes | Yes | Yes | N/A |
| Share sheet (files) | No | Yes | Partial | No | No | N/A |

---

## Appendix: Key File Paths (Existing Code)

### Import Pipeline (Backend)
- `services/api/src/api/v1/import_job/start_import.py` -- StartImport endpoint (modify for new source types)
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py` -- ParseSourceTask (add new source type handlers)
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` -- ExtractRecipeTask (add video/audio/PDF extraction)
- `libraries/utils/utils/services/recipe_extractors/__init__.py` -- Extractor registry (add VideoMetadataExtractor, PDFExtractor)
- `libraries/utils/utils/services/recipe_extractors/text_extractor.py` -- Text extractor (reused for all media types after preprocessing)
- `libraries/utils/utils/services/recipe_extractors/ai_extractor.py` -- AI HTML extractor

### Share Sheet (Flutter)
- `app/lib/main.dart` -- `_handleSharedFiles()` (extend for file types)
- `app/lib/features/recipes/add_recipe/share_import_screen.dart` -- Share import screen (URL-only currently)

### Parser Service
- `services/parser/src/main.py` -- OCR service (reusable for PDF page OCR)
- `services/parser/src/model.py` -- HunyuanOCR model

### New Files to Create
- `libraries/utils/utils/services/recipe_extractors/video_extractor.py` -- Video metadata + audio extraction
- `libraries/utils/utils/services/recipe_extractors/pdf_extractor.py` -- PDF text/OCR extraction
- `libraries/utils/utils/services/recipe_extractors/audio_extractor.py` -- Audio transcription
- `libraries/utils/utils/services/url_classifier.py` -- Social media URL detection
- `libraries/utils/utils/tasks/import_tasks/media_preprocess_task.py` -- Media preprocessing orchestrator
- `app/lib/features/recipes/add_recipe/pdf_import_screen.dart` -- PDF import screen
- `app/lib/features/recipes/add_recipe/audio_import_screen.dart` -- Audio import screen
- `app/lib/features/recipes/add_recipe/video_import_screen.dart` -- Video file import screen

---

*Sources consulted for this investigation:*
- [OpenAI API Pricing](https://openai.com/api/pricing/) -- Whisper ($0.006/min), GPT-4o-mini Transcribe ($0.003/min), GPT-4o-mini ($0.15/$0.60 per 1M tokens)
- [Whisper API Pricing Analysis](https://brasstranscripts.com/blog/openai-whisper-api-pricing-2025-self-hosted-vs-managed) -- Self-hosted vs. managed cost comparison
- [Pestle TikTok Feature (TechCrunch)](https://techcrunch.com/2024/11/25/pestle-recipe-app-can-now-save-dishes-from-tiktok/) -- On-device ML approach, <1 second processing
- [Pestle Instagram Reels Feature (TechCrunch)](https://techcrunch.com/2024/07/08/pestles-app-can-now-save-recipes-from-reels-using-on-device-ai/) -- Caption-based extraction, 0.1 second processing
- [ReciMe Import from TikTok (Help)](https://recime.app/help/en/articles/11661452-import-from-tiktok) -- Cloud AI extraction from video audio
- [ReciMe Import from Instagram (Help)](https://recime.app/help/en/articles/11596425-import-from-instagram) -- Audio extraction with website fallback
- [Supadata TikTok Transcript API](https://supadata.ai/tiktok-transcript-api) -- Free API for TikTok transcripts
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp) -- Open source video metadata/download tool, 1700+ sites
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/en/latest/) -- PDF text extraction and OCR integration
- [receive_sharing_intent Flutter package](https://pub.dev/packages/receive_sharing_intent) -- iOS/Android share extension for Flutter
- [GPT-4o Mini Vision Token Calculator](https://github.com/jamesmcroft/openai-image-token-calculator) -- Image token cost estimation
- [Pluck vs Pestle Comparison](https://pluckrecipes.com/blog/pluck-vs-pestle/) -- Detailed competitor comparison on video extraction
- [Best Recipe Apps 2026](https://pluckrecipes.com/best-recipe-app/) -- Comprehensive competitor landscape
