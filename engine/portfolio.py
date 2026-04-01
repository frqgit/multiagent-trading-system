"""Portfolio Manager — position sizing, risk management, and portfolio analytics.

Supports multiple position-sizing methods:
  - Fixed size
  - Percent of equity
  - Percent risk (volatility-scaled)
  - Kelly criterion
  - Equal weight (multi-asset)

Usage:
    from engine.portfolio import PortfolioManager, PortfolioConfig
    pm = PortfolioManager(PortfolioConfig(initial_capital=100_000))
    size = pm.calculate_position_size(price=50.0, method="pct_risk", stop_distance=2.0)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class PortfolioConfig:
    """Portfolio-level configuration."""
    initial_capital: float = 100_000.0
    max_position_pct: float = 0.20       # max 20% in single position
    max_portfolio_risk_pct: float = 0.06 # max 6% total portfolio risk
    max_correlated_positions: int = 3    # limit correlated bets
    max_open_positions: int = 10
    risk_per_trade_pct: float = 0.02     # 2% risk per trade
    commission_pct: float = 0.001
    margin_requirement: float = 1.0


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------

@dataclass
class Position:
    """An open portfolio position."""
    symbol: str
    side: str              # "LONG" or "SHORT"
    shares: float
    entry_price: float
    entry_date: str
    current_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    trailing_stop: float = 0.0
    unrealized_pnl: float = 0.0
    pnl_pct: float = 0.0
    risk_amount: float = 0.0

    def update(self, price: float) -> None:
        """Update position with current price."""
        self.current_price = price
        if self.side == "LONG":
            self.unrealized_pnl = self.shares * (price - self.entry_price)
        else:
            self.unrealized_pnl = self.shares * (self.entry_price - price)
        cost = self.shares * self.entry_price
        self.pnl_pct = (self.unrealized_pnl / cost * 100) if cost else 0

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "shares": self.shares,
            "entry_price": round(self.entry_price, 4),
            "current_price": round(self.current_price, 4),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "pnl_pct": round(self.pnl_pct, 2),
            "stop_loss": round(self.stop_loss, 4),
            "market_value": round(self.market_value, 2),
        }


# ---------------------------------------------------------------------------
# Portfolio Manager
# ---------------------------------------------------------------------------

class PortfolioManager:
    """Manages positions, sizing, and portfolio-level risk."""

    def __init__(self, config: PortfolioConfig | None = None) -> None:
        self.config = config or PortfolioConfig()
        self.cash: float = self.config.initial_capital
        self.positions: dict[str, Position] = {}
        self.closed_trades: list[dict[str, Any]] = []
        self._peak_equity: float = self.config.initial_capital

    # ------------------------------------------------------------------
    # Equity / metrics
    # ------------------------------------------------------------------

    @property
    def equity(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    @property
    def total_exposure(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def exposure_pct(self) -> float:
        eq = self.equity
        return (self.total_exposure / eq * 100) if eq > 0 else 0

    @property
    def drawdown_pct(self) -> float:
        self._peak_equity = max(self._peak_equity, self.equity)
        return ((self._peak_equity - self.equity) / self._peak_equity * 100) if self._peak_equity > 0 else 0

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def calculate_position_size(
        self,
        price: float,
        method: str = "pct_equity",
        stop_distance: float | None = None,
        win_rate: float | None = None,
        avg_win_loss_ratio: float | None = None,
        volatility: float | None = None,
        n_assets: int = 1,
    ) -> int:
        """Calculate position size (shares) using the chosen method.

        Methods:
            fixed       — fixed dollar amount (config.risk_per_trade_pct * equity)
            pct_equity  — percent of equity
            pct_risk    — risk-based (requires stop_distance)
            kelly       — Kelly criterion (requires win_rate, avg_win_loss_ratio)
            equal_weight— equal allocation across n_assets
            volatility  — inverse-volatility weighting (requires volatility)
        """
        eq = self.equity
        cfg = self.config
        max_shares = int(eq * cfg.max_position_pct / price) if price > 0 else 0

        if method == "fixed":
            alloc = eq * cfg.risk_per_trade_pct
            shares = int(alloc / price) if price > 0 else 0

        elif method == "pct_equity":
            alloc = eq * cfg.risk_per_trade_pct
            shares = int(alloc / price) if price > 0 else 0

        elif method == "pct_risk":
            if not stop_distance or stop_distance <= 0:
                logger.warning("pct_risk needs stop_distance > 0, using pct_equity fallback")
                return self.calculate_position_size(price, method="pct_equity")
            risk_amount = eq * cfg.risk_per_trade_pct
            shares = int(risk_amount / stop_distance)

        elif method == "kelly":
            if not win_rate or not avg_win_loss_ratio:
                logger.warning("kelly needs win_rate and avg_win_loss_ratio, using pct_equity fallback")
                return self.calculate_position_size(price, method="pct_equity")
            w = min(max(win_rate, 0.01), 0.99)
            r = max(avg_win_loss_ratio, 0.01)
            kelly_f = w - (1 - w) / r
            # Half-Kelly for safety
            kelly_f = max(min(kelly_f * 0.5, cfg.max_position_pct), 0)
            alloc = eq * kelly_f
            shares = int(alloc / price) if price > 0 else 0

        elif method == "equal_weight":
            n = max(n_assets, 1)
            alloc = eq / n * (1 - 0.05)  # 5% cash buffer
            shares = int(alloc / price) if price > 0 else 0

        elif method == "volatility":
            if not volatility or volatility <= 0:
                return self.calculate_position_size(price, method="pct_equity")
            target_risk = eq * cfg.risk_per_trade_pct
            shares = int(target_risk / (price * volatility))

        else:
            logger.warning("Unknown sizing method '%s', using pct_equity", method)
            return self.calculate_position_size(price, method="pct_equity")

        # Enforce max position cap
        shares = min(shares, max_shares)
        # Enforce cash availability
        cost = shares * price * (1 + cfg.commission_pct)
        if cost > self.cash * 0.95:
            shares = int(self.cash * 0.95 / (price * (1 + cfg.commission_pct)))

        return max(shares, 0)

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def open_position(
        self,
        symbol: str,
        side: str,
        price: float,
        shares: int,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        date: str = "",
    ) -> Position | None:
        """Open a new position if risk limits allow."""
        cfg = self.config

        # Check max positions
        if len(self.positions) >= cfg.max_open_positions:
            logger.warning("Max open positions (%d) reached", cfg.max_open_positions)
            return None

        # Check if already have position in symbol
        if symbol in self.positions:
            logger.warning("Already have position in %s", symbol)
            return None

        cost = shares * price * (1 + cfg.commission_pct)
        if cost > self.cash:
            logger.warning("Insufficient cash for %s: need %.2f, have %.2f", symbol, cost, self.cash)
            return None

        # Execute
        self.cash -= cost
        risk = shares * abs(price - stop_loss) if stop_loss else shares * price * cfg.risk_per_trade_pct

        pos = Position(
            symbol=symbol, side=side, shares=shares,
            entry_price=price, entry_date=date,
            current_price=price, stop_loss=stop_loss,
            take_profit=take_profit, risk_amount=risk,
        )
        self.positions[symbol] = pos
        logger.info("Opened %s %d shares of %s @ %.2f", side, shares, symbol, price)
        return pos

    def close_position(self, symbol: str, price: float, date: str = "", reason: str = "manual") -> dict[str, Any] | None:
        """Close an existing position."""
        if symbol not in self.positions:
            return None

        pos = self.positions.pop(symbol)
        pos.update(price)

        proceeds = pos.shares * price * (1 - self.config.commission_pct)
        if pos.side == "SHORT":
            # For short: profit = entry - exit
            proceeds = pos.shares * (2 * pos.entry_price - price) * (1 - self.config.commission_pct)
        self.cash += proceeds

        trade = {
            "symbol": symbol, "side": pos.side,
            "entry_price": pos.entry_price, "exit_price": price,
            "shares": pos.shares, "pnl": round(pos.unrealized_pnl, 2),
            "pnl_pct": round(pos.pnl_pct, 2),
            "entry_date": pos.entry_date, "exit_date": date,
            "reason": reason,
        }
        self.closed_trades.append(trade)
        logger.info("Closed %s %s @ %.2f — P&L: %.2f (%.1f%%)", symbol, reason, price, pos.unrealized_pnl, pos.pnl_pct)
        return trade

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update all positions with current prices."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update(price)

    def check_stops(self, prices: dict[str, float], date: str = "") -> list[dict[str, Any]]:
        """Check stop-loss and take-profit levels for all positions."""
        closed = []
        for symbol, price in prices.items():
            if symbol not in self.positions:
                continue
            pos = self.positions[symbol]
            pos.update(price)

            should_close = False
            reason = ""

            if pos.side == "LONG":
                if pos.stop_loss and price <= pos.stop_loss:
                    should_close, reason = True, "stop_loss"
                elif pos.take_profit and price >= pos.take_profit:
                    should_close, reason = True, "take_profit"
            else:
                if pos.stop_loss and price >= pos.stop_loss:
                    should_close, reason = True, "stop_loss"
                elif pos.take_profit and price <= pos.take_profit:
                    should_close, reason = True, "take_profit"

            if should_close:
                result = self.close_position(symbol, price, date, reason)
                if result:
                    closed.append(result)
        return closed

    # ------------------------------------------------------------------
    # Portfolio analytics
    # ------------------------------------------------------------------

    def portfolio_summary(self) -> dict[str, Any]:
        """Return current portfolio state."""
        positions_list = [p.to_dict() for p in self.positions.values()]
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        total_realized = sum(t["pnl"] for t in self.closed_trades)

        return {
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "exposure_pct": round(self.exposure_pct, 1),
            "drawdown_pct": round(self.drawdown_pct, 2),
            "open_positions": len(self.positions),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "total_realized_pnl": round(total_realized, 2),
            "total_closed_trades": len(self.closed_trades),
            "positions": positions_list,
        }

    def risk_report(self) -> dict[str, Any]:
        """Generate a risk assessment of the current portfolio."""
        cfg = self.config
        eq = self.equity

        total_risk = sum(p.risk_amount for p in self.positions.values())
        risk_pct = (total_risk / eq * 100) if eq > 0 else 0

        long_exposure = sum(p.market_value for p in self.positions.values() if p.side == "LONG")
        short_exposure = sum(p.market_value for p in self.positions.values() if p.side == "SHORT")

        # Concentration: largest position as pct of equity
        max_pos_pct = 0.0
        if self.positions:
            max_pos_pct = max(p.market_value / eq * 100 for p in self.positions.values()) if eq > 0 else 0

        return {
            "total_risk_pct": round(risk_pct, 2),
            "max_risk_limit_pct": cfg.max_portfolio_risk_pct * 100,
            "risk_within_limits": risk_pct <= cfg.max_portfolio_risk_pct * 100,
            "long_exposure": round(long_exposure, 2),
            "short_exposure": round(short_exposure, 2),
            "net_exposure": round(long_exposure - short_exposure, 2),
            "gross_exposure_pct": round((long_exposure + short_exposure) / eq * 100, 1) if eq > 0 else 0,
            "max_position_pct": round(max_pos_pct, 1),
            "max_position_limit_pct": cfg.max_position_pct * 100,
            "concentration_ok": max_pos_pct <= cfg.max_position_pct * 100,
            "open_slots": cfg.max_open_positions - len(self.positions),
            "drawdown_pct": round(self.drawdown_pct, 2),
        }

    def reset(self) -> None:
        """Reset portfolio to initial state."""
        self.cash = self.config.initial_capital
        self.positions.clear()
        self.closed_trades.clear()
        self._peak_equity = self.config.initial_capital
