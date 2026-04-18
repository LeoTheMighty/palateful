"""ffmpeg wrapper for local video files (sbf-4).

Extracts an audio-only MP3 track from a video blob so the existing
GPT-4o-mini transcription path can take over. Hard cap of 20 minutes
(`-t 1200`) prevents runaway spend on long clips; ffmpeg runs in its
own process group so Celery's `soft_time_limit` can signal the whole
tree (not just the Python parent) when ECS drains a task mid-clip.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Hard upper bound on source video duration. ffmpeg's `-t` caps the
# *output* at 20 minutes; that's the right knob because Whisper billing
# tracks extracted audio length, not the original clip.
MAX_VIDEO_DURATION_SECONDS = 1200

# Target audio bitrate. 64 kbps mp3 is a well-known Whisper-safe bitrate
# — smaller than the stream's own audio track in virtually every case,
# so upload + transcription stay cheap.
AUDIO_BITRATE = "64k"


class VideoDecodeError(RuntimeError):
    """Raised when ffmpeg exits non-zero on a video_file import."""

    def __init__(self, stderr_tail: str) -> None:
        super().__init__(stderr_tail or "ffmpeg failed")
        self.stderr_tail = stderr_tail


@dataclass
class ExtractedAudio:
    """Result of a successful audio extraction."""

    path: str  # Local path to the `.mp3` file, ready for transcribe_audio().
    size_bytes: int
    stderr_tail: str  # For telemetry even on success.


def extract_audio_to_file(video_path: str, output_path: str) -> ExtractedAudio:
    """Run ffmpeg to pull a mono 64 kbps MP3 out of ``video_path``.

    Uses process-group signaling so SIGTERM / SIGKILL to the Python
    parent takes the whole ffmpeg tree with it — Celery's
    ``soft_time_limit`` (configured in the worker) delivers SIGTERM to
    the parent; without ``os.setsid`` ffmpeg would survive and hold
    ``/tmp`` hostage until the ECS task was force-killed.
    """
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output if it exists (tempfile-scoped anyway).
        "-hide_banner",
        "-loglevel", "error",
        "-i", video_path,
        "-vn",  # Strip video.
        "-t", str(MAX_VIDEO_DURATION_SECONDS),
        "-acodec", "libmp3lame",
        "-b:a", AUDIO_BITRATE,
        "-ac", "1",  # Mono — Whisper is fine with it.
        output_path,
    ]

    proc = subprocess.Popen(  # noqa: S603 — cmd is fixed above.
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,  # Own process group, see docstring.
    )

    try:
        _stdout, stderr = proc.communicate()
    except BaseException:
        # Include KeyboardInterrupt / SystemExit (Celery soft-time-limit
        # raises SoftTimeLimitExceeded which inherits BaseException).
        # Kill the whole group so we don't leave an orphan ffmpeg.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        raise

    stderr_tail = (stderr or b"").decode("utf-8", errors="replace")[-2000:]

    if proc.returncode != 0:
        raise VideoDecodeError(stderr_tail)

    try:
        size = os.path.getsize(output_path)
    except OSError as exc:  # pragma: no cover — ffmpeg reported ok but file vanished.
        raise VideoDecodeError(f"output missing after ffmpeg: {exc}") from exc

    return ExtractedAudio(path=output_path, size_bytes=size, stderr_tail=stderr_tail)
