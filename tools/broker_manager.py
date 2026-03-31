"""Broker Manager — multi-broker orchestration, routing, and failover.

Manages the lifecycle of all configured broker connections and provides a
single entry point for the execution engine to route orders to the correct
broker with automatic failover, health monitoring, and best-execution
routing.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from tools.broker_base import (
    BaseBroker, BrokerID, BrokerOrder, BrokerQuote, BrokerPosition,
    BrokerAccount, OrderStatus,
)

logger = logging.getLogger(__name__)


class BrokerManager:
    """Manages multiple broker connections with smart routing and failover."""

    def __init__(self):
        self._brokers: dict[str, BaseBroker] = {}
        self._primary_broker: str | None = None
        self._health_status: dict[str, dict] = {}
        self._order_log: list[dict] = []

    # ── Registration & Lifecycle ───────────────────────────────────────

    def register_broker(self, broker: BaseBroker, primary: bool = False):
        bid = broker.broker_id.value
        self._brokers[bid] = broker
        if primary or not self._primary_broker:
            self._primary_broker = bid
        logger.info("Registered broker: %s (primary=%s)", bid, primary)

    async def connect_all(self) -> dict[str, bool]:
        results = {}
        tasks = {bid: broker.connect() for bid, broker in self._brokers.items()}
        for bid, coro in tasks.items():
            try:
                results[bid] = await coro
            except Exception as exc:
                logger.error("Failed to connect %s: %s", bid, exc)
                results[bid] = False
        return results

    async def disconnect_all(self):
        for bid, broker in self._brokers.items():
            try:
                await broker.disconnect()
            except Exception:
                pass

    async def health_check_all(self) -> dict[str, dict]:
        for bid, broker in self._brokers.items():
            try:
                self._health_status[bid] = await broker.health_check()
            except Exception as exc:
                self._health_status[bid] = {"healthy": False, "error": str(exc)}
        return self._health_status

    # ── Broker Access ──────────────────────────────────────────────────

    def get_broker(self, broker_id: str | None = None) -> BaseBroker | None:
        if broker_id:
            return self._brokers.get(broker_id)
        return self._brokers.get(self._primary_broker or "")

    @property
    def primary(self) -> BaseBroker | None:
        return self._brokers.get(self._primary_broker or "")

    @property
    def connected_brokers(self) -> list[str]:
        return [bid for bid, b in self._brokers.items() if b.is_connected]

    @property
    def all_brokers(self) -> dict[str, BaseBroker]:
        return dict(self._brokers)

    def list_brokers(self) -> list[dict[str, Any]]:
        return [
            {
                "broker_id": bid,
                "display_name": b.display_name,
                "connected": b.is_connected,
                "primary": bid == self._primary_broker,
                "supported_exchanges": b.supported_exchanges,
                "supported_order_types": b.supported_order_types,
            }
            for bid, b in self._brokers.items()
        ]

    # ── Smart Order Routing ────────────────────────────────────────────

    async def route_order(
        self,
        order: BrokerOrder,
        preferred_broker: str | None = None,
    ) -> BrokerOrder:
        """Route an order to the best available broker.

        Priority:
        1. Preferred broker (if specified and connected)
        2. Broker that supports the order's exchange
        3. Primary broker
        4. Any connected broker (failover)
        """
        broker = self._select_broker(order, preferred_broker)
        if not broker:
            order.status = OrderStatus.REJECTED.value
            order.error_message = "No connected broker available for this order"
            return order

        order.broker = broker.broker_id.value
        result = await broker.place_order(order)

        # Log the order for audit
        self._order_log.append({
            "order_id": order.order_id,
            "broker": broker.broker_id.value,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "status": result.status,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Failover: if order rejected, try next available broker
        if result.status in (OrderStatus.REJECTED.value, OrderStatus.ERROR.value):
            fallback = self._get_fallback_broker(order, exclude=broker.broker_id.value)
            if fallback:
                logger.warning(
                    "Order %s rejected by %s, failing over to %s",
                    order.order_id, broker.broker_id.value, fallback.broker_id.value,
                )
                order.broker = fallback.broker_id.value
                result = await fallback.place_order(order)

        return result

    def _select_broker(self, order: BrokerOrder, preferred: str | None) -> BaseBroker | None:
        # 1. Preferred
        if preferred and preferred in self._brokers:
            b = self._brokers[preferred]
            if b.is_connected:
                return b

        # 2. Exchange-aware selection
        exchange = order.exchange or "ASX"
        for bid, b in self._brokers.items():
            if b.is_connected and exchange in b.supported_exchanges:
                return b

        # 3. Primary
        primary = self.primary
        if primary and primary.is_connected:
            return primary

        # 4. Any connected
        for bid, b in self._brokers.items():
            if b.is_connected:
                return b
        return None

    def _get_fallback_broker(self, order: BrokerOrder, exclude: str) -> BaseBroker | None:
        for bid, b in self._brokers.items():
            if bid != exclude and b.is_connected:
                exchange = order.exchange or "ASX"
                if exchange in b.supported_exchanges:
                    return b
        return None

    # ── Aggregated Views ───────────────────────────────────────────────

    async def get_all_positions(self) -> dict[str, list[BrokerPosition]]:
        """Get positions from all connected brokers."""
        result = {}
        for bid, broker in self._brokers.items():
            if broker.is_connected:
                try:
                    result[bid] = await broker.get_positions()
                except Exception as exc:
                    logger.error("Error fetching positions from %s: %s", bid, exc)
                    result[bid] = []
        return result

    async def get_all_accounts(self) -> dict[str, BrokerAccount]:
        """Get account summaries from all connected brokers."""
        result = {}
        for bid, broker in self._brokers.items():
            if broker.is_connected:
                try:
                    result[bid] = await broker.get_account()
                except Exception as exc:
                    logger.error("Error fetching account from %s: %s", bid, exc)
        return result

    async def get_consolidated_portfolio(self) -> dict[str, Any]:
        """Get consolidated portfolio across all brokers."""
        all_positions = await self.get_all_positions()
        all_accounts = await self.get_all_accounts()

        total_equity = 0.0
        total_cash = 0.0
        total_unrealized = 0.0
        consolidated_positions: dict[str, dict] = {}

        for bid, acct in all_accounts.items():
            total_equity += acct.total_equity
            total_cash += acct.cash_balance
            total_unrealized += acct.unrealized_pnl

        for bid, positions in all_positions.items():
            for pos in positions:
                key = pos.symbol
                if key in consolidated_positions:
                    existing = consolidated_positions[key]
                    total_qty = existing["quantity"] + pos.quantity
                    if total_qty > 0:
                        existing["avg_cost"] = (
                            (existing["avg_cost"] * existing["quantity"] +
                             pos.avg_cost * pos.quantity) / total_qty
                        )
                    existing["quantity"] = total_qty
                    existing["market_value"] += pos.market_value
                    existing["unrealized_pnl"] += pos.unrealized_pnl
                    existing["brokers"].append(bid)
                else:
                    consolidated_positions[key] = {
                        "symbol": pos.symbol,
                        "quantity": pos.quantity,
                        "avg_cost": pos.avg_cost,
                        "current_price": pos.current_price,
                        "market_value": pos.market_value,
                        "unrealized_pnl": pos.unrealized_pnl,
                        "brokers": [bid],
                    }

        return {
            "total_equity": round(total_equity, 2),
            "total_cash": round(total_cash, 2),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "positions": list(consolidated_positions.values()),
            "accounts": {bid: {
                "cash": acct.cash_balance,
                "equity": acct.total_equity,
                "margin_used": acct.margin_used,
            } for bid, acct in all_accounts.items()},
            "connected_brokers": self.connected_brokers,
        }

    async def get_best_quote(self, symbol: str, exchange: str = "ASX",
                             currency: str = "AUD") -> BrokerQuote | None:
        """Get the best available quote across all connected brokers."""
        quotes: list[BrokerQuote] = []
        for bid, broker in self._brokers.items():
            if broker.is_connected and exchange in broker.supported_exchanges:
                try:
                    q = await broker.get_quote(symbol, exchange, currency)
                    quotes.append(q)
                except Exception:
                    pass
        if not quotes:
            return None
        # Return quote with tightest spread
        return min(quotes, key=lambda q: (q.ask or 999999) - (q.bid or 0))

    @property
    def order_audit_log(self) -> list[dict]:
        return list(self._order_log)


# ── Singleton Factory ──────────────────────────────────────────────────────

_broker_manager: BrokerManager | None = None


def get_broker_manager() -> BrokerManager:
    global _broker_manager
    if _broker_manager is None:
        _broker_manager = BrokerManager()
    return _broker_manager


async def initialize_brokers() -> BrokerManager:
    """Initialize all configured brokers from environment settings.

    Called during application startup. Only brokers with valid credentials
    are registered.
    """
    from core.config import get_settings
    settings = get_settings()

    manager = get_broker_manager()

    # 1. Interactive Brokers
    if settings.ibkr_host:
        try:
            from tools.brokers.ibkr_broker import IBKRBroker
            ibkr = IBKRBroker(
                host=settings.ibkr_host,
                port=settings.ibkr_port,
                client_id=settings.ibkr_client_id,
                mode=settings.ibkr_mode,
            )
            manager.register_broker(ibkr, primary=True)
        except Exception as exc:
            logger.warning("IBKR broker init failed: %s", exc)

    # 2. CommSec
    if getattr(settings, "commsec_client_id", ""):
        try:
            from tools.brokers.commsec_broker import CommSecBroker
            commsec = CommSecBroker(
                client_id=settings.commsec_client_id,
                client_secret=settings.commsec_client_secret,
                account_id=settings.commsec_account_id,
                refresh_token=settings.commsec_refresh_token,
            )
            manager.register_broker(commsec)
        except Exception as exc:
            logger.warning("CommSec broker init failed: %s", exc)

    # 3. IG Markets
    if getattr(settings, "ig_api_key", ""):
        try:
            from tools.brokers.ig_broker import IGMarketsBroker
            ig = IGMarketsBroker(
                api_key=settings.ig_api_key,
                username=settings.ig_username,
                password=settings.ig_password,
                account_id=settings.ig_account_id,
            )
            manager.register_broker(ig)
        except Exception as exc:
            logger.warning("IG Markets broker init failed: %s", exc)

    # 4. CMC Markets
    if getattr(settings, "cmc_api_key", ""):
        try:
            from tools.brokers.cmc_broker import CMCMarketsBroker
            cmc = CMCMarketsBroker(
                api_key=settings.cmc_api_key,
                username=settings.cmc_username,
                password=settings.cmc_password,
                account_id=settings.cmc_account_id,
            )
            manager.register_broker(cmc)
        except Exception as exc:
            logger.warning("CMC Markets broker init failed: %s", exc)

    # 5. SelfWealth
    if getattr(settings, "selfwealth_api_key", ""):
        try:
            from tools.brokers.selfwealth_broker import SelfWealthBroker
            sw = SelfWealthBroker(
                api_key=settings.selfwealth_api_key,
                client_id=settings.selfwealth_client_id,
                client_secret=settings.selfwealth_secret,
                account_id=settings.selfwealth_account_id,
            )
            manager.register_broker(sw)
        except Exception as exc:
            logger.warning("SelfWealth broker init failed: %s", exc)

    # Connect all registered brokers
    results = await manager.connect_all()
    for bid, ok in results.items():
        if ok:
            logger.info("Broker %s connected successfully", bid)
        else:
            logger.warning("Broker %s failed to connect", bid)

    return manager
