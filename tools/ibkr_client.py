"""Interactive Brokers client — wraps ib_insync for market data + order execution.

Supports paper and live trading modes. When TWS/IB Gateway is not available,
all methods gracefully degrade and return error dicts.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ib_insync is optional — loaded lazily
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


@dataclass
class IBKROrder:
    order_id: str = ""
    symbol: str = ""
    action: str = ""  # BUY or SELL
    order_type: str = "MKT"  # MKT, LMT, STP, STP_LMT
    quantity: float = 0
    limit_price: float | None = None
    stop_price: float | None = None
    status: str = "pending"
    filled_qty: float = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    placed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class IBKRPosition:
    symbol: str = ""
    quantity: float = 0
    avg_cost: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class IBKRClient:
    """Manages connection to Interactive Brokers TWS / IB Gateway.

    Usage:
        client = IBKRClient()
        connected = await client.connect()
        if connected:
            data = await client.get_market_data("AAPL")
            order = await client.place_order("AAPL", "BUY", 10, "MKT")
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1,
                 mode: str = "paper"):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.mode = mode  # paper | live
        self._ib = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        if self._ib is None:
            return False
        try:
            return self._ib.isConnected()
        except Exception:
            return False

    async def connect(self) -> bool:
        """Connect to TWS / IB Gateway. Returns True on success."""
        if not _ensure_ib():
            logger.warning("ib_insync not installed — IBKR features disabled")
            return False

        try:
            self._ib = _ib_insync.IB()
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._ib.connect,
                    self.host,
                    self.port,
                    clientId=self.client_id,
                    readonly=(self.mode != "live"),
                ),
                timeout=10,
            )
            self._connected = True
            logger.info("Connected to IBKR %s mode on %s:%s", self.mode, self.host, self.port)
            return True
        except asyncio.TimeoutError:
            logger.warning("IBKR connection timed out (%s:%s)", self.host, self.port)
            return False
        except Exception as e:
            logger.warning("IBKR connection failed: %s", e)
            return False

    async def disconnect(self):
        if self._ib and self.is_connected:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self._connected = False

    def _not_connected(self) -> dict:
        return {"error": "Not connected to IBKR. Please ensure TWS or IB Gateway is running."}

    # ── Market Data ──────────────────────────────────────────────────────

    async def get_market_data(self, symbol: str, exchange: str = "SMART",
                              currency: str = "USD") -> dict[str, Any]:
        """Fetch real-time market data snapshot for a symbol."""
        if not self.is_connected:
            return self._not_connected()

        try:
            contract = _ib_insync.Stock(symbol, exchange, currency)
            self._ib.qualifyContracts(contract)

            ticker = self._ib.reqMktData(contract, genericTickList="", snapshot=True,
                                         regulatorySnapshot=False)
            await asyncio.sleep(2)  # wait for data

            return {
                "symbol": symbol,
                "bid": ticker.bid if ticker.bid != -1 else None,
                "ask": ticker.ask if ticker.ask != -1 else None,
                "last": ticker.last if ticker.last != -1 else None,
                "volume": ticker.volume if ticker.volume != -1 else None,
                "high": ticker.high if ticker.high != -1 else None,
                "low": ticker.low if ticker.low != -1 else None,
                "close": ticker.close if ticker.close != -1 else None,
                "open": ticker.open if ticker.open != -1 else None,
            }
        except Exception as e:
            logger.error("IBKR market data error for %s: %s", symbol, e)
            return {"error": str(e), "symbol": symbol}

    async def get_historical_data(self, symbol: str, duration: str = "1 Y",
                                   bar_size: str = "1 day",
                                   exchange: str = "SMART",
                                   currency: str = "USD") -> list[dict]:
        """Fetch historical bars."""
        if not self.is_connected:
            return [self._not_connected()]

        try:
            contract = _ib_insync.Stock(symbol, exchange, currency)
            self._ib.qualifyContracts(contract)

            bars = await asyncio.to_thread(
                self._ib.reqHistoricalData,
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )
            return [
                {
                    "date": str(b.date),
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars
            ]
        except Exception as e:
            logger.error("IBKR historical data error: %s", e)
            return [{"error": str(e)}]

    # ── Order Execution ──────────────────────────────────────────────────

    async def place_order(self, symbol: str, action: str, quantity: float,
                          order_type: str = "MKT", limit_price: float | None = None,
                          stop_price: float | None = None,
                          exchange: str = "SMART", currency: str = "USD") -> dict[str, Any]:
        """Place an order. action: BUY or SELL. order_type: MKT, LMT, STP, STP_LMT."""
        if not self.is_connected:
            return self._not_connected()

        if self.mode == "paper":
            logger.info("IBKR PAPER ORDER: %s %s %s @ %s", action, quantity, symbol, order_type)

        try:
            contract = _ib_insync.Stock(symbol, exchange, currency)
            self._ib.qualifyContracts(contract)

            if order_type == "MKT":
                order = _ib_insync.MarketOrder(action, quantity)
            elif order_type == "LMT" and limit_price:
                order = _ib_insync.LimitOrder(action, quantity, limit_price)
            elif order_type == "STP" and stop_price:
                order = _ib_insync.StopOrder(action, quantity, stop_price)
            elif order_type == "STP_LMT" and stop_price and limit_price:
                order = _ib_insync.Order(
                    action=action,
                    totalQuantity=quantity,
                    orderType="STP LMT",
                    lmtPrice=limit_price,
                    auxPrice=stop_price,
                )
            else:
                return {"error": f"Invalid order_type={order_type} or missing price params"}

            trade = self._ib.placeOrder(contract, order)
            await asyncio.sleep(1)

            return {
                "success": True,
                "order_id": str(trade.order.orderId),
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "order_type": order_type,
                "status": trade.orderStatus.status,
                "filled": trade.orderStatus.filled,
                "avg_fill_price": trade.orderStatus.avgFillPrice,
                "mode": self.mode,
            }
        except Exception as e:
            logger.error("IBKR order error: %s", e)
            return {"error": str(e), "success": False}

    async def cancel_order(self, order_id: int) -> dict:
        if not self.is_connected:
            return self._not_connected()
        try:
            for trade in self._ib.openTrades():
                if trade.order.orderId == order_id:
                    self._ib.cancelOrder(trade.order)
                    return {"success": True, "message": f"Order {order_id} cancelled"}
            return {"error": f"Order {order_id} not found"}
        except Exception as e:
            return {"error": str(e)}

    # ── Portfolio ─────────────────────────────────────────────────────────

    async def get_positions(self) -> list[dict]:
        """Get all current positions."""
        if not self.is_connected:
            return [self._not_connected()]
        try:
            positions = self._ib.positions()
            return [
                {
                    "symbol": p.contract.symbol,
                    "quantity": p.position,
                    "avg_cost": p.avgCost,
                    "market_value": p.position * p.avgCost,
                    "account": p.account,
                }
                for p in positions
            ]
        except Exception as e:
            return [{"error": str(e)}]

    async def get_account_summary(self) -> dict:
        """Get account-level summary (balance, equity, margin)."""
        if not self.is_connected:
            return self._not_connected()
        try:
            summary = self._ib.accountSummary()
            result = {}
            for item in summary:
                result[item.tag] = {"value": item.value, "currency": item.currency}
            return result
        except Exception as e:
            return {"error": str(e)}

    async def get_open_orders(self) -> list[dict]:
        """Get all open/pending orders."""
        if not self.is_connected:
            return [self._not_connected()]
        try:
            trades = self._ib.openTrades()
            return [
                {
                    "order_id": t.order.orderId,
                    "symbol": t.contract.symbol,
                    "action": t.order.action,
                    "quantity": t.order.totalQuantity,
                    "order_type": t.order.orderType,
                    "status": t.orderStatus.status,
                    "filled": t.orderStatus.filled,
                    "remaining": t.orderStatus.remaining,
                }
                for t in trades
            ]
        except Exception as e:
            return [{"error": str(e)}]

    async def get_pnl(self) -> dict:
        """Get portfolio P&L."""
        if not self.is_connected:
            return self._not_connected()
        try:
            pnl_list = self._ib.pnl()
            if pnl_list:
                p = pnl_list[0]
                return {
                    "daily_pnl": p.dailyPnL,
                    "unrealized_pnl": p.unrealizedPnL,
                    "realized_pnl": p.realizedPnL,
                }
            return {"daily_pnl": 0, "unrealized_pnl": 0, "realized_pnl": 0}
        except Exception as e:
            return {"error": str(e)}


# Module-level singleton
_ibkr_client: IBKRClient | None = None


def get_ibkr_client() -> IBKRClient:
    """Get or create the IBKR client singleton."""
    global _ibkr_client
    if _ibkr_client is None:
        from core.config import get_settings
        settings = get_settings()
        _ibkr_client = IBKRClient(
            host=settings.ibkr_host,
            port=settings.ibkr_port,
            client_id=settings.ibkr_client_id,
            mode=settings.ibkr_mode,
        )
    return _ibkr_client
