"""Live Execution Agent — real-market order execution through multi-broker OMS.

Replaces paper-trading simulation with real broker connections.
Routes all orders through the Risk Engine → Compliance Agent → OMS → Broker.

This agent is the primary interface used by the orchestrator and decision
agent for executing trade decisions in production.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.order_management import get_oms
from core.risk_engine import get_risk_engine
from agents.compliance_agent import get_compliance_agent
from tools.broker_manager import get_broker_manager

logger = logging.getLogger(__name__)


class LiveExecutionAgent:
    """Enterprise execution agent for real-market trading.

    Pipeline:
    1. Decision agent produces a signal (BUY/SELL/HOLD + confidence)
    2. Risk engine validates position sizing and portfolio constraints
    3. Compliance agent checks regulatory rules
    4. OMS routes the order to the best available broker
    5. Post-trade updates: risk state, compliance log, audit trail
    """

    name = "LiveExecutionAgent"

    def __init__(self):
        self._oms = get_oms()
        self._risk_engine = get_risk_engine()
        self._compliance = get_compliance_agent()

    # ── Primary Execution Interface ────────────────────────────────────

    async def execute_signal(
        self,
        symbol: str,
        signal: dict[str, Any],
        user_id: str = "auto",
        preferred_broker: str | None = None,
        exchange: str = "ASX",
        currency: str = "AUD",
    ) -> dict[str, Any]:
        """Execute a trading signal from the decision agent.

        Args:
            symbol: Stock symbol (e.g., 'CBA', 'BHP', 'AAPL')
            signal: Dict with keys: action, confidence, entry_price,
                    stop_loss, target_price, position_size_recommendation
            user_id: User originating the trade
            preferred_broker: Broker to route to (optional)
            exchange: Target exchange
            currency: Currency code

        Returns:
            Execution result including order details and risk metrics.
        """
        action = signal.get("action", "HOLD").upper()
        confidence = signal.get("confidence", 0)

        # Very low confidence → do not execute
        if confidence < 0.15:
            return {
                "executed": False,
                "reason": f"Confidence too low ({confidence:.2f}) — minimum 0.15 required",
                "action": action,
                "confidence": confidence,
            }

        # HOLD → do nothing
        if action == "HOLD":
            return {
                "executed": False,
                "reason": "HOLD signal — no trade executed",
                "action": action,
                "confidence": confidence,
            }

        side = "BUY" if action in ("BUY", "STRONG_BUY") else "SELL"
        entry_price = signal.get("entry_price", 0)
        stop_loss = signal.get("stop_loss")
        take_profit = signal.get("target_price")
        recommended_qty = signal.get("position_size_recommendation")

        # Get price from broker if not provided
        if not entry_price or entry_price <= 0:
            entry_price = await self._get_live_price(symbol, exchange, currency)
            if entry_price <= 0:
                return {"executed": False, "reason": f"Cannot get price for {symbol}"}

        # Calculate position size if not specified
        if not recommended_qty or recommended_qty <= 0:
            recommended_qty = self._risk_engine.validate_order(
                symbol=symbol, side=side, quantity=1, price=entry_price,
                portfolio_value=await self._get_portfolio_value(),
                current_positions=self._oms.positions,
            ).get("recommended_quantity", 0)

        if recommended_qty <= 0:
            return {
                "executed": False,
                "reason": "Risk engine recommends zero position size",
            }

        # Compliance check
        compliance_result = await self._compliance.pre_trade_compliance_check(
            symbol=symbol, side=side, quantity=recommended_qty,
            price=entry_price, user_id=user_id,
            portfolio_positions=self._oms.positions,
        )
        if not compliance_result["approved"]:
            return {
                "executed": False,
                "reason": "Compliance check failed",
                "violations": compliance_result["violations"],
            }

        # Determine order type
        order_type = "MKT"
        limit_price = None
        if action in ("BUY", "STRONG_BUY") and entry_price:
            # Use limit order for non-STRONG signals to control slippage
            if action == "BUY":
                order_type = "LMT"
                limit_price = entry_price

        # Submit through OMS
        result = await self._oms.submit_order(
            symbol=symbol,
            side=side,
            quantity=recommended_qty,
            order_type=order_type,
            price=limit_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exchange=exchange,
            currency=currency,
            preferred_broker=preferred_broker,
            user_id=user_id,
            strategy=signal.get("strategy", "multi_agent"),
        )

        # Post-trade compliance logging
        if result.get("success"):
            self._compliance.record_trade(
                symbol=symbol, side=side, quantity=recommended_qty,
                price=result.get("avg_fill_price", entry_price),
                user_id=user_id,
                broker=result.get("broker", ""),
            )

        return {
            "executed": result.get("success", False),
            "action": action,
            "side": side,
            "symbol": symbol,
            "quantity": recommended_qty,
            "order_type": order_type,
            "broker": result.get("broker"),
            "order_id": result.get("order_id"),
            "status": result.get("status"),
            "avg_fill_price": result.get("avg_fill_price"),
            "commission": result.get("commission"),
            "auto_stop_loss": result.get("auto_stop_loss"),
            "risk_check": result.get("risk_check"),
            "compliance": compliance_result,
            "error": result.get("error"),
        }

    # ── Close Position ─────────────────────────────────────────────────

    async def close_position(
        self,
        symbol: str,
        user_id: str = "auto",
        preferred_broker: str | None = None,
        exchange: str = "ASX",
        currency: str = "AUD",
    ) -> dict[str, Any]:
        """Close an existing position entirely."""
        positions = self._oms.positions
        if symbol not in positions:
            return {"success": False, "error": f"No open position in {symbol}"}

        qty = positions[symbol]["quantity"]
        return await self._oms.submit_order(
            symbol=symbol,
            side="SELL",
            quantity=qty,
            order_type="MKT",
            exchange=exchange,
            currency=currency,
            preferred_broker=preferred_broker,
            user_id=user_id,
            strategy="position_close",
        )

    # ── Emergency Controls ─────────────────────────────────────────────

    async def emergency_stop(self, reason: str = "Manual emergency stop") -> dict[str, Any]:
        """Activate kill switch: cancel all orders and close all positions."""
        self._risk_engine.activate_kill_switch(reason)

        cancel_result = await self._oms.cancel_all_orders()
        close_result = await self._oms.close_all_positions(reason)

        return {
            "kill_switch": True,
            "reason": reason,
            "orders_cancelled": cancel_result.get("cancelled", 0),
            "positions_closed": close_result.get("closed", []),
        }

    async def resume_trading(self) -> dict[str, Any]:
        """Deactivate kill switch and resume trading."""
        self._risk_engine.deactivate_kill_switch()
        return {"kill_switch": False, "message": "Trading resumed"}

    # ── Portfolio Views ────────────────────────────────────────────────

    async def get_portfolio(self) -> dict[str, Any]:
        """Get consolidated portfolio across all brokers."""
        broker_manager = get_broker_manager()
        return await broker_manager.get_consolidated_portfolio()

    async def get_risk_status(self) -> dict[str, Any]:
        """Get current risk engine status."""
        return self._risk_engine.get_status()

    async def get_compliance_report(self, hours: int = 24) -> dict[str, Any]:
        """Get compliance trade report."""
        return self._compliance.get_trade_report(hours=hours)

    async def get_broker_status(self) -> list[dict]:
        """Get status of all registered brokers."""
        broker_manager = get_broker_manager()
        return broker_manager.list_brokers()

    # ── Helpers ────────────────────────────────────────────────────────

    async def _get_live_price(self, symbol: str, exchange: str, currency: str) -> float:
        broker_manager = get_broker_manager()
        try:
            quote = await broker_manager.get_best_quote(symbol, exchange, currency)
            if quote and quote.last:
                return quote.last
            if quote and quote.bid and quote.ask:
                return (quote.bid + quote.ask) / 2
        except Exception:
            pass
        try:
            from tools.stock_api import fetch_stock_data
            snap = await asyncio.to_thread(fetch_stock_data, symbol)
            return snap.price
        except Exception:
            return 0.0

    async def _get_portfolio_value(self) -> float:
        try:
            portfolio = await self.get_portfolio()
            return portfolio.get("total_equity", 100000)
        except Exception:
            return 100000
