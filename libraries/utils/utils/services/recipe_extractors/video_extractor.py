"""Video metadata extractor using yt-dlp for social media recipe videos."""

import logging
import re

from utils.services.recipe_extractors.base import ExtractionResult
from utils.services.recipe_extractors.text_extractor import extract_recipe_from_text

logger = logging.getLogger(__name__)

# Keywords that indicate recipe content in video metadata
_RECIPE_INDICATORS = re.compile(
    r"\b("
    r"recipe|ingredient|tablespoon|teaspoon|tbsp|tsp|cups?|ounces?|oz"
    r"|preheat|bake|saut[eé]|simmer|boil|whisk|stir|chop|dice|mince"
    r"|flour|sugar|butter|salt|pepper|garlic|onion|olive oil"
    r"|serves?\s*\d|servings?"
    r")\b",
    re.IGNORECASE,
)

_RECIPE_INDICATOR_THRESHOLD = 2


class VideoMetadataExtractor:
    """Extract recipe data from social media video metadata using yt-dlp."""

    def extract_metadata(self, url: str) -> dict:
        """Extract video metadata without downloading the video.

        Returns a dict with: title, description, subtitles_text, duration,
        platform, uploader, thumbnail_url.
        """
        import yt_dlp

        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en-GB"],
            "extract_flat": False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return {"error": "Could not extract video info"}
        except Exception as e:
            logger.warning("yt-dlp failed for %s: %s", url, e)
            return {"error": f"Failed to fetch video info: {e}"}

        # Extract subtitles text
        subtitles_text = self._extract_subtitles_text(info)

        return {
            "title": info.get("title") or "",
            "description": info.get("description") or "",
            "subtitles_text": subtitles_text,
            "duration": info.get("duration"),
            "platform": info.get("extractor_key") or info.get("extractor") or "",
            "uploader": info.get("uploader") or info.get("channel") or "",
            "thumbnail_url": info.get("thumbnail"),
        }

    def _extract_subtitles_text(self, info: dict) -> str:
        """Extract subtitle text from yt-dlp info dict.

        Tries manual subtitles first, then auto-generated.
        """
        for sub_key in ("subtitles", "automatic_captions"):
            subs = info.get(sub_key) or {}
            for lang in ("en", "en-US", "en-GB"):
                if lang not in subs:
                    continue
                for fmt in subs[lang]:
                    # yt-dlp may include subtitle data inline
                    if "data" in fmt:
                        return self._clean_subtitle_data(fmt["data"])
        return ""

    def _clean_subtitle_data(self, data: str) -> str:
        """Clean raw subtitle data (VTT/SRT format) to plain text."""
        # Remove VTT/SRT headers and timestamps
        lines = data.split("\n")
        text_lines = []
        for line in lines:
            line = line.strip()
            # Skip empty, timestamps, VTT headers, and cue numbers
            if not line:
                continue
            if re.match(r"^\d+$", line):
                continue
            if re.match(r"^\d{2}:\d{2}", line):
                continue
            if line.startswith("WEBVTT") or line.startswith("NOTE"):
                continue
            # Remove HTML tags from subtitles
            line = re.sub(r"<[^>]+>", "", line)
            if line and line not in text_lines:
                text_lines.append(line)
        return " ".join(text_lines)


def has_recipe_content(metadata: dict) -> bool:
    """Check if video metadata contains recipe-like content.

    Counts recipe indicator keywords across title, description, and subtitles.
    Returns True if count >= threshold.
    """
    combined = " ".join([
        metadata.get("title", ""),
        metadata.get("description", ""),
        metadata.get("subtitles_text", ""),
    ])
    matches = _RECIPE_INDICATORS.findall(combined)
    return len(matches) >= _RECIPE_INDICATOR_THRESHOLD


def extract_recipe_from_video(url: str) -> ExtractionResult:
    """Extract recipe from a social media video URL.

    Uses yt-dlp to fetch metadata (title, description, subtitles) without
    downloading the video, then feeds the text to the AI extractor.

    Returns ExtractionResult with extractor_used="video_metadata" on success,
    or a failure result if no recipe content is found.
    """
    extractor = VideoMetadataExtractor()
    metadata = extractor.extract_metadata(url)

    if "error" in metadata:
        return ExtractionResult(
            success=False,
            error_message=metadata["error"],
            error_code="VIDEO_METADATA_ERROR",
            extractor_used="video_metadata",
        )

    if not has_recipe_content(metadata):
        return ExtractionResult(
            success=False,
            error_message="No written recipe found in this video — try audio transcription or paste the recipe text",
            error_code="NO_RECIPE_CONTENT",
            extractor_used="video_metadata",
        )

    # Compose text from metadata and feed to AI text extractor
    parts = []
    if metadata.get("title"):
        parts.append(f"Title: {metadata['title']}")
    if metadata.get("uploader"):
        parts.append(f"By: {metadata['uploader']}")
    if metadata.get("description"):
        parts.append(f"\n{metadata['description']}")
    if metadata.get("subtitles_text"):
        parts.append(f"\nSubtitles/Captions:\n{metadata['subtitles_text']}")

    combined_text = "\n".join(parts)

    result = extract_recipe_from_text(combined_text)

    # Override extractor_used to indicate the video metadata path
    if result.success:
        result.extractor_used = "video_metadata"
    if result.recipe and metadata.get("thumbnail_url"):
        result.recipe.image_url = result.recipe.image_url or metadata["thumbnail_url"]
    if result.recipe:
        result.recipe.source_url = url

    return result
