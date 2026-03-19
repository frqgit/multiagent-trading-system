"""News Analyst Agent — fetches and summarizes relevant news."""

from __future__ import annotations

import logging
from typing import Any

from tools.news_api import fetch_news, TICKER_TO_SEARCH

logger = logging.getLogger(__name__)


class NewsAnalystAgent:
    """Fetches recent news articles and prepares them for sentiment analysis."""

    name = "NewsAnalystAgent"

    async def analyze(self, symbol: str) -> dict[str, Any]:
        logger.info("[%s] Fetching news for %s", self.name, symbol)
        # Pass the raw symbol — news_api.py handles the smart query mapping
        try:
            articles = await fetch_news(symbol, days_back=7, max_articles=12)
        except Exception as exc:
            logger.error("[%s] News fetch failed: %s", self.name, exc)
            return {"symbol": symbol, "articles": [], "error": str(exc)}

        formatted = []
        for a in articles:
            formatted.append({
                "title": a.title,
                "source": a.source,
                "description": a.description[:500],
                "published_at": a.published_at,
                "url": a.url,
            })

        headlines = " | ".join(a.title for a in articles) if articles else "No recent news found."

        return {
            "symbol": symbol.upper(),
            "article_count": len(formatted),
            "articles": formatted,
            "headlines_summary": headlines,
        }
