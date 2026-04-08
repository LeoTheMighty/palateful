# Epic: Universal Media-to-Recipe Import

## Overview

Enable Palateful to accept ANY piece of media — TikTok videos, Instagram Reels, YouTube clips, PDFs, voice memos, shared files — and turn it into a structured recipe. The core insight: all media types eventually produce text, which feeds into the existing `extract_recipe_from_text()` pipeline. This epic adds media-specific preprocessing stages and a URL router for social media platforms.

## Design Principles (from Party Mode discussion)

1. **All roads lead to text** — every media type produces text → existing AI structuring pipeline
2. **Tiered cost optimization** — try free/cheap methods first (metadata, JSON-LD), expensive fallbacks (audio transcription) only when needed
3. **Never show errors, always show fallbacks** — "Couldn't read this video? Try pasting the recipe text instead"
4. **Users think in "I have a link" not "I have a video URL"** — the UI says "From Link" not "Video Import"
5. **Quick Import on top** — Link, Photo, Paste as the top 3; PDF, Voice, Spreadsheet, Manual behind "More Options"

## Story Map

| Story | Title | Est. Effort | Dependencies |
|-------|-------|-------------|--------------|
| 1 | Social Media URL Router + Video Metadata Extraction | 5–7 days | None |
| 2 | Audio Transcription Fallback for Videos | 3–4 days | Story 1 |
| 3 | PDF Import — Text + OCR Dual Path | 5–7 days | None |
| 4 | Audio File Import (Voice Memos) | 2–3 days | Story 2 (reuses Whisper) |
| 5 | Add Recipe Sheet Redesign + Share Sheet Files | 2–3 days | Stories 1, 3, 4 |

**Total estimated effort: 17–24 days**

**Critical path: Story 1 → Story 2 → Story 4**
**Independent: Story 3 (PDF) can run in parallel with Stories 1–2**
**Story 5 ties it all together with the UI refresh**
