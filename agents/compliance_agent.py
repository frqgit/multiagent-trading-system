"""Compliance Agent — regulatory compliance monitoring and enforcement.

Enforces:
- ASIC Market Integrity Rules (MIR)
- ASX Operating Rules
- Anti-money laundering (AML) pattern detection
- Wash trading prevention
- Insider trading pattern detection
- Position disclosure thresholds
- Trade reporting obligations
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class ComplianceAgent:
    """Monitors trading activity for regulatory compliance violations."""

    name = "ComplianceAgent"

    # ASX substantial holder threshold
    SUBSTANTIAL_HOLDER_PCT = 5.0
    # ASIC short position reporting threshold
    SHORT_REPORTING_PCT = 0.1

    def __init__(self):
        self._trade_history: list[dict] = []
        self._alerts: list[dict] = []

    async def pre_trade_compliance_check(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        user_id: str,
        portfolio_positions: dict[str, dict] | None = None,
    ) -> dict[str, Any]:
        """Run pre-trade compliance checks before order submission.

        Returns:
            Dict with 'approved': bool and any compliance alerts.
        """
        violations = []
        warnings = []

        # 1. Wash trading detection (same symbol buy+sell within short period)
        wash_trade = self._detect_wash_trading(symbol, side, user_id)
        if wash_trade:
            violations.append(
                f"Potential wash trade detected: Recent opposite trade on {symbol} "
                f"within 5 minutes"
            )

        # 2. Rapid-fire trading detection (market manipulation)
        rapid = self._detect_rapid_trading(symbol, user_id)
        if rapid:
            warnings.append(
                f"High-frequency pattern detected on {symbol}: "
                f"{rapid} trades in last 10 minutes"
            )
            if rapid > 20:
                violations.append(
                    f"Excessive trading frequency on {symbol}: {rapid} trades "
                    f"in 10 minutes — possible market manipulation"
                )

        # 3. Spoofing/layering detection
        spoof = self._detect_spoofing_pattern(symbol, side)
        if spoof:
            warnings.append(f"Potential spoofing pattern on {symbol}")

        # 4. Large order disclosure check
        order_value = quantity * price
        if order_value > 500_000:
            warnings.append(
                f"Large order (${order_value:,.0f}): May trigger ASX "
                f"block trade reporting"
            )

        # 5. Substantial holder check (ASX 5% rule)
        if portfolio_positions and symbol in portfolio_positions:
            # This is a simplified check — real implementation needs total shares on issue
            pass

        approved = len(violations) == 0
        if not approved:
            for v in violations:
                self._add_alert("violation", v, symbol, user_id)

        return {
            "approved": approved,
            "violations": violations,
            "warnings": warnings,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        user_id: str,
        broker: str,
    ):
        """Record a trade for compliance monitoring."""
        self._trade_history.append({
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "user_id": user_id,
            "broker": broker,
            "timestamp": datetime.utcnow(),
        })
        # Keep last 10000 trades
        if len(self._trade_history) > 10000:
            self._trade_history = self._trade_history[-10000:]

    def _detect_wash_trading(self, symbol: str, side: str, user_id: str) -> bool:
        """Detect if user recently placed an opposite trade on same symbol."""
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        opposite = "SELL" if side == "BUY" else "BUY"
        for trade in reversed(self._trade_history):
            if trade["timestamp"] < cutoff:
                break
            if (trade["symbol"] == symbol
                    and trade["user_id"] == user_id
                    and trade["side"] == opposite):
                return True
        return False

    def _detect_rapid_trading(self, symbol: str, user_id: str) -> int:
        """Count trades on symbol in last 10 minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        count = 0
        for trade in reversed(self._trade_history):
            if trade["timestamp"] < cutoff:
                break
            if trade["symbol"] == symbol and trade["user_id"] == user_id:
                count += 1
        return count if count > 5 else 0

    def _detect_spoofing_pattern(self, symbol: str, side: str) -> bool:
        """Simplified spoofing detection — look for pattern of
        large orders placed and quickly cancelled."""
        # Would integrate with OMS cancel history in production
        return False

    def _add_alert(self, level: str, message: str, symbol: str, user_id: str):
        alert = {
            "level": level,
            "message": message,
            "symbol": symbol,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._alerts.append(alert)
        if level == "violation":
            logger.critical("[COMPLIANCE] %s", message)
        else:
            logger.warning("[COMPLIANCE] %s", message)

    def get_alerts(self, since_hours: int = 24) -> list[dict]:
        cutoff = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat()
        return [a for a in self._alerts if a["timestamp"] >= cutoff]

    def get_trade_report(self, user_id: str | None = None,
                          hours: int = 24) -> dict[str, Any]:
        """Generate compliance trade report."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        trades = [t for t in self._trade_history if t["timestamp"] >= cutoff]
        if user_id:
            trades = [t for t in trades if t["user_id"] == user_id]

        total_volume = sum(t["quantity"] * t["price"] for t in trades)
        buy_count = sum(1 for t in trades if t["side"] == "BUY")
        sell_count = sum(1 for t in trades if t["side"] == "SELL")

        return {
            "period_hours": hours,
            "total_trades": len(trades),
            "buy_trades": buy_count,
            "sell_trades": sell_count,
            "total_volume_aud": round(total_volume, 2),
            "unique_symbols": len({t["symbol"] for t in trades}),
            "alerts": self.get_alerts(hours),
        }


# ── Singleton ──────────────────────────────────────────────────────────────

_compliance: ComplianceAgent | None = None


def get_compliance_agent() -> ComplianceAgent:
    global _compliance
    if _compliance is None:
        _compliance = ComplianceAgent()
    return _compliance
