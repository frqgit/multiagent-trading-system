"""Research Agent — gathers web intelligence using web_search & web_fetch.

Runs in parallel with Market + News agents to add a web research dimension:
analyst ratings, earnings data, SEC filings, and competitive outlook.
Then uses LLM to synthesize findings into structured research insights.
"""

from __future__ import annotations

import logging
from typing import Any

from core.llm import llm_json
from tools.web_financial import research_stock_web

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior equity research analyst. You will receive raw web research data about a stock — search results, page extracts, and financial data.

Synthesize the data into a structured JSON research brief:
{
  "analyst_consensus": "buy" | "hold" | "sell" | "strong_buy" | "strong_sell" | "unknown",
  "average_price_target": <number or null>,
  "price_target_range": {"low": <number or null>, "high": <number or null>},
  "recent_earnings_surprise": "beat" | "miss" | "inline" | "unknown",
  "revenue_trend": "growing" | "declining" | "stable" | "unknown",
  "key_developments": ["development1", "development2", "development3"],
  "competitive_position": "strong" | "moderate" | "weak" | "unknown",
  "insider_activity": "buying" | "selling" | "mixed" | "unknown",
  "risks_from_research": ["risk1", "risk2"],
  "opportunities_from_research": ["opportunity1", "opportunity2"],
  "research_summary": "2-3 sentence summary of the most important findings from web research"
}

RULES:
- Only include data you can actually find in the provided research. Use "unknown" / null when data is absent.
- Extract specific numbers (price targets, revenue figures) when mentioned in the text.
- Focus on the most recent and material information.
- Be concise but specific. Reference actual sources when possible.
- Do NOT make up numbers or ratings that aren't in the research data."""


class ResearchAgent:
    """Gathers and synthesizes web research for deeper stock analysis."""

    name = "ResearchAgent"

    async def analyze(self, symbol: str) -> dict[str, Any]:
        """Run web research and LLM synthesis for a symbol."""
        logger.info("[%s] Starting web research for %s", self.name, symbol)

        try:
            raw_research = await research_stock_web(symbol)
        except Exception as exc:
            logger.error("[%s] Web research failed for %s: %s", self.name, symbol, exc)
            return self._empty_result(symbol, f"Web research failed: {exc}")

        summary = raw_research.get("summary", "")
        if not summary or summary == "No web research data gathered.":
            logger.warning("[%s] No web research data for %s", self.name, symbol)
            return self._empty_result(symbol, "No web research data available")

        # Truncate to stay within LLM context limits
        if len(summary) > 12000:
            summary = summary[:12000] + "\n[...truncated]"

        user_prompt = f"""Stock: {symbol}

=== WEB RESEARCH DATA ===
{summary}

Synthesize the above into a structured research brief."""

        try:
            result = await llm_json(SYSTEM_PROMPT, user_prompt)
            result["symbol"] = symbol
            result["sources_searched"] = sum(
                len(v) for v in raw_research.get("search_results", {}).values()
            )
            result["pages_analyzed"] = sum(
                len(v) for v in raw_research.get("page_extracts", {}).values()
            )
            return result
        except Exception as exc:
            logger.error("[%s] LLM synthesis failed for %s: %s", self.name, symbol, exc)
            return self._empty_result(symbol, f"LLM synthesis failed: {exc}")

    @staticmethod
    def _empty_result(symbol: str, reason: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "analyst_consensus": "unknown",
            "average_price_target": None,
            "price_target_range": {"low": None, "high": None},
            "recent_earnings_surprise": "unknown",
            "revenue_trend": "unknown",
            "key_developments": [],
            "competitive_position": "unknown",
            "insider_activity": "unknown",
            "risks_from_research": [],
            "opportunities_from_research": [],
            "research_summary": reason,
            "sources_searched": 0,
            "pages_analyzed": 0,
        }
