"""Sentiment Agent — uses LLM to analyze sentiment of news headlines."""

from __future__ import annotations

import logging
from typing import Any

from core.llm import llm_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior financial sentiment analyst at a top-tier investment bank. You will receive a stock symbol and a set of recent news articles with titles, descriptions, and sources.

Perform a rigorous multi-dimensional sentiment analysis and return a JSON object:
{
  "sentiment": "strongly_positive" | "positive" | "neutral" | "negative" | "strongly_negative" | "mixed",
  "confidence": 0.0 to 1.0,
  "impact_level": "critical" | "high" | "medium" | "low" | "negligible",
  "key_themes": ["theme1", "theme2", "theme3"],
  "catalysts": ["upcoming event or catalyst that could move the stock"],
  "media_tone": "bullish" | "bearish" | "cautious" | "neutral" | "speculative",
  "reasoning": "2-3 sentences explaining sentiment drivers and potential market impact with specific references to articles"
}

RULES:
- Distinguish between company-specific news and general market/sector news.
- Weight articles by recency and source credibility (Reuters, Bloomberg, WSJ > blogs).
- Look for catalysts: earnings, FDA approvals, lawsuits, insider activity, analyst upgrades/downgrades.
- "critical" impact = earnings miss/beat, M&A, regulatory action, CEO departure.
- "high" impact = analyst rating changes, product launches, competitive threats.
- Reference specific article titles in your reasoning.
- If articles are contradictory, set sentiment to "mixed" and explain both sides."""


class SentimentAgent:
    """Evaluates news sentiment via LLM reasoning."""

    name = "SentimentAgent"

    async def analyze(self, symbol: str, news_data: dict[str, Any]) -> dict[str, Any]:
        logger.info("[%s] Analyzing sentiment for %s", self.name, symbol)

        headlines = news_data.get("headlines_summary", "No news available.")
        articles = news_data.get("articles", [])
        articles_text = ""
        for i, a in enumerate(articles[:10], 1):
            src = a.get('source', 'Unknown')
            date = a.get('published', '')[:10]
            articles_text += f"{i}. [{src} | {date}] {a.get('title', 'N/A')}\n   {a.get('description', 'No description')}\n\n"

        if not articles_text.strip():
            return {
                "symbol": symbol,
                "sentiment": "neutral",
                "confidence": 0.3,
                "impact_level": "negligible",
                "key_themes": [],
                "catalysts": [],
                "media_tone": "neutral",
                "reasoning": "No recent news available for analysis.",
            }

        user_prompt = f"""Stock: {symbol}
Total articles found: {news_data.get('article_count', len(articles))}

=== NEWS ARTICLES ===
{articles_text}
=== HEADLINES SUMMARY ===
{headlines}

Analyze the overall news sentiment, identify catalysts, and assess potential market impact."""

        try:
            result = await llm_json(SYSTEM_PROMPT, user_prompt)
            result["symbol"] = symbol
            return result
        except Exception as exc:
            logger.error("[%s] LLM sentiment analysis failed: %s", self.name, exc)
            return {
                "symbol": symbol,
                "sentiment": "neutral",
                "confidence": 0.0,
                "impact_level": "low",
                "key_themes": [],
                "reasoning": f"Analysis failed: {exc}",
                "error": str(exc),
            }
