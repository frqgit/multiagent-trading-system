"""IG Markets — Australian CFD/share trading broker.

IG Markets offers DMA (Direct Market Access) to ASX and international
markets via a well-documented REST + streaming API.

Docs: https://labs.ig.com/rest-trading-api-reference
Env vars:
    IG_API_KEY        – API key from IG Labs
    IG_USERNAME       – IG account username
    IG_PASSWORD       – IG account password
    IG_ACCOUNT_ID     – IG trading account ID
    IG_API_URL        – API base URL (default: https://api.ig.com/gateway/deal)
    IG_DEMO           – "false" for live (default "false")
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


class IGMarketsBroker(BaseBroker):
    """IG Markets REST API broker adapter."""

    broker_id = BrokerID.IG_MARKETS
    display_name = "IG Markets"
    supported_exchanges = ["ASX", "NYSE", "NASDAQ", "LSE"]
    supported_order_types = ["MKT", "LMT", "STP"]

    def __init__(
        self,
        api_key: str = "",
        username: str = "",
        password: str = "",
        account_id: str = "",
        api_url: str = "https://api.ig.com/gateway/deal",
        demo: bool = False,
    ):
        super().__init__()
        self.api_key = api_key
        self.username = username
        self.password = password
        self.account_id = account_id
        self.api_url = api_url.rstrip("/")
        self.demo = demo
        self._cst: str = ""           # Client session token
        self._security_token: str = ""  # X-SECURITY-TOKEN
        self._http: httpx.AsyncClient | None = None

    # ── Connection ─────────────────────────────────────────────────────

    async def connect(self) -> bool:
        try:
            base = "https://demo-api.ig.com/gateway/deal" if self.demo else self.api_url
            self._http = httpx.AsyncClient(base_url=base, timeout=30)
            resp = await self._http.post(
                "/session",
                json={"identifier": self.username, "password": self.password},
                headers={
                    "X-IG-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json; charset=UTF-8",
                    "VERSION": "3",
                },
            )
            resp.raise_for_status()
            self._cst = resp.headers.get("CST", "")
            self._security_token = resp.headers.get("X-SECURITY-TOKEN", "")
            data = resp.json()
            if self.account_id and data.get("currentAccountId") != self.account_id:
                await self._switch_account(self.account_id)
            self._connected = True
            logger.info("IG Markets connected [account=%s]", self.account_id or data.get("currentAccountId"))
            return True
        except Exception as exc:
            logger.error("IG Markets connection failed: %s", exc)
            return False

    async def _switch_account(self, account_id: str):
        resp = await self._http.put(
            "/session",
            json={"accountId": account_id, "defaultAccount": "false"},
            headers=self._auth_headers(version="1"),
        )
        resp.raise_for_status()

    async def disconnect(self) -> bool:
        if self._http:
            try:
                await self._http.delete("/session", headers=self._auth_headers())
            except Exception:
                pass
            await self._http.aclose()
        self._connected = False
        return True

    async def health_check(self) -> dict[str, Any]:
        try:
            resp = await self._http.get("/session", headers=self._auth_headers())
            healthy = resp.status_code == 200
        except Exception:
            healthy = False
        self._connected = healthy
        return {"healthy": healthy, "broker": self.broker_id.value}

    def _auth_headers(self, version: str = "2") -> dict[str, str]:
        return {
            "X-IG-API-KEY": self.api_key,
            "CST": self._cst,
            "X-SECURITY-TOKEN": self._security_token,
            "Content-Type": "application/json",
            "Accept": "application/json; charset=UTF-8",
            "VERSION": version,
        }

    # ── Market Data ────────────────────────────────────────────────────

    async def get_quote(self, symbol: str, exchange: str = "ASX",
                        currency: str = "AUD") -> BrokerQuote:
        epic = self._symbol_to_epic(symbol, exchange)
        resp = await self._http.get(
            f"/markets/{epic}", headers=self._auth_headers(),
        )
        resp.raise_for_status()
        snap = resp.json().get("snapshot", {})
        return BrokerQuote(
            symbol=symbol, broker=self.broker_id.value,
            bid=snap.get("bid"), ask=snap.get("offer"),
            last=snap.get("marketPrice"),
            high=snap.get("high"), low=snap.get("low"),
        )

    async def get_historical_bars(self, symbol: str, duration: str = "1Y",
                                   bar_size: str = "1d", exchange: str = "ASX",
                                   currency: str = "AUD") -> list[BrokerBar]:
        epic = self._symbol_to_epic(symbol, exchange)
        resolution = self._bar_size_to_resolution(bar_size)
        resp = await self._http.get(
            f"/prices/{epic}", headers=self._auth_headers(version="3"),
            params={"resolution": resolution, "max": 365, "pageSize": 0},
        )
        resp.raise_for_status()
        prices = resp.json().get("prices", [])
        bars = []
        for p in prices:
            o = p.get("openPrice", {})
            h = p.get("highPrice", {})
            l = p.get("lowPrice", {})
            c = p.get("closePrice", {})
            bars.append(BrokerBar(
                date=p.get("snapshotTime", ""),
                open=(o.get("bid", 0) + o.get("ask", 0)) / 2 if o else 0,
                high=(h.get("bid", 0) + h.get("ask", 0)) / 2 if h else 0,
                low=(l.get("bid", 0) + l.get("ask", 0)) / 2 if l else 0,
                close=(c.get("bid", 0) + c.get("ask", 0)) / 2 if c else 0,
                volume=p.get("lastTradedVolume", 0),
            ))
        return bars

    # ── Orders ─────────────────────────────────────────────────────────

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        epic = self._symbol_to_epic(order.symbol, order.exchange or "ASX")
        direction = "BUY" if order.side == OrderSide.BUY.value else "SELL"

        payload: dict[str, Any] = {
            "epic": epic,
            "direction": direction,
            "size": order.quantity,
            "orderType": self._map_order_type(order.order_type),
            "currencyCode": order.currency or "AUD",
            "guaranteedStop": "false",
            "forceOpen": "true",
        }
        if order.limit_price:
            payload["level"] = order.limit_price
        if order.stop_loss_price:
            payload["stopLevel"] = order.stop_loss_price
        if order.take_profit_price:
            payload["limitLevel"] = order.take_profit_price

        try:
            resp = await self._http.post(
                "/positions/otc", json=payload,
                headers=self._auth_headers(version="2"),
            )
            resp.raise_for_status()
            data = resp.json()
            deal_ref = data.get("dealReference", "")
            # Confirm deal
            confirm = await self._confirm_deal(deal_ref)
            order.broker_order_id = confirm.get("dealId", deal_ref)
            order.status = OrderStatus.FILLED.value if confirm.get("dealStatus") == "ACCEPTED" else OrderStatus.REJECTED.value
            order.avg_fill_price = confirm.get("level", 0)
            order.filled_qty = confirm.get("size", order.quantity)
            order.updated_at = datetime.utcnow()
            if confirm.get("reason"):
                order.error_message = confirm["reason"]
            return order
        except httpx.HTTPStatusError as exc:
            order.status = OrderStatus.REJECTED.value
            order.error_message = str(exc.response.text)
            return order

    async def _confirm_deal(self, deal_ref: str) -> dict:
        import asyncio
        await asyncio.sleep(1)
        resp = await self._http.get(
            f"/confirms/{deal_ref}", headers=self._auth_headers(),
        )
        return resp.json() if resp.status_code == 200 else {}

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        resp = await self._http.delete(
            f"/positions/otc/{order_id}", headers=self._auth_headers(),
        )
        status = OrderStatus.CANCELLED.value if resp.status_code == 200 else OrderStatus.ERROR.value
        return BrokerOrder(order_id=order_id, status=status, broker=self.broker_id.value)

    async def modify_order(self, order_id: str, **kwargs) -> BrokerOrder:
        payload = {}
        if "stop_loss_price" in kwargs:
            payload["stopLevel"] = kwargs["stop_loss_price"]
        if "take_profit_price" in kwargs:
            payload["limitLevel"] = kwargs["take_profit_price"]
        resp = await self._http.put(
            f"/positions/otc/{order_id}", json=payload,
            headers=self._auth_headers(),
        )
        return BrokerOrder(
            order_id=order_id,
            status=OrderStatus.ACCEPTED.value if resp.status_code == 200 else OrderStatus.ERROR.value,
            broker=self.broker_id.value,
        )

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        resp = await self._http.get(
            f"/positions/{order_id}", headers=self._auth_headers(),
        )
        data = resp.json() if resp.status_code == 200 else {}
        pos = data.get("position", {})
        return BrokerOrder(
            order_id=order_id,
            broker_order_id=pos.get("dealId", ""),
            status=OrderStatus.FILLED.value if pos else OrderStatus.ERROR.value,
            filled_qty=pos.get("dealSize", 0),
            avg_fill_price=pos.get("openLevel", 0),
            broker=self.broker_id.value,
        )

    async def get_open_orders(self) -> list[BrokerOrder]:
        resp = await self._http.get(
            "/workingorders", headers=self._auth_headers(version="2"),
        )
        orders = resp.json().get("workingOrders", [])
        return [
            BrokerOrder(
                order_id=o.get("workingOrderData", {}).get("dealId", ""),
                broker=self.broker_id.value,
                symbol=o.get("marketData", {}).get("instrumentName", ""),
                side=o.get("workingOrderData", {}).get("direction", ""),
                quantity=o.get("workingOrderData", {}).get("orderSize", 0),
                status=OrderStatus.SUBMITTED.value,
            )
            for o in orders
        ]

    # ── Positions & Account ────────────────────────────────────────────

    async def get_positions(self) -> list[BrokerPosition]:
        resp = await self._http.get(
            "/positions", headers=self._auth_headers(version="2"),
        )
        positions = resp.json().get("positions", [])
        return [
            BrokerPosition(
                symbol=p.get("market", {}).get("instrumentName", ""),
                broker=self.broker_id.value,
                quantity=p.get("position", {}).get("dealSize", 0),
                avg_cost=p.get("position", {}).get("openLevel", 0),
                current_price=p.get("market", {}).get("bid", 0),
                unrealized_pnl=p.get("position", {}).get("profitLoss", 0),
                currency=p.get("position", {}).get("currency", "AUD"),
            )
            for p in positions
        ]

    async def get_account(self) -> BrokerAccount:
        resp = await self._http.get(
            "/accounts", headers=self._auth_headers(),
        )
        accounts = resp.json().get("accounts", [])
        acct_data = next(
            (a for a in accounts if a.get("accountId") == self.account_id),
            accounts[0] if accounts else {},
        )
        bal = acct_data.get("balance", {})
        return BrokerAccount(
            broker=self.broker_id.value,
            account_id=acct_data.get("accountId", ""),
            cash_balance=bal.get("available", 0),
            portfolio_value=bal.get("balance", 0),
            total_equity=bal.get("balance", 0),
            margin_used=bal.get("deposit", 0),
            margin_available=bal.get("available", 0),
            unrealized_pnl=bal.get("profitLoss", 0),
            buying_power=bal.get("available", 0),
            currency=acct_data.get("currency", "AUD"),
        )

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _symbol_to_epic(symbol: str, exchange: str) -> str:
        """Convert symbol + exchange to IG epic format.
        e.g., CBA on ASX → 'AA.D.CBA.DAILY.IP'
        """
        if exchange.upper() == "ASX":
            return f"AA.D.{symbol.upper()}.DAILY.IP"
        elif exchange.upper() in ("NYSE", "NASDAQ"):
            return f"UA.D.{symbol.upper()}.DAILY.IP"
        return f"IX.D.{symbol.upper()}.DAILY.IP"

    @staticmethod
    def _bar_size_to_resolution(bar_size: str) -> str:
        mapping = {"1m": "MINUTE", "5m": "MINUTE_5", "15m": "MINUTE_15",
                    "1h": "HOUR", "4h": "HOUR_4", "1d": "DAY", "1w": "WEEK"}
        return mapping.get(bar_size, "DAY")

    @staticmethod
    def _map_order_type(ot: str) -> str:
        mapping = {
            OrderType.MARKET.value: "MARKET",
            OrderType.LIMIT.value: "LIMIT",
            OrderType.STOP.value: "STOP",
        }
        return mapping.get(ot, "MARKET")
