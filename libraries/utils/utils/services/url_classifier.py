"""URL classifier for routing social media URLs to video extraction pipeline."""

import re
from enum import Enum


class SocialPlatform(str, Enum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    PINTEREST = "pinterest"
    FACEBOOK = "facebook"
    WEB = "web"


_PLATFORM_PATTERNS: list[tuple[SocialPlatform, re.Pattern]] = [
    # TikTok
    (SocialPlatform.TIKTOK, re.compile(
        r"(?:https?://)?(?:www\.)?tiktok\.com/@[^/]+/video/\d+", re.IGNORECASE)),
    (SocialPlatform.TIKTOK, re.compile(
        r"(?:https?://)?vm\.tiktok\.com/\w+", re.IGNORECASE)),
    (SocialPlatform.TIKTOK, re.compile(
        r"(?:https?://)?(?:www\.)?tiktok\.com/t/\w+", re.IGNORECASE)),
    # Instagram
    (SocialPlatform.INSTAGRAM, re.compile(
        r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|reels)/[\w-]+", re.IGNORECASE)),
    (SocialPlatform.INSTAGRAM, re.compile(
        r"(?:https?://)?instagr\.am/[\w-]+", re.IGNORECASE)),
    # YouTube
    (SocialPlatform.YOUTUBE, re.compile(
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+", re.IGNORECASE)),
    (SocialPlatform.YOUTUBE, re.compile(
        r"(?:https?://)?youtu\.be/[\w-]+", re.IGNORECASE)),
    (SocialPlatform.YOUTUBE, re.compile(
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+", re.IGNORECASE)),
    # Pinterest
    (SocialPlatform.PINTEREST, re.compile(
        r"(?:https?://)?(?:www\.)?pinterest\.com/pin/[\w-]+", re.IGNORECASE)),
    (SocialPlatform.PINTEREST, re.compile(
        r"(?:https?://)?pin\.it/\w+", re.IGNORECASE)),
    # Facebook
    (SocialPlatform.FACEBOOK, re.compile(
        r"(?:https?://)?(?:www\.)?facebook\.com/.+/videos/\d+", re.IGNORECASE)),
    (SocialPlatform.FACEBOOK, re.compile(
        r"(?:https?://)?fb\.watch/\w+", re.IGNORECASE)),
]


def detect_platform(url: str) -> SocialPlatform:
    """Detect which social media platform a URL belongs to.

    Returns SocialPlatform.WEB for non-social-media URLs.
    """
    if not url:
        return SocialPlatform.WEB

    for platform, pattern in _PLATFORM_PATTERNS:
        if pattern.search(url):
            return platform

    return SocialPlatform.WEB


def is_social_media_url(url: str) -> bool:
    """Check if a URL is from a supported social media platform."""
    return detect_platform(url) != SocialPlatform.WEB
