"""Execution Agent — Order management and execution simulation.

Implements:
- Paper trading simulation
- Order management (market, limit, stop orders)
- Position tracking
- Slippage and commission modeling
- Risk-based position sizing
- Execution analytics
"""

from __future__ import annotations

import asyncio
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path
from enum import Enum
import uuid

import numpy as np

logger = logging.getLogger(__name__)


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Order representation."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None  # For limit/stop orders
    stop_price: float | None = None  # For stop orders
    trail_percent: float | None = None  # For trailing stop
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: datetime | None = None
    commission: float = 0.0
    slippage: float = 0.0


@dataclass
class Position:
    """Position representation."""
    symbol: str
    quantity: float
    average_cost: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    open_date: datetime = field(default_factory=datetime.now)


@dataclass
class Trade:
    """Completed trade record."""
    trade_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    return_pct: float
    commission: float
    slippage: float
    entry_date: datetime
    exit_date: datetime
    holding_period_days: float


class ExecutionAgent:
    """
    Simulated order execution and portfolio management.
    
    Capabilities:
    - Paper trading with realistic simulation
    - Multiple order types (market, limit, stop)
    - Position tracking and P&L calculation
    - Slippage and commission modeling
    - Risk-based position sizing
    - Trade history and analytics
    """

    name = "ExecutionAgent"
    
    # Files for persistence
    PORTFOLIO_FILE = "portfolio.json"
    ORDERS_FILE = "orders.json"
    TRADES_FILE = "trades.json"
    
    # Default settings
    DEFAULT_COMMISSION_RATE = 0.001  # 0.1% commission
    DEFAULT_SLIPPAGE_BPS = 5  # 5 basis points
    
    def __init__(
        self,
        data_dir: str = "./data",
        initial_capital: float = 100000.0,
        commission_rate: float = DEFAULT_COMMISSION_RATE,
        slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps
        
        # Load or initialize portfolio
        self.portfolio = self._load_portfolio(initial_capital)
        self.open_orders: list[Order] = self._load_orders()
        self.trade_history: list[Trade] = self._load_trades()
    
    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        stop_price: float | None = None,
        trail_percent: float | None = None,
        current_price: float | None = None,
    ) -> dict[str, Any]:
        """
        Submit an order for execution.
        
        Args:
            symbol: Stock symbol
            side: "buy" or "sell"
            quantity: Number of shares
            order_type: "market", "limit", "stop", "stop_limit", "trailing_stop"
            price: Limit price (for limit orders)
            stop_price: Stop trigger price
            trail_percent: Trailing percent for trailing stop
            current_price: Current market price (for simulation)
            
        Returns:
            Order confirmation with status
        """
        logger.info("[%s] Order submission: %s %s %s @ %s", 
                    self.name, side.upper(), quantity, symbol, order_type)
        
        # Validate order
        validation = self._validate_order(symbol, side, quantity, order_type, price, current_price)
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"],
            }
        
        # Create order
        order = Order(
            order_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=OrderSide(side.lower()),
            order_type=OrderType(order_type.lower()),
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            trail_percent=trail_percent,
            status=OrderStatus.OPEN,
        )
        
        # For market orders, execute immediately
        if order.order_type == OrderType.MARKET and current_price:
            result = self._execute_order(order, current_price)
            return result
        
        # For other orders, add to open orders
        self.open_orders.append(order)
        self._save_orders()
        
        return {
            "success": True,
            "order_id": order.order_id,
            "status": order.status.value,
            "message": f"Order submitted: {side.upper()} {quantity} {symbol}",
            "order": self._order_to_dict(order),
        }
    
    async def check_orders(
        self,
        current_prices: dict[str, float],
    ) -> list[dict]:
        """
        Check open orders against current prices and execute if triggered.
        
        Args:
            current_prices: Dict mapping symbols to current prices
            
        Returns:
            List of execution results
        """
        results = []
        orders_to_remove = []
        
        for order in self.open_orders:
            if order.symbol not in current_prices:
                continue
            
            price = current_prices[order.symbol]
            
            # Check if order should be executed
            should_execute = self._should_execute(order, price)
            
            if should_execute:
                result = self._execute_order(order, price)
                results.append(result)
                orders_to_remove.append(order)
        
        # Remove executed orders
        for order in orders_to_remove:
            self.open_orders.remove(order)
        
        self._save_orders()
        return results
    
    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open order."""
        for order in self.open_orders:
            if order.order_id == order_id:
                order.status = OrderStatus.CANCELLED
                self.open_orders.remove(order)
                self._save_orders()
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "message": "Order cancelled",
                }
        
        return {
            "success": False,
            "error": f"Order {order_id} not found",
        }
    
    async def get_position(self, symbol: str) -> dict[str, Any] | None:
        """Get current position for a symbol."""
        positions = self.portfolio.get("positions", {})
        
        if symbol not in positions:
            return None
        
        return positions[symbol]
    
    async def get_portfolio_summary(
        self,
        current_prices: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Get portfolio summary with current values.
        
        Args:
            current_prices: Optional dict of current prices for valuation
            
        Returns:
            Portfolio summary with positions, P&L, and metrics
        """
        positions = self.portfolio.get("positions", {})
        cash = self.portfolio.get("cash", 0)
        initial_capital = self.portfolio.get("initial_capital", 100000)
        
        # Calculate position values
        position_details = []
        total_position_value = 0
        total_unrealized_pnl = 0
        
        for symbol, pos in positions.items():
            current_price = current_prices.get(symbol, pos.get("current_price", pos["average_cost"])) if current_prices else pos.get("current_price", pos["average_cost"])
            
            quantity = pos["quantity"]
            avg_cost = pos["average_cost"]
            
            market_value = quantity * current_price
            cost_basis = quantity * avg_cost
            unrealized_pnl = market_value - cost_basis
            return_pct = (unrealized_pnl / cost_basis) * 100 if cost_basis > 0 else 0
            
            position_details.append({
                "symbol": symbol,
                "quantity": quantity,
                "average_cost": round(avg_cost, 2),
                "current_price": round(current_price, 2),
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "return_pct": round(return_pct, 2),
            })
            
            total_position_value += market_value
            total_unrealized_pnl += unrealized_pnl
        
        # Total portfolio value
        total_value = cash + total_position_value
        total_pnl = total_value - initial_capital
        total_return = (total_pnl / initial_capital) * 100
        
        # Trade statistics
        trades = self.trade_history
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        total_realized_pnl = sum(t.pnl for t in trades)
        
        return {
            "summary": {
                "total_value": round(total_value, 2),
                "cash": round(cash, 2),
                "position_value": round(total_position_value, 2),
                "initial_capital": initial_capital,
                "total_pnl": round(total_pnl, 2),
                "total_return_pct": round(total_return, 2),
                "unrealized_pnl": round(total_unrealized_pnl, 2),
                "realized_pnl": round(total_realized_pnl, 2),
            },
            "positions": position_details,
            "open_orders": len(self.open_orders),
            "trade_statistics": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": total_trades - winning_trades,
                "win_rate": round(win_rate, 3),
                "avg_win": round(np.mean([t.pnl for t in trades if t.pnl > 0]), 2) if winning_trades > 0 else 0,
                "avg_loss": round(np.mean([t.pnl for t in trades if t.pnl <= 0]), 2) if total_trades - winning_trades > 0 else 0,
            },
        }
    
    async def calculate_position_size(
        self,
        symbol: str,
        signal: dict,
        current_price: float,
        volatility: float | None = None,
        max_position_pct: float = 0.1,
        max_risk_pct: float = 0.02,
    ) -> dict[str, Any]:
        """
        Calculate recommended position size based on risk parameters.
        
        Args:
            symbol: Stock symbol
            signal: Trading signal with confidence
            current_price: Current market price
            volatility: Annualized volatility (optional)
            max_position_pct: Maximum portfolio percentage per position
            max_risk_pct: Maximum risk per trade as portfolio percentage
            
        Returns:
            Position sizing recommendation
        """
        portfolio_value = self.portfolio.get("cash", 100000) + sum(
            pos.get("quantity", 0) * pos.get("current_price", pos["average_cost"])
            for pos in self.portfolio.get("positions", {}).values()
        )
        
        # Method 1: Fixed percentage of portfolio
        max_position_value = portfolio_value * max_position_pct
        shares_by_max_position = int(max_position_value / current_price)
        
        # Method 2: Volatility-based (if volatility provided)
        if volatility and volatility > 0:
            # Daily volatility to risk per share
            daily_vol = volatility / np.sqrt(252)
            dollar_risk_per_share = current_price * daily_vol
            
            # Max risk in dollars
            max_risk_dollars = portfolio_value * max_risk_pct
            shares_by_volatility = int(max_risk_dollars / dollar_risk_per_share)
        else:
            shares_by_volatility = shares_by_max_position
        
        # Method 3: Confidence-adjusted
        confidence = signal.get("confidence", 0.5)
        confidence_multiplier = 0.5 + confidence  # 0.5 to 1.5
        
        # Take minimum of sizing methods
        base_shares = min(shares_by_max_position, shares_by_volatility)
        recommended_shares = int(base_shares * confidence_multiplier)
        
        # Ensure at least 1 share if any position recommended
        if recommended_shares == 0 and base_shares > 0:
            recommended_shares = 1
        
        position_value = recommended_shares * current_price
        position_pct = (position_value / portfolio_value) * 100
        
        return {
            "symbol": symbol,
            "recommended_shares": recommended_shares,
            "position_value": round(position_value, 2),
            "position_pct": round(position_pct, 2),
            "current_price": round(current_price, 2),
            "sizing_methods": {
                "by_max_position": shares_by_max_position,
                "by_volatility": shares_by_volatility,
                "by_confidence": round(confidence_multiplier, 2),
            },
            "parameters": {
                "max_position_pct": max_position_pct,
                "max_risk_pct": max_risk_pct,
                "portfolio_value": round(portfolio_value, 2),
            },
        }
    
    async def get_trade_history(
        self,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get trade history, optionally filtered by symbol."""
        trades = self.trade_history
        
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]
        
        # Sort by exit date descending
        trades = sorted(trades, key=lambda t: t.exit_date, reverse=True)
        
        return [self._trade_to_dict(t) for t in trades[:limit]]
    
    async def get_execution_analytics(self) -> dict[str, Any]:
        """Get execution quality analytics."""
        if not self.trade_history:
            return {"message": "No trades to analyze"}
        
        trades = self.trade_history
        
        # Slippage analysis
        total_slippage = sum(t.slippage for t in trades)
        avg_slippage = total_slippage / len(trades)
        
        # Commission analysis
        total_commission = sum(t.commission for t in trades)
        avg_commission = total_commission / len(trades)
        
        # Timing analysis
        holding_periods = [t.holding_period_days for t in trades]
        
        # Returns analysis
        returns = [t.return_pct for t in trades]
        winning_returns = [r for r in returns if r > 0]
        losing_returns = [r for r in returns if r <= 0]
        
        # Profit factor
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy
        win_rate = len(winning_returns) / len(returns) if returns else 0
        avg_win = np.mean(winning_returns) if winning_returns else 0
        avg_loss = abs(np.mean(losing_returns)) if losing_returns else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if returns else 0
        
        return {
            "total_trades": len(trades),
            "execution_costs": {
                "total_slippage": round(total_slippage, 2),
                "avg_slippage": round(avg_slippage, 2),
                "total_commission": round(total_commission, 2),
                "avg_commission": round(avg_commission, 2),
            },
            "timing": {
                "avg_holding_period_days": round(np.mean(holding_periods), 1),
                "min_holding_period_days": round(min(holding_periods), 1),
                "max_holding_period_days": round(max(holding_periods), 1),
            },
            "performance": {
                "win_rate": round(win_rate, 3),
                "profit_factor": round(profit_factor, 2),
                "expectancy_pct": round(expectancy, 2),
                "avg_return_pct": round(np.mean(returns), 2),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
            },
            "distribution": {
                "return_std": round(np.std(returns), 2),
                "best_trade_pct": round(max(returns), 2),
                "worst_trade_pct": round(min(returns), 2),
            },
        }
    
    def _validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        price: float | None,
        current_price: float | None,
    ) -> dict[str, Any]:
        """Validate order parameters."""
        if side.lower() not in ["buy", "sell"]:
            return {"valid": False, "error": "Invalid side. Must be 'buy' or 'sell'"}
        
        if quantity <= 0:
            return {"valid": False, "error": "Quantity must be positive"}
        
        if order_type.lower() not in [e.value for e in OrderType]:
            return {"valid": False, "error": f"Invalid order type. Must be one of {[e.value for e in OrderType]}"}
        
        if order_type.lower() in ["limit", "stop_limit"] and price is None:
            return {"valid": False, "error": "Limit price required for limit orders"}
        
        # Check buying power for buy orders
        if side.lower() == "buy":
            required_capital = quantity * (price or current_price or 0)
            available_cash = self.portfolio.get("cash", 0)
            
            if required_capital > available_cash:
                return {"valid": False, "error": f"Insufficient funds. Required: ${required_capital:.2f}, Available: ${available_cash:.2f}"}
        
        # Check position for sell orders
        if side.lower() == "sell":
            positions = self.portfolio.get("positions", {})
            current_position = positions.get(symbol, {}).get("quantity", 0)
            
            if quantity > current_position:
                return {"valid": False, "error": f"Insufficient position. Requested: {quantity}, Available: {current_position}"}
        
        return {"valid": True}
    
    def _should_execute(self, order: Order, current_price: float) -> bool:
        """Check if order should be executed based on type and price."""
        if order.order_type == OrderType.MARKET:
            return True
        
        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY:
                return current_price <= order.price
            else:
                return current_price >= order.price
        
        if order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY:
                return current_price >= order.stop_price
            else:
                return current_price <= order.stop_price
        
        if order.order_type == OrderType.STOP_LIMIT:
            # First check stop, then limit
            if order.stop_price:
                if order.side == OrderSide.BUY:
                    return current_price >= order.stop_price and current_price <= order.price
                else:
                    return current_price <= order.stop_price and current_price >= order.price
        
        return False
    
    def _execute_order(self, order: Order, market_price: float) -> dict[str, Any]:
        """Execute an order with slippage and commission modeling."""
        # Calculate slippage
        slippage_pct = self.slippage_bps / 10000
        if order.side == OrderSide.BUY:
            fill_price = market_price * (1 + slippage_pct)
        else:
            fill_price = market_price * (1 - slippage_pct)
        
        slippage_cost = abs(fill_price - market_price) * order.quantity
        
        # Calculate commission
        commission = order.quantity * fill_price * self.commission_rate
        
        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_fill_price = fill_price
        order.filled_at = datetime.now()
        order.commission = commission
        order.slippage = slippage_cost
        
        # Update portfolio
        self._update_portfolio(order)
        
        return {
            "success": True,
            "order_id": order.order_id,
            "status": "filled",
            "execution": {
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": order.quantity,
                "market_price": round(market_price, 2),
                "fill_price": round(fill_price, 2),
                "slippage": round(slippage_cost, 2),
                "commission": round(commission, 2),
                "total_cost": round(order.quantity * fill_price + commission, 2),
            },
        }
    
    def _update_portfolio(self, order: Order) -> None:
        """Update portfolio after order execution."""
        positions = self.portfolio.get("positions", {})
        
        if order.side == OrderSide.BUY:
            # Deduct cash
            total_cost = order.quantity * order.average_fill_price + order.commission
            self.portfolio["cash"] -= total_cost
            
            # Add/update position
            if order.symbol in positions:
                pos = positions[order.symbol]
                # Average in
                total_quantity = pos["quantity"] + order.quantity
                total_cost_basis = pos["quantity"] * pos["average_cost"] + order.quantity * order.average_fill_price
                pos["average_cost"] = total_cost_basis / total_quantity
                pos["quantity"] = total_quantity
                pos["current_price"] = order.average_fill_price
            else:
                positions[order.symbol] = {
                    "quantity": order.quantity,
                    "average_cost": order.average_fill_price,
                    "current_price": order.average_fill_price,
                    "open_date": datetime.now().isoformat(),
                }
        
        else:  # SELL
            pos = positions.get(order.symbol)
            if pos:
                # Calculate P&L before updating
                pnl = (order.average_fill_price - pos["average_cost"]) * order.quantity - order.commission
                return_pct = ((order.average_fill_price / pos["average_cost"]) - 1) * 100
                
                # Record trade
                trade = Trade(
                    trade_id=str(uuid.uuid4())[:8],
                    symbol=order.symbol,
                    side="sell",
                    quantity=order.quantity,
                    entry_price=pos["average_cost"],
                    exit_price=order.average_fill_price,
                    pnl=pnl,
                    return_pct=return_pct,
                    commission=order.commission,
                    slippage=order.slippage,
                    entry_date=datetime.fromisoformat(pos.get("open_date", datetime.now().isoformat())),
                    exit_date=datetime.now(),
                    holding_period_days=(datetime.now() - datetime.fromisoformat(pos.get("open_date", datetime.now().isoformat()))).days,
                )
                self.trade_history.append(trade)
                
                # Add cash from sale
                self.portfolio["cash"] += order.quantity * order.average_fill_price - order.commission
                
                # Update or remove position
                remaining = pos["quantity"] - order.quantity
                if remaining > 0:
                    pos["quantity"] = remaining
                else:
                    del positions[order.symbol]
        
        self.portfolio["positions"] = positions
        self._save_portfolio()
        self._save_trades()
    
    def _order_to_dict(self, order: Order) -> dict:
        """Convert Order to dict."""
        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": order.quantity,
            "price": order.price,
            "stop_price": order.stop_price,
            "status": order.status.value,
            "filled_quantity": order.filled_quantity,
            "average_fill_price": order.average_fill_price,
            "created_at": order.created_at.isoformat(),
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            "commission": order.commission,
            "slippage": order.slippage,
        }
    
    def _trade_to_dict(self, trade: Trade) -> dict:
        """Convert Trade to dict."""
        return {
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "entry_price": round(trade.entry_price, 2),
            "exit_price": round(trade.exit_price, 2),
            "pnl": round(trade.pnl, 2),
            "return_pct": round(trade.return_pct, 2),
            "commission": round(trade.commission, 2),
            "slippage": round(trade.slippage, 2),
            "entry_date": trade.entry_date.isoformat(),
            "exit_date": trade.exit_date.isoformat(),
            "holding_period_days": trade.holding_period_days,
        }
    
    def _load_portfolio(self, initial_capital: float) -> dict:
        """Load portfolio from file or initialize."""
        portfolio_path = self.data_dir / self.PORTFOLIO_FILE
        
        if portfolio_path.exists():
            try:
                with open(portfolio_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("[%s] Failed to load portfolio: %s", self.name, e)
        
        return {
            "cash": initial_capital,
            "initial_capital": initial_capital,
            "positions": {},
        }
    
    def _save_portfolio(self) -> None:
        """Save portfolio to file."""
        portfolio_path = self.data_dir / self.PORTFOLIO_FILE
        
        try:
            with open(portfolio_path, "w") as f:
                json.dump(self.portfolio, f, indent=2)
        except Exception as e:
            logger.warning("[%s] Failed to save portfolio: %s", self.name, e)
    
    def _load_orders(self) -> list[Order]:
        """Load open orders from file."""
        orders_path = self.data_dir / self.ORDERS_FILE
        
        if orders_path.exists():
            try:
                with open(orders_path, "r") as f:
                    data = json.load(f)
                    return [self._dict_to_order(o) for o in data]
            except Exception as e:
                logger.warning("[%s] Failed to load orders: %s", self.name, e)
        
        return []
    
    def _dict_to_order(self, data: dict) -> Order:
        """Convert dict to Order."""
        return Order(
            order_id=data["order_id"],
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            order_type=OrderType(data["order_type"]),
            quantity=data["quantity"],
            price=data.get("price"),
            stop_price=data.get("stop_price"),
            status=OrderStatus(data["status"]),
            filled_quantity=data.get("filled_quantity", 0),
            average_fill_price=data.get("average_fill_price", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            filled_at=datetime.fromisoformat(data["filled_at"]) if data.get("filled_at") else None,
            commission=data.get("commission", 0),
            slippage=data.get("slippage", 0),
        )
    
    def _save_orders(self) -> None:
        """Save open orders to file."""
        orders_path = self.data_dir / self.ORDERS_FILE
        
        try:
            with open(orders_path, "w") as f:
                json.dump([self._order_to_dict(o) for o in self.open_orders], f, indent=2)
        except Exception as e:
            logger.warning("[%s] Failed to save orders: %s", self.name, e)
    
    def _load_trades(self) -> list[Trade]:
        """Load trade history from file."""
        trades_path = self.data_dir / self.TRADES_FILE
        
        if trades_path.exists():
            try:
                with open(trades_path, "r") as f:
                    data = json.load(f)
                    return [self._dict_to_trade(t) for t in data]
            except Exception as e:
                logger.warning("[%s] Failed to load trades: %s", self.name, e)
        
        return []
    
    def _dict_to_trade(self, data: dict) -> Trade:
        """Convert dict to Trade."""
        return Trade(
            trade_id=data["trade_id"],
            symbol=data["symbol"],
            side=data["side"],
            quantity=data["quantity"],
            entry_price=data["entry_price"],
            exit_price=data["exit_price"],
            pnl=data["pnl"],
            return_pct=data["return_pct"],
            commission=data["commission"],
            slippage=data["slippage"],
            entry_date=datetime.fromisoformat(data["entry_date"]),
            exit_date=datetime.fromisoformat(data["exit_date"]),
            holding_period_days=data["holding_period_days"],
        )
    
    def _save_trades(self) -> None:
        """Save trade history to file."""
        trades_path = self.data_dir / self.TRADES_FILE
        
        try:
            with open(trades_path, "w") as f:
                json.dump([self._trade_to_dict(t) for t in self.trade_history], f, indent=2)
        except Exception as e:
            logger.warning("[%s] Failed to save trades: %s", self.name, e)
    
    async def reset_portfolio(self, initial_capital: float = 100000.0) -> dict[str, Any]:
        """Reset portfolio to initial state."""
        self.portfolio = {
            "cash": initial_capital,
            "initial_capital": initial_capital,
            "positions": {},
        }
        self.open_orders = []
        self.trade_history = []
        
        self._save_portfolio()
        self._save_orders()
        self._save_trades()
        
        return {
            "success": True,
            "message": f"Portfolio reset with ${initial_capital:,.2f} initial capital",
        }
