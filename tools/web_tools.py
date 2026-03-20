"""Built-in web crawling tools — inspired by OpenClaw's web_search & web_fetch.

web_search  — Search the web using Brave Search API (primary) or DuckDuckGo (fallback).
web_fetch   — HTTP GET + readable content extraction (HTML → clean text).
Results are cached in-memory for 15 minutes.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import os
import re
import time
import urllib.parse
from typing import Any

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)

_IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# ---------------------------------------------------------------------------
# Global rate limiter for DDG — prevent 202 Ratelimit from concurrent requests
# ---------------------------------------------------------------------------
_ddg_semaphore: asyncio.Semaphore | None = None


def _get_ddg_semaphore() -> asyncio.Semaphore:
    """Lazy-init semaphore (must be created inside a running event loop)."""
    global _ddg_semaphore
    if _ddg_semaphore is None:
        _ddg_semaphore = asyncio.Semaphore(2)  # max 2 concurrent DDG searches
    return _ddg_semaphore


# ---------------------------------------------------------------------------
# Cache — simple in-memory TTL cache
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def _cache_key(prefix: str, *parts: str) -> str:
    raw = f"{prefix}:{'|'.join(parts)}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL_SECONDS:
        return entry[1]
    _cache.pop(key, None)
    return None


def _set_cached(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)
    # Evict old entries periodically
    if len(_cache) > 500:
        cutoff = time.time() - CACHE_TTL_SECONDS
        stale = [k for k, (t, _) in _cache.items() if t < cutoff]
        for k in stale:
            _cache.pop(k, None)


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------

_BLOCKED_HOSTS = {"localhost", "0.0.0.0", "metadata.google.internal", "169.254.169.254"}


def _validate_url(url: str) -> None:
    """Block private/internal URLs to prevent SSRF."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs allowed, got: {parsed.scheme}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("No hostname in URL")
    if hostname.lower() in _BLOCKED_HOSTS:
        raise ValueError(f"Blocked hostname: {hostname}")
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise ValueError(f"URL points to private/reserved IP: {hostname}")
    except ValueError:
        pass  # hostname is a domain name, not IP — OK


# ---------------------------------------------------------------------------
# HTML text extraction (no external dependency beyond stdlib + bs4)
# ---------------------------------------------------------------------------

_STRIP_TAGS = {
    "script", "style", "nav", "footer", "header", "aside", "noscript",
    "iframe", "svg", "form", "button", "input", "select", "textarea",
}


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove noise tags
        for tag in soup.find_all(_STRIP_TAGS):
            tag.decompose()

        # Try to find main content area
        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.find("div", class_=re.compile(r"(content|article|post|entry)", re.I))
            or soup.body
            or soup
        )

        text = main.get_text(separator="\n", strip=True)

        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    except ImportError:
        # Fallback: basic regex HTML stripping
        return _basic_html_strip(html)


def _basic_html_strip(html: str) -> str:
    """Fallback HTML-to-text without BeautifulSoup."""
    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# web_search — Brave Search API (primary) or DuckDuckGo API (fallback)
# ---------------------------------------------------------------------------

async def web_search(
    query: str,
    *,
    max_results: int = 5,
    freshness: str | None = None,
) -> list[dict[str, str]]:
    """Search the web. Returns list of {title, url, snippet}.

    Uses Brave Search API if BRAVE_API_KEY is set, else falls back to
    DuckDuckGo search (via duckduckgo-search library — no API key needed).
    """
    key = _cache_key("search", query, str(max_results), str(freshness))
    cached = _get_cached(key)
    if cached is not None:
        logger.debug("web_search cache hit for: %s", query)
        return cached

    settings = get_settings()
    brave_key = getattr(settings, "brave_api_key", "")

    results: list[dict[str, str]] = []

    # Strategy 1: Brave Search API
    if brave_key:
        try:
            results = await _brave_search(query, max_results, freshness, brave_key)
            logger.info("Brave search returned %d results for: %s", len(results), query)
        except Exception as exc:
            logger.warning("Brave search failed for '%s': %s", query, exc)

    # Strategy 2: DuckDuckGo (no API key needed)
    if not results:
        try:
            results = await _ddg_search(query, max_results)
            logger.info("DDG search returned %d results for: %s", len(results), query)
        except Exception as exc:
            logger.warning("DDG search failed for '%s': %s", query, exc)

    # Strategy 3: Direct Google search scrape as last resort
    if not results:
        try:
            results = await _google_scrape_search(query, max_results)
            logger.info("Google scrape returned %d results for: %s", len(results), query)
        except Exception as exc:
            logger.warning("Google scrape search failed for '%s': %s", query, exc)

    if not results:
        logger.error("All search strategies failed for: %s", query)

    _set_cached(key, results)
    return results


async def _brave_search(
    query: str,
    count: int,
    freshness: str | None,
    api_key: str,
) -> list[dict[str, str]]:
    """Search via Brave Search API."""
    params: dict[str, Any] = {"q": query, "count": min(count, 10)}
    if freshness:
        params["freshness"] = freshness  # day, week, month, year

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params=params,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("web", {}).get("results", [])[:count]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", ""),
        })
    return results


async def _ddg_search(query: str, max_results: int) -> list[dict[str, str]]:
    """Search via DuckDuckGo with rate limiting and retry."""
    import os

    try:
        from duckduckgo_search import DDGS
        from duckduckgo_search.exceptions import DuckDuckGoSearchException
    except ImportError:
        logger.warning("duckduckgo-search package not installed — DDG search unavailable")
        return []

    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    max_attempts = 2 if is_serverless else 3
    sem = _get_ddg_semaphore()

    for attempt in range(max_attempts):
        async with sem:
            if attempt > 0:
                delay = 2.0 * (attempt + 1) if is_serverless else 3.0 * (2 ** attempt)
                logger.debug("DDG retry %d for '%s', waiting %.1fs", attempt + 1, query, delay)
                await asyncio.sleep(delay)

            try:
                def _sync_search() -> list[dict[str, str]]:
                    results = []
                    with DDGS() as ddgs:
                        for r in ddgs.text(query, max_results=max_results):
                            results.append({
                                "title": r.get("title", ""),
                                "url": r.get("href", ""),
                                "snippet": r.get("body", ""),
                            })
                    return results

                result = await asyncio.wait_for(
                    asyncio.to_thread(_sync_search),
                    timeout=10.0 if is_serverless else 15.0,
                )
                if result:
                    return result
            except asyncio.TimeoutError:
                logger.warning("DDG search timed out (attempt %d/%d) for '%s'", attempt + 1, max_attempts, query)
                if attempt < max_attempts - 1:
                    continue
                return []
            except DuckDuckGoSearchException as exc:
                if "Ratelimit" in str(exc) and attempt < max_attempts - 1:
                    logger.info("DDG rate limited (attempt %d/%d), will retry: %s", attempt + 1, max_attempts, query)
                    continue
                raise
            except Exception:
                raise

        await asyncio.sleep(0.5)

    return []


async def _google_scrape_search(query: str, max_results: int) -> list[dict[str, str]]:
    """Last resort: scrape Google search results page."""
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded_q}&num={max_results}"

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        })
        resp.raise_for_status()

    results = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        for g in soup.select("div.g"):
            link = g.find("a", href=True)
            if not link:
                continue
            href = link["href"]
            if not href.startswith("http"):
                continue
            title_el = g.find("h3")
            title = title_el.get_text(strip=True) if title_el else ""
            snippet_el = g.find("div", class_="VwiC3b") or g.find("span", class_="st")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            if title:
                results.append({"title": title, "url": href, "snippet": snippet})
            if len(results) >= max_results:
                break
    except ImportError:
        logger.warning("BeautifulSoup not available for Google scrape fallback")

    return results


# ---------------------------------------------------------------------------
# web_fetch — HTTP GET + readable content extraction
# ---------------------------------------------------------------------------

async def web_fetch(
    url: str,
    *,
    max_chars: int = 30000,
    extract_mode: str = "text",
) -> dict[str, Any]:
    """Fetch a URL and extract readable content.

    Returns {url, content, title, status_code, content_length}.
    """
    _validate_url(url)

    key = _cache_key("fetch", url, str(max_chars))
    cached = _get_cached(key)
    if cached is not None:
        logger.debug("web_fetch cache hit for: %s", url)
        return cached

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=15 if _IS_SERVERLESS else 30,
        follow_redirects=True,
        max_redirects=3,
    ) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    raw_body = resp.text

    # Extract readable content from HTML
    if "html" in content_type.lower():
        content = _extract_text_from_html(raw_body)
        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_body, re.S | re.I)
        title = title_match.group(1).strip() if title_match else ""
    else:
        content = raw_body
        title = ""

    # Truncate to max_chars
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n[Truncated at {max_chars} chars]"

    result = {
        "url": url,
        "title": title,
        "content": content,
        "status_code": resp.status_code,
        "content_length": len(content),
    }

    _set_cached(key, result)
    return result
