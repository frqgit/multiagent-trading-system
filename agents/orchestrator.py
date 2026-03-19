"""Orchestrator Agent — coordinates all sub-agents and aggregates results.

Supports OpenClaw-style natural language: the LLM-based router understands
any financial query (quick status, deep analysis, comparisons, general
questions) and dispatches to the appropriate pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from agents.market_agent import MarketAnalystAgent
from agents.news_agent import NewsAnalystAgent
from agents.sentiment_agent import SentimentAgent
from agents.risk_agent import RiskManagerAgent
from agents.decision_agent import DecisionAgent
from agents.research_agent import ResearchAgent
from core.llm import llm_json, llm_chat, start_tracking
from tools.web_tools import web_search, web_fetch

logger = logging.getLogger(__name__)

# ── LLM prompt for intent classification ──────────────────────────────────
_ROUTER_SYSTEM = """You are a financial query router. Given a user message, classify it and extract relevant info.

Return JSON:
{
  "intent": "quick_status" | "full_analysis" | "general_question" | "comparison" | "news_query",
  "symbols": ["AAPL"],
  "query": "the original question rephrased for clarity",
  "exchange_hint": "ASX" | "NYSE" | "NASDAQ" | "LSE" | "" 
}

RULES:
- "quick_status": user wants current price / status / quick overview of a stock.
- "full_analysis": user explicitly asks for deep analysis, BUY/SELL recommendation, or technical analysis.
- "general_question": question about markets, sectors, economy, strategies — no specific stock required.
- "comparison": user wants to compare two or more stocks.
- "news_query": user wants latest news about a stock or topic.
- Extract ALL stock ticker symbols mentioned or implied. Map company names to tickers:
  "Commonwealth Bank" or "CBA" → "CBA.AX" (ASX)
  "Apple" → "AAPL", "Microsoft" → "MSFT", "Google" → "GOOGL", "Tesla" → "TSLA"
  "Amazon" → "AMZN", "NVIDIA" → "NVDA", "Meta" → "META"
  "BHP" → "BHP.AX", "Westpac" → "WBC.AX", "ANZ" → "ANZ.AX", "NAB" → "NAB.AX"
  "Samsung" → "005930.KS", "Toyota" → "7203.T" or "TM"
  "Reliance" → "RELIANCE.NS", "Tata" → "TCS.NS"
  For Australian stocks, append ".AX". For other non-US stocks, use the appropriate Yahoo Finance suffix.
- If the user mentions a company name, resolve it to its ticker.
- If user says "analyze" or "should I buy/sell", use "full_analysis".
- If user says "price", "status", "how is", "what is", "current", "quote" — use "quick_status".
- exchange_hint: if the stock is on a specific exchange (e.g. ASX, LSE), include it.
- NEVER leave symbols empty if the user mentions ANY stock or company."""

# ── Prompt for general financial Q&A ──────────────────────────────────────
_QA_SYSTEM = """You are a senior financial analyst assistant. Answer the user's financial question using the provided web research data.

RULES:
- Be specific, cite numbers and sources where possible.
- If data is insufficient, say so honestly.
- Keep answers concise but comprehensive (3-8 paragraphs).
- Format with markdown for readability.
- Do NOT make up data. Use only what is provided."""


class OrchestratorAgent:
    """
    Central coordinator that:
    1. Uses LLM to understand any natural language query (intent + symbols)
    2. Routes to the appropriate handler (quick status, full analysis, Q&A, etc.)
    3. Returns a flexible response with both text and structured data
    """

    name = "OrchestratorAgent"

    def __init__(self) -> None:
        self.market_agent = MarketAnalystAgent()
        self.news_agent = NewsAnalystAgent()
        self.sentiment_agent = SentimentAgent()
        self.risk_agent = RiskManagerAgent()
        self.decision_agent = DecisionAgent()
        self.research_agent = ResearchAgent()

    # ── Public entry point ────────────────────────────────────────────────
    async def chat(self, user_message: str) -> dict[str, Any]:
        """OpenClaw-style: understand any query and respond appropriately."""
        start = time.monotonic()
        usage = start_tracking()
        logger.info("[%s] Received query: %s", self.name, user_message[:120])

        # Step 1: LLM-based intent classification
        try:
            parsed = await llm_json(_ROUTER_SYSTEM, user_message)
        except Exception as exc:
            logger.error("[%s] Router LLM failed: %s", self.name, exc)
            parsed = {"intent": "general_question", "symbols": [], "query": user_message}

        intent = parsed.get("intent", "general_question")
        symbols = parsed.get("symbols", [])
        query = parsed.get("query", user_message)

        logger.info("[%s] Routed → intent=%s, symbols=%s", self.name, intent, symbols)

        # Step 2: Dispatch to the right handler
        if intent == "quick_status" and symbols:
            result = await self._handle_quick_status(symbols, query)
        elif intent == "full_analysis" and symbols:
            result = await self._handle_full_analysis(symbols)
        elif intent == "comparison" and len(symbols) >= 2:
            result = await self._handle_comparison(symbols, query)
        elif intent == "news_query" and symbols:
            result = await self._handle_news_query(symbols, query)
        elif symbols:
            # Has symbols but ambiguous intent → quick status
            result = await self._handle_quick_status(symbols, query)
        else:
            # No symbols → general financial Q&A with web search
            result = await self._handle_general_question(query)

        result["elapsed_seconds"] = round(time.monotonic() - start, 2)
        result["intent"] = intent
        result["parsed_symbols"] = symbols
        result["token_usage"] = usage.to_dict()
        return result

    # ── Quick status (fast, just market data + brief LLM summary) ─────────
    async def _handle_quick_status(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Fetch market data and produce a concise natural language answer."""
        market_results = await asyncio.gather(
            *[self.market_agent.analyze(s) for s in symbols]
        )

        # Build context for LLM summary
        data_text = ""
        structured = []
        for md in market_results:
            if "error" in md and "price" not in md:
                data_text += f"\n{md.get('symbol', '?')}: ERROR — {md.get('error')}"
                structured.append(md)
                continue
            sym = md.get("symbol", "?")
            data_text += f"""
{sym} ({md.get('company_name', sym)}) — {md.get('sector', 'N/A')}
  Price: ${md.get('price')} | Change: {md.get('price_change_pct', 0):+.2f}%
  Day Range: ${md.get('day_low')} – ${md.get('day_high')}
  52-Wk Range: ${md.get('week52_low')} – ${md.get('week52_high')}
  Volume: {md.get('volume_formatted', 'N/A')} (Avg: {md.get('avg_volume', 'N/A')})
  Market Cap: {md.get('market_cap_formatted', 'N/A')}
  P/E: {md.get('pe_ratio', 'N/A')} | EPS: {md.get('eps', 'N/A')} | Beta: {md.get('beta', 'N/A')}
  RSI: {md.get('rsi', 'N/A')} | Trend: {md.get('trend', 'N/A')}
  MA20: {md.get('ma20', 'N/A')} | MA50: {md.get('ma50', 'N/A')}
  MACD: {md.get('macd', 'N/A')} | Signal: {md.get('macd_signal', 'N/A')}
  Signals: {', '.join(md.get('signals', []))}
"""
            structured.append(md)

        summary_prompt = f"""User asked: "{query}"

Here is the real-time market data:
{data_text}

Give a clear, concise answer to the user's question. Include key numbers (price, change, volume, RSI, trend). Format with markdown. Be direct and conversational."""

        try:
            answer = await llm_chat(
                "You are a helpful financial assistant. Answer questions about stocks using the provided real-time data. Be concise, specific, and format with markdown.",
                summary_prompt,
                max_tokens=1024,
            )
        except Exception as exc:
            logger.error("[%s] Summary LLM failed: %s", self.name, exc)
            # Fallback: produce a plain-text summary
            parts = []
            for md in market_results:
                if "price" in md:
                    parts.append(
                        f"**{md['symbol']}** ({md.get('company_name', '')}): "
                        f"${md['price']} ({md.get('price_change_pct', 0):+.2f}%) — "
                        f"RSI {md.get('rsi', 'N/A')}, Trend: {md.get('trend', 'N/A')}"
                    )
            answer = "\n".join(parts) or f"Error generating summary: {exc}"

        return {
            "type": "quick_status",
            "answer": answer,
            "market_data": structured,
            "symbols": symbols,
        }

    # ── Full analysis (existing heavy pipeline) ───────────────────────────
    async def _handle_full_analysis(self, symbols: list[str]) -> dict[str, Any]:
        """Run the complete multi-agent analysis pipeline."""
        results = await self.analyze_multiple(symbols)

        # Build a summary
        summaries = []
        for r in results:
            d = r.get("decision", {})
            summaries.append(
                f"**{r.get('symbol', '?')}**: {d.get('action', 'HOLD')} "
                f"(confidence {d.get('confidence', 0):.0%})"
            )

        return {
            "type": "full_analysis",
            "answer": "## Analysis Complete\n\n" + " | ".join(summaries),
            "analyses": results,
            "symbols": [r.get("symbol", "") for r in results],
        }

    # ── Comparison ────────────────────────────────────────────────────────
    async def _handle_comparison(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Fetch market data for multiple stocks and compare them."""
        market_results = await asyncio.gather(
            *[self.market_agent.analyze(s) for s in symbols]
        )

        # Build comparison table for LLM
        comp_text = ""
        for md in market_results:
            if "error" in md and "price" not in md:
                comp_text += f"\n{md.get('symbol')}: Data unavailable\n"
                continue
            comp_text += f"""
{md.get('symbol')} ({md.get('company_name', '?')}):
  Price: ${md.get('price')} | Change: {md.get('price_change_pct', 0):+.2f}%
  Market Cap: {md.get('market_cap_formatted', 'N/A')} | P/E: {md.get('pe_ratio', 'N/A')}
  RSI: {md.get('rsi', 'N/A')} | Trend: {md.get('trend', 'N/A')} | Beta: {md.get('beta', 'N/A')}
  52-Wk Range: ${md.get('week52_low')} – ${md.get('week52_high')}
  Volatility: {md.get('volatility', 'N/A')}% | Dividend Yield: {md.get('dividend_yield', 'N/A')}
"""

        try:
            answer = await llm_chat(
                "You are a financial analyst. Compare stocks using the provided data. Use markdown tables where helpful. Be specific with numbers.",
                f'User asked: "{query}"\n\nMarket Data:\n{comp_text}\n\nProvide a clear comparison addressing the user\'s question.',
                max_tokens=1500,
            )
        except Exception as exc:
            answer = f"Comparison data fetched but summary failed: {exc}"

        return {
            "type": "comparison",
            "answer": answer,
            "market_data": market_results,
            "symbols": symbols,
        }

    # ── News query ────────────────────────────────────────────────────────
    async def _handle_news_query(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Fetch news and summarize for the user."""
        news_results = await asyncio.gather(
            *[self.news_agent.analyze(s) for s in symbols]
        )

        all_articles = []
        news_text = ""
        for nd in news_results:
            for a in nd.get("articles", [])[:8]:
                all_articles.append(a)
                news_text += f"- [{a.get('source', '?')}] {a.get('title', 'N/A')}\n  {a.get('description', '')[:200]}\n\n"

        try:
            answer = await llm_chat(
                "You are a financial news analyst. Summarize the latest news for the user. Highlight key developments and potential market impact. Use markdown.",
                f'User asked: "{query}"\n\nLatest News:\n{news_text or "No recent news found."}',
                max_tokens=1200,
            )
        except Exception as exc:
            answer = f"News fetched but summary failed: {exc}"

        return {
            "type": "news_query",
            "answer": answer,
            "articles": all_articles,
            "symbols": symbols,
        }

    # ── General financial Q&A (web search + LLM) ─────────────────────────
    async def _handle_general_question(self, query: str) -> dict[str, Any]:
        """Answer general financial questions using web search."""
        import os
        is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

        # Search the web (fewer results on serverless to stay within timeout)
        try:
            search_results = await asyncio.wait_for(
                web_search(query, max_results=3 if is_serverless else 5),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.warning("[%s] Web search timed out for: %s", self.name, query)
            search_results = []
        except Exception as exc:
            logger.warning("[%s] Web search failed: %s", self.name, exc)
            search_results = []

        # Fetch top results for deeper context (fewer on serverless)
        fetched_content = ""
        if search_results:
            max_fetches = 1 if is_serverless else 3
            fetch_tasks = []
            for r in search_results[:max_fetches]:
                url = r.get("url", "")
                if url:
                    fetch_tasks.append(web_fetch(url, max_chars=4000 if is_serverless else 8000))
            if fetch_tasks:
                try:
                    pages = await asyncio.wait_for(
                        asyncio.gather(*fetch_tasks, return_exceptions=True),
                        timeout=8.0,
                    )
                except asyncio.TimeoutError:
                    logger.warning("[%s] Web fetch timed out", self.name)
                    pages = []
                for page in pages:
                    if isinstance(page, dict) and "content" in page:
                        fetched_content += f"\n--- Source: {page.get('url', '?')} ---\n"
                        fetched_content += page["content"][:6000] + "\n"

        # Build context
        search_text = ""
        for r in search_results:
            search_text += f"- {r.get('title', 'N/A')}: {r.get('snippet', '')}\n  URL: {r.get('url', '')}\n"

        context = f"""Search Results:
{search_text}

Fetched Page Content:
{fetched_content[:15000] if fetched_content else 'No pages fetched.'}"""

        try:
            answer = await llm_chat(
                _QA_SYSTEM,
                f'User question: "{query}"\n\nWeb Research:\n{context}',
                max_tokens=1500 if is_serverless else 2048,
            )
        except Exception as exc:
            logger.error("[%s] LLM Q&A failed: %s (%s)", self.name, exc, type(exc).__name__)
            # Fallback: try a simpler LLM call without web context
            try:
                answer = await llm_chat(
                    "You are a helpful financial assistant. Answer concisely using your knowledge.",
                    f'User question: "{query}"',
                    max_tokens=800,
                )
            except Exception as fallback_exc:
                logger.error("[%s] LLM fallback also failed: %s", self.name, fallback_exc)
                if search_results:
                    # At least return the search snippets
                    answer = "**I found some results but couldn't generate a summary:**\n\n"
                    for r in search_results[:3]:
                        answer += f"- [{r.get('title', 'N/A')}]({r.get('url', '')})\n  {r.get('snippet', '')}\n\n"
                else:
                    answer = f"Sorry, I'm unable to process this request right now. Please try again in a moment. (Error: {fallback_exc})"

        return {
            "type": "general_question",
            "answer": answer,
            "search_results": search_results,
            "symbols": [],
        }

    # ── Existing pipeline methods (unchanged) ─────────────────────────────
    async def analyze_symbol(self, symbol: str) -> dict[str, Any]:
        """Full pipeline analysis for a single symbol."""
        start = time.monotonic()
        symbol = symbol.upper().strip()
        logger.info("[%s] Starting analysis pipeline for %s", self.name, symbol)

        # Phase 1: Market data + News + Web Research in parallel
        market_task = asyncio.create_task(self.market_agent.analyze(symbol))
        news_task = asyncio.create_task(self.news_agent.analyze(symbol))
        research_task = asyncio.create_task(self.research_agent.analyze(symbol))
        market_data, news_data, research_data = await asyncio.gather(
            market_task, news_task, research_task
        )

        if "error" in market_data and "price" not in market_data:
            return {
                "symbol": symbol,
                "error": f"Failed to fetch market data: {market_data['error']}",
                "elapsed_seconds": round(time.monotonic() - start, 2),
            }

        # Phase 2: Sentiment analysis (depends on news)
        sentiment_data = await self.sentiment_agent.analyze(symbol, news_data)

        # Phase 3: Risk assessment (depends on market + sentiment)
        risk_data = await self.risk_agent.analyze(market_data, sentiment_data)

        # Phase 4: Final decision (depends on all — including web research)
        decision = await self.decision_agent.decide(symbol, market_data, sentiment_data, risk_data, research_data)

        elapsed = round(time.monotonic() - start, 2)
        logger.info("[%s] Pipeline complete for %s in %.2fs", self.name, symbol, elapsed)

        return {
            "symbol": symbol,
            "decision": decision,
            "market_data": market_data,
            "news": news_data,
            "sentiment": sentiment_data,
            "risk": risk_data,
            "research": research_data,
            "elapsed_seconds": elapsed,
        }

    async def analyze_multiple(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Run analysis for multiple symbols concurrently."""
        tasks = [self.analyze_symbol(s) for s in symbols]
        return await asyncio.gather(*tasks)

    @staticmethod
    def parse_symbols(user_input: str) -> list[str]:
        """Extract stock symbols from user text (legacy regex fallback)."""
        import re
        raw = re.findall(r"\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b", user_input.upper())
        stop_words = {
            "I", "A", "THE", "AND", "OR", "IS", "IT", "IN", "ON", "AT", "TO",
            "FOR", "OF", "DO", "MY", "ME", "IF", "SO", "UP", "BY", "AN", "AS",
            "BE", "NO", "AM", "WE", "HE", "OK", "CAN", "ALL", "BUT", "HOW",
            "BUY", "SELL", "HOLD", "WHAT", "ABOUT", "SHOULD", "STOCK", "ANALYZE",
            "THINK", "TELL", "GIVE", "WITH", "THIS", "THAT", "LOOK", "INTO",
            "FIND", "CURRENT", "STATUS", "GET", "SHOW", "CHECK", "PRICE",
            "NEWS", "COMPARE", "VS", "MARKET", "TODAY", "NOW", "LATEST",
        }
        return [s for s in dict.fromkeys(raw) if s not in stop_words]
