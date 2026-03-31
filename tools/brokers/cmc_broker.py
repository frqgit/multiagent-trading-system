"""CMC Markets — Australian-based global CFD & share trading broker.

CMC Markets provides DMA access to ASX and international markets through
their Next Generation platform REST API.

Docs: https://www.cmcmarkets.com/en-au/api-documentation
Env vars:
    CMC_API_KEY      – API key
    CMC_USERNAME     – CMC account username
    CMC_PASSWORD     – Account password
    CMC_ACCOUNT_ID   – Trading account ID
    CMC_API_URL      – API base (default: https://ciapi.cityindex.com/TradingAPI)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx

from tools.broker_base import (
    BaseBroker, BrokerID, BrokerQuote, BrokerBar, BrokerOrder, BrokerPosition,
    BrokerAccount, OrderType, OrderSide, OrderStatus,
)

logger = logging.getLogger(__name__)


class CMCMarketsBroker(BaseBroker):
    """CMC Markets REST API broker adapter."""

    broker_id = BrokerID.CMC_MARKETS
    display_name = "CMC Markets"
    supported_exchanges = ["ASX", "NYSE", "NASDAQ", "LSE"]
    supported_order_types = ["MKT", "LMT", "STP", "STP_LMT"]

    # CMC Markets fee schedule (ASX shares)
    COMMISSION_RATE = 0.0010  # 0.10% or $11 min
    COMMISSION_MIN = 11.00

    def __init__(
        self,
        api_key: str = "",
        username: str = "",
        password: str = "",
        account_id: str = "",
        api_url: str = "https://ciapi.cityindex.com/TradingAPI",
    ):
        super().__init__()
        self.api_key = api_key
        self.username = username
        self.password = password
        self.account_id = account_id
        self.api_url = api_url.rstrip("/")
        self._session_token: str = ""
        self._http: httpx.AsyncClient | None = None

    # ── Connection ─────────────────────────────────────────────────────

    async def connect(self) -> bool:
        try:
            self._http = httpx.AsyncClient(base_url=self.api_url, timeout=30)
            resp = await self._http.post(
                "/session",
                json={
                    "UserName": self.username,
                    "Password": self.password,
                    "AppKey": self.api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._session_token = data.get("Session", "")
            self._connected = True
            logger.info("CMC Markets connected [account=%s]", self.account_id)
            return True
        except Exception as exc:
            logger.error("CMC Markets connection failed: %s", exc)
            return False

    async def disconnect(self) -> bool:
        if self._http and self._session_token:
            try:
                await self._http.post(
                    "/session/deleteSession",
                    params={"UserName": self.username, "Session": self._session_token},
                )
            except Exception:
                pass
            await self._http.aclose()
        self._connected = False
        return True

    async def health_check(self) -> dict[str, Any]:
        try:
            resp = await self._http.get(
                "/useraccount/ClientAndTradingAccount",
                headers=self._auth_headers(),
            )
            healthy = resp.status_code == 200
        except Exception:
            healthy = False
        self._connected = healthy
        return {"healthy": healthy, "broker": self.broker_id.value}

    def _auth_headers(self) -> dict[str, str]:
        return {
            "UserName": self.username,
            "Session": self._session_token,
            "Content-Type": "application/json",
        }

    # ── Market Data ────────────────────────────────────────────────────

    async def get_quote(self, symbol: str, exchange: str = "ASX",
                        currency: str = "AUD") -> BrokerQuote:
        market_id = self._resolve_market_id(symbol, exchange)
        resp = await self._http.get(
            f"/market/{market_id}/information", headers=self._auth_headers(),
        )
        resp.raise_for_status()
        m = resp.json().get("MarketInformation", {})
        return BrokerQuote(
            symbol=symbol, broker=self.broker_id.value,
            bid=m.get("Bid"), ask=m.get("Offer"),
            last=m.get("Price"), high=m.get("High"), low=m.get("Low"),
        )

    async def get_historical_bars(self, symbol: str, duration: str = "1Y",
                                   bar_size: str = "1d", exchange: str = "ASX",
                                   currency: str = "AUD") -> list[BrokerBar]:
        market_id = self._resolve_market_id(symbol, exchange)
        interval = self._bar_size_to_interval(bar_size)
        span_count = self._duration_to_count(duration)
        resp = await self._http.get(
            f"/market/{market_id}/barhistory",
            params={"interval": interval, "span": span_count, "PriceBars": "MID"},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        bars_data = resp.json().get("PriceBars", [])
        return [
            BrokerBar(
                date=b.get("BarDate", ""),
                open=b.get("Open", 0),
                high=b.get("High", 0),
                low=b.get("Low", 0),
                close=b.get("Close", 0),
                volume=b.get("Volume", 0),
            )
            for b in bars_data
        ]

    # ── Orders ─────────────────────────────────────────────────────────

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        market_id = self._resolve_market_id(order.symbol, order.exchange or "ASX")
        direction = "buy" if order.side == OrderSide.BUY.value else "sell"

        payload: dict[str, Any] = {
            "MarketId": market_id,
            "Direction": direction,
            "Quantity": order.quantity,
            "TradingAccountId": self.account_id,
            "OfferPrice": order.limit_price,
            "BidPrice": order.limit_price,
        }

        endpoint = "/order/newtradeorder"
        if order.order_type == OrderType.LIMIT.value:
            endpoint = "/order/newstoplimitorder"
            payload["OrderType"] = "Limit"
            if order.limit_price:
                payload["TriggerPrice"] = order.limit_price
        elif order.order_type == OrderType.STOP.value:
            endpoint = "/order/newstoplimitorder"
            payload["OrderType"] = "Stop"
            if order.stop_price:
                payload["TriggerPrice"] = order.stop_price

        try:
            resp = await self._http.post(
                endpoint, json=payload, headers=self._auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            order.broker_order_id = str(data.get("OrderId", ""))
            order.status = (OrderStatus.FILLED.value
                           if data.get("StatusReason") == 1
                           else OrderStatus.SUBMITTED.value)
            order.commission = self._calculate_commission(
                order.quantity * (order.limit_price or order.avg_fill_price or 0)
            )
            order.updated_at = datetime.utcnow()
            return order
        except httpx.HTTPStatusError as exc:
            order.status = OrderStatus.REJECTED.value
            order.error_message = str(exc.response.text)
            return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        resp = await self._http.post(
            "/order/cancel", json={"OrderId": int(order_id),
                                    "TradingAccountId": self.account_id},
            headers=self._auth_headers(),
        )
        status = OrderStatus.CANCELLED.value if resp.status_code == 200 else OrderStatus.ERROR.value
        return BrokerOrder(order_id=order_id, status=status, broker=self.broker_id.value)

    async def modify_order(self, order_id: str, **kwargs) -> BrokerOrder:
        payload: dict[str, Any] = {"OrderId": int(order_id),
                                    "TradingAccountId": self.account_id}
        if "limit_price" in kwargs:
            payload["TriggerPrice"] = kwargs["limit_price"]
        if "quantity" in kwargs:
            payload["Quantity"] = kwargs["quantity"]
        resp = await self._http.put(
            "/order/updatetradeorder", json=payload, headers=self._auth_headers(),
        )
        return BrokerOrder(
            order_id=order_id,
            status=OrderStatus.ACCEPTED.value if resp.status_code == 200 else OrderStatus.ERROR.value,
            broker=self.broker_id.value,
        )

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        resp = await self._http.get(
            "/order/openpositions",
            params={"TradingAccountId": self.account_id},
            headers=self._auth_headers(),
        )
        orders = resp.json().get("OpenPositions", [])
        for o in orders:
            if str(o.get("OrderId")) == order_id:
                return BrokerOrder(
                    order_id=order_id,
                    broker_order_id=str(o.get("OrderId", "")),
                    status=OrderStatus.FILLED.value,
                    filled_qty=o.get("Quantity", 0),
                    avg_fill_price=o.get("Price", 0),
                    broker=self.broker_id.value,
                )
        return BrokerOrder(order_id=order_id, status=OrderStatus.ERROR.value,
                           broker=self.broker_id.value)

    async def get_open_orders(self) -> list[BrokerOrder]:
        resp = await self._http.get(
            "/order/activeorders",
            params={"TradingAccountId": self.account_id},
            headers=self._auth_headers(),
        )
        orders = resp.json().get("ActiveOrders", [])
        return [
            BrokerOrder(
                order_id=str(o.get("OrderId", "")),
                broker=self.broker_id.value,
                symbol=str(o.get("MarketId", "")),
                side="BUY" if o.get("Direction", "").lower() == "buy" else "SELL",
                quantity=o.get("Quantity", 0),
                status=OrderStatus.SUBMITTED.value,
            )
            for o in orders
        ]

    # ── Positions & Account ────────────────────────────────────────────

    async def get_positions(self) -> list[BrokerPosition]:
        resp = await self._http.get(
            "/order/openpositions",
            params={"TradingAccountId": self.account_id},
            headers=self._auth_headers(),
        )
        positions = resp.json().get("OpenPositions", [])
        return [
            BrokerPosition(
                symbol=str(p.get("MarketId", "")),
                broker=self.broker_id.value,
                quantity=p.get("Quantity", 0),
                avg_cost=p.get("Price", 0),
                current_price=p.get("CurrentPrice", 0),
                unrealized_pnl=p.get("UnrealisedPnL", 0),
                realized_pnl=p.get("RealisedPnL", 0),
                currency=p.get("Currency", "AUD"),
            )
            for p in positions
        ]

    async def get_account(self) -> BrokerAccount:
        resp = await self._http.get(
            "/margin/ClientAccountMargin",
            headers=self._auth_headers(),
        )
        d = resp.json()
        return BrokerAccount(
            broker=self.broker_id.value,
            account_id=self.account_id,
            cash_balance=d.get("Cash", 0),
            portfolio_value=d.get("NetEquity", 0),
            total_equity=d.get("NetEquity", 0),
            margin_used=d.get("Margin", 0),
            margin_available=d.get("MarginAvailable", 0),
            unrealized_pnl=d.get("UnrealisedPnL", 0),
            buying_power=d.get("TradingResource", 0),
            currency=d.get("Currency", "AUD"),
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _resolve_market_id(self, symbol: str, exchange: str) -> str:
        """CMC uses numeric market IDs — this is a simplified mapper.
        In production you'd call /market/search?SearchByMarketName=...
        """
        return f"{symbol}.{exchange}"

    @staticmethod
    def _bar_size_to_interval(bar_size: str) -> str:
        mapping = {"1m": "MINUTE", "5m": "MINUTE_5", "15m": "MINUTE_15",
                    "1h": "HOUR", "4h": "HOUR_4", "1d": "DAY", "1w": "WEEK"}
        return mapping.get(bar_size, "DAY")

    @staticmethod
    def _duration_to_count(duration: str) -> int:
        d = duration.upper()
        if "Y" in d:
            return 365
        if "M" in d:
            return 30
        if "W" in d:
            return 7
        return 365

    def _calculate_commission(self, trade_value: float) -> float:
        fee = max(trade_value * self.COMMISSION_RATE, self.COMMISSION_MIN)
        return round(fee, 2)
