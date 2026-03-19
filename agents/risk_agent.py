"""Risk Manager Agent — evaluates risk factors and adds constraints."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RiskManagerAgent:
    """Evaluates volatility, RSI, beta, MACD, 52-week position, and sentiment to constrain trading decisions."""

    name = "RiskManagerAgent"

    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    HIGH_VOLATILITY_THRESHOLD = 40
    HIGH_BETA_THRESHOLD = 1.5
    MAX_RISK_SCORE = 10

    async def analyze(self, market_data: dict[str, Any], sentiment_data: dict[str, Any]) -> dict[str, Any]:
        symbol = market_data.get("symbol", "UNKNOWN")
        logger.info("[%s] Evaluating risk for %s", self.name, symbol)

        risk_score = 0
        warnings: list[str] = []
        constraints: list[str] = []

        # --- Volatility risk ---
        volatility = market_data.get("volatility", 0)
        if volatility > self.HIGH_VOLATILITY_THRESHOLD:
            risk_score += 3
            warnings.append(f"High volatility: {volatility:.1f}% annualized")
            constraints.append("Reduce position size due to high volatility")
        elif volatility > 25:
            risk_score += 1
            warnings.append(f"Elevated volatility: {volatility:.1f}%")

        # --- Beta risk ---
        beta = market_data.get("beta")
        if beta is not None:
            if beta > self.HIGH_BETA_THRESHOLD:
                risk_score += 2
                warnings.append(f"High beta ({beta:.2f}): stock amplifies market moves")
                constraints.append("High beta: reduce position size in uncertain markets")
            elif beta > 1.2:
                risk_score += 1
                warnings.append(f"Above-average beta ({beta:.2f})")

        # --- RSI risk ---
        rsi = market_data.get("rsi", 50)
        if rsi > self.RSI_OVERBOUGHT:
            risk_score += 2
            warnings.append(f"RSI {rsi:.1f} — overbought territory")
            constraints.append("Overbought: consider waiting for pullback before buying")
        elif rsi < self.RSI_OVERSOLD:
            risk_score += 1
            warnings.append(f"RSI {rsi:.1f} — oversold; potential reversal zone")

        # --- Trend risk ---
        trend = market_data.get("trend", "sideways")
        if trend in ("bearish", "strong_bearish"):
            risk_score += 2
            warnings.append(f"Bearish trend detected ({trend})")
            constraints.append("Bearish trend: avoid large long positions")
        elif trend == "sideways":
            risk_score += 1
            warnings.append("No clear trend — sideways movement")

        # --- MACD divergence risk ---
        macd = market_data.get("macd")
        macd_signal = market_data.get("macd_signal")
        if macd is not None and macd_signal is not None:
            if macd < macd_signal and macd < 0:
                risk_score += 1
                warnings.append(f"MACD bearish ({macd:.2f} < signal {macd_signal:.2f})")

        # --- 52-week position risk ---
        price = market_data.get("price", 0)
        w52_high = market_data.get("week52_high")
        w52_low = market_data.get("week52_low")
        if w52_high and w52_low and price and w52_high > w52_low:
            position = (price - w52_low) / (w52_high - w52_low)
            if position > 0.95:
                risk_score += 2
                warnings.append(f"Trading near 52-week high ({position:.0%} of range)")
                constraints.append("Near 52-week high: limited upside, elevated downside risk")
            elif position < 0.10:
                warnings.append(f"Near 52-week low ({position:.0%} of range) — potential value or falling knife")

        # --- Sentiment risk ---
        sentiment = sentiment_data.get("sentiment", "neutral")
        impact = sentiment_data.get("impact_level", "low")
        if sentiment in ("negative", "strongly_negative") and impact in ("high", "critical"):
            risk_score += 3
            warnings.append(f"Strongly negative sentiment with {impact} impact")
            constraints.append("Negative high-impact news: strongly avoid buying")
        elif sentiment in ("negative", "strongly_negative"):
            risk_score += 1
            warnings.append("Negative sentiment detected")
        elif sentiment == "mixed":
            risk_score += 1
            warnings.append("Mixed market sentiment")

        # --- Price change spike ---
        pct_change = abs(market_data.get("price_change_pct", 0))
        if pct_change > 5:
            risk_score += 2
            warnings.append(f"Large price move: {market_data.get('price_change_pct')}% in last session")
            constraints.append("Extreme price movement: wait for stabilization")

        # --- Valuation risk (PE) ---
        pe = market_data.get("pe_ratio")
        if pe is not None:
            if pe > 50:
                risk_score += 1
                warnings.append(f"High P/E ratio ({pe:.1f}): expensive valuation")
            elif pe < 0:
                risk_score += 1
                warnings.append(f"Negative P/E ({pe:.1f}): company not profitable")

        risk_score = min(risk_score, self.MAX_RISK_SCORE)
        risk_level = "low" if risk_score <= 3 else ("medium" if risk_score <= 6 else "high")

        return {
            "symbol": symbol,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "warnings": warnings,
            "constraints": constraints,
            "allow_buy": risk_score < 7,
            "allow_sell": True,
        }
