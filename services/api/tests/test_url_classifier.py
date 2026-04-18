"""sbf-5: unit tests for url_classifier.detect_platform.

The endpoint calls detect_platform() at ImportItem creation time to
decide whether a /import URL is a social-media video (TikTok /
Instagram / YouTube / Pinterest / Facebook) or a regular web page.
The extractor task keeps a defensive fallback call; these tests pin
the primary contract here so neither side silently drifts.
"""

from __future__ import annotations

import pytest

from utils.services.url_classifier import (
    SocialPlatform,
    detect_platform,
    is_social_media_url,
)


class TestDetectPlatform:
    @pytest.mark.parametrize("url", [
        "https://www.tiktok.com/@somechef/video/7123456789012345678",
        "https://vm.tiktok.com/ZMabc123/",
        "https://www.tiktok.com/t/ABCdef/",
    ])
    def test_tiktok_variants(self, url):
        assert detect_platform(url) == SocialPlatform.TIKTOK

    @pytest.mark.parametrize("url", [
        "https://www.instagram.com/p/CxYzAbc/",
        "https://instagram.com/reel/CxYzAbc/",
        "https://www.instagram.com/reels/CxYzAbc/",
        "https://instagr.am/shortcode-ab",
    ])
    def test_instagram_variants(self, url):
        assert detect_platform(url) == SocialPlatform.INSTAGRAM

    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/abc_123",
    ])
    def test_youtube_variants(self, url):
        assert detect_platform(url) == SocialPlatform.YOUTUBE

    @pytest.mark.parametrize("url", [
        "https://www.pinterest.com/pin/123456789/",
        "https://pin.it/ABCdef",
    ])
    def test_pinterest_variants(self, url):
        assert detect_platform(url) == SocialPlatform.PINTEREST

    @pytest.mark.parametrize("url", [
        "https://www.facebook.com/cookingchannel/videos/987654321",
        "https://fb.watch/shortcode",
    ])
    def test_facebook_variants(self, url):
        assert detect_platform(url) == SocialPlatform.FACEBOOK

    @pytest.mark.parametrize("url", [
        "https://www.nytimes.com/recipes/1016847/risotto",
        "https://bonappetit.com/recipe/chocolate-chip-cookies",
        "https://somerandomblog.example.com/2024/pasta",
        "https://www.google.com/search?q=pasta+recipe",
        "",
        None,
    ])
    def test_web_default(self, url):
        assert detect_platform(url) == SocialPlatform.WEB

    def test_is_social_media_url_aligns(self):
        assert is_social_media_url("https://www.tiktok.com/@x/video/1") is True
        assert is_social_media_url("https://nytimes.com/recipes/1") is False
