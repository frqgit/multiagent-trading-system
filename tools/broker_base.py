"""Abstract broker interface — defines the contract all broker integrations must follow.

Enterprise-grade broker abstraction supporting:
- Real market data (quotes, L2, historical bars)
- Real order execution (market, limit, stop, stop-limit, trailing-stop, bracket)
- Position and account management
- Order lifecycle tracking
- Connection health monitoring
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────────────────

class BrokerID(str, Enum):
    """Supported Australian brokers."""
    IBKR = "ibkr"
    COMMSEC = "commsec"
    IG_MARKETS = "ig_markets"
    CMC_MARKETS = "cmc_markets"
    SELFWEALTH = "selfwealth"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"
    TRAILING_STOP = "TRAIL"
    BRACKET = "BRACKET"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"


class Exchange(str, Enum):
    ASX = "ASX"          # Australian Securities Exchange
    SMART = "SMART"      # IBKR smart routing
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    LSE = "LSE"          # London Stock Exchange
    CBOE_AU = "CBOE_AU"  # Cboe Australia


class Currency(str, Enum):
    AUD = "AUD"
    USD = "USD"
    GBP = "GBP"
    EUR = "EUR"


# ── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class BrokerQuote:
    """Real-time quote snapshot."""
    symbol: str
    broker: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BrokerBar:
    """Historical price bar."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class BrokerOrder:
    """Standardised order representation across all brokers."""
    order_id: str
    broker_order_id: str = ""   # broker's native order ID
    broker: str = ""
    symbol: str = ""
    exchange: str = "ASX"
    currency: str = "AUD"
    side: str = "BUY"
    order_type: str = "MKT"
    quantity: float = 0
    limit_price: float | None = None
    stop_price: float | None = None
    trail_percent: float | None = None
    # bracket legs
    take_profit_price: float | None = None
    stop_loss_price: float | None = None
    status: str = "pending"
    filled_qty: float = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: str = ""


@dataclass
class BrokerPosition:
    """Standardised position representation."""
    symbol: str
    broker: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    currency: str = "AUD"


@dataclass
class BrokerAccount:
    """Standardised account summary."""
    broker: str
    account_id: str = ""
    cash_balance: float = 0.0
    portfolio_value: float = 0.0
    total_equity: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    currency: str = "AUD"
    buying_power: float = 0.0


# ── Abstract Broker Class ──────────────────────────────────────────────────

class BaseBroker(ABC):
    """Abstract interface every broker integration must implement.

    Guarantees a uniform API surface for the execution engine regardless of
    which broker backs the trade.
    """

    broker_id: BrokerID
    display_name: str
    supported_exchanges: list[str]
    supported_order_types: list[str]

    def __init__(self):
        self._connected = False
        self._last_heartbeat: datetime | None = None

    # ── Connection Lifecycle ───────────────────────────────────────────

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the broker. Returns True on success."""

    @abstractmethod
    async def disconnect(self) -> bool:
        """Gracefully close the broker connection."""

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check connection health. Returns status dict with at least 'healthy': bool."""

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Market Data ────────────────────────────────────────────────────

    @abstractmethod
    async def get_quote(self, symbol: str, exchange: str = "ASX",
                        currency: str = "AUD") -> BrokerQuote:
        """Fetch a real-time quote snapshot."""

    @abstractmethod
    async def get_historical_bars(self, symbol: str, duration: str = "1Y",
                                   bar_size: str = "1d", exchange: str = "ASX",
                                   currency: str = "AUD") -> list[BrokerBar]:
        """Fetch historical OHLCV bars."""

    # ── Order Execution ────────────────────────────────────────────────

    @abstractmethod
    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        """Submit an order. Returns the updated order with broker_order_id and status."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> BrokerOrder:
        """Cancel an existing order. Returns updated order with new status."""

    @abstractmethod
    async def modify_order(self, order_id: str, **kwargs) -> BrokerOrder:
        """Modify an existing order (price, quantity, etc.)."""

    @abstractmethod
    async def get_order_status(self, order_id: str) -> BrokerOrder:
        """Poll broker for the latest status of an order."""

    @abstractmethod
    async def get_open_orders(self) -> list[BrokerOrder]:
        """List all open/pending orders."""

    # ── Positions & Account ────────────────────────────────────────────

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Fetch all current positions."""

    @abstractmethod
    async def get_account(self) -> BrokerAccount:
        """Fetch account summary (balance, equity, margin)."""

    # ── Bracket / OCO helpers ──────────────────────────────────────────

    async def place_bracket_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float | None,
        take_profit: float,
        stop_loss: float,
        exchange: str = "ASX",
        currency: str = "AUD",
    ) -> dict[str, BrokerOrder]:
        """Place a bracket order (entry + take-profit + stop-loss).

        Default implementation creates three orders. Brokers with native
        bracket support should override.
        """
        import uuid

        entry = BrokerOrder(
            order_id=str(uuid.uuid4())[:12],
            broker=self.broker_id.value,
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            side=side,
            order_type=OrderType.LIMIT.value if entry_price else OrderType.MARKET.value,
            quantity=quantity,
            limit_price=entry_price,
        )
        entry = await self.place_order(entry)

        tp = BrokerOrder(
            order_id=str(uuid.uuid4())[:12],
            broker=self.broker_id.value,
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            side=OrderSide.SELL.value if side == OrderSide.BUY.value else OrderSide.BUY.value,
            order_type=OrderType.LIMIT.value,
            quantity=quantity,
            limit_price=take_profit,
        )

        sl = BrokerOrder(
            order_id=str(uuid.uuid4())[:12],
            broker=self.broker_id.value,
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            side=OrderSide.SELL.value if side == OrderSide.BUY.value else OrderSide.BUY.value,
            order_type=OrderType.STOP.value,
            quantity=quantity,
            stop_price=stop_loss,
        )

        tp = await self.place_order(tp)
        sl = await self.place_order(sl)

        return {"entry": entry, "take_profit": tp, "stop_loss": sl}
