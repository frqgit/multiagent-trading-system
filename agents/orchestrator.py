"""Orchestrator Agent — coordinates all sub-agents and aggregates results.

Supports OpenClaw-style natural language: the LLM-based router understands
any financial query (quick status, deep analysis, comparisons, general
questions) and dispatches to the appropriate pipeline.

Enhanced with:
- Portfolio optimization
- Backtesting
- Volatility modeling
- Technical strategy analysis
- Correlation analysis
- Adaptive learning
- Paper trading execution
- **Live multi-broker execution** (IBKR, CommSec, IG Markets, CMC Markets, SelfWealth)
- Enterprise risk engine with circuit breakers and kill switch
- ASIC/ASX compliance monitoring
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TYPE_CHECKING

from agents.market_agent import MarketAnalystAgent
from agents.news_agent import NewsAnalystAgent
from agents.sentiment_agent import SentimentAgent
from agents.risk_agent import RiskManagerAgent
from agents.decision_agent import DecisionAgent
from agents.research_agent import ResearchAgent
from agents.global_market_agent import GlobalMarketAdvisorAgent
from agents.ml_agent import MLPredictionAgent
from agents.strategy_builder import StrategyBuilderAgent
from core.llm import llm_json, llm_chat, start_tracking
from tools.web_tools import web_search, web_fetch

# Lazy imports for advanced agents (require scipy)
# These are imported on first use to avoid breaking basic endpoints
_ADVANCED_AGENTS_AVAILABLE = False
PortfolioOptimizationAgent = None
BacktestingAgent = None
VolatilityModelingAgent = None
TechnicalStrategyAgent = None
CorrelationAnalysisAgent = None
AdaptiveLearningAgent = None
ExecutionAgent = None

# Live trading imports (loaded separately — no scipy dependency)
_LIVE_TRADING_AVAILABLE = False
LiveExecutionAgent = None

def _load_live_trading():
    """Load live execution agent and supporting modules."""
    global _LIVE_TRADING_AVAILABLE, LiveExecutionAgent
    if _LIVE_TRADING_AVAILABLE:
        return True
    try:
        from agents.live_execution_agent import LiveExecutionAgent as _Live
        LiveExecutionAgent = _Live
        _LIVE_TRADING_AVAILABLE = True
        logger.info("Live trading agent loaded successfully")
        return True
    except ImportError as e:
        logger.warning("Live trading agent unavailable: %s", e)
        return False

def _load_advanced_agents():
    """Lazy load advanced agents that require scipy."""
    global _ADVANCED_AGENTS_AVAILABLE
    global PortfolioOptimizationAgent, BacktestingAgent, VolatilityModelingAgent
    global TechnicalStrategyAgent, CorrelationAnalysisAgent, AdaptiveLearningAgent, ExecutionAgent
    
    if _ADVANCED_AGENTS_AVAILABLE:
        return True
    
    try:
        from agents.portfolio_agent import PortfolioOptimizationAgent as _Portfolio
        from agents.backtest_agent import BacktestingAgent as _Backtest
        from agents.volatility_agent import VolatilityModelingAgent as _Volatility
        from agents.technical_strategy_agent import TechnicalStrategyAgent as _Technical
        from agents.correlation_agent import CorrelationAnalysisAgent as _Correlation
        from agents.adaptive_agent import AdaptiveLearningAgent as _Adaptive
        from agents.execution_agent import ExecutionAgent as _Execution
        
        PortfolioOptimizationAgent = _Portfolio
        BacktestingAgent = _Backtest
        VolatilityModelingAgent = _Volatility
        TechnicalStrategyAgent = _Technical
        CorrelationAnalysisAgent = _Correlation
        AdaptiveLearningAgent = _Adaptive
        ExecutionAgent = _Execution
        
        _ADVANCED_AGENTS_AVAILABLE = True
        logger.info("Advanced trading agents loaded successfully")
        return True
    except ImportError as e:
        logger.warning("Advanced agents unavailable (scipy not installed): %s", e)
        return False

logger = logging.getLogger(__name__)

# ── LLM prompt for intent classification ──────────────────────────────────
_ROUTER_SYSTEM = """You are a financial query router. Given a user message, classify it and extract relevant info.

Return JSON:
{
  "intent": "quick_status" | "full_analysis" | "general_question" | "comparison" | "news_query" | "global_outlook" | "portfolio_optimization" | "backtest" | "volatility_analysis" | "technical_analysis" | "correlation_analysis" | "execution" | "strategy_builder" | "ml_prediction" | "engine",
  "symbols": ["AAPL"],
  "query": "the original question rephrased for clarity",
  "exchange_hint": "ASX" | "NYSE" | "NASDAQ" | "LSE" | "" 
}

RULES:
- "quick_status": user wants current price / status / quick overview of a stock.
- "full_analysis": user explicitly asks for deep analysis, BUY/SELL recommendation.
- "general_question": question about markets, sectors, economy, strategies — no specific stock required.
- "comparison": user wants to compare two or more stocks.
- "news_query": user wants latest news about a stock or topic.
- "global_outlook": user asks about global markets, world economy, macro outlook, "what should I buy/sell", sector recommendations, or market conditions.
- "portfolio_optimization": user wants to optimize a portfolio, efficient frontier, risk parity, position sizing, rebalancing, or asset allocation.
- "backtest": user wants to backtest a strategy, test historical performance, run Monte Carlo simulation, or walk-forward analysis.
- "volatility_analysis": user asks about volatility, VIX, GARCH, volatility forecast, regime detection, or risk metrics.
- "technical_analysis": user wants technical analysis, chart patterns, indicators (RSI, MACD, Bollinger), Ichimoku, support/resistance, Fibonacci.
- "correlation_analysis": user asks about correlation, cointegration, pair trading, beta, or diversification analysis.
- "execution": user wants to place a trade, check portfolio, view positions, order status, or paper trade.
- "strategy_builder": user wants to create, test, or manage a custom trading strategy, build a strategy, strategy templates, or strategy performance.
- "ml_prediction": user wants ML prediction, machine learning forecast, AI prediction, or quantitative/data-driven prediction for a stock.
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
- If user says "global", "world market", "macro", "economy", "what should I buy", "market outlook", "sector rotation", "best stocks", "market conditions" — use "global_outlook".
- If user says "optimize", "allocation", "efficient frontier", "risk parity", "rebalance", "portfolio weights" — use "portfolio_optimization".
- If user says "backtest", "historical", "monte carlo", "walk forward", "test strategy", "performance test" — use "backtest".
- If user says "volatility", "GARCH", "VIX", "vol forecast", "regime" — use "volatility_analysis".
- If user says "technical", "chart", "pattern", "RSI", "MACD", "Bollinger", "Ichimoku", "support", "resistance", "Fibonacci" — use "technical_analysis".
- If user says "correlation", "cointegration", "pair trade", "beta", "diversification" — use "correlation_analysis".
- If user says "trade", "buy", "sell", "order", "portfolio", "position", "execute", "paper" — use "execution".
- If user says "strategy", "create strategy", "build strategy", "strategy template", "custom strategy", "strategy builder" — use "strategy_builder".
- If user says "ml predict", "machine learning", "ai prediction", "quantitative", "model prediction", "forecast model" — use "ml_prediction".
- If user says "engine", "run engine", "engine backtest", "engine signals", "golden cross", "rsi reversion", "macd crossover", "bollinger squeeze", "supertrend", "donchian breakout", "keltner", "adx trend", "ichimoku cloud strategy", "engine strategy", "built-in strategy" — use "engine".
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
    
    Enhanced capabilities:
    - Portfolio optimization with Markowitz, Black-Litterman, Risk Parity
    - Backtesting with walk-forward and Monte Carlo simulation
    - Volatility modeling with GARCH and regime detection
    - Technical analysis with multiple strategies and pattern recognition
    - Correlation analysis with pair trading signals
    - Adaptive learning with regime-based strategy selection
    - Paper trading execution with position management
    - **Live multi-broker execution** with risk-gated OMS
    """

    name = "OrchestratorAgent"

    def __init__(self) -> None:
        # Core agents (always available)
        self.market_agent = MarketAnalystAgent()
        self.news_agent = NewsAnalystAgent()
        self.sentiment_agent = SentimentAgent()
        self.risk_agent = RiskManagerAgent()
        self.decision_agent = DecisionAgent()
        self.research_agent = ResearchAgent()
        self.global_market_agent = GlobalMarketAdvisorAgent()
        self.ml_agent = MLPredictionAgent()
        self.strategy_builder = StrategyBuilderAgent()
        
        # Advanced agents (lazy-loaded, require scipy)
        self._advanced_loaded = False
        self.portfolio_agent = None
        self.backtest_agent = None
        self.volatility_agent = None
        self.technical_agent = None
        self.correlation_agent = None
        self.adaptive_agent = None
        self.execution_agent = None

        # Live trading agent (lazy-loaded, no scipy dependency)
        self._live_loaded = False
        self.live_execution_agent = None

        # Determine trading mode from config
        try:
            from core.config import get_settings
            settings = get_settings()
            self._trading_mode = getattr(settings, "trading_mode", "paper")
            self._auto_trading = getattr(settings, "auto_trading_enabled", False)
        except Exception:
            self._trading_mode = "paper"
            self._auto_trading = False
    
    def _ensure_advanced_agents(self) -> bool:
        """Lazy-load advanced agents on first use."""
        if self._advanced_loaded:
            return self.portfolio_agent is not None
        
        self._advanced_loaded = True
        if _load_advanced_agents():
            self.portfolio_agent = PortfolioOptimizationAgent()
            self.backtest_agent = BacktestingAgent()
            self.volatility_agent = VolatilityModelingAgent()
            self.technical_agent = TechnicalStrategyAgent()
            self.correlation_agent = CorrelationAnalysisAgent()
            self.adaptive_agent = AdaptiveLearningAgent()
            self.execution_agent = ExecutionAgent()
            return True
        return False
    
    def _advanced_agents_unavailable(self, feature: str) -> dict[str, Any]:
        """Return error response when advanced agents are unavailable."""
        return {
            "type": "error",
            "answer": f"⚠️ **{feature.title()} is unavailable** in this environment.\n\n"
                      f"This feature requires the `scipy` package which is not installed. "
                      f"Please use the Docker deployment or local installation for advanced trading features.",
            "symbols": [],
        }

    def _ensure_live_agent(self) -> bool:
        """Lazy-load live execution agent on first use."""
        if self._live_loaded:
            return self.live_execution_agent is not None
        self._live_loaded = True
        if _load_live_trading():
            self.live_execution_agent = LiveExecutionAgent()
            return True
        return False

    @property
    def is_live_mode(self) -> bool:
        return self._trading_mode == "live"

    # ── Public entry point ────────────────────────────────────────────────
    async def chat(self, user_message: str) -> dict[str, Any]:
        """OpenClaw-style: understand any query and respond appropriately."""
        start = time.monotonic()
        usage = start_tracking()
        logger.info("[%s] Received query: %s", self.name, user_message[:120])

        # Step 1: LLM-based intent classification
        llm_available = True
        try:
            parsed = await llm_json(_ROUTER_SYSTEM, user_message)
        except Exception as exc:
            logger.error("[%s] Router LLM failed: %s", self.name, exc)
            llm_available = False
            # Fallback: use regex-based symbol extraction instead of giving up
            fallback_symbols = self.parse_symbols(user_message)
            if fallback_symbols:
                parsed = {"intent": "quick_status", "symbols": fallback_symbols, "query": user_message}
            else:
                parsed = {"intent": "general_question", "symbols": [], "query": user_message}

        intent = parsed.get("intent", "general_question")
        symbols = parsed.get("symbols", [])
        query = parsed.get("query", user_message)

        logger.info("[%s] Routed → intent=%s, symbols=%s, llm_available=%s",
                     self.name, intent, symbols, llm_available)

        # Step 2: Dispatch to the right handler
        if intent == "global_outlook":
            result = await self._handle_global_outlook(symbols, query)
        elif intent == "ml_prediction" and symbols:
            result = await self._handle_ml_prediction(symbols, query)
        elif intent == "engine":
            result = await self._handle_engine(symbols, query)
        elif intent == "strategy_builder":
            result = await self._handle_strategy_builder(symbols, query)
        elif intent == "portfolio_optimization" and symbols:
            if self._ensure_advanced_agents():
                result = await self._handle_portfolio_optimization(symbols, query)
            else:
                result = self._advanced_agents_unavailable("portfolio optimization")
        elif intent == "backtest" and symbols:
            if self._ensure_advanced_agents():
                result = await self._handle_backtest(symbols, query)
            else:
                result = self._advanced_agents_unavailable("backtesting")
        elif intent == "volatility_analysis" and symbols:
            if self._ensure_advanced_agents():
                result = await self._handle_volatility_analysis(symbols, query)
            else:
                result = self._advanced_agents_unavailable("volatility analysis")
        elif intent == "technical_analysis" and symbols:
            if self._ensure_advanced_agents():
                result = await self._handle_technical_analysis(symbols, query)
            else:
                result = self._advanced_agents_unavailable("technical analysis")
        elif intent == "correlation_analysis" and len(symbols) >= 2:
            if self._ensure_advanced_agents():
                result = await self._handle_correlation_analysis(symbols, query)
            else:
                result = self._advanced_agents_unavailable("correlation analysis")
        elif intent == "execution":
            if self.is_live_mode and self._ensure_live_agent():
                result = await self._handle_live_execution(symbols, query)
            elif self._ensure_advanced_agents():
                result = await self._handle_execution(symbols, query)
            else:
                result = self._advanced_agents_unavailable("paper trading")
        elif intent == "quick_status" and symbols:
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
            # Fallback: produce a plain-text summary from the raw data
            parts = []
            for md in market_results:
                if "price" in md:
                    sym = md.get('symbol', '?')
                    name = md.get('company_name', sym)
                    change_pct = md.get('price_change_pct', 0)
                    change_icon = "📈" if change_pct >= 0 else "📉"
                    parts.append(
                        f"### {change_icon} {name} ({sym})\n"
                        f"- **Price:** ${md['price']} ({change_pct:+.2f}%)\n"
                        f"- **RSI:** {md.get('rsi', 'N/A')} | **Trend:** {md.get('trend', 'N/A')}\n"
                        f"- **Day Range:** ${md.get('day_low', 'N/A')} – ${md.get('day_high', 'N/A')}\n"
                        f"- **Volume:** {md.get('volume_formatted', 'N/A')} | **Market Cap:** {md.get('market_cap_formatted', 'N/A')}"
                    )
                elif "error" in md:
                    parts.append(f"**{md.get('symbol', '?')}**: Could not fetch data — {md['error']}")
            if parts:
                answer = "\n\n".join(parts)
                answer += "\n\n> *AI summary unavailable — showing raw market data.*"
            else:
                answer = "⚠️ Could not fetch market data or generate a summary. Please try again."

        return {
            "type": "quick_status",
            "answer": answer,
            "market_data": structured,
            "symbols": symbols,
        }

    # ── Full analysis (existing heavy pipeline) ───────────────────────────
    async def _handle_full_analysis(self, symbols: list[str]) -> dict[str, Any]:
        """Run the complete multi-agent analysis pipeline with global macro overlay."""
        import os
        is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

        # Run stock-specific analysis and global macro analysis in parallel
        global_timeout = 15.0 if is_serverless else 30.0
        analysis_task = asyncio.create_task(self.analyze_multiple(symbols))

        try:
            global_task = asyncio.create_task(
                self.global_market_agent.analyze(target_symbol=symbols[0] if symbols else None)
            )
            global_data = await asyncio.wait_for(asyncio.shield(global_task), timeout=global_timeout)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("[%s] Global market analysis timed out or failed: %s", self.name, exc)
            global_data = self.global_market_agent.empty_result(f"Global analysis unavailable: {exc}")

        results = await analysis_task

        # Enrich each result with global context
        for r in results:
            r["global_macro"] = global_data

        # Build an enhanced summary
        macro_bias = global_data.get("overall_bias", "neutral")
        guidance = global_data.get("buy_sell_guidance", {})
        action_bias = guidance.get("action_bias", "stay_selective")

        summaries = []
        for r in results:
            d = r.get("decision", {})
            agents_count = len(r.get("agents_used", []))
            summaries.append(
                f"**{r.get('symbol', '?')}**: {d.get('action', 'HOLD')} "
                f"(confidence {d.get('confidence', 0):.0%}, {agents_count} agents)"
            )

        macro_line = f"\n\n**Global Macro Bias**: {macro_bias.replace('_', ' ').title()} — {action_bias.replace('_', ' ').title()}"
        macro_summary = global_data.get("macro_summary", "")
        if macro_summary:
            macro_line += f"\n\n> {macro_summary}"

        return {
            "type": "full_analysis",
            "answer": "## Analysis Complete\n\n" + " | ".join(summaries) + macro_line,
            "analyses": results,
            "global_macro": global_data,
            "symbols": [r.get("symbol", "") for r in results],
        }

    # ── Global market outlook ─────────────────────────────────────────────
    async def _handle_global_outlook(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Provide global market overview with sector recommendations and BUY/SELL advice."""
        import os
        is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

        global_timeout = 20.0 if is_serverless else 40.0

        try:
            global_data = await asyncio.wait_for(
                self.global_market_agent.analyze(
                    target_symbol=symbols[0] if symbols else None
                ),
                timeout=global_timeout,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.error("[%s] Global outlook failed: %s", self.name, exc)
            global_data = self.global_market_agent.empty_result(f"Global analysis failed: {exc}")

        # If the user also mentioned symbols, run quick market data for them alongside
        stock_context = []
        if symbols:
            market_results = await asyncio.gather(
                *[self.market_agent.analyze(s) for s in symbols[:5]],
                return_exceptions=True,
            )
            for md in market_results:
                if isinstance(md, Exception):
                    continue
                stock_context.append(md)

        # Build the answer using LLM
        guidance = global_data.get("buy_sell_guidance", {})
        regime = global_data.get("global_regime", "unknown")
        bias = global_data.get("overall_bias", "neutral")
        macro_summary = global_data.get("macro_summary", "No data available.")
        recommended = global_data.get("recommended_sectors", [])
        avoid = global_data.get("avoid_sectors", [])
        geo = global_data.get("geographic_outlook", {})
        risks = global_data.get("key_macro_risks", [])
        opportunities = global_data.get("key_macro_opportunities", [])
        vix_assessment = global_data.get("vix_assessment", "unknown")
        cycle_phase = global_data.get("market_cycle_phase", "uncertain")
        cross_signals = global_data.get("cross_market_signals", {})

        # Build a rich markdown overview
        answer_parts = [
            f"## 🌍 Global Market Outlook",
            f"",
            f"**Macro Regime:** {regime.replace('_', ' ').title()} | "
            f"**Overall Bias:** {bias.replace('_', ' ').title()} | "
            f"**Market Cycle:** {cycle_phase.replace('_', ' ').title()}",
            f"",
            f"**VIX Assessment:** {vix_assessment.replace('_', ' ').title()} (Level: {cross_signals.get('vix_level', 'N/A')})",
            f"",
            f"### Market Summary",
            macro_summary,
            f"",
        ]

        if recommended:
            answer_parts.append(f"### ✅ Recommended Sectors")
            answer_parts.append(", ".join(recommended))
            answer_parts.append("")

        if avoid:
            answer_parts.append(f"### ⚠️ Sectors to Avoid")
            answer_parts.append(", ".join(avoid))
            answer_parts.append("")

        # Geographic outlook
        if any(v != "neutral" for v in geo.values()):
            answer_parts.append("### 🗺️ Geographic Outlook")
            for region, outlook in geo.items():
                icon = "🟢" if outlook == "positive" else ("🔴" if outlook == "negative" else "⚪")
                answer_parts.append(f"- {icon} **{region.upper()}**: {outlook.title()}")
            answer_parts.append("")

        # Actionable guidance
        answer_parts.append("### 💡 BUY/SELL Guidance")
        answer_parts.append(f"- **Action Bias:** {guidance.get('action_bias', 'stay_selective').replace('_', ' ').title()}")
        answer_parts.append(f"- **Position Sizing:** {guidance.get('position_sizing', 'reduced').title()}")
        answer_parts.append(f"- **Rationale:** {guidance.get('rationale', 'N/A')}")
        answer_parts.append("")

        if risks:
            answer_parts.append("### ⛔ Key Macro Risks")
            for r in risks:
                answer_parts.append(f"- {r}")
            answer_parts.append("")

        if opportunities:
            answer_parts.append("### 🚀 Key Opportunities")
            for o in opportunities:
                answer_parts.append(f"- {o}")
            answer_parts.append("")

        # If specific stocks were mentioned, add context
        if stock_context:
            answer_parts.append("### 📊 Referenced Stocks")
            for md in stock_context:
                if "error" in md and "price" not in md:
                    continue
                sym = md.get("symbol", "?")
                price = md.get("price", "N/A")
                change = md.get("price_change_pct", 0)
                trend = md.get("trend", "N/A")
                rsi = md.get("rsi", "N/A")
                icon = "📈" if change >= 0 else "📉"
                answer_parts.append(
                    f"- {icon} **{md.get('company_name', sym)} ({sym})**: "
                    f"${price} ({change:+.2f}%) | Trend: {trend} | RSI: {rsi}"
                )
            answer_parts.append("")

        answer = "\n".join(answer_parts)

        return {
            "type": "global_outlook",
            "answer": answer,
            "global_macro": global_data,
            "market_data": stock_context,
            "symbols": symbols,
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
            logger.error("[%s] Comparison LLM failed: %s", self.name, exc)
            answer = f"## Stock Comparison\n\n{comp_text}\n\n> *AI summary unavailable — showing raw comparison data.*"

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
            logger.error("[%s] News LLM failed: %s", self.name, exc)
            if all_articles:
                answer = "## Latest News\n\n"
                for a in all_articles[:8]:
                    answer += f"- **{a.get('title', 'N/A')}** ({a.get('source', '?')})\n  {a.get('description', '')[:200]}\n\n"
                answer += "> *AI summary unavailable — showing raw headlines.*"
            else:
                answer = "No recent news found and AI summary unavailable."

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
                    # At least return the search snippets formatted nicely
                    answer = "**Here are the most relevant results I found:**\n\n"
                    for r in search_results[:5]:
                        answer += f"- [{r.get('title', 'N/A')}]({r.get('url', '')})\n  {r.get('snippet', '')}\n\n"
                    answer += "\n> *AI summary unavailable — the LLM service could not be reached. Showing raw search results instead.*"
                else:
                    answer = (
                        "⚠️ **Service temporarily unavailable.** The AI language model could not be reached.\n\n"
                        "Please check that the `OPENAI_API_KEY` environment variable is set correctly "
                        "and that the OpenAI API is accessible from your deployment environment.\n\n"
                        "Try again in a moment."
                    )

        return {
            "type": "general_question",
            "answer": answer,
            "search_results": search_results,
            "symbols": [],
        }

    # ── Portfolio Optimization Handler ────────────────────────────────────
    async def _handle_portfolio_optimization(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Optimize portfolio allocation using Modern Portfolio Theory."""
        logger.info("[%s] Portfolio optimization for %s", self.name, symbols)
        
        try:
            result = await self.portfolio_agent.analyze(symbols)
        except Exception as exc:
            logger.error("[%s] Portfolio optimization failed: %s", self.name, exc)
            return {
                "type": "portfolio_optimization",
                "answer": f"⚠️ Portfolio optimization failed: {exc}",
                "symbols": symbols,
            }
        
        # Build answer
        opt = result.get("optimization", {})
        metrics = result.get("current_metrics", {})
        
        answer_parts = [
            "## 📊 Portfolio Optimization Results",
            "",
            f"**Symbols:** {', '.join(symbols)}",
            "",
            "### Optimal Weights",
        ]
        
        for strategy in ["max_sharpe", "min_variance", "risk_parity"]:
            weights = opt.get(f"{strategy}_weights", {})
            if weights:
                answer_parts.append(f"\n**{strategy.replace('_', ' ').title()}:**")
                for sym, w in weights.items():
                    answer_parts.append(f"- {sym}: {w*100:.1f}%")
        
        if metrics:
            answer_parts.append("\n### Portfolio Metrics")
            answer_parts.append(f"- **Expected Return:** {metrics.get('expected_return', 0)*100:.2f}%")
            answer_parts.append(f"- **Volatility:** {metrics.get('volatility', 0)*100:.2f}%")
            answer_parts.append(f"- **Sharpe Ratio:** {metrics.get('sharpe_ratio', 0):.2f}")
        
        rebal = result.get("rebalancing", {})
        if rebal.get("needs_rebalancing"):
            answer_parts.append("\n### Rebalancing Recommendations")
            for rec in rebal.get("recommendations", [])[:5]:
                answer_parts.append(f"- {rec}")
        
        return {
            "type": "portfolio_optimization",
            "answer": "\n".join(answer_parts),
            "optimization": result,
            "symbols": symbols,
        }

    # ── Backtesting Handler ───────────────────────────────────────────────
    async def _handle_backtest(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Run backtesting on historical data."""
        logger.info("[%s] Backtesting for %s", self.name, symbols)
        
        symbol = symbols[0]  # Backtest single symbol
        
        # Determine strategy from query
        strategy = "ma_crossover"  # default
        query_lower = query.lower()
        if "rsi" in query_lower or "mean reversion" in query_lower:
            strategy = "rsi_mean_reversion"
        elif "momentum" in query_lower:
            strategy = "momentum"
        elif "breakout" in query_lower:
            strategy = "breakout"
        elif "macd" in query_lower:
            strategy = "macd"
        elif "bollinger" in query_lower:
            strategy = "bollinger"
        
        try:
            result = await self.backtest_agent.backtest_strategy(symbol, strategy)
        except Exception as exc:
            logger.error("[%s] Backtest failed: %s", self.name, exc)
            return {
                "type": "backtest",
                "answer": f"⚠️ Backtest failed: {exc}",
                "symbols": symbols,
            }
        
        perf = result.get("performance", {})
        metrics = result.get("metrics", {})
        
        answer_parts = [
            f"## 📈 Backtest Results: {strategy.replace('_', ' ').title()}",
            f"",
            f"**Symbol:** {symbol}",
            f"",
            "### Performance Summary",
            f"- **Total Return:** {perf.get('total_return', 0)*100:.2f}%",
            f"- **Annualized Return:** {perf.get('annualized_return', 0)*100:.2f}%",
            f"- **Sharpe Ratio:** {perf.get('sharpe_ratio', 0):.2f}",
            f"- **Max Drawdown:** {perf.get('max_drawdown', 0)*100:.2f}%",
            f"",
            "### Trade Statistics",
            f"- **Total Trades:** {metrics.get('total_trades', 0)}",
            f"- **Win Rate:** {metrics.get('win_rate', 0)*100:.1f}%",
            f"- **Profit Factor:** {metrics.get('profit_factor', 0):.2f}",
            f"- **Avg Trade Return:** {metrics.get('avg_trade_return', 0)*100:.2f}%",
        ]
        
        return {
            "type": "backtest",
            "answer": "\n".join(answer_parts),
            "backtest_results": result,
            "symbols": symbols,
        }

    # ── Volatility Analysis Handler ───────────────────────────────────────
    async def _handle_volatility_analysis(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Analyze volatility with multiple models."""
        logger.info("[%s] Volatility analysis for %s", self.name, symbols)
        
        symbol = symbols[0]
        
        try:
            result = await self.volatility_agent.analyze(symbol)
        except Exception as exc:
            logger.error("[%s] Volatility analysis failed: %s", self.name, exc)
            return {
                "type": "volatility_analysis",
                "answer": f"⚠️ Volatility analysis failed: {exc}",
                "symbols": symbols,
            }
        
        vol = result.get("volatility_estimates", {})
        regime = result.get("regime", {})
        forecast = result.get("forecast", {})
        
        answer_parts = [
            f"## 📊 Volatility Analysis: {symbol}",
            f"",
            "### Current Volatility Estimates (Annualized)",
            f"- **Historical (20-day):** {vol.get('historical_20d', 0)*100:.2f}%",
            f"- **EWMA:** {vol.get('ewma', 0)*100:.2f}%",
            f"- **Parkinson (High-Low):** {vol.get('parkinson', 0)*100:.2f}%",
            f"- **GARCH(1,1):** {vol.get('garch', 0)*100:.2f}%",
            f"",
            "### Volatility Regime",
            f"- **Current Regime:** {regime.get('current', 'Unknown').title()}",
            f"- **Trend:** {regime.get('trend', 'stable').title()}",
            f"",
            "### Forecast",
            f"- **Next Day Vol:** {forecast.get('next_day', 0)*100:.2f}%",
            f"- **Next Week Vol:** {forecast.get('next_week', 0)*100:.2f}%",
        ]
        
        risk = result.get("risk_assessment", {})
        if risk:
            answer_parts.append("")
            answer_parts.append("### Risk Assessment")
            answer_parts.append(f"- **VaR (95%):** {risk.get('var_95', 0)*100:.2f}%")
            answer_parts.append(f"- **CVaR (95%):** {risk.get('cvar_95', 0)*100:.2f}%")
        
        return {
            "type": "volatility_analysis",
            "answer": "\n".join(answer_parts),
            "volatility_data": result,
            "symbols": symbols,
        }

    # ── Technical Analysis Handler ────────────────────────────────────────
    async def _handle_technical_analysis(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Run comprehensive technical analysis."""
        logger.info("[%s] Technical analysis for %s", self.name, symbols)
        
        symbol = symbols[0]
        
        try:
            result = await self.technical_agent.analyze(symbol)
        except Exception as exc:
            logger.error("[%s] Technical analysis failed: %s", self.name, exc)
            return {
                "type": "technical_analysis",
                "answer": f"⚠️ Technical analysis failed: {exc}",
                "symbols": symbols,
            }
        
        trend = result.get("trend_analysis", {})
        indicators = result.get("indicators", {})
        signals = result.get("signals", {})
        patterns = result.get("patterns", [])
        
        answer_parts = [
            f"## 📈 Technical Analysis: {symbol}",
            f"",
            "### Trend Analysis",
            f"- **Primary Trend:** {trend.get('primary', 'Unknown').title()}",
            f"- **Trend Strength:** {trend.get('strength', 0)*100:.0f}%",
            f"",
            "### Key Indicators",
            f"- **RSI (14):** {indicators.get('rsi', 0):.1f}",
            f"- **MACD:** {indicators.get('macd', 0):.2f} (Signal: {indicators.get('macd_signal', 0):.2f})",
            f"- **ADX:** {indicators.get('adx', 0):.1f}",
            f"- **Stochastic:** {indicators.get('stochastic_k', 0):.1f}",
        ]
        
        if patterns:
            answer_parts.append("")
            answer_parts.append("### Detected Patterns")
            for p in patterns[:5]:
                answer_parts.append(f"- {p.get('name', 'Unknown')}: {p.get('signal', 'N/A')}")
        
        overall = signals.get("overall", {})
        if overall:
            answer_parts.append("")
            answer_parts.append("### Overall Signal")
            answer_parts.append(f"**{overall.get('signal', 'HOLD')}** (Confidence: {overall.get('confidence', 0)*100:.0f}%)")
        
        return {
            "type": "technical_analysis",
            "answer": "\n".join(answer_parts),
            "technical_data": result,
            "symbols": symbols,
        }

    # ── Correlation Analysis Handler ──────────────────────────────────────
    async def _handle_correlation_analysis(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Analyze correlations and pair trading opportunities."""
        logger.info("[%s] Correlation analysis for %s", self.name, symbols)
        
        try:
            result = await self.correlation_agent.analyze_correlations(symbols)
        except Exception as exc:
            logger.error("[%s] Correlation analysis failed: %s", self.name, exc)
            return {
                "type": "correlation_analysis",
                "answer": f"⚠️ Correlation analysis failed: {exc}",
                "symbols": symbols,
            }
        
        matrix = result.get("correlation_matrix", {})
        pairs = result.get("top_pairs", [])
        diversification = result.get("diversification_metrics", {})
        
        answer_parts = [
            f"## 🔗 Correlation Analysis",
            f"",
            f"**Symbols:** {', '.join(symbols)}",
            f"",
            "### Correlation Matrix",
        ]
        
        # Build a simple correlation table
        for sym1, corrs in matrix.items():
            corr_str = ", ".join([f"{s2}: {c:.2f}" for s2, c in corrs.items() if s2 != sym1])
            answer_parts.append(f"- **{sym1}:** {corr_str}")
        
        if pairs:
            answer_parts.append("")
            answer_parts.append("### Top Correlated Pairs")
            for p in pairs[:5]:
                answer_parts.append(f"- {p.get('pair', '?')}: {p.get('correlation', 0):.2f}")
        
        answer_parts.append("")
        answer_parts.append("### Diversification Metrics")
        answer_parts.append(f"- **Average Correlation:** {diversification.get('avg_correlation', 0):.2f}")
        answer_parts.append(f"- **Diversification Score:** {diversification.get('score', 0)*100:.0f}%")
        
        return {
            "type": "correlation_analysis",
            "answer": "\n".join(answer_parts),
            "correlation_data": result,
            "symbols": symbols,
        }

    # ── Execution Handler ─────────────────────────────────────────────────
    # ── Live Execution Handler ─────────────────────────────────────────
    async def _handle_live_execution(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Handle live multi-broker trading execution."""
        logger.info("[%s] LIVE execution handler for: %s", self.name, query)
        query_lower = query.lower()

        # Portfolio summary across all brokers
        if any(kw in query_lower for kw in ["portfolio", "positions", "holdings", "balance"]):
            try:
                from tools.broker_manager import get_broker_manager
                manager = get_broker_manager()
                portfolio = await manager.get_consolidated_portfolio()
                accts = portfolio.get("accounts", {})
                total_equity = sum(a.get("equity", 0) for a in accts.values())
                total_cash = sum(a.get("cash", 0) for a in accts.values())
                all_positions = portfolio.get("positions", {})
                answer_parts = [
                    "## 💼 Live Portfolio (All Brokers)",
                    "",
                    f"**Total Equity:** ${total_equity:,.2f} | **Cash:** ${total_cash:,.2f}",
                    "",
                ]
                for bid, positions in all_positions.items():
                    if positions:
                        answer_parts.append(f"### {bid.upper()}")
                        for p in positions:
                            pnl = getattr(p, "unrealized_pnl", 0) or 0
                            icon = "📈" if pnl >= 0 else "📉"
                            answer_parts.append(
                                f"- {icon} **{p.symbol}**: {p.quantity} shares "
                                f"(P&L: ${pnl:+,.2f})"
                            )
                        answer_parts.append("")
                return {
                    "type": "live_execution",
                    "answer": "\n".join(answer_parts),
                    "portfolio": portfolio,
                    "symbols": symbols,
                }
            except Exception as exc:
                logger.error("[%s] Live portfolio failed: %s", self.name, exc)
                return {
                    "type": "live_execution",
                    "answer": f"⚠️ Could not retrieve live portfolio: {exc}",
                    "symbols": symbols,
                }

        # Live trade execution
        if any(kw in query_lower for kw in ["buy", "sell", "order", "trade", "execute"]):
            if not symbols:
                return {
                    "type": "live_execution",
                    "answer": "⚠️ Please specify a symbol to trade.",
                    "symbols": [],
                }
            symbol = symbols[0]
            side = "BUY" if "buy" in query_lower else "SELL"

            # Get market data for the symbol
            market_data = await self.market_agent.analyze(symbol)
            if "error" in market_data and "price" not in market_data:
                return {
                    "type": "live_execution",
                    "answer": f"⚠️ Could not get price for {symbol}: {market_data.get('error')}",
                    "symbols": symbols,
                }
            current_price = market_data.get("price", 0)

            # Run full analysis to get signal
            decision_data = await self.decision_agent.decide(
                symbol=symbol,
                market_data=market_data,
                news_data={"sentiment": "neutral"},
                sentiment_data={"overall_score": 0.5},
                risk_data={"risk_score": 5},
            )
            confidence = decision_data.get("confidence", 0.5)

            # Execute through live agent
            result = await self.live_execution_agent.execute_signal(
                symbol=symbol,
                signal={
                    "action": f"{'STRONG_' if confidence > 0.8 else ''}{side}",
                    "confidence": confidence,
                    "entry_price": current_price,
                    "stop_loss": decision_data.get("stop_loss"),
                    "target_price": decision_data.get("target_price"),
                },
            )

            if result.get("executed"):
                answer = (
                    f"## ✅ LIVE Order Executed\n\n"
                    f"**{side} {symbol}** — {result.get('quantity', 0)} shares @ "
                    f"${result.get('avg_fill_price', current_price):,.2f}\n"
                    f"**Broker:** {result.get('broker', 'N/A')}\n"
                    f"**Order ID:** `{result.get('order_id', 'N/A')}`"
                )
            elif result.get("risk_rejected"):
                answer = (
                    f"## 🛑 Order Blocked by Risk Engine\n\n"
                    f"**{side} {symbol}** was rejected.\n"
                    f"**Reason:** {result.get('risk_reason', 'Unknown')}"
                )
            else:
                answer = (
                    f"## ⚠️ Order Not Executed\n\n"
                    f"**{side} {symbol}** — {result.get('reason', 'Unknown error')}"
                )

            return {
                "type": "live_execution",
                "answer": answer,
                "execution_result": result,
                "symbols": symbols,
            }

        # Risk engine status
        if any(kw in query_lower for kw in ["risk", "kill switch", "circuit", "halt"]):
            try:
                from core.risk_engine import get_risk_engine
                status = get_risk_engine().get_status()
                answer_parts = [
                    "## 🛡️ Risk Engine Status",
                    "",
                    f"**Kill Switch:** {'🔴 ACTIVE' if status.get('kill_switch_active') else '🟢 Inactive'}",
                    f"**Trading Halted:** {'🔴 YES' if status.get('trading_halted') else '🟢 No'}",
                    f"**Daily P&L:** ${status.get('daily_pnl', 0):+,.2f}",
                    f"**Daily Orders:** {status.get('daily_order_count', 0)}",
                    f"**Open Positions:** {status.get('open_position_count', 0)}",
                ]
                if status.get("halt_reason"):
                    answer_parts.append(f"**Halt Reason:** {status['halt_reason']}")
                return {
                    "type": "live_execution",
                    "answer": "\n".join(answer_parts),
                    "risk_status": status,
                    "symbols": symbols,
                }
            except Exception as exc:
                return {
                    "type": "live_execution",
                    "answer": f"⚠️ Risk engine error: {exc}",
                    "symbols": symbols,
                }

        # Emergency stop
        if any(kw in query_lower for kw in ["emergency", "stop all", "cancel all", "close all"]):
            result = await self.live_execution_agent.emergency_stop(
                reason="Triggered via chat command"
            )
            return {
                "type": "live_execution",
                "answer": "## 🚨 Emergency Stop Activated\n\nAll orders cancelled. All positions closed. Kill switch engaged.",
                "emergency_result": result,
                "symbols": symbols,
            }

        # Default: show broker and OMS status
        try:
            from tools.broker_manager import get_broker_manager
            from core.order_management import get_oms
            brokers = get_broker_manager().list_brokers()
            oms_status = get_oms().get_status()
            answer_parts = [
                "## 🔌 Live Trading Status",
                "",
                f"**Mode:** LIVE | **Auto-Trading:** {'Enabled' if self._auto_trading else 'Disabled'}",
                "",
                "### Connected Brokers",
            ]
            for b in brokers:
                icon = "🟢" if b.get("connected") else "🔴"
                answer_parts.append(f"- {icon} **{b['id']}**: {b.get('status', 'unknown')}")
            answer_parts.append("")
            answer_parts.append(f"### OMS: {oms_status.get('active_orders', 0)} active orders")
            return {
                "type": "live_execution",
                "answer": "\n".join(answer_parts),
                "brokers": brokers,
                "oms_status": oms_status,
                "symbols": symbols,
            }
        except Exception as exc:
            return {
                "type": "live_execution",
                "answer": f"⚠️ Could not get trading status: {exc}",
                "symbols": symbols,
            }

    # ── Paper Execution Handler ───────────────────────────────────────────
    async def _handle_execution(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Handle paper trading execution and portfolio queries."""
        logger.info("[%s] Execution handler for: %s", self.name, query)
        
        query_lower = query.lower()
        
        # Portfolio summary
        if any(kw in query_lower for kw in ["portfolio", "positions", "holdings", "balance"]):
            # Get current prices for valuation if we have symbols
            current_prices = {}
            if symbols:
                market_results = await asyncio.gather(
                    *[self.market_agent.analyze(s) for s in symbols],
                    return_exceptions=True,
                )
                for md in market_results:
                    if isinstance(md, dict) and "price" in md:
                        current_prices[md["symbol"]] = md["price"]
            
            portfolio = await self.execution_agent.get_portfolio_summary(current_prices or None)
            
            summary = portfolio.get("summary", {})
            positions = portfolio.get("positions", [])
            stats = portfolio.get("trade_statistics", {})
            
            answer_parts = [
                "## 💼 Portfolio Summary",
                "",
                "### Account Value",
                f"- **Total Value:** ${summary.get('total_value', 0):,.2f}",
                f"- **Cash:** ${summary.get('cash', 0):,.2f}",
                f"- **Position Value:** ${summary.get('position_value', 0):,.2f}",
                f"- **Total P&L:** ${summary.get('total_pnl', 0):+,.2f} ({summary.get('total_return_pct', 0):+.2f}%)",
            ]
            
            if positions:
                answer_parts.append("")
                answer_parts.append("### Open Positions")
                for pos in positions:
                    icon = "📈" if pos.get("unrealized_pnl", 0) >= 0 else "📉"
                    answer_parts.append(
                        f"- {icon} **{pos['symbol']}**: {pos['quantity']} shares @ ${pos['current_price']:.2f} "
                        f"(P&L: ${pos['unrealized_pnl']:+,.2f})"
                    )
            
            answer_parts.append("")
            answer_parts.append("### Trade Statistics")
            answer_parts.append(f"- **Total Trades:** {stats.get('total_trades', 0)}")
            answer_parts.append(f"- **Win Rate:** {stats.get('win_rate', 0)*100:.1f}%")
            
            return {
                "type": "execution",
                "answer": "\n".join(answer_parts),
                "portfolio": portfolio,
                "symbols": symbols,
            }
        
        # If user wants to trade
        if any(kw in query_lower for kw in ["buy", "sell", "order"]):
            # Get current price
            if not symbols:
                return {
                    "type": "execution",
                    "answer": "⚠️ Please specify a symbol to trade.",
                    "symbols": [],
                }
            
            symbol = symbols[0]
            side = "buy" if "buy" in query_lower else "sell"
            
            # Get current price
            market_data = await self.market_agent.analyze(symbol)
            if "error" in market_data and "price" not in market_data:
                return {
                    "type": "execution",
                    "answer": f"⚠️ Could not get price for {symbol}: {market_data.get('error')}",
                    "symbols": symbols,
                }
            
            current_price = market_data.get("price", 0)
            
            # Get recommended position size
            sizing = await self.execution_agent.calculate_position_size(
                symbol,
                {"confidence": 0.7},
                current_price,
            )
            
            answer_parts = [
                f"## 📝 Trade Setup: {side.upper()} {symbol}",
                "",
                f"**Current Price:** ${current_price:.2f}",
                "",
                "### Recommended Position Size",
                f"- **Shares:** {sizing.get('recommended_shares', 0)}",
                f"- **Value:** ${sizing.get('position_value', 0):,.2f}",
                f"- **% of Portfolio:** {sizing.get('position_pct', 0):.1f}%",
                "",
                "To execute this trade, confirm the quantity and I'll submit the order.",
            ]
            
            return {
                "type": "execution",
                "answer": "\n".join(answer_parts),
                "trade_setup": {
                    "symbol": symbol,
                    "side": side,
                    "current_price": current_price,
                    "sizing": sizing,
                },
                "symbols": symbols,
            }
        
        # Default: show analytics
        analytics = await self.execution_agent.get_execution_analytics()
        
        return {
            "type": "execution",
            "answer": "## 📊 Execution Analytics\n\n" + str(analytics),
            "analytics": analytics,
            "symbols": symbols,
        }

    # ── ML Prediction Handler ─────────────────────────────────────────────
    async def _handle_ml_prediction(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Run ML-based price prediction for symbols."""
        logger.info("[%s] ML prediction for %s", self.name, symbols)

        results = []
        for symbol in symbols[:3]:
            try:
                prediction = await self.ml_agent.train_and_predict(symbol)
                results.append(prediction)
            except Exception as exc:
                logger.error("[%s] ML prediction failed for %s: %s", self.name, symbol, exc)
                results.append({"symbol": symbol, "error": str(exc)})

        answer_parts = ["## 🤖 ML Prediction Results\n"]
        for pred in results:
            sym = pred.get("symbol", "?")
            if "error" in pred:
                answer_parts.append(f"**{sym}:** Prediction failed — {pred['error']}\n")
                continue
            signal = pred.get("prediction", "HOLD")
            confidence = pred.get("confidence", 0)
            method = pred.get("method", "unknown")
            icon = "📈" if signal == "BUY" else ("📉" if signal == "SELL" else "⏸️")
            answer_parts.append(
                f"### {icon} {sym}\n"
                f"- **Signal:** {signal} (confidence {confidence:.0%})\n"
                f"- **Method:** {method}\n"
            )
            probabilities = pred.get("probabilities", {})
            if probabilities:
                answer_parts.append("- **Probabilities:**")
                for label, prob in probabilities.items():
                    answer_parts.append(f"  - {label}: {prob:.1%}")
                answer_parts.append("")
            features = pred.get("key_features", {})
            if features:
                answer_parts.append("- **Key features:** " + ", ".join(
                    f"{k}={v:.3f}" for k, v in list(features.items())[:5]
                ))
            answer_parts.append("")

        return {
            "type": "ml_prediction",
            "answer": "\n".join(answer_parts),
            "predictions": results,
            "symbols": symbols,
        }

    # ── Engine Handler ────────────────────────────────────────────────────
    async def _handle_engine(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Handle engine queries — run built-in strategies, backtest, signals."""
        logger.info("[%s] Engine query: %s, symbols=%s", self.name, query, symbols)

        from engine.strategy import BUILTIN_STRATEGIES, StrategyEngine
        from engine.backtest import Backtester, BacktestConfig
        import yfinance as yf

        # Detect which strategy user wants
        q_lower = query.lower()
        strategy_name = None
        for name in BUILTIN_STRATEGIES:
            if name.replace("_", " ") in q_lower or name in q_lower:
                strategy_name = name
                break
        if not strategy_name:
            strategy_name = "golden_cross"  # default

        strategy = BUILTIN_STRATEGIES[strategy_name]
        symbol = symbols[0] if symbols else "AAPL"

        # Fetch data
        try:
            df = yf.download(symbol, period="1y", interval="1d", progress=False)
            if hasattr(df.columns, 'levels') and df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)
        except Exception as e:
            return {
                "type": "engine",
                "answer": f"## ⚙️ Engine Error\n\nFailed to fetch data for {symbol}: {e}",
                "symbols": symbols,
            }

        if df is None or df.empty:
            return {
                "type": "engine",
                "answer": f"## ⚙️ Engine\n\nNo data available for **{symbol}**.",
                "symbols": symbols,
            }

        # Decide: backtest or signals
        wants_backtest = any(kw in q_lower for kw in ["backtest", "test", "performance", "monte carlo", "walk forward"])

        if wants_backtest:
            bt = Backtester(BacktestConfig(initial_capital=100_000))
            result = bt.run(strategy, df, symbol)
            summary = result.summary()

            answer_parts = [
                f"## ⚙️ Engine Backtest — {strategy.name}",
                f"**Symbol:** {symbol} | **Period:** {summary['period']}",
                f"**Total Bars:** {summary['total_bars']}\n",
                "### Performance",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Total Return | {summary['total_return']} |",
                f"| Annual Return | {summary['annual_return']} |",
                f"| Sharpe Ratio | {summary['sharpe_ratio']} |",
                f"| Sortino Ratio | {summary['sortino_ratio']} |",
                f"| Max Drawdown | {summary['max_drawdown']} |",
                f"| Volatility | {summary['volatility']} |",
                "",
                "### Trade Statistics",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Total Trades | {summary['total_trades']} |",
                f"| Win Rate | {summary['win_rate']} |",
                f"| Profit Factor | {summary['profit_factor']} |",
                f"| Expectancy | ${summary['expectancy']} |",
                f"| Avg Win | {summary['avg_win']} |",
                f"| Avg Loss | {summary['avg_loss']} |",
                f"| Max Consecutive Wins | {summary['max_consecutive_wins']} |",
                f"| Max Consecutive Losses | {summary['max_consecutive_losses']} |",
                "",
                f"**Initial Capital:** ${summary['initial_capital']:,.2f} → **Final:** ${summary['final_capital']:,.2f}",
            ]

            return {
                "type": "engine_backtest",
                "answer": "\n".join(answer_parts),
                "backtest_summary": summary,
                "equity_curve": result.equity_curve[-252:],
                "trades_count": len(result.trades),
                "symbols": symbols,
            }
        else:
            # Generate signals
            engine = StrategyEngine()
            signals = engine.generate_signals_list(strategy, df)
            recent = signals[-10:] if signals else []

            answer_parts = [
                f"## ⚙️ Engine Signals — {strategy.name}",
                f"**Symbol:** {symbol} | **Period:** 1Y | **Total Bars:** {len(df)}\n",
                f"**Total Signals:** {len(signals)}\n",
            ]

            if recent:
                answer_parts.append("### Recent Signals")
                answer_parts.append("| Date | Signal |")
                answer_parts.append("|------|--------|")
                for s in recent:
                    answer_parts.append(f"| {s['date']} | {s['signal']} |")
            else:
                answer_parts.append("_No signals generated in the selected period._")

            answer_parts.extend([
                "",
                f"**Strategy Rules:**",
                f"- Entry Long: `{strategy.entry_long}`",
                f"- Exit Long: `{strategy.exit_long}`",
            ])
            if strategy.entry_short:
                answer_parts.append(f"- Entry Short: `{strategy.entry_short}`")
            if strategy.stop_loss_pct:
                answer_parts.append(f"- Stop Loss: {strategy.stop_loss_pct*100:.1f}%")

            return {
                "type": "engine_signals",
                "answer": "\n".join(answer_parts),
                "signals": recent,
                "total_signals": len(signals),
                "strategy_name": strategy.name,
                "symbols": symbols,
            }

    # ── Strategy Builder Handler ──────────────────────────────────────────
    async def _handle_strategy_builder(self, symbols: list[str], query: str) -> dict[str, Any]:
        """Handle strategy builder queries — list templates, show info."""
        logger.info("[%s] Strategy builder query: %s", self.name, query)

        templates = self.strategy_builder.get_templates()

        answer_parts = [
            "## 🛠️ Strategy Builder\n",
            "Available strategy templates:\n",
        ]
        for key, tpl in templates.items():
            answer_parts.append(
                f"### {tpl['name']}\n"
                f"{tpl['description']}\n"
                f"- **Parameters:** {', '.join(tpl['parameters'].keys())}\n"
                f"- **Entry rules:** {', '.join(tpl['entry_rules'])}\n"
                f"- **Exit rules:** {', '.join(tpl['exit_rules'])}\n"
            )

        answer_parts.append(
            "\n---\nTo create a strategy, use the Strategy Builder in the sidebar "
            "or the `/api/v1/strategies` API endpoints."
        )

        return {
            "type": "strategy_builder",
            "answer": "\n".join(answer_parts),
            "templates": templates,
            "symbols": symbols,
        }

    # ── Existing pipeline methods (unchanged) ─────────────────────────────
    async def analyze_symbol(self, symbol: str) -> dict[str, Any]:
        """Full pipeline analysis for a single symbol — ALL agents orchestrated."""
        import os
        is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

        start = time.monotonic()
        symbol = symbol.upper().strip()
        logger.info("[%s] Starting FULL orchestrated pipeline for %s (serverless=%s)", self.name, symbol, is_serverless)

        # Serverless-aware timeouts (must fit within Vercel maxDuration)
        research_timeout = 10.0 if is_serverless else 25.0
        sentiment_timeout = 8.0 if is_serverless else 15.0
        decision_timeout = 15.0 if is_serverless else 30.0
        global_macro_timeout = 12.0 if is_serverless else 25.0
        advanced_timeout = 10.0 if is_serverless else 20.0

        # ── Phase 1: Market data + News + Research + Global Macro ALL in parallel ──
        market_task = asyncio.create_task(self.market_agent.analyze(symbol))
        news_task = asyncio.create_task(self.news_agent.analyze(symbol))

        # Research can be slow — give it a timeout
        try:
            research_task = asyncio.create_task(self.research_agent.analyze(symbol))
            research_data = await asyncio.wait_for(asyncio.shield(research_task), timeout=research_timeout)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("[%s] Research timed out or failed for %s: %s", self.name, symbol, exc)
            research_data = self.research_agent._empty_result(symbol, f"Research unavailable: {exc}")

        # Global macro runs in parallel with everything else
        try:
            global_task = asyncio.create_task(
                self.global_market_agent.analyze(target_symbol=symbol)
            )
            global_data = await asyncio.wait_for(asyncio.shield(global_task), timeout=global_macro_timeout)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("[%s] Global macro failed for %s: %s", self.name, symbol, exc)
            global_data = self.global_market_agent.empty_result(f"Global analysis unavailable: {exc}")

        market_data = await market_task
        news_data = await news_task

        if "error" in market_data and "price" not in market_data:
            return {
                "symbol": symbol,
                "error": f"Failed to fetch market data: {market_data['error']}",
                "elapsed_seconds": round(time.monotonic() - start, 2),
            }

        # ── Phase 2: Sentiment analysis (depends on news) ──
        try:
            sentiment_data = await asyncio.wait_for(
                self.sentiment_agent.analyze(symbol, news_data),
                timeout=sentiment_timeout,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("[%s] Sentiment analysis failed for %s: %s", self.name, symbol, exc)
            sentiment_data = {
                "symbol": symbol,
                "sentiment": "neutral",
                "confidence": 0.0,
                "impact_level": "low",
                "key_themes": [],
                "reasoning": f"Sentiment analysis unavailable: {exc}",
            }

        # ── Phase 3: Risk assessment (depends on market + sentiment + global macro) ──
        try:
            risk_data = await self.risk_agent.analyze(market_data, sentiment_data, global_data)
        except Exception as exc:
            logger.warning("[%s] Risk assessment failed for %s: %s", self.name, symbol, exc)
            risk_data = {
                "symbol": symbol,
                "risk_score": 5,
                "risk_level": "medium",
                "warnings": [f"Risk assessment failed: {exc}"],
                "constraints": [],
                "allow_buy": True,
                "allow_sell": True,
            }

        # ── Phase 4: ML prediction (parallel with advanced agents) ──
        ml_prediction = {}
        ml_task = asyncio.create_task(self._safe_ml_predict(symbol))

        # ── Phase 5: Advanced agents — volatility, technical, correlation, portfolio ──
        # These run in parallel and are optional (require scipy)
        volatility_data = {}
        technical_data = {}
        correlation_data = {}
        portfolio_context = {}

        if self._ensure_advanced_agents():
            adv_tasks = []

            # Volatility agent
            async def _run_volatility():
                try:
                    return await asyncio.wait_for(
                        self.volatility_agent.analyze_volatility(symbol),
                        timeout=advanced_timeout,
                    )
                except Exception as e:
                    logger.warning("[%s] Volatility analysis failed for %s: %s", self.name, symbol, e)
                    return {"error": str(e)}

            # Technical strategy agent
            async def _run_technical():
                try:
                    return await asyncio.wait_for(
                        self.technical_agent.analyze(symbol),
                        timeout=advanced_timeout,
                    )
                except Exception as e:
                    logger.warning("[%s] Technical analysis failed for %s: %s", self.name, symbol, e)
                    return {"error": str(e)}

            # Correlation agent (uses symbol + sector peers)
            async def _run_correlation():
                try:
                    sector = market_data.get("sector", "")
                    peers = market_data.get("sector_peers", [symbol])
                    symbols_for_corr = [symbol] + [p for p in peers if p != symbol][:3]
                    if len(symbols_for_corr) < 2:
                        return {}
                    return await asyncio.wait_for(
                        self.correlation_agent.analyze_correlations(symbols_for_corr),
                        timeout=advanced_timeout,
                    )
                except Exception as e:
                    logger.warning("[%s] Correlation analysis failed for %s: %s", self.name, symbol, e)
                    return {"error": str(e)}

            # Portfolio context (if portfolio agent has context method)
            async def _run_portfolio():
                try:
                    if hasattr(self.portfolio_agent, 'get_portfolio_context'):
                        return await asyncio.wait_for(
                            self.portfolio_agent.get_portfolio_context(symbol),
                            timeout=advanced_timeout,
                        )
                    # Fallback: use basic analyze with the symbol
                    return {}
                except Exception as e:
                    logger.warning("[%s] Portfolio context failed for %s: %s", self.name, symbol, e)
                    return {"error": str(e)}

            vol_task = asyncio.create_task(_run_volatility())
            tech_task = asyncio.create_task(_run_technical())
            corr_task = asyncio.create_task(_run_correlation())
            port_task = asyncio.create_task(_run_portfolio())

            volatility_data, technical_data, correlation_data, portfolio_context = await asyncio.gather(
                vol_task, tech_task, corr_task, port_task
            )

        # Await ML prediction
        ml_prediction = await ml_task

        # ── Phase 6: Final orchestrated decision (ALL agent data) ──
        try:
            decision = await asyncio.wait_for(
                self.decision_agent.decide(
                    symbol=symbol,
                    market_data=market_data,
                    sentiment_data=sentiment_data,
                    risk_data=risk_data,
                    research_data=research_data,
                    global_macro=global_data,
                    volatility_data=volatility_data,
                    technical_data=technical_data,
                    correlation_data=correlation_data,
                    ml_prediction=ml_prediction,
                    portfolio_context=portfolio_context,
                ),
                timeout=decision_timeout,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.error("[%s] Decision failed for %s: %s", self.name, symbol, exc)
            decision = {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": 0.0,
                "reasoning": f"Decision engine timed out or failed: {exc}. Defaulting to HOLD.",
                "key_factors": ["engine_failure"],
                "position_size_recommendation": "avoid",
            }

        elapsed = round(time.monotonic() - start, 2)
        agents_used = ["MarketAgent", "NewsAgent", "SentimentAgent", "RiskAgent",
                       "ResearchAgent", "GlobalMarketAgent", "MLAgent", "DecisionAgent"]
        if volatility_data and not volatility_data.get("error"):
            agents_used.append("VolatilityAgent")
        if technical_data and not technical_data.get("error"):
            agents_used.append("TechnicalStrategyAgent")
        if correlation_data and not correlation_data.get("error"):
            agents_used.append("CorrelationAgent")
        if portfolio_context and not portfolio_context.get("error"):
            agents_used.append("PortfolioAgent")

        logger.info("[%s] Pipeline complete for %s in %.2fs — %d agents used",
                     self.name, symbol, elapsed, len(agents_used))

        return {
            "symbol": symbol,
            "decision": decision,
            "market_data": market_data,
            "news": news_data,
            "sentiment": sentiment_data,
            "risk": risk_data,
            "research": research_data,
            "global_macro": global_data,
            "ml_prediction": ml_prediction,
            "volatility": volatility_data,
            "technical": technical_data,
            "correlation": correlation_data,
            "portfolio_context": portfolio_context,
            "agents_used": agents_used,
            "elapsed_seconds": elapsed,
        }

    async def _safe_ml_predict(self, symbol: str) -> dict:
        """Run ML prediction with timeout, returning empty dict on failure."""
        try:
            return await asyncio.wait_for(
                self.ml_agent.train_and_predict(symbol),
                timeout=10.0,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("[%s] ML prediction unavailable for %s: %s", self.name, symbol, exc)
            return {}

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
            "BUY", "SELL", "WHAT", "ABOUT", "SHOULD", "STOCK", "ANALYZE",
            "THINK", "TELL", "GIVE", "WITH", "THIS", "THAT", "LOOK", "INTO",
            "FIND", "CURRENT", "STATUS", "GET", "SHOW", "CHECK", "PRICE",
            "NEWS", "COMPARE", "VS", "MARKET", "TODAY", "NOW", "LATEST",
        }
        return [s for s in dict.fromkeys(raw) if s not in stop_words]
