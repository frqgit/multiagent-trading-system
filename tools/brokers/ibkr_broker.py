"""Interactive Brokers (IBKR) — Enterprise broker adapter.

Wraps ib_insync to conform to the BaseBroker abstraction. Supports the full
range of IBKR order types including native bracket orders.

IBKR is the primary broker for international equities + ASX access.
Requires TWS or IB Gateway running locally or via a secure tunnel.

Env vars (in .env):
    IBKR_HOST      – TWS/Gateway host  (default 127.0.0.1)
    IBKR_PORT      – TWS/Gateway port  (default 7497)
    IBKR_CLIENT_ID – API client id      (default 1)
    IBKR_MODE      – "live" (never "paper" for production)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from tools.broker_base import (
    BaseBroker, BrokerID, BrokerQuote, BrokerBar, BrokerOrder, BrokerPosition,
    BrokerAccount, OrderType, OrderSide, OrderStatus,
)

logger = logging.getLogger(__name__)

# ib_insync remains optional to avoid hard dependency
_ib_insync = None
_ib_available = False


def _ensure_ib():
    global _ib_insync, _ib_available
    if _ib_insync is not None:
        return _ib_available
    try:
        import ib_insync as _mod
        _ib_insync = _mod
        _ib_available = True
    except ImportError:
        _ib_available = False
    return _ib_available


class IBKRBroker(BaseBroker):
    """Interactive Brokers broker adapter (via ib_insync)."""

    broker_id = BrokerID.IBKR
    display_name = "Interactive Brokers"
    supported_exchanges = ["SMART", "ASX", "NYSE", "NASDAQ", "LSE", "CBOE_AU"]
    supported_order_types = ["MKT", "LMT", "STP", "STP_LMT", "TRAIL", "BRACKET"]

    def __init__(self, host: str = "127.0.0.1", port: int = 7497,
                 client_id: int = 1, mode: str = "live"):
        super().__init__()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.mode = mode
        self._ib = None
        # Map internal order_id → broker trade object for tracking
        self._order_map: dict[str, Any] = {}

    # ── Connection ─────────────────────────────────────────────────────

    async def connect(self) -> bool:
        if not _ensure_ib():
            logger.error("ib_insync not installed — install with: pip install ib_insync")
            return False
        try:
            self._ib = _ib_insync.IB()
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._ib.connect,
                    self.host, self.port,
                    clientId=self.client_id,
                    readonly=False,  # real trading — never readonly
                ),
                timeout=15,
            )
            self._connected = True
            logger.info("IBKR connected [%s] %s:%s", self.mode, self.host, self.port)
            return True
        except asyncio.TimeoutError:
            logger.error("IBKR connection timeout %s:%s", self.host, self.port)
            return False
        except Exception as exc:
            logger.error("IBKR connection failed: %s", exc)
            return False

    async def disconnect(self) -> bool:
        if self._ib:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self._connected = False
        return True

    async def health_check(self) -> dict[str, Any]:
        connected = False
        if self._ib:
            try:
                connected = self._ib.isConnected()
            except Exception:
                connected = False
        self._connected = connected
        return {
            "healthy": connected,
            "broker": self.broker_id.value,
            "mode": self.mode,
            "host": self.host,
            "port": self.port,
        }

    # ── Market Data ────────────────────────────────────────────────────

    async def get_quote(self, symbol: str, exchange: str = "SMART",
                        currency: str = "AUD") -> BrokerQuote:
        if not self._connected:
            raise ConnectionError("IBKR not connected")
        contract = _ib_insync.Stock(symbol, exchange, currency)
        self._ib.qualifyContracts(contract)
        ticker = self._ib.reqMktData(contract, snapshot=True)
        await asyncio.sleep(2)
        return BrokerQuote(
            symbol=symbol, broker=self.broker_id.value,
            bid=ticker.bid if ticker.bid != -1 else None,
            ask=ticker.ask if ticker.ask != -1 else None,
            last=ticker.last if ticker.last != -1 else None,
            volume=int(ticker.volume) if ticker.volume != -1 else None,
            open=ticker.open if ticker.open != -1 else None,
            high=ticker.high if ticker.high != -1 else None,
            low=ticker.low if ticker.low != -1 else None,
            close=ticker.close if ticker.close != -1 else None,
        )

    async def get_historical_bars(self, symbol: str, duration: str = "1 Y",
                                   bar_size: str = "1 day", exchange: str = "SMART",
                                   currency: str = "AUD") -> list[BrokerBar]:
        if not self._connected:
            raise ConnectionError("IBKR not connected")
        contract = _ib_insync.Stock(symbol, exchange, currency)
        self._ib.qualifyContracts(contract)
        bars = await asyncio.to_thread(
            self._ib.reqHistoricalData, contract, endDateTime="",
            durationStr=duration, barSizeSetting=bar_size,
            whatToShow="TRADES", useRTH=True, formatDate=1,
        )
        return [
            BrokerBar(date=str(b.date), open=b.open, high=b.high,
                      low=b.low, close=b.close, volume=int(b.volume))
            for b in bars
        ]

    # ── Orders ─────────────────────────────────────────────────────────

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        if not self._connected:
            order.status = OrderStatus.ERROR.value
            order.error_message = "IBKR not connected"
            return order

        try:
            exch = order.exchange or "SMART"
            ccy = order.currency or "AUD"
            contract = _ib_insync.Stock(order.symbol, exch, ccy)
            self._ib.qualifyContracts(contract)

            ib_order = self._build_ib_order(order)
            trade = self._ib.placeOrder(contract, ib_order)
            await asyncio.sleep(1)  # allow fill callback

            order.broker_order_id = str(trade.order.orderId)
            order.status = self._map_status(trade.orderStatus.status)
            order.filled_qty = trade.orderStatus.filled
            order.avg_fill_price = trade.orderStatus.avgFillPrice
            order.updated_at = datetime.utcnow()
            self._order_map[order.order_id] = trade
            return order
        except Exception as exc:
            logger.error("IBKR place_order error: %s", exc)
            order.status = OrderStatus.ERROR.value
            order.error_message = str(exc)
            return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        trade = self._order_map.get(order_id)
        if not trade:
            return BrokerOrder(order_id=order_id, status=OrderStatus.ERROR.value,
                               error_message="Order not found in local map")
        self._ib.cancelOrder(trade.order)
        await asyncio.sleep(0.5)
        return BrokerOrder(
            order_id=order_id, status=OrderStatus.CANCELLED.value,
            broker_order_id=str(trade.order.orderId),
        )

    async def modify_order(self, order_id: str, **kwargs) -> BrokerOrder:
        trade = self._order_map.get(order_id)
        if not trade:
            return BrokerOrder(order_id=order_id, status=OrderStatus.ERROR.value,
                               error_message="Order not found")
        if "limit_price" in kwargs:
            trade.order.lmtPrice = kwargs["limit_price"]
        if "quantity" in kwargs:
            trade.order.totalQuantity = kwargs["quantity"]
        self._ib.placeOrder(trade.contract, trade.order)
        await asyncio.sleep(0.5)
        return BrokerOrder(
            order_id=order_id, status=self._map_status(trade.orderStatus.status),
            broker_order_id=str(trade.order.orderId),
        )

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        trade = self._order_map.get(order_id)
        if not trade:
            return BrokerOrder(order_id=order_id, status=OrderStatus.ERROR.value,
                               error_message="Order not tracked")
        return BrokerOrder(
            order_id=order_id,
            broker_order_id=str(trade.order.orderId),
            status=self._map_status(trade.orderStatus.status),
            filled_qty=trade.orderStatus.filled,
            avg_fill_price=trade.orderStatus.avgFillPrice,
        )

    async def get_open_orders(self) -> list[BrokerOrder]:
        if not self._connected:
            return []
        orders = []
        for t in self._ib.openTrades():
            orders.append(BrokerOrder(
                order_id=str(t.order.orderId),
                broker_order_id=str(t.order.orderId),
                broker=self.broker_id.value,
                symbol=t.contract.symbol,
                side=t.order.action,
                order_type=t.order.orderType,
                quantity=t.order.totalQuantity,
                status=self._map_status(t.orderStatus.status),
                filled_qty=t.orderStatus.filled,
                avg_fill_price=t.orderStatus.avgFillPrice,
            ))
        return orders

    # ── Positions & Account ────────────────────────────────────────────

    async def get_positions(self) -> list[BrokerPosition]:
        if not self._connected:
            return []
        return [
            BrokerPosition(
                symbol=p.contract.symbol,
                broker=self.broker_id.value,
                quantity=p.position,
                avg_cost=p.avgCost,
                market_value=p.position * p.avgCost,
                currency=p.contract.currency or "AUD",
            )
            for p in self._ib.positions()
        ]

    async def get_account(self) -> BrokerAccount:
        if not self._connected:
            return BrokerAccount(broker=self.broker_id.value)
        summary = self._ib.accountSummary()
        acct = BrokerAccount(broker=self.broker_id.value)
        for item in summary:
            tag = item.tag
            val = float(item.value) if item.value.replace(".", "").replace("-", "").isdigit() else 0
            if tag == "TotalCashValue":
                acct.cash_balance = val
            elif tag == "GrossPositionValue":
                acct.portfolio_value = val
            elif tag == "NetLiquidation":
                acct.total_equity = val
            elif tag == "MaintMarginReq":
                acct.margin_used = val
            elif tag == "AvailableFunds":
                acct.margin_available = val
                acct.buying_power = val
            elif tag == "UnrealizedPnL":
                acct.unrealized_pnl = val
            elif tag == "RealizedPnL":
                acct.realized_pnl = val
        acct.account_id = summary[0].account if summary else ""
        return acct

    # ── Native bracket order override ──────────────────────────────────

    async def place_bracket_order(
        self, symbol: str, side: str, quantity: float,
        entry_price: float | None, take_profit: float, stop_loss: float,
        exchange: str = "SMART", currency: str = "AUD",
    ) -> dict[str, BrokerOrder]:
        if not self._connected:
            err = BrokerOrder(order_id="", status=OrderStatus.ERROR.value,
                              error_message="IBKR not connected")
            return {"entry": err, "take_profit": err, "stop_loss": err}

        contract = _ib_insync.Stock(symbol, exchange, currency)
        self._ib.qualifyContracts(contract)

        bracket = self._ib.bracketOrder(
            action=side, quantity=quantity,
            limitPrice=entry_price or 0,
            takeProfitPrice=take_profit, stopLossPrice=stop_loss,
        )
        trades = []
        for o in bracket:
            t = self._ib.placeOrder(contract, o)
            trades.append(t)
        await asyncio.sleep(1)

        result = {}
        labels = ["entry", "take_profit", "stop_loss"]
        for label, t in zip(labels, trades):
            result[label] = BrokerOrder(
                order_id=str(t.order.orderId),
                broker_order_id=str(t.order.orderId),
                broker=self.broker_id.value,
                symbol=symbol, side=side, quantity=quantity,
                status=self._map_status(t.orderStatus.status),
            )
            self._order_map[result[label].order_id] = t
        return result

    # ── Helpers ────────────────────────────────────────────────────────

    def _build_ib_order(self, order: BrokerOrder):
        ot = order.order_type
        if ot == OrderType.MARKET.value:
            return _ib_insync.MarketOrder(order.side, order.quantity)
        elif ot == OrderType.LIMIT.value and order.limit_price:
            return _ib_insync.LimitOrder(order.side, order.quantity, order.limit_price)
        elif ot == OrderType.STOP.value and order.stop_price:
            return _ib_insync.StopOrder(order.side, order.quantity, order.stop_price)
        elif ot == OrderType.STOP_LIMIT.value and order.stop_price and order.limit_price:
            return _ib_insync.Order(
                action=order.side, totalQuantity=order.quantity,
                orderType="STP LMT",
                lmtPrice=order.limit_price, auxPrice=order.stop_price,
            )
        elif ot == OrderType.TRAILING_STOP.value and order.trail_percent:
            return _ib_insync.Order(
                action=order.side, totalQuantity=order.quantity,
                orderType="TRAIL", trailingPercent=order.trail_percent,
            )
        else:
            return _ib_insync.MarketOrder(order.side, order.quantity)

    @staticmethod
    def _map_status(ib_status: str) -> str:
        mapping = {
            "PendingSubmit": OrderStatus.PENDING.value,
            "PendingCancel": OrderStatus.PENDING.value,
            "PreSubmitted": OrderStatus.SUBMITTED.value,
            "Submitted": OrderStatus.SUBMITTED.value,
            "Filled": OrderStatus.FILLED.value,
            "Cancelled": OrderStatus.CANCELLED.value,
            "Inactive": OrderStatus.REJECTED.value,
            "ApiCancelled": OrderStatus.CANCELLED.value,
        }
        return mapping.get(ib_status, OrderStatus.PENDING.value)
