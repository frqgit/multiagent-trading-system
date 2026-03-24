"""Global Market Advisor Agent — analyzes global economic conditions and cross-market
signals to provide macro-aware BUY/SELL recommendations.

This agent gathers data on:
- Major global indices (S&P 500, NASDAQ, Dow, FTSE, Nikkei, DAX, etc.)
- Key economic indicators (Treasury yields, VIX, USD strength, oil, gold)
- Cross-market correlations and sector rotation signals
- Global risk appetite and macro regime detection

It then produces an actionable macro overlay that the orchestrator combines
with stock-specific analysis for better-informed trading decisions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from core.llm import llm_json
from tools.web_tools import web_search

logger = logging.getLogger(__name__)

# ── Major global market tickers (all available via yfinance) ───────────────
_GLOBAL_INDICES = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ Composite",
    "^DJI": "Dow Jones",
    "^VIX": "CBOE Volatility Index (VIX)",
    "^FTSE": "FTSE 100 (UK)",
    "^N225": "Nikkei 225 (Japan)",
    "^GDAXI": "DAX (Germany)",
    "^HSI": "Hang Seng (Hong Kong)",
}

_MACRO_TICKERS = {
    "^TNX": "10-Year Treasury Yield",
    "DX-Y.NYB": "US Dollar Index",
    "GC=F": "Gold Futures",
    "CL=F": "Crude Oil WTI",
    "BTC-USD": "Bitcoin",
}

# ── LLM Prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior global macro strategist at a world-class investment bank. You will receive real-time data on major global indices, commodities, currencies, and volatility measures, along with recent global economic news.

Your task: produce a rigorous macro-economic assessment and actionable advice.

Return a JSON object:
{
  "global_regime": "risk_on" | "risk_off" | "mixed" | "transitioning",
  "regime_confidence": 0.0 to 1.0,
  "market_cycle_phase": "expansion" | "peak" | "contraction" | "trough" | "uncertain",
  "overall_bias": "bullish" | "bearish" | "neutral" | "cautiously_bullish" | "cautiously_bearish",
  "vix_assessment": "low_fear" | "moderate_caution" | "elevated_fear" | "extreme_panic",
  "sector_rotation_signal": "offensive" | "defensive" | "mixed",
  "recommended_sectors": ["sector1", "sector2", "sector3"],
  "avoid_sectors": ["sector1", "sector2"],
  "geographic_outlook": {
    "us": "positive" | "neutral" | "negative",
    "europe": "positive" | "neutral" | "negative",
    "asia": "positive" | "neutral" | "negative",
    "emerging": "positive" | "neutral" | "negative"
  },
  "key_macro_risks": ["risk1", "risk2", "risk3"],
  "key_macro_opportunities": ["opportunity1", "opportunity2"],
  "buy_sell_guidance": {
    "action_bias": "favor_buying" | "favor_selling" | "stay_selective" | "raise_cash",
    "position_sizing": "full" | "reduced" | "minimal",
    "rationale": "2-3 sentence explanation of the macro stance"
  },
  "macro_summary": "3-5 sentence comprehensive global market summary referencing specific data points (index levels, VIX, yields, oil, USD)"
}

RULES:
- Reference ACTUAL numbers from the data (index levels, percentage changes, VIX level, yield, etc.).
- VIX below 15 = low fear; 15-20 = moderate; 20-30 = elevated; above 30 = panic.
- Rising Treasury yields + falling equities = risk-off signal.
- Strong USD usually pressures emerging markets and commodities.
- Gold rising + VIX rising = flight to safety.
- Consider sector rotation: defensive (utilities, healthcare, staples) vs offensive (tech, discretionary, financials).
- Be specific and quantitative — never vague."""


class GlobalMarketAdvisorAgent:
    """Evaluates global market conditions to provide macro-aware BUY/SELL guidance."""

    name = "GlobalMarketAdvisorAgent"

    async def analyze(self, target_symbol: str | None = None) -> dict[str, Any]:
        """Run full global macro analysis.

        Args:
            target_symbol: Optional stock symbol for contextualizing the advice.
        """
        start = time.monotonic()
        logger.info("[%s] Starting global market analysis", self.name)

        # Phase 1: Fetch global index and macro data in parallel
        index_data, macro_data = await asyncio.gather(
            self._fetch_indices(),
            self._fetch_macro_indicators(),
        )

        # Phase 2: Fetch recent global economic news
        news_context = await self._fetch_global_news()

        # Phase 3: Compute cross-market signals
        cross_signals = self._compute_cross_market_signals(index_data, macro_data)

        # Phase 4: LLM synthesis
        assessment = await self._synthesize(
            index_data, macro_data, news_context, cross_signals, target_symbol
        )

        elapsed = round(time.monotonic() - start, 2)
        assessment["elapsed_seconds"] = elapsed
        assessment["indices_fetched"] = len(index_data)
        assessment["macro_fetched"] = len(macro_data)
        assessment["cross_market_signals"] = cross_signals

        logger.info("[%s] Global analysis complete in %.2fs", self.name, elapsed)
        return assessment

    # ── Data fetching ──────────────────────────────────────────────────────

    async def _fetch_indices(self) -> dict[str, dict[str, Any]]:
        """Fetch major global index data."""
        results = {}
        tasks = {
            ticker: asyncio.create_task(self._fetch_ticker(ticker, name))
            for ticker, name in _GLOBAL_INDICES.items()
        }
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for ticker, data in zip(tasks.keys(), gathered):
            if isinstance(data, Exception):
                logger.warning("[%s] Failed to fetch index %s: %s", self.name, ticker, data)
                results[ticker] = {"name": _GLOBAL_INDICES[ticker], "error": str(data)}
            else:
                results[ticker] = data
        return results

    async def _fetch_macro_indicators(self) -> dict[str, dict[str, Any]]:
        """Fetch macro indicator data (yields, USD, gold, oil, crypto)."""
        results = {}
        tasks = {
            ticker: asyncio.create_task(self._fetch_ticker(ticker, name))
            for ticker, name in _MACRO_TICKERS.items()
        }
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for ticker, data in zip(tasks.keys(), gathered):
            if isinstance(data, Exception):
                logger.warning("[%s] Failed to fetch macro %s: %s", self.name, ticker, data)
                results[ticker] = {"name": _MACRO_TICKERS[ticker], "error": str(data)}
            else:
                results[ticker] = data
        return results

    async def _fetch_ticker(self, ticker: str, name: str) -> dict[str, Any]:
        """Fetch a single ticker's recent data using yfinance."""
        import numpy as np
        import yfinance as yf

        def _do_fetch():
            t = yf.Ticker(ticker)
            hist = t.history(period="1mo")
            if hist.empty:
                raise ValueError(f"No data for {ticker}")
            closes = hist["Close"].values.astype(float)
            current = float(closes[-1])
            prev = float(closes[-2]) if len(closes) >= 2 else current
            change = current - prev
            change_pct = (change / prev * 100) if prev else 0
            # 5-day and 20-day change
            change_5d = ((current - float(closes[-5])) / float(closes[-5]) * 100) if len(closes) >= 5 else 0
            change_20d = ((current - float(closes[0])) / float(closes[0]) * 100) if len(closes) >= 2 else 0
            # Simple volatility
            if len(closes) > 1:
                daily_ret = np.diff(closes) / closes[:-1]
                vol = float(np.std(daily_ret) * np.sqrt(252) * 100)
            else:
                vol = 0.0
            return {
                "name": name,
                "ticker": ticker,
                "price": round(current, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "change_5d_pct": round(change_5d, 2),
                "change_20d_pct": round(change_20d, 2),
                "volatility": round(vol, 2),
                "high_20d": round(float(np.max(closes)), 2),
                "low_20d": round(float(np.min(closes)), 2),
            }

        return await asyncio.to_thread(_do_fetch)

    async def _fetch_global_news(self) -> str:
        """Fetch recent global economy news via web search."""
        queries = [
            "global economy outlook markets today",
            "Federal Reserve interest rates policy latest",
        ]
        all_snippets = []
        for q in queries:
            try:
                results = await asyncio.wait_for(
                    web_search(q, max_results=3),
                    timeout=8.0,
                )
                for r in results:
                    snippet = r.get("snippet", "")
                    title = r.get("title", "")
                    if snippet:
                        all_snippets.append(f"• {title}: {snippet}")
            except (asyncio.TimeoutError, Exception) as exc:
                logger.warning("[%s] Global news search failed for '%s': %s", self.name, q, exc)

        return "\n".join(all_snippets) if all_snippets else "No recent global news available."

    # ── Cross-market signal computation ────────────────────────────────────

    def _compute_cross_market_signals(
        self,
        indices: dict[str, dict[str, Any]],
        macro: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute rule-based cross-market signals from the data."""
        signals = {}

        # VIX regime
        vix = macro.get("^VIX", {})
        vix_level = vix.get("price", 20)
        if vix_level < 15:
            signals["vix_regime"] = "complacent"
        elif vix_level < 20:
            signals["vix_regime"] = "normal"
        elif vix_level < 30:
            signals["vix_regime"] = "elevated"
        else:
            signals["vix_regime"] = "panic"
        signals["vix_level"] = vix_level

        # Risk appetite: positive equity indices + low VIX = risk-on
        sp500 = indices.get("^GSPC", {})
        nasdaq = indices.get("^IXIC", {})
        sp_change = sp500.get("change_5d_pct", 0)
        nq_change = nasdaq.get("change_5d_pct", 0)
        if sp_change > 1 and nq_change > 1 and vix_level < 20:
            signals["risk_appetite"] = "strong"
        elif sp_change < -1 and nq_change < -1 and vix_level > 20:
            signals["risk_appetite"] = "weak"
        else:
            signals["risk_appetite"] = "moderate"

        # Treasury yield direction
        tnx = macro.get("^TNX", {})
        yield_change = tnx.get("change_5d_pct", 0)
        if yield_change > 3:
            signals["yield_trend"] = "rising_sharply"
        elif yield_change > 0:
            signals["yield_trend"] = "rising"
        elif yield_change > -3:
            signals["yield_trend"] = "falling"
        else:
            signals["yield_trend"] = "falling_sharply"
        signals["treasury_10y"] = tnx.get("price", 0)

        # USD strength
        dxy = macro.get("DX-Y.NYB", {})
        usd_change = dxy.get("change_5d_pct", 0)
        if usd_change > 1:
            signals["usd_trend"] = "strengthening"
        elif usd_change < -1:
            signals["usd_trend"] = "weakening"
        else:
            signals["usd_trend"] = "stable"

        # Safe haven demand: gold up + VIX up = flight to safety
        gold = macro.get("GC=F", {})
        gold_change = gold.get("change_5d_pct", 0)
        vix_change = vix.get("change_5d_pct", 0)
        if gold_change > 1 and vix_change > 5:
            signals["safe_haven_demand"] = "high"
        elif gold_change > 0 and vix_change > 0:
            signals["safe_haven_demand"] = "moderate"
        else:
            signals["safe_haven_demand"] = "low"

        # Global breadth: how many indices are positive
        positive_count = 0
        total_count = 0
        for data in indices.values():
            if "error" not in data:
                total_count += 1
                if data.get("change_5d_pct", 0) > 0:
                    positive_count += 1
        if total_count > 0:
            breadth = positive_count / total_count
            signals["global_breadth"] = round(breadth, 2)
            signals["global_breadth_label"] = (
                "broad_rally" if breadth > 0.75 else
                "moderate_participation" if breadth > 0.5 else
                "narrow_participation" if breadth > 0.25 else
                "broad_decline"
            )
        else:
            signals["global_breadth"] = 0
            signals["global_breadth_label"] = "no_data"

        # Oil pressure
        oil = macro.get("CL=F", {})
        oil_change = oil.get("change_5d_pct", 0)
        if oil_change > 5:
            signals["oil_pressure"] = "rising_sharply"
        elif oil_change > 1:
            signals["oil_pressure"] = "rising"
        elif oil_change < -5:
            signals["oil_pressure"] = "falling_sharply"
        elif oil_change < -1:
            signals["oil_pressure"] = "falling"
        else:
            signals["oil_pressure"] = "stable"

        return signals

    # ── LLM synthesis ──────────────────────────────────────────────────────

    async def _synthesize(
        self,
        indices: dict[str, dict[str, Any]],
        macro: dict[str, dict[str, Any]],
        news: str,
        cross_signals: dict[str, Any],
        target_symbol: str | None,
    ) -> dict[str, Any]:
        """Use LLM to produce the global macro assessment."""

        # Build data text for context
        idx_text = ""
        for ticker, data in indices.items():
            if "error" in data:
                idx_text += f"  {data.get('name', ticker)}: DATA UNAVAILABLE\n"
                continue
            idx_text += (
                f"  {data['name']} ({ticker}): {data['price']} "
                f"(1d: {data['change_pct']:+.2f}%, 5d: {data['change_5d_pct']:+.2f}%, "
                f"20d: {data['change_20d_pct']:+.2f}%) "
                f"Vol: {data['volatility']:.1f}%\n"
            )

        macro_text = ""
        for ticker, data in macro.items():
            if "error" in data:
                macro_text += f"  {data.get('name', ticker)}: DATA UNAVAILABLE\n"
                continue
            macro_text += (
                f"  {data['name']} ({ticker}): {data['price']} "
                f"(1d: {data['change_pct']:+.2f}%, 5d: {data['change_5d_pct']:+.2f}%, "
                f"20d: {data['change_20d_pct']:+.2f}%)\n"
            )

        signals_text = "\n".join(f"  {k}: {v}" for k, v in cross_signals.items())

        target_line = f"\nThe user is specifically considering: {target_symbol}. Factor this into your sector and geographic advice." if target_symbol else ""

        user_prompt = f"""=== GLOBAL INDICES (Real-Time) ===
{idx_text}
=== MACRO INDICATORS ===
{macro_text}
=== CROSS-MARKET SIGNALS (Computed) ===
{signals_text}

=== RECENT GLOBAL ECONOMIC NEWS ===
{news}
{target_line}

Produce your global macro assessment and actionable guidance based on ALL the above data."""

        try:
            result = await llm_json(_SYSTEM_PROMPT, user_prompt)
            return result
        except Exception as exc:
            logger.error("[%s] LLM synthesis failed: %s", self.name, exc)
            # Produce a rule-based fallback from cross signals
            return self._fallback_assessment(cross_signals)

    def _fallback_assessment(self, signals: dict[str, Any]) -> dict[str, Any]:
        """Produce a basic assessment when LLM is unavailable."""
        vix = signals.get("vix_level", 20)
        appetite = signals.get("risk_appetite", "moderate")
        breadth_label = signals.get("global_breadth_label", "no_data")

        if appetite == "strong" and vix < 20:
            bias = "bullish"
            regime = "risk_on"
            action = "favor_buying"
            sizing = "full"
        elif appetite == "weak" or vix > 25:
            bias = "bearish"
            regime = "risk_off"
            action = "favor_selling"
            sizing = "reduced"
        else:
            bias = "neutral"
            regime = "mixed"
            action = "stay_selective"
            sizing = "reduced"

        return {
            "global_regime": regime,
            "regime_confidence": 0.4,
            "market_cycle_phase": "uncertain",
            "overall_bias": bias,
            "vix_assessment": signals.get("vix_regime", "moderate_caution"),
            "sector_rotation_signal": "mixed",
            "recommended_sectors": [],
            "avoid_sectors": [],
            "geographic_outlook": {
                "us": "neutral", "europe": "neutral",
                "asia": "neutral", "emerging": "neutral",
            },
            "key_macro_risks": ["LLM unavailable — limited analysis"],
            "key_macro_opportunities": [],
            "buy_sell_guidance": {
                "action_bias": action,
                "position_sizing": sizing,
                "rationale": (
                    f"Rule-based assessment: VIX at {vix}, risk appetite is {appetite}, "
                    f"global breadth is {breadth_label}. AI synthesis unavailable."
                ),
            },
            "macro_summary": (
                f"Global markets show {appetite} risk appetite with VIX at {vix}. "
                f"Market breadth is {breadth_label}. Detailed AI analysis unavailable."
            ),
        }

    def empty_result(self, reason: str = "Global analysis unavailable") -> dict[str, Any]:
        """Return a safe empty result when the agent cannot run."""
        return {
            "global_regime": "unknown",
            "regime_confidence": 0.0,
            "market_cycle_phase": "uncertain",
            "overall_bias": "neutral",
            "vix_assessment": "unknown",
            "sector_rotation_signal": "mixed",
            "recommended_sectors": [],
            "avoid_sectors": [],
            "geographic_outlook": {
                "us": "neutral", "europe": "neutral",
                "asia": "neutral", "emerging": "neutral",
            },
            "key_macro_risks": [reason],
            "key_macro_opportunities": [],
            "buy_sell_guidance": {
                "action_bias": "stay_selective",
                "position_sizing": "reduced",
                "rationale": reason,
            },
            "macro_summary": reason,
            "cross_market_signals": {},
            "indices_fetched": 0,
            "macro_fetched": 0,
            "elapsed_seconds": 0,
        }
