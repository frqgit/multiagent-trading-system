"""Financial web research tools — specialized web crawling for stock analysis.

Uses web_search and web_fetch to gather:
- Analyst ratings & price targets
- Earnings data & revenue forecasts
- Company outlook & competitive analysis
- SEC filings highlights
- Social / forum sentiment
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from tools.web_tools import web_search, web_fetch

logger = logging.getLogger(__name__)

# Key financial sources to fetch for deep research
_FINANCE_URLS: dict[str, str] = {
    "yahoo_finance": "https://finance.yahoo.com/quote/{symbol}",
    "marketwatch": "https://www.marketwatch.com/investing/stock/{symbol_lower}",
    "stockanalysis": "https://stockanalysis.com/stocks/{symbol_lower}/",
}


async def research_stock_web(symbol: str) -> dict[str, Any]:
    """Run comprehensive web research for a stock symbol.

    Performs parallel web searches on:
    1. Analyst ratings & price targets
    2. Recent earnings / financials
    3. Sector outlook & competitive position
    Then fetches the top results for deeper extraction.

    Returns structured dict with research findings.
    """
    symbol_upper = symbol.upper()
    logger.info("Starting web research for %s", symbol_upper)

    # --- Phase 1: sequential web searches (avoid DDG rate limit) ---
    search_queries = [
        (f"{symbol_upper} stock analyst rating price target 2026", "analyst_ratings"),
        (f"{symbol_upper} earnings revenue quarterly results", "earnings"),
        (f"{symbol_upper} stock forecast outlook analysis", "outlook"),
        (f"{symbol_upper} SEC filing insider trading", "sec_filings"),
    ]

    categorized: dict[str, list[dict]] = {}
    all_urls: list[tuple[str, str]] = []  # (url, category)
    for i, (query, category) in enumerate(search_queries):
        if i > 0:
            await asyncio.sleep(2.0)  # Delay between searches to avoid rate limits
        try:
            result = await web_search(query, max_results=3, freshness="month")
        except Exception as exc:
            logger.warning("Search failed for '%s': %s", query, exc)
            result = []
        categorized[category] = result
        for item in result[:2]:  # Top 2 URLs per category for fetching
            url = item.get("url", "")
            if url:
                all_urls.append((url, category))

    # --- Phase 2: fetch top pages for deeper content ---
    fetch_tasks = [
        web_fetch(url, max_chars=8000)
        for url, _ in all_urls[:6]  # Cap at 6 pages to limit latency
    ]
    fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    page_contents: dict[str, list[dict]] = {
        "analyst_ratings": [],
        "earnings": [],
        "outlook": [],
        "sec_filings": [],
    }

    for (url, category), result in zip(all_urls[:6], fetch_results):
        if isinstance(result, Exception):
            logger.warning("Fetch failed for %s: %s", url, result)
            continue
        page_contents[category].append({
            "url": url,
            "title": result.get("title", ""),
            "excerpt": result.get("content", "")[:3000],
        })

    # --- Phase 3: Also try to fetch a financial data page directly ---
    direct_pages = await _fetch_financial_pages(symbol_upper)

    # --- Build structured research output ---
    research = {
        "symbol": symbol_upper,
        "search_results": {
            category: [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")}
                for r in results
            ]
            for category, results in categorized.items()
        },
        "page_extracts": {
            category: [
                {"title": p["title"], "url": p["url"], "excerpt": p["excerpt"][:2000]}
                for p in pages
            ]
            for category, pages in page_contents.items()
        },
        "direct_pages": direct_pages,
        "summary": _build_summary(categorized, page_contents),
    }

    logger.info("Web research complete for %s: %d search results, %d pages fetched",
                symbol_upper,
                sum(len(v) for v in categorized.values()),
                sum(len(v) for v in page_contents.values()))

    return research


async def _fetch_financial_pages(symbol: str) -> dict[str, str]:
    """Attempt to fetch key financial data pages directly."""
    pages: dict[str, str] = {}
    sym_lower = symbol.lower()

    urls_to_try = [
        ("stockanalysis", f"https://stockanalysis.com/stocks/{sym_lower}/"),
    ]

    for name, url in urls_to_try:
        try:
            result = await web_fetch(url, max_chars=10000)
            pages[name] = result.get("content", "")[:5000]
        except Exception as exc:
            logger.debug("Direct fetch failed for %s (%s): %s", name, url, exc)
            pages[name] = ""

    return pages


def _build_summary(
    search_results: dict[str, list[dict]],
    page_contents: dict[str, list[dict]],
) -> str:
    """Build a text summary of all research findings for LLM consumption."""
    parts: list[str] = []

    for category, results in search_results.items():
        if not results:
            continue
        label = category.replace("_", " ").title()
        parts.append(f"--- {label} ---")
        for r in results:
            snippet = r.get("snippet", "")
            title = r.get("title", "")
            if snippet:
                parts.append(f"• {title}: {snippet}")
            elif title:
                parts.append(f"• {title}")
        parts.append("")

    for category, pages in page_contents.items():
        for p in pages:
            excerpt = p.get("excerpt", "").strip()
            if excerpt and len(excerpt) > 100:
                label = category.replace("_", " ").title()
                parts.append(f"[{label} — {p.get('title', 'Page')}]")
                parts.append(excerpt[:2000])
                parts.append("")

    return "\n".join(parts) if parts else "No web research data gathered."
