"""Backtesting Agent — Historical strategy validation and performance analysis.

Implements:
- Walk-forward analysis
- Monte Carlo simulation
- Strategy signal backtesting
- Performance metrics (Sharpe, Sortino, Calmar, etc.)
- Drawdown analysis
- Trade analytics
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a single trade."""
    entry_date: str
    exit_date: str
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    holding_days: int
    signal: str


@dataclass
class BacktestResult:
    """Complete backtest results."""
    strategy_name: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    avg_trade_pnl: float
    total_trades: int
    trades: list[TradeRecord]
    equity_curve: list[dict]
    drawdown_curve: list[dict]
    monthly_returns: list[dict]


class BacktestingAgent:
    """
    Validates trading strategies against historical data.
    
    Capabilities:
    - Single-asset strategy backtesting
    - Multi-asset portfolio backtesting
    - Walk-forward optimization
    - Monte Carlo simulation
    - Comprehensive performance metrics
    """

    name = "BacktestingAgent"
    
    # Default parameters
    INITIAL_CAPITAL = 100000
    COMMISSION_RATE = 0.001  # 0.1% per trade
    SLIPPAGE_RATE = 0.0005  # 0.05% slippage
    
    async def backtest_strategy(
        self,
        symbol: str,
        strategy: str = "ma_crossover",
        start_date: str | None = None,
        end_date: str | None = None,
        initial_capital: float = INITIAL_CAPITAL,
        strategy_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Backtest a trading strategy on historical data.
        
        Args:
            symbol: Stock symbol to test
            strategy: Strategy name ('ma_crossover', 'rsi_mean_reversion', 
                      'momentum', 'breakout', 'macd')
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            initial_capital: Starting capital
            strategy_params: Strategy-specific parameters
            
        Returns:
            Complete backtest results with trades and metrics
        """
        logger.info("[%s] Backtesting %s strategy on %s", self.name, strategy, symbol)
        
        # Default to 2 years of data
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        
        # Fetch historical data
        try:
            data = await self._fetch_historical_data(symbol, start_date, end_date)
        except Exception as e:
            logger.error("[%s] Failed to fetch data: %s", self.name, e)
            return {"error": f"Failed to fetch data: {e}", "symbol": symbol}
        
        if data is None or len(data) < 50:
            return {"error": "Insufficient historical data", "symbol": symbol}
        
        # Get strategy function
        strategy_func = self._get_strategy(strategy)
        if strategy_func is None:
            return {"error": f"Unknown strategy: {strategy}", "symbol": symbol}
        
        # Generate signals
        params = strategy_params or {}
        signals = strategy_func(data, **params)
        
        # Execute backtest
        result = self._execute_backtest(
            symbol, data, signals, initial_capital, strategy
        )
        
        # Calculate additional metrics
        metrics = self._calculate_metrics(result, data)
        
        return {
            "strategy": strategy,
            "symbol": symbol,
            "period": f"{start_date} to {end_date}",
            "trading_days": len(data),
            "initial_capital": initial_capital,
            "final_capital": round(result["final_capital"], 2),
            "total_return_pct": round(result["total_return"] * 100, 2),
            "annualized_return_pct": round(metrics["annualized_return"] * 100, 2),
            "sharpe_ratio": round(metrics["sharpe_ratio"], 3),
            "sortino_ratio": round(metrics["sortino_ratio"], 3),
            "calmar_ratio": round(metrics["calmar_ratio"], 3),
            "max_drawdown_pct": round(metrics["max_drawdown"] * 100, 2),
            "max_drawdown_duration_days": metrics["max_dd_duration"],
            "total_trades": result["total_trades"],
            "winning_trades": result["winning_trades"],
            "losing_trades": result["losing_trades"],
            "win_rate_pct": round(result["win_rate"] * 100, 2),
            "profit_factor": round(result["profit_factor"], 3),
            "avg_win_pct": round(result["avg_win"] * 100, 2),
            "avg_loss_pct": round(result["avg_loss"] * 100, 2),
            "best_trade_pct": round(result["best_trade"] * 100, 2),
            "worst_trade_pct": round(result["worst_trade"] * 100, 2),
            "avg_holding_days": round(result["avg_hold_days"], 1),
            "exposure_pct": round(result["exposure"] * 100, 2),
            "trades": result["trades"][:20],  # Last 20 trades
            "equity_curve": result["equity_curve"][-100:],  # Last 100 points
            "monthly_returns": metrics["monthly_returns"][-12:],  # Last 12 months
            "strategy_params": params,
        }
    
    async def walk_forward_analysis(
        self,
        symbol: str,
        strategy: str = "ma_crossover",
        in_sample_days: int = 252,
        out_sample_days: int = 63,
        total_periods: int = 4,
    ) -> dict[str, Any]:
        """
        Perform walk-forward optimization to validate strategy robustness.
        
        Args:
            symbol: Stock symbol
            strategy: Strategy name
            in_sample_days: Training period length
            out_sample_days: Testing period length
            total_periods: Number of walk-forward periods
            
        Returns:
            Walk-forward analysis results
        """
        logger.info("[%s] Walk-forward analysis on %s", self.name, symbol)
        
        total_days = (in_sample_days + out_sample_days) * total_periods
        end_date = datetime.now()
        start_date = end_date - timedelta(days=total_days)
        
        # Fetch all data
        try:
            data = await self._fetch_historical_data(
                symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
            )
        except Exception as e:
            return {"error": f"Failed to fetch data: {e}", "symbol": symbol}
        
        if data is None or len(data) < total_days * 0.7:
            return {"error": "Insufficient data for walk-forward analysis", "symbol": symbol}
        
        periods = []
        combined_oos_returns = []
        
        for i in range(total_periods):
            # Define period boundaries
            is_start = i * (in_sample_days + out_sample_days)
            is_end = is_start + in_sample_days
            oos_start = is_end
            oos_end = oos_start + out_sample_days
            
            if oos_end > len(data):
                break
            
            is_data = data[is_start:is_end]
            oos_data = data[oos_start:oos_end]
            
            # Optimize on in-sample
            best_params = self._optimize_strategy_params(strategy, is_data)
            
            # Test on out-of-sample
            strategy_func = self._get_strategy(strategy)
            signals = strategy_func(oos_data, **best_params)
            oos_result = self._execute_backtest(
                symbol, oos_data, signals, self.INITIAL_CAPITAL, strategy
            )
            
            periods.append({
                "period": i + 1,
                "in_sample_dates": f"{is_data[0]['date']} to {is_data[-1]['date']}",
                "out_sample_dates": f"{oos_data[0]['date']} to {oos_data[-1]['date']}",
                "optimized_params": best_params,
                "in_sample_return": round(self._quick_return(is_data, strategy, best_params) * 100, 2),
                "out_sample_return": round(oos_result["total_return"] * 100, 2),
                "out_sample_trades": oos_result["total_trades"],
                "out_sample_win_rate": round(oos_result["win_rate"] * 100, 2),
            })
            
            combined_oos_returns.append(oos_result["total_return"])
        
        avg_oos_return = np.mean(combined_oos_returns) if combined_oos_returns else 0
        std_oos_return = np.std(combined_oos_returns) if len(combined_oos_returns) > 1 else 0
        
        return {
            "symbol": symbol,
            "strategy": strategy,
            "total_periods": len(periods),
            "in_sample_days": in_sample_days,
            "out_sample_days": out_sample_days,
            "avg_out_sample_return_pct": round(avg_oos_return * 100, 2),
            "std_out_sample_return_pct": round(std_oos_return * 100, 2),
            "consistency_score": round((avg_oos_return / std_oos_return) if std_oos_return > 0 else 0, 2),
            "periods": periods,
            "robustness_grade": self._grade_robustness(combined_oos_returns),
        }
    
    async def monte_carlo_simulation(
        self,
        symbol: str,
        strategy: str = "ma_crossover",
        num_simulations: int = 1000,
        confidence_levels: list[float] = [0.05, 0.25, 0.50, 0.75, 0.95],
    ) -> dict[str, Any]:
        """
        Run Monte Carlo simulation to estimate strategy risk distribution.
        
        Args:
            symbol: Stock symbol
            strategy: Strategy name
            num_simulations: Number of Monte Carlo trials
            confidence_levels: Percentiles to report
            
        Returns:
            Monte Carlo simulation results with confidence intervals
        """
        logger.info("[%s] Monte Carlo simulation for %s", self.name, symbol)
        
        # First run backtest to get trade returns
        backtest = await self.backtest_strategy(symbol, strategy)
        
        if "error" in backtest:
            return backtest
        
        if backtest["total_trades"] < 10:
            return {
                "error": "Insufficient trades for Monte Carlo simulation",
                "symbol": symbol,
            }
        
        # Extract trade returns
        trade_returns = [t.get("pnl_pct", 0) / 100 for t in backtest.get("trades", [])]
        
        # Run simulations
        final_returns = []
        max_drawdowns = []
        
        for _ in range(num_simulations):
            # Resample trades with replacement
            sampled = np.random.choice(trade_returns, size=len(trade_returns), replace=True)
            
            # Calculate cumulative return
            cumulative = np.cumprod(1 + sampled)
            final_returns.append(cumulative[-1] - 1)
            
            # Calculate max drawdown
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = (cumulative - running_max) / running_max
            max_drawdowns.append(np.min(drawdowns))
        
        # Calculate percentiles
        final_returns = np.array(final_returns)
        max_drawdowns = np.array(max_drawdowns)
        
        return_percentiles = {
            f"p{int(p*100)}": round(np.percentile(final_returns, p * 100) * 100, 2)
            for p in confidence_levels
        }
        
        drawdown_percentiles = {
            f"p{int(p*100)}": round(np.percentile(max_drawdowns, p * 100) * 100, 2)
            for p in confidence_levels
        }
        
        return {
            "symbol": symbol,
            "strategy": strategy,
            "num_simulations": num_simulations,
            "base_trades": len(trade_returns),
            "expected_return_pct": round(np.mean(final_returns) * 100, 2),
            "return_std_pct": round(np.std(final_returns) * 100, 2),
            "return_percentiles": return_percentiles,
            "expected_max_drawdown_pct": round(np.mean(max_drawdowns) * 100, 2),
            "drawdown_percentiles": drawdown_percentiles,
            "probability_of_profit": round(np.mean(final_returns > 0) * 100, 2),
            "probability_of_10pct_loss": round(np.mean(final_returns < -0.10) * 100, 2),
            "var_95": round(np.percentile(final_returns, 5) * 100, 2),
            "cvar_95": round(np.mean(final_returns[final_returns <= np.percentile(final_returns, 5)]) * 100, 2),
        }
    
    async def _fetch_historical_data(
        self, symbol: str, start_date: str, end_date: str
    ) -> list[dict] | None:
        """Fetch OHLCV data from yfinance."""
        def _fetch():
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, auto_adjust=True)
            
            if df.empty:
                return None
            
            data = []
            for idx, row in df.iterrows():
                data.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            return data
        
        return await asyncio.to_thread(_fetch)
    
    def _get_strategy(self, name: str) -> Callable | None:
        """Get strategy signal generator function."""
        strategies = {
            "ma_crossover": self._strategy_ma_crossover,
            "rsi_mean_reversion": self._strategy_rsi_reversion,
            "momentum": self._strategy_momentum,
            "breakout": self._strategy_breakout,
            "macd": self._strategy_macd,
            "bollinger": self._strategy_bollinger,
        }
        return strategies.get(name)
    
    def _strategy_ma_crossover(
        self, data: list[dict], fast: int = 20, slow: int = 50
    ) -> list[int]:
        """Moving average crossover strategy. Returns signals (+1, 0, -1)."""
        closes = np.array([d["close"] for d in data])
        
        if len(closes) < slow:
            return [0] * len(closes)
        
        fast_ma = self._sma(closes, fast)
        slow_ma = self._sma(closes, slow)
        
        signals = []
        for i in range(len(closes)):
            if i < slow:
                signals.append(0)
            elif fast_ma[i] > slow_ma[i] and fast_ma[i-1] <= slow_ma[i-1]:
                signals.append(1)  # Buy
            elif fast_ma[i] < slow_ma[i] and fast_ma[i-1] >= slow_ma[i-1]:
                signals.append(-1)  # Sell
            else:
                signals.append(0)  # Hold
        
        return signals
    
    def _strategy_rsi_reversion(
        self, data: list[dict], period: int = 14, oversold: int = 30, overbought: int = 70
    ) -> list[int]:
        """RSI mean reversion strategy."""
        closes = np.array([d["close"] for d in data])
        rsi = self._compute_rsi(closes, period)
        
        signals = []
        for i in range(len(closes)):
            if i < period:
                signals.append(0)
            elif rsi[i] < oversold and rsi[i-1] >= oversold:
                signals.append(1)  # Buy oversold
            elif rsi[i] > overbought and rsi[i-1] <= overbought:
                signals.append(-1)  # Sell overbought
            else:
                signals.append(0)
        
        return signals
    
    def _strategy_momentum(
        self, data: list[dict], lookback: int = 20, threshold: float = 0.05
    ) -> list[int]:
        """Momentum strategy based on price change."""
        closes = np.array([d["close"] for d in data])
        
        signals = []
        for i in range(len(closes)):
            if i < lookback:
                signals.append(0)
            else:
                momentum = (closes[i] - closes[i - lookback]) / closes[i - lookback]
                if momentum > threshold:
                    signals.append(1)
                elif momentum < -threshold:
                    signals.append(-1)
                else:
                    signals.append(0)
        
        return signals
    
    def _strategy_breakout(
        self, data: list[dict], lookback: int = 20
    ) -> list[int]:
        """Breakout strategy - buy on 20-day high, sell on 20-day low."""
        closes = np.array([d["close"] for d in data])
        highs = np.array([d["high"] for d in data])
        lows = np.array([d["low"] for d in data])
        
        signals = []
        for i in range(len(closes)):
            if i < lookback:
                signals.append(0)
            else:
                period_high = np.max(highs[i-lookback:i])
                period_low = np.min(lows[i-lookback:i])
                
                if closes[i] > period_high:
                    signals.append(1)
                elif closes[i] < period_low:
                    signals.append(-1)
                else:
                    signals.append(0)
        
        return signals
    
    def _strategy_macd(
        self, data: list[dict], fast: int = 12, slow: int = 26, signal: int = 9
    ) -> list[int]:
        """MACD crossover strategy."""
        closes = np.array([d["close"] for d in data])
        
        if len(closes) < slow + signal:
            return [0] * len(closes)
        
        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)
        macd = ema_fast - ema_slow
        signal_line = self._ema(macd, signal)
        
        signals = []
        for i in range(len(closes)):
            if i < slow + signal:
                signals.append(0)
            elif macd[i] > signal_line[i] and macd[i-1] <= signal_line[i-1]:
                signals.append(1)
            elif macd[i] < signal_line[i] and macd[i-1] >= signal_line[i-1]:
                signals.append(-1)
            else:
                signals.append(0)
        
        return signals
    
    def _strategy_bollinger(
        self, data: list[dict], period: int = 20, num_std: float = 2.0
    ) -> list[int]:
        """Bollinger Bands mean reversion strategy."""
        closes = np.array([d["close"] for d in data])
        
        if len(closes) < period:
            return [0] * len(closes)
        
        sma = self._sma(closes, period)
        std = self._rolling_std(closes, period)
        
        upper = sma + num_std * std
        lower = sma - num_std * std
        
        signals = []
        for i in range(len(closes)):
            if i < period:
                signals.append(0)
            elif closes[i] < lower[i]:
                signals.append(1)  # Buy at lower band
            elif closes[i] > upper[i]:
                signals.append(-1)  # Sell at upper band
            else:
                signals.append(0)
        
        return signals
    
    def _execute_backtest(
        self,
        symbol: str,
        data: list[dict],
        signals: list[int],
        initial_capital: float,
        strategy: str,
    ) -> dict[str, Any]:
        """Execute backtest and calculate performance."""
        capital = initial_capital
        position = 0  # Number of shares held
        entry_price = 0.0
        entry_date = ""
        trades = []
        equity_curve = []
        
        for i, (bar, signal) in enumerate(zip(data, signals)):
            price = bar["close"]
            date = bar["date"]
            
            # Calculate current equity
            equity = capital + position * price
            equity_curve.append({"date": date, "equity": round(equity, 2)})
            
            # Process signals
            if signal == 1 and position == 0:  # Buy signal
                # Apply slippage and commission
                buy_price = price * (1 + self.SLIPPAGE_RATE)
                commission = capital * self.COMMISSION_RATE
                shares = int((capital - commission) / buy_price)
                
                if shares > 0:
                    position = shares
                    entry_price = buy_price
                    entry_date = date
                    capital -= shares * buy_price + commission
                    
            elif signal == -1 and position > 0:  # Sell signal
                # Apply slippage and commission
                sell_price = price * (1 - self.SLIPPAGE_RATE)
                commission = position * sell_price * self.COMMISSION_RATE
                
                pnl = position * (sell_price - entry_price) - commission
                pnl_pct = (sell_price - entry_price) / entry_price
                
                capital += position * sell_price - commission
                
                # Calculate holding period
                entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
                exit_dt = datetime.strptime(date, "%Y-%m-%d")
                holding_days = (exit_dt - entry_dt).days
                
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": date,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(sell_price, 2),
                    "shares": position,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct * 100, 2),
                    "holding_days": holding_days,
                })
                
                position = 0
                entry_price = 0.0
        
        # Close any open position at end
        if position > 0:
            final_price = data[-1]["close"] * (1 - self.SLIPPAGE_RATE)
            commission = position * final_price * self.COMMISSION_RATE
            pnl = position * (final_price - entry_price) - commission
            pnl_pct = (final_price - entry_price) / entry_price
            capital += position * final_price - commission
            
            entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
            exit_dt = datetime.strptime(data[-1]["date"], "%Y-%m-%d")
            holding_days = (exit_dt - entry_dt).days
            
            trades.append({
                "entry_date": entry_date,
                "exit_date": data[-1]["date"],
                "entry_price": round(entry_price, 2),
                "exit_price": round(final_price, 2),
                "shares": position,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct * 100, 2),
                "holding_days": holding_days,
                "note": "Closed at end of backtest",
            })
        
        # Calculate summary statistics
        winning = [t for t in trades if t["pnl"] > 0]
        losing = [t for t in trades if t["pnl"] <= 0]
        
        total_return = (capital - initial_capital) / initial_capital
        win_rate = len(winning) / len(trades) if trades else 0
        
        gross_profit = sum(t["pnl"] for t in winning)
        gross_loss = abs(sum(t["pnl"] for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        avg_win = np.mean([t["pnl_pct"] / 100 for t in winning]) if winning else 0
        avg_loss = np.mean([t["pnl_pct"] / 100 for t in losing]) if losing else 0
        
        best_trade = max((t["pnl_pct"] / 100 for t in trades), default=0)
        worst_trade = min((t["pnl_pct"] / 100 for t in trades), default=0)
        
        avg_hold = np.mean([t["holding_days"] for t in trades]) if trades else 0
        
        # Calculate exposure (% time in market)
        days_in_market = sum(t["holding_days"] for t in trades)
        total_days = len(data)
        exposure = days_in_market / total_days if total_days > 0 else 0
        
        return {
            "final_capital": capital,
            "total_return": total_return,
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "avg_hold_days": avg_hold,
            "exposure": exposure,
            "trades": trades,
            "equity_curve": equity_curve,
        }
    
    def _calculate_metrics(
        self, result: dict[str, Any], data: list[dict]
    ) -> dict[str, Any]:
        """Calculate additional risk/return metrics."""
        equity = [e["equity"] for e in result["equity_curve"]]
        
        if len(equity) < 2:
            return {
                "annualized_return": 0,
                "sharpe_ratio": 0,
                "sortino_ratio": 0,
                "calmar_ratio": 0,
                "max_drawdown": 0,
                "max_dd_duration": 0,
                "monthly_returns": [],
            }
        
        # Daily returns
        equity = np.array(equity)
        returns = np.diff(equity) / equity[:-1]
        
        # Annualized return
        total_days = len(equity)
        years = total_days / 252
        total_return = (equity[-1] - equity[0]) / equity[0]
        ann_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Sharpe ratio (assuming 5% risk-free rate)
        excess_returns = returns - 0.05 / 252
        sharpe = np.sqrt(252) * np.mean(excess_returns) / np.std(returns) if np.std(returns) > 0 else 0
        
        # Sortino ratio
        negative_returns = returns[returns < 0]
        downside_std = np.std(negative_returns) if len(negative_returns) > 0 else np.std(returns)
        sortino = np.sqrt(252) * np.mean(excess_returns) / downside_std if downside_std > 0 else 0
        
        # Max drawdown
        running_max = np.maximum.accumulate(equity)
        drawdowns = (equity - running_max) / running_max
        max_dd = np.min(drawdowns)
        
        # Max drawdown duration
        in_drawdown = equity < running_max
        dd_duration = 0
        max_duration = 0
        for is_dd in in_drawdown:
            if is_dd:
                dd_duration += 1
                max_duration = max(max_duration, dd_duration)
            else:
                dd_duration = 0
        
        # Calmar ratio
        calmar = ann_return / abs(max_dd) if max_dd != 0 else 0
        
        # Monthly returns
        monthly = self._calculate_monthly_returns(result["equity_curve"])
        
        return {
            "annualized_return": ann_return,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "max_drawdown": max_dd,
            "max_dd_duration": max_duration,
            "monthly_returns": monthly,
        }
    
    def _calculate_monthly_returns(self, equity_curve: list[dict]) -> list[dict]:
        """Calculate monthly return summary."""
        if not equity_curve:
            return []
        
        monthly = {}
        for point in equity_curve:
            month_key = point["date"][:7]  # YYYY-MM
            if month_key not in monthly:
                monthly[month_key] = {"first": point["equity"], "last": point["equity"]}
            else:
                monthly[month_key]["last"] = point["equity"]
        
        results = []
        for month, values in monthly.items():
            ret = (values["last"] - values["first"]) / values["first"]
            results.append({"month": month, "return_pct": round(ret * 100, 2)})
        
        return results
    
    def _optimize_strategy_params(
        self, strategy: str, data: list[dict]
    ) -> dict[str, Any]:
        """Simple parameter optimization for walk-forward."""
        # Define parameter grids
        param_grids = {
            "ma_crossover": [
                {"fast": 10, "slow": 30},
                {"fast": 20, "slow": 50},
                {"fast": 10, "slow": 50},
                {"fast": 5, "slow": 20},
            ],
            "rsi_mean_reversion": [
                {"period": 14, "oversold": 30, "overbought": 70},
                {"period": 7, "oversold": 25, "overbought": 75},
                {"period": 21, "oversold": 35, "overbought": 65},
            ],
            "momentum": [
                {"lookback": 10, "threshold": 0.03},
                {"lookback": 20, "threshold": 0.05},
                {"lookback": 30, "threshold": 0.08},
            ],
            "macd": [
                {"fast": 12, "slow": 26, "signal": 9},
                {"fast": 8, "slow": 17, "signal": 9},
                {"fast": 5, "slow": 35, "signal": 5},
            ],
        }
        
        grid = param_grids.get(strategy, [{}])
        best_params = grid[0]
        best_return = float('-inf')
        
        strategy_func = self._get_strategy(strategy)
        if not strategy_func:
            return best_params
        
        for params in grid:
            signals = strategy_func(data, **params)
            result = self._execute_backtest("test", data, signals, self.INITIAL_CAPITAL, strategy)
            if result["total_return"] > best_return:
                best_return = result["total_return"]
                best_params = params
        
        return best_params
    
    def _quick_return(self, data: list[dict], strategy: str, params: dict) -> float:
        """Quick return calculation for optimization."""
        strategy_func = self._get_strategy(strategy)
        if not strategy_func:
            return 0
        signals = strategy_func(data, **params)
        result = self._execute_backtest("test", data, signals, self.INITIAL_CAPITAL, strategy)
        return result["total_return"]
    
    def _grade_robustness(self, returns: list[float]) -> str:
        """Grade strategy robustness based on walk-forward results."""
        if not returns:
            return "N/A"
        
        positive = sum(1 for r in returns if r > 0)
        ratio = positive / len(returns)
        avg = np.mean(returns)
        
        if ratio >= 0.75 and avg > 0.05:
            return "A"
        elif ratio >= 0.5 and avg > 0.02:
            return "B"
        elif ratio >= 0.5 or avg > 0:
            return "C"
        else:
            return "D"
    
    # Helper functions
    def _sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Simple moving average."""
        result = np.full(len(data), np.nan)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential moving average."""
        result = np.zeros(len(data))
        multiplier = 2 / (period + 1)
        result[0] = data[0]
        
        for i in range(1, len(data)):
            result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
        
        return result
    
    def _rolling_std(self, data: np.ndarray, period: int) -> np.ndarray:
        """Rolling standard deviation."""
        result = np.full(len(data), np.nan)
        for i in range(period - 1, len(data)):
            result[i] = np.std(data[i - period + 1:i + 1])
        return result
    
    def _compute_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Compute RSI."""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        result = np.full(len(prices), 50.0)
        
        for i in range(period, len(prices)):
            avg_gain = np.mean(gains[i-period:i])
            avg_loss = np.mean(losses[i-period:i])
            
            if avg_loss == 0:
                result[i] = 100
            else:
                rs = avg_gain / avg_loss
                result[i] = 100 - (100 / (1 + rs))
        
        return result
