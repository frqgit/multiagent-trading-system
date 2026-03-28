"""Risk Manager Agent — evaluates risk factors and adds constraints.

Enhanced with:
- Configurable risk thresholds from settings
- Daily loss limit tracking
- Auto-stop trading when limits exceeded
- Position sizing constraints
- Trade-level max loss enforcement
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RiskManagerAgent:
    """Evaluates volatility, RSI, beta, MACD, 52-week position, and sentiment to constrain trading decisions.

    Enhanced with configurable risk management:
    - max_loss_per_trade_pct: Maximum loss allowed per individual trade
    - daily_loss_limit_pct: Maximum daily portfolio loss before auto-stop
    - max_position_pct: Maximum portfolio allocation per position
    - auto_stop_loss_pct: Automatic stop-loss percentage for all positions
    """

    name = "RiskManagerAgent"

    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    HIGH_VOLATILITY_THRESHOLD = 40
    HIGH_BETA_THRESHOLD = 1.5
    MAX_RISK_SCORE = 10

    def __init__(self):
        self._daily_pnl: float = 0.0  # Tracks daily P&L as percentage
        self._trading_halted: bool = False
        self._halt_reason: str = ""

        # Load configurable limits from settings
        try:
            from core.config import get_settings
            settings = get_settings()
            self.max_loss_per_trade_pct = settings.max_loss_per_trade_pct
            self.daily_loss_limit_pct = settings.daily_loss_limit_pct
            self.max_position_pct = settings.max_position_pct
            self.auto_stop_loss_pct = settings.auto_stop_loss_pct
        except Exception:
            self.max_loss_per_trade_pct = 2.0
            self.daily_loss_limit_pct = 5.0
            self.max_position_pct = 10.0
            self.auto_stop_loss_pct = 3.0

    def update_daily_pnl(self, pnl_pct: float) -> None:
        """Update the running daily P&L. Call after each trade closes."""
        self._daily_pnl += pnl_pct
        if self._daily_pnl <= -self.daily_loss_limit_pct:
            self._trading_halted = True
            self._halt_reason = (
                f"Daily loss limit reached: {self._daily_pnl:.2f}% "
                f"(limit: -{self.daily_loss_limit_pct:.1f}%)"
            )
            logger.warning("[%s] TRADING HALTED — %s", self.name, self._halt_reason)

    def reset_daily(self) -> None:
        """Reset daily tracking counters (call at start of each trading day)."""
        self._daily_pnl = 0.0
        self._trading_halted = False
        self._halt_reason = ""

    @property
    def is_trading_halted(self) -> bool:
        return self._trading_halted

    def get_position_size_limit(self, portfolio_value: float, current_price: float) -> dict[str, Any]:
        """Calculate maximum position size based on risk limits."""
        max_value = portfolio_value * (self.max_position_pct / 100)
        max_shares = int(max_value / current_price) if current_price > 0 else 0
        stop_loss_price = current_price * (1 - self.auto_stop_loss_pct / 100)
        risk_per_share = current_price - stop_loss_price
        max_risk_value = portfolio_value * (self.max_loss_per_trade_pct / 100)
        risk_based_shares = int(max_risk_value / risk_per_share) if risk_per_share > 0 else max_shares
        recommended = min(max_shares, risk_based_shares)
        return {
            "max_shares_by_position_limit": max_shares,
            "max_shares_by_risk_limit": risk_based_shares,
            "recommended_shares": recommended,
            "max_position_value": round(max_value, 2),
            "auto_stop_loss_price": round(stop_loss_price, 2),
            "max_loss_per_trade": round(max_risk_value, 2),
        }

    async def analyze(self, market_data: dict[str, Any], sentiment_data: dict[str, Any], global_macro: dict[str, Any] | None = None) -> dict[str, Any]:
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

        # --- Global macro risk overlay ---
        if global_macro and global_macro.get("global_regime") != "unknown":
            regime = global_macro.get("global_regime", "mixed")
            vix_assessment = global_macro.get("vix_assessment", "moderate_caution")
            guidance = global_macro.get("buy_sell_guidance", {})
            action_bias = guidance.get("action_bias", "stay_selective")
            macro_risks = global_macro.get("key_macro_risks", [])
            cross_signals = global_macro.get("cross_market_signals", {})

            # Risk-off regime increases risk
            if regime == "risk_off":
                risk_score += 2
                warnings.append("Global regime is risk-off — macro headwinds for equities")
                constraints.append("Risk-off environment: reduce long exposure")
            elif regime == "transitioning":
                risk_score += 1
                warnings.append("Global regime is transitioning — increased uncertainty")

            # VIX elevated or panic
            if vix_assessment in ("elevated_fear", "extreme_panic"):
                risk_score += 1
                vix_level = cross_signals.get("vix_level", "N/A")
                warnings.append(f"VIX at {vix_level} — {vix_assessment.replace('_', ' ')}")
                if vix_assessment == "extreme_panic":
                    constraints.append("Extreme VIX: avoid new positions until volatility subsides")

            # Macro guidance says raise cash or favor selling
            if action_bias in ("favor_selling", "raise_cash"):
                risk_score += 1
                warnings.append(f"Global macro guidance: {action_bias.replace('_', ' ')}")
                constraints.append("Macro environment favors caution — consider reducing positions")

            # Safe haven demand is high
            if cross_signals.get("safe_haven_demand") == "high":
                risk_score += 1
                warnings.append("High safe-haven demand (gold + VIX rising) — flight to safety underway")

            # Weak global breadth
            breadth_label = cross_signals.get("global_breadth_label", "")
            if breadth_label in ("broad_decline", "narrow_participation"):
                risk_score += 1
                warnings.append(f"Global market breadth: {breadth_label.replace('_', ' ')}")

            # Append top macro risks
            for mr in macro_risks[:2]:
                warnings.append(f"Macro risk: {mr}")

        risk_score = min(risk_score, self.MAX_RISK_SCORE)
        risk_level = "low" if risk_score <= 3 else ("medium" if risk_score <= 6 else "high")

        # --- Auto-stop trading check ---
        allow_buy = risk_score < 7
        if self._trading_halted:
            allow_buy = False
            warnings.append(f"⛔ TRADING HALTED: {self._halt_reason}")
            constraints.append("All new positions blocked — daily loss limit hit")

        # --- Position sizing constraints ---
        price = market_data.get("price", 0)
        position_limits = {}
        if price > 0:
            position_limits = {
                "max_position_pct": self.max_position_pct,
                "max_loss_per_trade_pct": self.max_loss_per_trade_pct,
                "auto_stop_loss_pct": self.auto_stop_loss_pct,
                "auto_stop_loss_price": round(price * (1 - self.auto_stop_loss_pct / 100), 2),
            }

        return {
            "symbol": symbol,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "warnings": warnings,
            "constraints": constraints,
            "allow_buy": allow_buy,
            "allow_sell": True,
            "trading_halted": self._trading_halted,
            "daily_pnl_pct": round(self._daily_pnl, 2),
            "risk_limits": {
                "max_loss_per_trade_pct": self.max_loss_per_trade_pct,
                "daily_loss_limit_pct": self.daily_loss_limit_pct,
                "max_position_pct": self.max_position_pct,
                "auto_stop_loss_pct": self.auto_stop_loss_pct,
            },
            "position_limits": position_limits,
        }
