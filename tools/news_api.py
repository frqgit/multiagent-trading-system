"""News fetcher using NewsAPI with smart query building."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)

NEWS_API_EVERYTHING = "https://newsapi.org/v2/everything"
NEWS_API_HEADLINES = "https://newsapi.org/v2/top-headlines"

# Better mapping: ticker → (company name, extra search terms)
TICKER_TO_SEARCH: dict[str, tuple[str, str]] = {
    "AAPL": ("Apple", "Apple Inc OR AAPL stock"),
    "MSFT": ("Microsoft", "Microsoft OR MSFT stock"),
    "GOOGL": ("Alphabet Google", "Google OR Alphabet OR GOOGL stock"),
    "GOOG": ("Alphabet Google", "Google OR Alphabet OR GOOG stock"),
    "AMZN": ("Amazon", "Amazon OR AMZN stock"),
    "TSLA": ("Tesla", "Tesla OR TSLA stock OR Elon Musk Tesla"),
    "NVDA": ("NVIDIA", "NVIDIA OR NVDA stock OR AI chips"),
    "META": ("Meta Platforms", "Meta OR Facebook OR META stock"),
    "NFLX": ("Netflix", "Netflix OR NFLX stock"),
    "JPM": ("JPMorgan Chase", "JPMorgan OR JPM stock"),
    "V": ("Visa Inc", "Visa stock OR payment"),
    "BRK.B": ("Berkshire Hathaway", "Berkshire Hathaway OR Warren Buffett"),
    "JNJ": ("Johnson & Johnson", "Johnson Johnson OR JNJ stock"),
    "WMT": ("Walmart", "Walmart OR WMT stock"),
    "PG": ("Procter Gamble", "Procter Gamble OR PG stock"),
    "DIS": ("Walt Disney", "Disney OR DIS stock"),
    "AMD": ("AMD", "AMD stock OR Advanced Micro Devices"),
    "INTC": ("Intel", "Intel stock OR INTC"),
    "CRM": ("Salesforce", "Salesforce OR CRM stock"),
    "COIN": ("Coinbase", "Coinbase OR COIN stock OR crypto"),
}


@dataclass
class NewsArticle:
    title: str
    source: str
    url: str
    published_at: str
    description: str

    def to_dict(self) -> dict:
        return self.__dict__


async def fetch_news(query: str, days_back: int = 7, max_articles: int = 12) -> list[NewsArticle]:
    """Fetch recent news articles. Uses stock-specific queries for better relevance."""
    settings = get_settings()
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Build an optimized search query
    ticker_upper = query.upper().strip()
    if ticker_upper in TICKER_TO_SEARCH:
        _, search_query = TICKER_TO_SEARCH[ticker_upper]
    else:
        # Generic ticker: search for "SYMBOL stock"
        search_query = f'"{query}" stock'

    params = {
        "q": search_query,
        "from": from_date,
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "language": "en",
        "apiKey": settings.news_api_key,
    }

    articles: list[NewsArticle] = []

    async with httpx.AsyncClient(timeout=20) as client:
        # Primary: /everything endpoint
        try:
            resp = await client.get(NEWS_API_EVERYTHING, params=params)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("articles", []):
                title = item.get("title") or ""
                if title and title != "[Removed]":
                    articles.append(
                        NewsArticle(
                            title=title,
                            source=item.get("source", {}).get("name", "Unknown"),
                            url=item.get("url", ""),
                            published_at=item.get("publishedAt", ""),
                            description=(item.get("description") or "")[:500],
                        )
                    )
        except Exception as exc:
            logger.warning("NewsAPI /everything failed for '%s': %s", query, exc)

        # Fallback: if few results, try /top-headlines for business
        if len(articles) < 3:
            try:
                hl_params = {
                    "q": TICKER_TO_SEARCH.get(ticker_upper, (query, query))[0].split()[0],
                    "category": "business",
                    "pageSize": 5,
                    "language": "en",
                    "apiKey": settings.news_api_key,
                }
                resp2 = await client.get(NEWS_API_HEADLINES, params=hl_params)
                resp2.raise_for_status()
                data2 = resp2.json()
                existing_titles = {a.title for a in articles}
                for item in data2.get("articles", []):
                    title = item.get("title") or ""
                    if title and title != "[Removed]" and title not in existing_titles:
                        articles.append(
                            NewsArticle(
                                title=title,
                                source=item.get("source", {}).get("name", "Unknown"),
                                url=item.get("url", ""),
                                published_at=item.get("publishedAt", ""),
                                description=(item.get("description") or "")[:500],
                            )
                        )
            except Exception as exc:
                logger.warning("NewsAPI /top-headlines fallback failed: %s", exc)

    logger.info("Fetched %d news articles for '%s'", len(articles), query)
    return articles
