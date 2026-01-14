"""Base scraper with async HTTP, rate limiting, and caching."""

import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from ..models import ScrapedIngredient

console = Console()


class BaseScraper(ABC):
    """Abstract base class for ingredient scrapers.

    Provides:
    - Async HTTP client with connection pooling
    - Rate limiting
    - Response caching
    - Retry logic with exponential backoff
    """

    # Override in subclasses
    SOURCE_NAME: str = "base"
    BASE_URL: str = ""

    def __init__(
        self,
        cache_dir: Path | None = None,
        rate_limit: float | None = None,
        cache_ttl_hours: int = 24,
    ):
        self.cache_dir = cache_dir or settings.scraper_cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit = rate_limit or settings.scraper_rate_limit_per_second
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        self._last_request_time: float = 0
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseScraper":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.scraper_timeout_seconds),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, raising if not in async context."""
        if self._client is None:
            raise RuntimeError("Scraper must be used as async context manager")
        return self._client

    async def _rate_limit_wait(self) -> None:
        """Wait to respect rate limiting."""
        if self.rate_limit <= 0:
            return

        min_interval = 1.0 / self.rate_limit
        elapsed = asyncio.get_event_loop().time() - self._last_request_time

        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)

        self._last_request_time = asyncio.get_event_loop().time()

    def _get_cache_key(self, url: str, params: dict[str, Any] | None = None) -> str:
        """Generate a cache key for a request."""
        cache_data = f"{url}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.sha256(cache_data.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the cache file path for a cache key."""
        source_cache_dir = self.cache_dir / self.SOURCE_NAME
        source_cache_dir.mkdir(parents=True, exist_ok=True)
        return source_cache_dir / f"{cache_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if a cached response is still valid."""
        if not cache_path.exists():
            return False

        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self.cache_ttl

    def _read_cache(self, cache_path: Path) -> dict[str, Any] | None:
        """Read a cached response."""
        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, cache_path: Path, data: dict[str, Any]) -> None:
        """Write a response to cache."""
        try:
            with open(cache_path, "w") as f:
                json.dump(data, f)
        except OSError as e:
            console.print(f"[yellow]Warning: Could not write cache: {e}[/yellow]")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _fetch(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Fetch a URL with rate limiting, caching, and retries.

        Args:
            url: The URL to fetch
            params: Query parameters
            headers: HTTP headers
            use_cache: Whether to use cached responses

        Returns:
            The JSON response data
        """
        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(url, params)
            cache_path = self._get_cache_path(cache_key)
            cached = self._read_cache(cache_path)
            if cached is not None:
                return cached

        # Rate limit
        await self._rate_limit_wait()

        # Make request
        response = await self.client.get(url, params=params, headers=headers)
        response.raise_for_status()

        data = response.json()

        # Cache the response
        if use_cache:
            self._write_cache(cache_path, data)

        return data

    async def _fetch_all_pages(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        page_param: str = "page",
        limit_param: str = "limit",
        page_size: int = 100,
        max_pages: int | None = None,
        results_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated API.

        Args:
            url: Base URL
            params: Base query parameters
            page_param: Name of the page parameter
            limit_param: Name of the limit/page size parameter
            page_size: Number of items per page
            max_pages: Maximum number of pages to fetch (None for all)
            results_key: Key in response containing results list

        Returns:
            Combined list of all results
        """
        all_results: list[dict[str, Any]] = []
        page = 1
        params = params or {}

        while True:
            if max_pages and page > max_pages:
                break

            page_params = {**params, page_param: page, limit_param: page_size}
            data = await self._fetch(url, params=page_params)

            # Extract results
            if results_key:
                results = data.get(results_key, [])
            elif isinstance(data, list):
                results = data
            else:
                results = data.get("results", data.get("items", data.get("data", [])))

            if not results:
                break

            all_results.extend(results)
            console.print(f"[dim]  Page {page}: {len(results)} items[/dim]")

            # Check if there are more pages
            if len(results) < page_size:
                break

            page += 1

        return all_results

    @abstractmethod
    async def scrape(self, limit: int | None = None) -> list[ScrapedIngredient]:
        """Scrape ingredients from the source.

        Args:
            limit: Maximum number of ingredients to scrape (None for all)

        Returns:
            List of scraped ingredients
        """
        pass

    def clear_cache(self) -> int:
        """Clear all cached responses for this scraper.

        Returns:
            Number of cache files deleted
        """
        source_cache_dir = self.cache_dir / self.SOURCE_NAME
        if not source_cache_dir.exists():
            return 0

        count = 0
        for cache_file in source_cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1

        return count
