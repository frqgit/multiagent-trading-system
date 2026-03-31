"""Decision Agent — combines all signals to produce a final 4-tier trading decision.

Outputs one of: STRONG_BUY, BUY, SELL, STRONG_SELL (no HOLD)."""

from __future__ import annotations

import logging
from typing import Any

from core.llm import llm_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite Wall Street quantitative analyst and portfolio strategist. You will receive REAL-TIME market data, news sentiment analysis, risk assessment, web research intelligence, and GLOBAL MACRO economic data for a specific stock.

Your job is to produce a rigorous, institution-grade trading decision using ALL available data.

You MUST choose ONE of exactly four actions. There is no HOLD — every analysis must commit to a directional view.

Return a JSON object:
{
  "action": "STRONG_BUY" | "BUY" | "SELL" | "STRONG_SELL",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-3 paragraph detailed explanation referencing SPECIFIC numbers (price, RSI, MA levels, PE ratio, MACD, VIX, global regime, volatility, technical patterns, correlation data, ML prediction, etc.)",
  "key_factors": ["factor1", "factor2", "factor3", "factor4", "factor5"],
  "risk_adjusted": true/false,
  "suggested_entry": <price or null>,
  "suggested_stop_loss": <price or null>,
  "target_price": <price or null>,
  "time_horizon": "short-term" | "medium-term" | "long-term",
  "macro_alignment": "aligned" | "neutral" | "conflicting",
  "position_size_recommendation": "full" | "half" | "quarter" | "minimal",
  "agent_consensus": {
    "technical": "bullish" | "bearish",
    "fundamental": "bullish" | "bearish",
    "sentiment": "bullish" | "bearish",
    "macro": "bullish" | "bearish",
    "ml_prediction": "bullish" | "bearish",
    "risk": "low" | "medium" | "high",
    "volatility": "low" | "medium" | "high"
  }
}

RULES:
- You MUST pick one of: STRONG_BUY, BUY, SELL, STRONG_SELL. Never output HOLD.
- If the signal is ambiguous or mixed, lean toward BUY if slightly bullish or SELL if slightly bearish. Commit to a direction.
- ALWAYS reference actual numbers from the data (don't make up prices).
- If risk constraints say "do not buy", use SELL (low confidence) and note it was risk-constrained.
- Use STRONG_BUY when technicals, fundamentals, sentiment, macro, ML, AND volatility all align bullishly with high confidence.
- Use STRONG_SELL when all signals converge bearishly with high conviction.
- Use BUY for moderate bullish conviction, SELL for moderate bearish conviction.
- suggested_entry should be near current price for BUY/STRONG_BUY, null for SELL/STRONG_SELL.
- suggested_stop_loss should reference the nearest support level (MA or recent low).
- target_price should reference the nearest resistance level for BUY.
- reasoning must be specific, referencing exact indicator values from ALL agents. Never be vague.
- Consider fundamental data (PE, EPS, market cap) alongside technicals.
- Factor in volatility regime, technical patterns, correlation data, and ML predictions when available.
- If global macro data is available, factor the macro regime, VIX level, sector rotation, and geographic outlook into your decision.
- macro_alignment: "aligned" if stock direction matches macro bias, "conflicting" if against macro, "neutral" otherwise.
- position_size_recommendation: adjust based on risk score, VIX, and macro guidance. "full" for low-risk aligned macro; "minimal" for high-risk conflicting macro.
- agent_consensus: summarize each agent's directional view so the user can see which agents agree/disagree."""


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
        volatility_data: dict[str, Any] | None = None,
        technical_data: dict[str, Any] | None = None,
        correlation_data: dict[str, Any] | None = None,
        ml_prediction: dict[str, Any] | None = None,
        portfolio_context: dict[str, Any] | None = None,
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

        # Build volatility section
        volatility_section = ""
        if volatility_data and not volatility_data.get("error"):
            volatility_section = f"""
=== VOLATILITY ANALYSIS ===
Current Volatility: {volatility_data.get('current_volatility', 'N/A')}
Volatility Regime: {volatility_data.get('regime', 'N/A')}
GARCH Forecast: {volatility_data.get('garch_forecast', 'N/A')}
Volatility Percentile: {volatility_data.get('percentile', 'N/A')}
Implied vs Realized: {volatility_data.get('iv_rv_spread', 'N/A')}
"""

        # Build technical analysis section
        technical_section = ""
        if technical_data and not technical_data.get("error"):
            signals = technical_data.get('signals', {})
            patterns = technical_data.get('patterns', [])
            overall = technical_data.get('overall_signal', {})
            technical_section = f"""
=== ADVANCED TECHNICAL ANALYSIS ===
Overall Signal: {overall.get('signal', 'N/A')} (Confidence: {overall.get('confidence', 'N/A')})
Strategy Signals: {'; '.join(f"{k}: {v}" for k, v in signals.items()) if signals else 'N/A'}
Chart Patterns: {', '.join(str(p) for p in patterns[:5]) if patterns else 'None detected'}
Support Levels: {technical_data.get('support_levels', 'N/A')}
Resistance Levels: {technical_data.get('resistance_levels', 'N/A')}
"""

        # Build correlation section
        correlation_section = ""
        if correlation_data and not correlation_data.get("error"):
            correlation_section = f"""
=== CORRELATION & PORTFOLIO CONTEXT ===
Sector Correlation: {correlation_data.get('sector_correlation', 'N/A')}
Market Beta: {correlation_data.get('market_beta', 'N/A')}
Diversification Score: {correlation_data.get('diversification_score', 'N/A')}
Correlated Pairs: {correlation_data.get('top_pairs', 'N/A')}
"""

        # Build ML prediction section
        ml_section = ""
        if ml_prediction and not ml_prediction.get("error"):
            ml_section = f"""
=== ML PREDICTION ===
ML Signal: {ml_prediction.get('prediction', 'N/A')}
ML Confidence: {ml_prediction.get('confidence', 'N/A')}
Method: {ml_prediction.get('method', 'N/A')}
Probabilities: {ml_prediction.get('probabilities', 'N/A')}
Key Features: {ml_prediction.get('key_features', 'N/A')}
"""

        # Build portfolio context section
        portfolio_section = ""
        if portfolio_context and not portfolio_context.get("error"):
            portfolio_section = f"""
=== PORTFOLIO CONTEXT ===
Current Allocation: {portfolio_context.get('current_allocation', 'N/A')}
Optimal Weight: {portfolio_context.get('optimal_weight', 'N/A')}
Portfolio Risk Contribution: {portfolio_context.get('risk_contribution', 'N/A')}
Rebalance Needed: {portfolio_context.get('rebalance_needed', 'N/A')}
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
{volatility_section}
{technical_section}
{correlation_section}
{ml_section}
{portfolio_section}
Produce your final institution-grade decision using ALL the data above. You MUST choose one of: STRONG_BUY, BUY, SELL, or STRONG_SELL. There is no HOLD option — commit to a directional view.
Factor in ALL agent data: market technicals, sentiment, risk, research, global macro, volatility regime, advanced technical patterns, correlations, ML predictions, and portfolio context.
Summarize each agent's view in the agent_consensus field."""

        try:
            result = await llm_json(SYSTEM_PROMPT, user_prompt)
            result["symbol"] = symbol
            result["preliminary_signal"] = preliminary
            # Enforce risk constraints — convert to SELL if buying is blocked
            if not risk_data.get("allow_buy", True) and result.get("action") in ("BUY", "STRONG_BUY"):
                result["action"] = "SELL"
                result["confidence"] = max(0.3, result.get("confidence", 0.5) * 0.5)
                result["risk_adjusted"] = True
                result["reasoning"] += " [OVERRIDDEN: Risk constraints prevent BUY — converted to SELL]"
            # Ensure no HOLD slips through from LLM
            if result.get("action") == "HOLD":
                # Convert HOLD to the preliminary signal direction
                if preliminary.get("action") == "BUY":
                    result["action"] = "BUY"
                elif preliminary.get("action") == "SELL":
                    result["action"] = "SELL"
                else:
                    result["action"] = "BUY"  # default to low-confidence BUY
                result["confidence"] = max(0.2, result.get("confidence", 0.3) * 0.6)
            return result
        except Exception as exc:
            logger.error("[%s] Decision failed: %s", self.name, exc)
            return {
                "symbol": symbol,
                "action": "SELL",
                "confidence": 0.1,
                "reasoning": f"Decision engine failed: {exc}. Defaulting to SELL with minimal confidence as a safety measure.",
                "key_factors": ["engine_failure"],
                "error": str(exc),
                "position_size_recommendation": "minimal",
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

        if score >= 5:
            return {"action": "STRONG_BUY", "confidence": min(0.7 + score * 0.03, 0.95)}
        elif score >= 2:
            return {"action": "BUY", "confidence": min(0.5 + score * 0.05, 0.85)}
        elif score <= -5:
            return {"action": "STRONG_SELL", "confidence": min(0.7 + abs(score) * 0.03, 0.95)}
        elif score <= -2:
            return {"action": "SELL", "confidence": min(0.5 + abs(score) * 0.05, 0.85)}
        elif score >= 0:
            return {"action": "BUY", "confidence": 0.35}
        else:
            return {"action": "SELL", "confidence": 0.35}
