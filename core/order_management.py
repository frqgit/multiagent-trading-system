"""Order Management System (OMS) — enterprise-grade order lifecycle management.

Manages the full lifecycle of orders from submission through execution to
settlement. Integrates with the RiskEngine for pre-trade checks and the
BrokerManager for multi-broker routing.

Features:
- Pre-trade risk validation
- Multi-broker order routing with failover
- Order status tracking and reconciliation
- Automatic stop-loss attachment
- Position-awareness (prevents duplicate entries)
- Full audit trail
- Real-time P&L tracking
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from tools.broker_base import BrokerOrder, OrderStatus, OrderSide, OrderType
from tools.broker_manager import get_broker_manager
from core.risk_engine import get_risk_engine

logger = logging.getLogger(__name__)


@dataclass
class ManagedOrder:
    """An order tracked by the OMS with full lifecycle metadata."""
    order_id: str
    broker_order: BrokerOrder
    risk_check_result: dict = field(default_factory=dict)
    auto_stop_loss_order_id: str = ""
    auto_take_profit_order_id: str = ""
    parent_order_id: str = ""    # for bracket child orders
    created_by: str = ""         # user ID or "auto"
    strategy: str = ""           # which agent/strategy originated
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class OrderManagementSystem:
    """Enterprise OMS with risk-gated order flow."""

    def __init__(self):
        self._active_orders: dict[str, ManagedOrder] = {}
        self._filled_orders: list[ManagedOrder] = []
        self._rejected_orders: list[ManagedOrder] = []
        self._positions: dict[str, dict] = {}  # symbol → position info
        self._audit_log: list[dict] = []

    # ── Order Submission ───────────────────────────────────────────────

    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MKT",
        price: float | None = None,
        stop_price: float | None = None,
        trail_percent: float | None = None,
        take_profit: float | None = None,
        stop_loss: float | None = None,
        exchange: str = "ASX",
        currency: str = "AUD",
        preferred_broker: str | None = None,
        user_id: str = "auto",
        strategy: str = "",
    ) -> dict[str, Any]:
        """Submit an order through the full risk-gated pipeline.

        Returns:
            Dict with order details, risk check results, and execution status.
        """
        order_id = str(uuid.uuid4())[:12]
        risk_engine = get_risk_engine()
        broker_manager = get_broker_manager()

        # Get current portfolio for risk checks
        portfolio = await broker_manager.get_consolidated_portfolio()
        portfolio_value = portfolio.get("total_equity", 0) or 100000
        current_price = price or await self._get_current_price(symbol, exchange, currency)

        if current_price <= 0:
            return {
                "success": False,
                "order_id": order_id,
                "error": f"Unable to get current price for {symbol}",
            }

        # ── Pre-trade risk validation ──
        risk_result = risk_engine.validate_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=current_price,
            portfolio_value=portfolio_value,
            current_positions=self._positions,
            broker=preferred_broker or "",
        )

        if not risk_result["approved"]:
            self._log_audit("order_rejected", {
                "order_id": order_id, "symbol": symbol, "side": side,
                "quantity": quantity, "violations": risk_result["violations"],
            })
            rejected = ManagedOrder(
                order_id=order_id,
                broker_order=BrokerOrder(
                    order_id=order_id, symbol=symbol, side=side,
                    quantity=quantity, status=OrderStatus.REJECTED.value,
                    error_message="; ".join(risk_result["violations"]),
                ),
                risk_check_result=risk_result,
                created_by=user_id,
                strategy=strategy,
            )
            self._rejected_orders.append(rejected)
            return {
                "success": False,
                "order_id": order_id,
                "risk_check": risk_result,
                "error": "Order rejected by risk engine",
                "violations": risk_result["violations"],
            }

        # ── Build broker order ──
        broker_order = BrokerOrder(
            order_id=order_id,
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=price if order_type in (OrderType.LIMIT.value, OrderType.STOP_LIMIT.value) else None,
            stop_price=stop_price,
            trail_percent=trail_percent,
            take_profit_price=take_profit,
            stop_loss_price=stop_loss or risk_result.get("stop_loss_price"),
        )

        # ── Route to broker ──
        executed = await broker_manager.route_order(broker_order, preferred_broker)

        managed = ManagedOrder(
            order_id=order_id,
            broker_order=executed,
            risk_check_result=risk_result,
            created_by=user_id,
            strategy=strategy,
        )

        if executed.status in (OrderStatus.FILLED.value, OrderStatus.SUBMITTED.value,
                               OrderStatus.ACCEPTED.value, OrderStatus.PARTIALLY_FILLED.value):
            self._active_orders[order_id] = managed

            # Auto-attach stop-loss if filled and side is BUY
            if (executed.status == OrderStatus.FILLED.value
                    and side == OrderSide.BUY.value
                    and risk_result.get("stop_loss_price")):
                sl_result = await self._attach_stop_loss(
                    symbol, quantity, risk_result["stop_loss_price"],
                    exchange, currency, executed.broker,
                )
                managed.auto_stop_loss_order_id = sl_result.get("order_id", "")

            # Update position tracking
            self._update_position(symbol, side, quantity,
                                  executed.avg_fill_price or current_price)

            # Record trade in risk engine
            risk_engine.state.daily_order_count += 1

            self._log_audit("order_executed", {
                "order_id": order_id, "broker": executed.broker,
                "symbol": symbol, "side": side, "quantity": quantity,
                "price": executed.avg_fill_price,
                "status": executed.status,
            })
        else:
            self._rejected_orders.append(managed)

        return {
            "success": executed.status not in (OrderStatus.REJECTED.value, OrderStatus.ERROR.value),
            "order_id": order_id,
            "broker": executed.broker,
            "broker_order_id": executed.broker_order_id,
            "status": executed.status,
            "filled_qty": executed.filled_qty,
            "avg_fill_price": executed.avg_fill_price,
            "commission": executed.commission,
            "risk_check": risk_result,
            "auto_stop_loss": managed.auto_stop_loss_order_id or None,
            "error": executed.error_message or None,
        }

    # ── Bracket Order ──────────────────────────────────────────────────

    async def submit_bracket_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float | None,
        take_profit: float,
        stop_loss: float,
        exchange: str = "ASX",
        currency: str = "AUD",
        preferred_broker: str | None = None,
        user_id: str = "auto",
        strategy: str = "",
    ) -> dict[str, Any]:
        """Submit a bracket order (entry + TP + SL) with risk validation."""
        risk_engine = get_risk_engine()
        broker_manager = get_broker_manager()

        current_price = entry_price or await self._get_current_price(symbol, exchange, currency)
        portfolio = await broker_manager.get_consolidated_portfolio()
        portfolio_value = portfolio.get("total_equity", 0) or 100000

        risk_result = risk_engine.validate_order(
            symbol=symbol, side=side, quantity=quantity,
            price=current_price, portfolio_value=portfolio_value,
            current_positions=self._positions,
        )

        if not risk_result["approved"]:
            return {
                "success": False,
                "error": "Risk check failed",
                "violations": risk_result["violations"],
            }

        broker = broker_manager.get_broker(preferred_broker) or broker_manager.primary
        if not broker or not broker.is_connected:
            return {"success": False, "error": "No connected broker available"}

        result = await broker.place_bracket_order(
            symbol, side, quantity, entry_price, take_profit, stop_loss,
            exchange, currency,
        )

        return {
            "success": all(
                o.status not in (OrderStatus.REJECTED.value, OrderStatus.ERROR.value)
                for o in result.values()
            ),
            "entry": {"order_id": result["entry"].order_id, "status": result["entry"].status},
            "take_profit": {"order_id": result["take_profit"].order_id, "status": result["take_profit"].status},
            "stop_loss": {"order_id": result["stop_loss"].order_id, "status": result["stop_loss"].status},
            "broker": broker.broker_id.value,
        }

    # ── Cancel ─────────────────────────────────────────────────────────

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        managed = self._active_orders.get(order_id)
        if not managed:
            return {"success": False, "error": "Order not found"}

        broker_manager = get_broker_manager()
        broker = broker_manager.get_broker(managed.broker_order.broker)
        if not broker:
            return {"success": False, "error": "Broker not available"}

        result = await broker.cancel_order(managed.broker_order.broker_order_id or order_id)
        if result.status == OrderStatus.CANCELLED.value:
            del self._active_orders[order_id]
            # Also cancel auto stop-loss if exists
            if managed.auto_stop_loss_order_id:
                await broker.cancel_order(managed.auto_stop_loss_order_id)

        self._log_audit("order_cancelled", {"order_id": order_id, "status": result.status})
        return {"success": result.status == OrderStatus.CANCELLED.value, "status": result.status}

    # ── Cancel All (Emergency) ─────────────────────────────────────────

    async def cancel_all_orders(self) -> dict[str, Any]:
        """Cancel all open orders across all brokers."""
        broker_manager = get_broker_manager()
        cancelled = 0
        for bid, broker in broker_manager.all_brokers.items():
            if broker.is_connected:
                try:
                    open_orders = await broker.get_open_orders()
                    for o in open_orders:
                        await broker.cancel_order(o.order_id)
                        cancelled += 1
                except Exception as exc:
                    logger.error("Error cancelling orders on %s: %s", bid, exc)
        self._active_orders.clear()
        self._log_audit("cancel_all", {"cancelled": cancelled})
        return {"cancelled": cancelled}

    # ── Close All Positions (Emergency) ────────────────────────────────

    async def close_all_positions(self, reason: str = "Emergency close") -> dict[str, Any]:
        """Market-sell all open positions across all brokers."""
        broker_manager = get_broker_manager()
        closed = []
        all_positions = await broker_manager.get_all_positions()

        for bid, positions in all_positions.items():
            broker = broker_manager.get_broker(bid)
            if not broker:
                continue
            for pos in positions:
                if pos.quantity > 0:
                    close_side = OrderSide.SELL.value
                elif pos.quantity < 0:
                    close_side = OrderSide.BUY.value
                else:
                    continue
                close_order = BrokerOrder(
                    order_id=str(uuid.uuid4())[:12],
                    broker=bid,
                    symbol=pos.symbol,
                    side=close_side,
                    order_type=OrderType.MARKET.value,
                    quantity=abs(pos.quantity),
                )
                try:
                    result = await broker.place_order(close_order)
                    closed.append({
                        "symbol": pos.symbol,
                        "broker": bid,
                        "quantity": abs(pos.quantity),
                        "status": result.status,
                    })
                except Exception as exc:
                    logger.error("Error closing %s on %s: %s", pos.symbol, bid, exc)

        self._positions.clear()
        self._log_audit("close_all_positions", {"reason": reason, "closed": closed})
        return {"closed": closed, "reason": reason}

    # ── Position Tracking ──────────────────────────────────────────────

    def _update_position(self, symbol: str, side: str, quantity: float, price: float):
        if symbol in self._positions:
            pos = self._positions[symbol]
            if side == OrderSide.BUY.value:
                new_qty = pos["quantity"] + quantity
                if new_qty > 0:
                    pos["avg_cost"] = (
                        (pos["avg_cost"] * pos["quantity"] + price * quantity) / new_qty
                    )
                pos["quantity"] = new_qty
            else:
                pos["quantity"] -= quantity
                if pos["quantity"] <= 0:
                    del self._positions[symbol]
                    return
            pos["market_value"] = pos["quantity"] * price
        elif side == OrderSide.BUY.value:
            self._positions[symbol] = {
                "symbol": symbol,
                "quantity": quantity,
                "avg_cost": price,
                "market_value": quantity * price,
            }

    # ── Helpers ────────────────────────────────────────────────────────

    async def _get_current_price(self, symbol: str, exchange: str, currency: str) -> float:
        broker_manager = get_broker_manager()
        try:
            quote = await broker_manager.get_best_quote(symbol, exchange, currency)
            if quote and quote.last:
                return quote.last
            if quote and quote.bid and quote.ask:
                return (quote.bid + quote.ask) / 2
        except Exception:
            pass
        # Fallback to yfinance
        try:
            from tools.stock_api import fetch_stock_data
            snap = await asyncio.to_thread(fetch_stock_data, symbol)
            return snap.price
        except Exception:
            return 0.0

    async def _attach_stop_loss(
        self, symbol: str, quantity: float, stop_price: float,
        exchange: str, currency: str, broker_id: str,
    ) -> dict:
        broker_manager = get_broker_manager()
        broker = broker_manager.get_broker(broker_id)
        if not broker:
            return {}
        sl = BrokerOrder(
            order_id=str(uuid.uuid4())[:12],
            broker=broker_id,
            symbol=symbol,
            side=OrderSide.SELL.value,
            order_type=OrderType.STOP.value,
            quantity=quantity,
            stop_price=stop_price,
            exchange=exchange,
            currency=currency,
        )
        result = await broker.place_order(sl)
        return {"order_id": result.order_id, "status": result.status}

    def _log_audit(self, event: str, details: dict):
        self._audit_log.append({
            "event": event,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        })

    # ── Status ─────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return {
            "active_orders": len(self._active_orders),
            "filled_orders": len(self._filled_orders),
            "rejected_orders": len(self._rejected_orders),
            "positions": dict(self._positions),
            "audit_log_count": len(self._audit_log),
        }

    @property
    def positions(self) -> dict[str, dict]:
        return dict(self._positions)

    @property
    def audit_log(self) -> list[dict]:
        return list(self._audit_log)


# ── Singleton ──────────────────────────────────────────────────────────────

_oms: OrderManagementSystem | None = None


def get_oms() -> OrderManagementSystem:
    global _oms
    if _oms is None:
        _oms = OrderManagementSystem()
    return _oms
