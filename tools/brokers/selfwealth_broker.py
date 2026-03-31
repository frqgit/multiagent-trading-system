"""SelfWealth — Australian flat-fee share trading broker.

SelfWealth offers $9.50 flat-fee ASX trades and access to US markets.
Integration uses the SelfWealth REST API.

Env vars:
    SELFWEALTH_API_KEY     – API key
    SELFWEALTH_CLIENT_ID   – OAuth client ID
    SELFWEALTH_SECRET      – OAuth client secret
    SELFWEALTH_ACCOUNT_ID  – Trading account
    SELFWEALTH_API_URL     – Base URL (default: https://api.selfwealth.com.au)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from tools.broker_base import (
    BaseBroker, BrokerID, BrokerQuote, BrokerBar, BrokerOrder, BrokerPosition,
    BrokerAccount, OrderType, OrderSide, OrderStatus,
)

logger = logging.getLogger(__name__)


class SelfWealthBroker(BaseBroker):
    """SelfWealth REST API broker adapter."""

    broker_id = BrokerID.SELFWEALTH
    display_name = "SelfWealth"
    supported_exchanges = ["ASX", "NYSE", "NASDAQ"]
    supported_order_types = ["MKT", "LMT"]

    # SelfWealth flat fee schedule
    COMMISSION_ASX = 9.50    # flat fee for ASX
    COMMISSION_US = 9.50     # flat fee for US

    def __init__(
        self,
        api_key: str = "",
        client_id: str = "",
        client_secret: str = "",
        account_id: str = "",
        api_url: str = "https://api.selfwealth.com.au",
    ):
        super().__init__()
        self.api_key = api_key
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self.api_url = api_url.rstrip("/")
        self._access_token: str = ""
        self._http: httpx.AsyncClient | None = None

    # ── Connection ─────────────────────────────────────────────────────

    async def connect(self) -> bool:
        try:
            self._http = httpx.AsyncClient(base_url=self.api_url, timeout=30)
            resp = await self._http.post(
                "/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()
            self._access_token = resp.json().get("access_token", "")
            self._connected = True
            logger.info("SelfWealth connected [account=%s]", self.account_id)
            return True
        except Exception as exc:
            logger.error("SelfWealth connection failed: %s", exc)
            return False

    async def disconnect(self) -> bool:
        if self._http:
            await self._http.aclose()
        self._connected = False
        return True

    async def health_check(self) -> dict[str, Any]:
        try:
            resp = await self._http.get("/v1/health", headers=self._auth_headers())
            healthy = resp.status_code == 200
        except Exception:
            healthy = False
        self._connected = healthy
        return {"healthy": healthy, "broker": self.broker_id.value}

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    # ── Market Data ────────────────────────────────────────────────────

    async def get_quote(self, symbol: str, exchange: str = "ASX",
                        currency: str = "AUD") -> BrokerQuote:
        resp = await self._http.get(
            f"/v1/market/quote/{symbol}",
            headers=self._auth_headers(),
            params={"exchange": exchange},
        )
        resp.raise_for_status()
        d = resp.json()
        return BrokerQuote(
            symbol=symbol, broker=self.broker_id.value,
            bid=d.get("bid"), ask=d.get("ask"), last=d.get("last"),
            volume=d.get("volume"), open=d.get("open"),
            high=d.get("high"), low=d.get("low"), close=d.get("close"),
        )

    async def get_historical_bars(self, symbol: str, duration: str = "1Y",
                                   bar_size: str = "1d", exchange: str = "ASX",
                                   currency: str = "AUD") -> list[BrokerBar]:
        resp = await self._http.get(
            f"/v1/market/history/{symbol}",
            headers=self._auth_headers(),
            params={"duration": duration, "interval": bar_size},
        )
        resp.raise_for_status()
        bars = resp.json().get("bars", [])
        return [
            BrokerBar(date=b["date"], open=b["open"], high=b["high"],
                      low=b["low"], close=b["close"], volume=b.get("volume", 0))
            for b in bars
        ]

    # ── Orders ─────────────────────────────────────────────────────────

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        payload = {
            "accountId": self.account_id,
            "symbol": order.symbol,
            "exchange": order.exchange or "ASX",
            "side": order.side,
            "orderType": "MARKET" if order.order_type == OrderType.MARKET.value else "LIMIT",
            "quantity": int(order.quantity),
        }
        if order.limit_price:
            payload["limitPrice"] = order.limit_price

        try:
            resp = await self._http.post(
                "/v1/orders", json=payload, headers=self._auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            order.broker_order_id = data.get("orderId", "")
            order.status = self._map_status(data.get("status", "submitted"))
            order.commission = self._get_commission(order.exchange or "ASX")
            order.updated_at = datetime.utcnow()
            return order
        except httpx.HTTPStatusError as exc:
            order.status = OrderStatus.REJECTED.value
            order.error_message = str(exc.response.text)
            return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        resp = await self._http.delete(
            f"/v1/orders/{order_id}", headers=self._auth_headers(),
        )
        status = OrderStatus.CANCELLED.value if resp.status_code == 200 else OrderStatus.ERROR.value
        return BrokerOrder(order_id=order_id, status=status, broker=self.broker_id.value)

    async def modify_order(self, order_id: str, **kwargs) -> BrokerOrder:
        resp = await self._http.put(
            f"/v1/orders/{order_id}", json=kwargs, headers=self._auth_headers(),
        )
        return BrokerOrder(
            order_id=order_id,
            status=OrderStatus.ACCEPTED.value if resp.status_code == 200 else OrderStatus.ERROR.value,
            broker=self.broker_id.value,
        )

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        resp = await self._http.get(
            f"/v1/orders/{order_id}", headers=self._auth_headers(),
        )
        data = resp.json()
        return BrokerOrder(
            order_id=order_id,
            broker_order_id=data.get("orderId", ""),
            status=self._map_status(data.get("status", "unknown")),
            filled_qty=data.get("filledQty", 0),
            avg_fill_price=data.get("avgPrice", 0),
            broker=self.broker_id.value,
        )

    async def get_open_orders(self) -> list[BrokerOrder]:
        resp = await self._http.get(
            "/v1/orders",
            headers=self._auth_headers(),
            params={"accountId": self.account_id, "status": "open"},
        )
        orders = resp.json().get("orders", [])
        return [
            BrokerOrder(
                order_id=o.get("orderId", ""),
                broker=self.broker_id.value,
                symbol=o.get("symbol", ""),
                side=o.get("side", ""),
                quantity=o.get("quantity", 0),
                status=self._map_status(o.get("status", "")),
            )
            for o in orders
        ]

    # ── Positions & Account ────────────────────────────────────────────

    async def get_positions(self) -> list[BrokerPosition]:
        resp = await self._http.get(
            f"/v1/accounts/{self.account_id}/holdings",
            headers=self._auth_headers(),
        )
        holdings = resp.json().get("holdings", [])
        return [
            BrokerPosition(
                symbol=h.get("symbol", ""),
                broker=self.broker_id.value,
                quantity=h.get("quantity", 0),
                avg_cost=h.get("avgCost", 0),
                current_price=h.get("lastPrice", 0),
                market_value=h.get("marketValue", 0),
                unrealized_pnl=h.get("unrealizedPnl", 0),
                currency="AUD",
            )
            for h in holdings
        ]

    async def get_account(self) -> BrokerAccount:
        resp = await self._http.get(
            f"/v1/accounts/{self.account_id}",
            headers=self._auth_headers(),
        )
        d = resp.json()
        return BrokerAccount(
            broker=self.broker_id.value,
            account_id=self.account_id,
            cash_balance=d.get("cashBalance", 0),
            portfolio_value=d.get("portfolioValue", 0),
            total_equity=d.get("totalEquity", 0),
            buying_power=d.get("buyingPower", 0),
            unrealized_pnl=d.get("unrealizedPnl", 0),
            currency="AUD",
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_commission(self, exchange: str) -> float:
        if exchange.upper() in ("NYSE", "NASDAQ"):
            return self.COMMISSION_US
        return self.COMMISSION_ASX

    @staticmethod
    def _map_status(raw: str) -> str:
        mapping = {
            "submitted": OrderStatus.SUBMITTED.value,
            "accepted": OrderStatus.ACCEPTED.value,
            "filled": OrderStatus.FILLED.value,
            "partially_filled": OrderStatus.PARTIALLY_FILLED.value,
            "cancelled": OrderStatus.CANCELLED.value,
            "rejected": OrderStatus.REJECTED.value,
            "expired": OrderStatus.EXPIRED.value,
        }
        return mapping.get(raw.lower(), OrderStatus.PENDING.value)
