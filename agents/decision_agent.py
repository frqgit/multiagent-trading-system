"""Decision Agent — combines all signals to produce a BUY/SELL/HOLD decision."""

from __future__ import annotations

import logging
from typing import Any

from core.llm import llm_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite Wall Street quantitative analyst and portfolio strategist. You will receive REAL-TIME market data, news sentiment analysis, risk assessment, web research intelligence, and GLOBAL MACRO economic data for a specific stock.

Your job is to produce a rigorous, institution-grade trading decision using ALL available data.

Return a JSON object:
{
  "action": "STRONG_BUY" | "BUY" | "SELL" | "STRONG_SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 paragraph detailed explanation referencing SPECIFIC numbers (price, RSI, MA levels, PE ratio, MACD, VIX, global regime, etc.)",
  "key_factors": ["factor1", "factor2", "factor3", "factor4"],
  "risk_adjusted": true/false,
  "suggested_entry": <price or null>,
  "suggested_stop_loss": <price or null>,
  "target_price": <price or null>,
  "time_horizon": "short-term" | "medium-term" | "long-term",
  "macro_alignment": "aligned" | "neutral" | "conflicting",
  "position_size_recommendation": "full" | "half" | "quarter" | "avoid"
}

RULES:
- ALWAYS reference actual numbers from the data (don't make up prices).
- If risk constraints say "do not buy", set action to HOLD and note it was risk-constrained.
- Confidence below 0.4 should default to HOLD.
- Use STRONG_BUY when technicals, fundamentals, sentiment, AND macro all align bullishly with high confidence.
- Use STRONG_SELL when all signals converge bearishly with high conviction.
- suggested_entry should be near current price for BUY, null for HOLD/SELL.
- suggested_stop_loss should reference the nearest support level (MA or recent low).
- target_price should reference the nearest resistance level for BUY.
- reasoning must be specific, referencing exact indicator values. Never be vague.
- Consider fundamental data (PE, EPS, market cap) alongside technicals.
- If global macro data is available, factor the macro regime, VIX level, sector rotation, and geographic outlook into your decision.
- macro_alignment: "aligned" if stock direction matches macro bias, "conflicting" if against macro, "neutral" otherwise.
- position_size_recommendation: adjust based on risk score, VIX, and macro guidance. "full" for low-risk aligned macro; "avoid" for high-risk conflicting macro."""


class DecisionAgent:
    """Produces the final trading decision by combining all agent outputs."""

    name = "DecisionAgent"

    async def decide(
        self,
        symbol: str,
        market_data: dict[str, Any],
        sentiment_data: dict[str, Any],
        risk_data: dict[str, Any],
        research_data: dict[str, Any] | None = None,
        global_macro: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        logger.info("[%s] Making decision for %s", self.name, symbol)

        # Build a rule-based preliminary signal
        preliminary = self._rule_based_signal(market_data, sentiment_data, risk_data)

        # Build research section
        research_section = ""
        if research_data and research_data.get("research_summary"):
            research_section = f"""
=== WEB RESEARCH INTELLIGENCE ===
Analyst Consensus: {research_data.get('analyst_consensus', 'unknown')}
Average Price Target: {research_data.get('average_price_target', 'N/A')}
Price Target Range: {research_data.get('price_target_range', {}).get('low', 'N/A')} — {research_data.get('price_target_range', {}).get('high', 'N/A')}
Recent Earnings: {research_data.get('recent_earnings_surprise', 'unknown')}
Revenue Trend: {research_data.get('revenue_trend', 'unknown')}
Competitive Position: {research_data.get('competitive_position', 'unknown')}
Insider Activity: {research_data.get('insider_activity', 'unknown')}
Key Developments: {'; '.join(research_data.get('key_developments', []))}
Research Risks: {'; '.join(research_data.get('risks_from_research', []))}
Research Opportunities: {'; '.join(research_data.get('opportunities_from_research', []))}
Research Summary: {research_data.get('research_summary', 'N/A')}
Sources: {research_data.get('sources_searched', 0)} searched, {research_data.get('pages_analyzed', 0)} pages analyzed
"""

        # Build global macro section
        global_section = ""
        if global_macro and global_macro.get("global_regime") != "unknown":
            guidance = global_macro.get("buy_sell_guidance", {})
            cross_signals = global_macro.get("cross_market_signals", {})
            global_section = f"""
=== GLOBAL MACRO ENVIRONMENT ===
Regime: {global_macro.get('global_regime', 'unknown')}
Overall Bias: {global_macro.get('overall_bias', 'neutral')}
Market Cycle Phase: {global_macro.get('market_cycle_phase', 'uncertain')}
VIX Assessment: {global_macro.get('vix_assessment', 'unknown')} (Level: {cross_signals.get('vix_level', 'N/A')})
Sector Rotation: {global_macro.get('sector_rotation_signal', 'mixed')}
Recommended Sectors: {', '.join(global_macro.get('recommended_sectors', []))}
Avoid Sectors: {', '.join(global_macro.get('avoid_sectors', []))}
Risk Appetite: {cross_signals.get('risk_appetite', 'unknown')}
Treasury 10Y: {cross_signals.get('treasury_10y', 'N/A')} (Trend: {cross_signals.get('yield_trend', 'N/A')})
USD Trend: {cross_signals.get('usd_trend', 'N/A')}
Safe Haven Demand: {cross_signals.get('safe_haven_demand', 'N/A')}
Global Breadth: {cross_signals.get('global_breadth_label', 'N/A')}
Oil Pressure: {cross_signals.get('oil_pressure', 'N/A')}
Macro Action Bias: {guidance.get('action_bias', 'stay_selective')}
Position Sizing Guidance: {guidance.get('position_sizing', 'reduced')}
Macro Risks: {'; '.join(global_macro.get('key_macro_risks', []))}
Macro Opportunities: {'; '.join(global_macro.get('key_macro_opportunities', []))}
Macro Summary: {global_macro.get('macro_summary', 'N/A')}
"""

        user_prompt = f"""Stock: {symbol}

=== COMPANY PROFILE ===
Name: {market_data.get('company_name', 'N/A')}
Sector: {market_data.get('sector', 'N/A')}
Market Cap: {market_data.get('market_cap_formatted', 'N/A')}
P/E Ratio: {market_data.get('pe_ratio', 'N/A')}
EPS: {market_data.get('eps', 'N/A')}
Dividend Yield: {market_data.get('dividend_yield', 'N/A')}
Beta: {market_data.get('beta', 'N/A')}

=== TECHNICAL DATA ===
Price: ${market_data.get('price')}
Trend: {market_data.get('trend')}
MA20: {market_data.get('ma20')} | MA50: {market_data.get('ma50')} | MA200: {market_data.get('ma200', 'N/A')}
EMA12: {market_data.get('ema12', 'N/A')} | EMA26: {market_data.get('ema26', 'N/A')}
MACD: {market_data.get('macd', 'N/A')} | MACD Signal: {market_data.get('macd_signal', 'N/A')}
RSI: {market_data.get('rsi')}
Volatility: {market_data.get('volatility')}%
52-Week Range: {market_data.get('week52_low', 'N/A')} - {market_data.get('week52_high', 'N/A')}
Price Change: {market_data.get('price_change_pct')}%
Signals: {', '.join(market_data.get('signals', []))}

=== NEWS SENTIMENT ===
Sentiment: {sentiment_data.get('sentiment')}
Confidence: {sentiment_data.get('confidence')}
Impact: {sentiment_data.get('impact_level')}
Media Tone: {sentiment_data.get('media_tone', 'N/A')}
Themes: {', '.join(sentiment_data.get('key_themes', []))}
Catalysts: {', '.join(sentiment_data.get('catalysts', []))}
Reasoning: {sentiment_data.get('reasoning')}

=== RISK ASSESSMENT ===
Risk Score: {risk_data.get('risk_score')}/10
Risk Level: {risk_data.get('risk_level')}
Warnings: {'; '.join(risk_data.get('warnings', []))}
Constraints: {'; '.join(risk_data.get('constraints', []))}
Allow Buy: {risk_data.get('allow_buy')}

=== PRELIMINARY RULE SIGNAL ===
{preliminary['action']} (confidence: {preliminary['confidence']})
{research_section}
{global_section}
Produce your final institution-grade decision using ALL the data above. If global macro data is available, factor the macro environment into your decision — align sector, risk regime, and position sizing with the global outlook."""

        try:
            result = await llm_json(SYSTEM_PROMPT, user_prompt)
            result["symbol"] = symbol
            result["preliminary_signal"] = preliminary
            # Enforce risk constraints
            if not risk_data.get("allow_buy", True) and result.get("action") in ("BUY", "STRONG_BUY"):
                result["action"] = "HOLD"
                result["risk_adjusted"] = True
                result["reasoning"] += " [OVERRIDDEN: Risk constraints prevent BUY]"
            return result
        except Exception as exc:
            logger.error("[%s] Decision failed: %s", self.name, exc)
            return {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": 0.0,
                "reasoning": f"Decision engine failed: {exc}",
                "key_factors": [],
                "error": str(exc),
            }

    @staticmethod
    def _rule_based_signal(
        market: dict[str, Any],
        sentiment: dict[str, Any],
        risk: dict[str, Any],
    ) -> dict[str, Any]:
        """Simple rule-based heuristic as a preliminary signal."""
        score = 0  # positive = bullish, negative = bearish

        # Trend
        trend = market.get("trend", "sideways")
        if trend == "bullish":
            score += 2
        elif trend == "bearish":
            score -= 2

        # RSI
        rsi = market.get("rsi", 50)
        if rsi < 30:
            score += 2  # oversold = potential buy
        elif rsi > 70:
            score -= 2  # overbought = potential sell

        # MA crossover
        if market.get("ma20", 0) > market.get("ma50", 0):
            score += 1
        else:
            score -= 1

        # Sentiment
        sent = sentiment.get("sentiment", "neutral")
        if sent == "positive":
            score += 2
        elif sent == "negative":
            score -= 2

        # Risk
        if risk.get("risk_level") == "high":
            score -= 1

        if score >= 3:
            return {"action": "BUY", "confidence": min(0.5 + score * 0.05, 0.85)}
        elif score <= -3:
            return {"action": "SELL", "confidence": min(0.5 + abs(score) * 0.05, 0.85)}
        else:
            return {"action": "HOLD", "confidence": 0.5}
