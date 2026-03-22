"""Audio transcription extractor using OpenAI GPT-4o-mini Transcribe API."""

import logging
import os
import tempfile

from utils.services.recipe_extractors.base import ExtractionResult
from utils.services.recipe_extractors.text_extractor import extract_recipe_from_text
from utils.services.recipe_extractors.video_extractor import has_recipe_content

logger = logging.getLogger(__name__)

MAX_AUDIO_DURATION_SECONDS = 600  # 10 minutes
GPT4O_MINI_TRANSCRIBE_COST_PER_MINUTE = 0.003


def download_audio(url: str) -> tuple[str | None, float | None, str | None]:
    """Download audio track from a video URL using yt-dlp.

    Returns (temp_file_path, duration_seconds, error_message).
    The caller is responsible for deleting the temp file.
    """
    import yt_dlp

    temp_dir = tempfile.mkdtemp(prefix="palateful_audio_")
    output_template = os.path.join(temp_dir, "audio.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None, None, "Could not download audio"
            duration = info.get("duration")
    except Exception as e:
        logger.warning("yt-dlp audio download failed for %s: %s", url, e)
        return None, None, f"Failed to download audio: {e}"

    # Find the output file
    audio_path = os.path.join(temp_dir, "audio.mp3")
    if not os.path.exists(audio_path):
        # yt-dlp may use a different extension
        for f in os.listdir(temp_dir):
            audio_path = os.path.join(temp_dir, f)
            break
        else:
            return None, duration, "Audio file not found after download"

    return audio_path, duration, None


def transcribe_audio(audio_path: str) -> tuple[str, int]:
    """Transcribe an audio file using OpenAI GPT-4o-mini Transcribe API.

    Returns (transcript_text, cost_cents).
    """
    from openai import OpenAI

    client = OpenAI()

    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
            language="en",
        )

    transcript = response.text or ""

    # Estimate cost based on file size (rough proxy for duration)
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    # MP3 at 128kbps ≈ 1MB per minute
    estimated_minutes = file_size_mb
    cost_dollars = estimated_minutes * GPT4O_MINI_TRANSCRIBE_COST_PER_MINUTE
    cost_cents = max(1, int(cost_dollars * 100))

    return transcript, cost_cents


def _cleanup_audio(audio_path: str):
    """Remove temporary audio file and its directory."""
    try:
        if audio_path and os.path.exists(audio_path):
            parent_dir = os.path.dirname(audio_path)
            os.remove(audio_path)
            if parent_dir and os.path.isdir(parent_dir):
                os.rmdir(parent_dir)
    except OSError:
        pass


def extract_recipe_from_audio(url: str, duration_seconds: float | None = None) -> ExtractionResult:
    """Extract recipe by downloading video audio and transcribing it.

    This is the Tier 2 fallback when video metadata (captions/description)
    doesn't contain recipe content.

    Args:
        url: Video URL to download audio from.
        duration_seconds: Known video duration (from metadata). Used to
            enforce the 10-minute cap before downloading.

    Returns:
        ExtractionResult with extractor_used="video_audio_transcript".
    """
    # Enforce duration cap
    if duration_seconds is not None and duration_seconds > MAX_AUDIO_DURATION_SECONDS:
        return ExtractionResult(
            success=False,
            error_message=f"Video is too long ({int(duration_seconds / 60)} minutes). Maximum is 10 minutes for audio transcription.",
            error_code="VIDEO_TOO_LONG",
            extractor_used="video_audio_transcript",
        )

    # Download audio
    audio_path, actual_duration, error = download_audio(url)
    if error or audio_path is None:
        return ExtractionResult(
            success=False,
            error_message=error or "Failed to download audio",
            error_code="AUDIO_DOWNLOAD_ERROR",
            extractor_used="video_audio_transcript",
        )

    # Check duration after download if not known beforehand
    if actual_duration is not None and actual_duration > MAX_AUDIO_DURATION_SECONDS:
        _cleanup_audio(audio_path)
        return ExtractionResult(
            success=False,
            error_message=f"Video is too long ({int(actual_duration / 60)} minutes). Maximum is 10 minutes.",
            error_code="VIDEO_TOO_LONG",
            extractor_used="video_audio_transcript",
        )

    try:
        # Transcribe
        transcript, transcription_cost_cents = transcribe_audio(audio_path)

        if not transcript.strip():
            return ExtractionResult(
                success=False,
                error_message="Couldn't find a recipe in this video",
                error_code="NO_RECIPE_CONTENT",
                extractor_used="video_audio_transcript",
                ai_cost_cents=transcription_cost_cents,
            )

        # Check if transcript has recipe content
        transcript_meta = {"title": "", "description": transcript, "subtitles_text": ""}
        if not has_recipe_content(transcript_meta):
            return ExtractionResult(
                success=False,
                error_message="Couldn't find a recipe in this video",
                error_code="NO_RECIPE_CONTENT",
                extractor_used="video_audio_transcript",
                ai_cost_cents=transcription_cost_cents,
            )

        # Feed transcript to AI extraction
        result = extract_recipe_from_text(transcript)
        result.ai_cost_cents += transcription_cost_cents
        if result.success:
            result.extractor_used = "video_audio_transcript"
        if result.recipe:
            result.recipe.source_url = url

        return result

    finally:
        _cleanup_audio(audio_path)
