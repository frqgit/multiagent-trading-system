"""CommSec (Commonwealth Securities) — Australia's largest retail broker.

CommSec offers trading on the ASX and international markets.
Integration uses the CommSec REST API (CDIA+ platform).

Env vars:
    COMMSEC_CLIENT_ID     – OAuth2 client ID
    COMMSEC_CLIENT_SECRET – OAuth2 client secret
    COMMSEC_ACCOUNT_ID    – Trading account number
    COMMSEC_API_URL       – API base URL (default: https://api.commsec.com.au)
    COMMSEC_REFRESH_TOKEN – Long-lived refresh token for auth
"""

from __future__ import annotations

import asyncio
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


class CommSecBroker(BaseBroker):
    """CommSec REST API broker adapter for ASX trading."""

    broker_id = BrokerID.COMMSEC
    display_name = "CommSec (Commonwealth Securities)"
    supported_exchanges = ["ASX"]
    supported_order_types = ["MKT", "LMT", "STP", "STP_LMT"]

    # CommSec fee schedule (as of 2025-2026)
    COMMISSION_FLAT_THRESHOLD = 10_000  # AUD
    COMMISSION_FLAT_FEE = 10.00         # trades ≤ $10k
    COMMISSION_PERCENT = 0.0012         # 0.12% for trades > $10k

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        account_id: str = "",
        api_url: str = "https://api.commsec.com.au",
        refresh_token: str = "",
    ):
        super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self.api_url = api_url.rstrip("/")
        self._refresh_token = refresh_token
        self._access_token: str = ""
        self._token_expiry: datetime = datetime.min
        self._http: httpx.AsyncClient | None = None

    # ── Connection ─────────────────────────────────────────────────────

    async def connect(self) -> bool:
        try:
            self._http = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=30,
                headers={"User-Agent": "MultiAgentTradingSystem/2.0"},
            )
            await self._authenticate()
            self._connected = True
            logger.info("CommSec connected [account=%s]", self.account_id)
            return True
        except Exception as exc:
            logger.error("CommSec connection failed: %s", exc)
            self._connected = False
            return False

    async def disconnect(self) -> bool:
        if self._http:
            await self._http.aclose()
        self._connected = False
        return True

    async def health_check(self) -> dict[str, Any]:
        try:
            await self._ensure_token()
            resp = await self._http.get("/v1/account/status",
                                        headers=self._auth_headers())
            healthy = resp.status_code == 200
        except Exception:
            healthy = False
        self._connected = healthy
        return {"healthy": healthy, "broker": self.broker_id.value,
                "account": self.account_id}

    # ── Auth ───────────────────────────────────────────────────────────

    async def _authenticate(self):
        resp = await self._http.post("/oauth2/token", data={
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self._refresh_token,
        })
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = datetime.utcnow() + timedelta(
            seconds=data.get("expires_in", 3600) - 60
        )
        if "refresh_token" in data:
            self._refresh_token = data["refresh_token"]

    async def _ensure_token(self):
        if datetime.utcnow() >= self._token_expiry:
            await self._authenticate()

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    # ── Market Data ────────────────────────────────────────────────────

    async def get_quote(self, symbol: str, exchange: str = "ASX",
                        currency: str = "AUD") -> BrokerQuote:
        await self._ensure_token()
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
        await self._ensure_token()
        resp = await self._http.get(
            f"/v1/market/history/{symbol}",
            headers=self._auth_headers(),
            params={"duration": duration, "interval": bar_size, "exchange": exchange},
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
        await self._ensure_token()
        payload = {
            "accountId": self.account_id,
            "symbol": order.symbol,
            "exchange": order.exchange or "ASX",
            "side": order.side,
            "orderType": order.order_type,
            "quantity": int(order.quantity),
        }
        if order.limit_price:
            payload["limitPrice"] = order.limit_price
        if order.stop_price:
            payload["stopPrice"] = order.stop_price

        try:
            resp = await self._http.post(
                "/v1/orders", json=payload, headers=self._auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            order.broker_order_id = data.get("orderId", "")
            order.status = self._map_status(data.get("status", "submitted"))
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
        await self._ensure_token()
        resp = await self._http.delete(
            f"/v1/orders/{order_id}", headers=self._auth_headers(),
        )
        status = OrderStatus.CANCELLED.value if resp.status_code == 200 else OrderStatus.ERROR.value
        return BrokerOrder(order_id=order_id, status=status,
                           broker=self.broker_id.value)

    async def modify_order(self, order_id: str, **kwargs) -> BrokerOrder:
        await self._ensure_token()
        resp = await self._http.put(
            f"/v1/orders/{order_id}", json=kwargs, headers=self._auth_headers(),
        )
        data = resp.json() if resp.status_code == 200 else {}
        return BrokerOrder(
            order_id=order_id,
            status=self._map_status(data.get("status", "error")),
            broker=self.broker_id.value,
        )

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        await self._ensure_token()
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
        await self._ensure_token()
        resp = await self._http.get(
            "/v1/orders", headers=self._auth_headers(),
            params={"accountId": self.account_id, "status": "open"},
        )
        orders = resp.json().get("orders", [])
        return [
            BrokerOrder(
                order_id=o.get("orderId", ""),
                broker=self.broker_id.value,
                symbol=o.get("symbol", ""),
                side=o.get("side", ""),
                order_type=o.get("orderType", ""),
                quantity=o.get("quantity", 0),
                status=self._map_status(o.get("status", "")),
            )
            for o in orders
        ]

    # ── Positions & Account ────────────────────────────────────────────

    async def get_positions(self) -> list[BrokerPosition]:
        await self._ensure_token()
        resp = await self._http.get(
            f"/v1/accounts/{self.account_id}/positions",
            headers=self._auth_headers(),
        )
        positions = resp.json().get("positions", [])
        return [
            BrokerPosition(
                symbol=p.get("symbol", ""),
                broker=self.broker_id.value,
                quantity=p.get("quantity", 0),
                avg_cost=p.get("avgCost", 0),
                current_price=p.get("lastPrice", 0),
                market_value=p.get("marketValue", 0),
                unrealized_pnl=p.get("unrealizedPnl", 0),
                realized_pnl=p.get("realizedPnl", 0),
                currency="AUD",
            )
            for p in positions
        ]

    async def get_account(self) -> BrokerAccount:
        await self._ensure_token()
        resp = await self._http.get(
            f"/v1/accounts/{self.account_id}/summary",
            headers=self._auth_headers(),
        )
        d = resp.json()
        return BrokerAccount(
            broker=self.broker_id.value,
            account_id=self.account_id,
            cash_balance=d.get("cashBalance", 0),
            portfolio_value=d.get("portfolioValue", 0),
            total_equity=d.get("totalEquity", 0),
            margin_used=d.get("marginUsed", 0),
            margin_available=d.get("marginAvailable", 0),
            unrealized_pnl=d.get("unrealizedPnl", 0),
            realized_pnl=d.get("realizedPnl", 0),
            buying_power=d.get("buyingPower", 0),
            currency="AUD",
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _calculate_commission(self, trade_value: float) -> float:
        if trade_value <= self.COMMISSION_FLAT_THRESHOLD:
            return self.COMMISSION_FLAT_FEE
        return round(trade_value * self.COMMISSION_PERCENT, 2)

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
