"""Backtesting Engine — event-driven backtester with full performance analytics.

Usage:
    from engine.backtest import Backtester, BacktestConfig
    from engine.strategy import Strategy, StrategyEngine

    config = BacktestConfig(initial_capital=100_000)
    bt = Backtester(config)
    result = bt.run(strategy, ohlcv_df)
    print(result.summary())
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from engine.strategy import Signal, Strategy, StrategyEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    """Backtester configuration."""
    initial_capital: float = 100_000.0
    commission_pct: float = 0.001        # 0.1% per trade
    slippage_pct: float = 0.0005         # 0.05% slippage
    margin_requirement: float = 1.0      # 1.0 = no leverage
    risk_free_rate: float = 0.04         # annual, for Sharpe
    compounding: bool = True             # reinvest profits
    short_selling: bool = True
    max_drawdown_limit: float | None = None  # stop if exceeded


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    """Single completed trade."""
    entry_date: str
    exit_date: str
    side: str              # "LONG" or "SHORT"
    entry_price: float
    exit_price: float
    shares: float
    commission: float
    slippage: float
    gross_pnl: float
    net_pnl: float
    pnl_pct: float
    holding_bars: int
    exit_reason: str       # "signal", "stop_loss", "take_profit", "trailing_stop", "max_bars"


# ---------------------------------------------------------------------------
# Backtest Result
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Full backtest output with metrics and trade log."""
    strategy_name: str
    symbol: str
    config: BacktestConfig
    start_date: str
    end_date: str
    total_bars: int

    # Capital
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annual_return_pct: float

    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration: int   # bars
    volatility_annual: float

    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    expectancy: float            # avg pnl per trade
    avg_holding_bars: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Time series
    equity_curve: list[float]
    drawdown_curve: list[float]
    monthly_returns: dict[str, float]
    trades: list[Trade]
    signals_df: pd.DataFrame | None = None

    def summary(self) -> dict[str, Any]:
        """Return a clean summary dict for API / display."""
        return {
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "period": f"{self.start_date} → {self.end_date}",
            "total_bars": self.total_bars,
            "initial_capital": round(self.initial_capital, 2),
            "final_capital": round(self.final_capital, 2),
            "total_return": f"{self.total_return_pct:.2f}%",
            "annual_return": f"{self.annual_return_pct:.2f}%",
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "calmar_ratio": round(self.calmar_ratio, 3),
            "max_drawdown": f"{self.max_drawdown_pct:.2f}%",
            "max_dd_duration_bars": self.max_drawdown_duration,
            "volatility": f"{self.volatility_annual:.2f}%",
            "total_trades": self.total_trades,
            "win_rate": f"{self.win_rate:.1f}%",
            "profit_factor": round(self.profit_factor, 3),
            "expectancy": round(self.expectancy, 2),
            "avg_win": f"{self.avg_win_pct:.2f}%",
            "avg_loss": f"{self.avg_loss_pct:.2f}%",
            "avg_holding_bars": round(self.avg_holding_bars, 1),
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "monthly_returns": self.monthly_returns,
        }


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

class Backtester:
    """Event-driven backtesting engine."""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()
        self._engine = StrategyEngine()

    def run(self, strategy: Strategy, df: pd.DataFrame, symbol: str = "UNKNOWN") -> BacktestResult:
        """Run a full backtest of *strategy* on OHLCV *df*."""
        cfg = self.config

        # Generate signals
        signals_df = self._engine.run(strategy, df)
        close = df["Close"].values
        high = df["High"].values
        low = df["Low"].values
        n = len(df)

        # State
        equity = np.full(n, cfg.initial_capital, dtype=float)
        cash = cfg.initial_capital
        position = 0        # shares held (positive=long, negative=short)
        entry_price = 0.0
        entry_bar = 0
        trailing_stop_price = 0.0
        trades: list[Trade] = []

        for i in range(1, n):
            sig = signals_df["signal"].iloc[i]
            price = close[i]
            equity[i] = equity[i - 1]

            # ── Check stop-loss / take-profit / trailing on open positions ──
            if position > 0:
                # Long position checks
                bar_low = low[i]
                bar_high = high[i]

                # Stop loss
                if strategy.stop_loss_pct and bar_low <= entry_price * (1 - strategy.stop_loss_pct):
                    exit_px = entry_price * (1 - strategy.stop_loss_pct)
                    trades.append(self._close_trade(
                        entry_price, exit_px, position, "LONG", entry_bar, i,
                        str(df.index[entry_bar]), str(df.index[i]), "stop_loss"))
                    cash += position * exit_px * (1 - cfg.commission_pct - cfg.slippage_pct)
                    position = 0
                    equity[i] = cash
                    continue

                # Take profit
                if strategy.take_profit_pct and bar_high >= entry_price * (1 + strategy.take_profit_pct):
                    exit_px = entry_price * (1 + strategy.take_profit_pct)
                    trades.append(self._close_trade(
                        entry_price, exit_px, position, "LONG", entry_bar, i,
                        str(df.index[entry_bar]), str(df.index[i]), "take_profit"))
                    cash += position * exit_px * (1 - cfg.commission_pct - cfg.slippage_pct)
                    position = 0
                    equity[i] = cash
                    continue

                # Trailing stop
                if strategy.trailing_stop_pct:
                    trailing_stop_price = max(trailing_stop_price, bar_high * (1 - strategy.trailing_stop_pct))
                    if bar_low <= trailing_stop_price:
                        exit_px = trailing_stop_price
                        trades.append(self._close_trade(
                            entry_price, exit_px, position, "LONG", entry_bar, i,
                            str(df.index[entry_bar]), str(df.index[i]), "trailing_stop"))
                        cash += position * exit_px * (1 - cfg.commission_pct - cfg.slippage_pct)
                        position = 0
                        equity[i] = cash
                        continue

                # Mark to market
                equity[i] = cash + position * price

            elif position < 0:
                # Short position checks
                bar_high = high[i]
                bar_low = low[i]

                if strategy.stop_loss_pct and bar_high >= entry_price * (1 + strategy.stop_loss_pct):
                    exit_px = entry_price * (1 + strategy.stop_loss_pct)
                    trades.append(self._close_trade(
                        entry_price, exit_px, abs(position), "SHORT", entry_bar, i,
                        str(df.index[entry_bar]), str(df.index[i]), "stop_loss"))
                    cash += abs(position) * (2 * entry_price - exit_px) * (1 - cfg.commission_pct - cfg.slippage_pct)
                    position = 0
                    equity[i] = cash
                    continue

                if strategy.take_profit_pct and bar_low <= entry_price * (1 - strategy.take_profit_pct):
                    exit_px = entry_price * (1 - strategy.take_profit_pct)
                    trades.append(self._close_trade(
                        entry_price, exit_px, abs(position), "SHORT", entry_bar, i,
                        str(df.index[entry_bar]), str(df.index[i]), "take_profit"))
                    cash += abs(position) * (2 * entry_price - exit_px) * (1 - cfg.commission_pct - cfg.slippage_pct)
                    position = 0
                    equity[i] = cash
                    continue

                # Mark to market
                equity[i] = cash + abs(position) * (2 * entry_price - price)
            else:
                equity[i] = cash

            # ── Process strategy signals ──
            if sig == Signal.LONG and position <= 0:
                # Close short first if any
                if position < 0:
                    trades.append(self._close_trade(
                        entry_price, price, abs(position), "SHORT", entry_bar, i,
                        str(df.index[entry_bar]), str(df.index[i]), "signal"))
                    cash += abs(position) * (2 * entry_price - price) * (1 - cfg.commission_pct - cfg.slippage_pct)
                    position = 0

                # Open long
                buy_price = price * (1 + cfg.slippage_pct)
                if cfg.compounding:
                    alloc = cash * 0.95  # keep 5% cash buffer
                else:
                    alloc = min(strategy.position_value, cash * 0.95)
                shares = int(alloc / (buy_price * (1 + cfg.commission_pct)))
                if shares > 0:
                    cost = shares * buy_price * (1 + cfg.commission_pct)
                    cash -= cost
                    position = shares
                    entry_price = buy_price
                    entry_bar = i
                    trailing_stop_price = buy_price * (1 - (strategy.trailing_stop_pct or 1.0))
                equity[i] = cash + position * price

            elif sig == Signal.SHORT and position >= 0 and cfg.short_selling:
                # Close long first if any
                if position > 0:
                    trades.append(self._close_trade(
                        entry_price, price, position, "LONG", entry_bar, i,
                        str(df.index[entry_bar]), str(df.index[i]), "signal"))
                    cash += position * price * (1 - cfg.commission_pct - cfg.slippage_pct)
                    position = 0

                # Open short
                sell_price = price * (1 - cfg.slippage_pct)
                if cfg.compounding:
                    alloc = cash * 0.95
                else:
                    alloc = min(strategy.position_value, cash * 0.95)
                shares = int(alloc / (sell_price * (1 + cfg.commission_pct)))
                if shares > 0:
                    cash += shares * sell_price * (1 - cfg.commission_pct)
                    position = -shares
                    entry_price = sell_price
                    entry_bar = i
                equity[i] = cash + abs(position) * (2 * entry_price - price) if position < 0 else cash

            elif sig == Signal.EXIT_LONG and position > 0:
                trades.append(self._close_trade(
                    entry_price, price, position, "LONG", entry_bar, i,
                    str(df.index[entry_bar]), str(df.index[i]), "signal"))
                cash += position * price * (1 - cfg.commission_pct - cfg.slippage_pct)
                position = 0
                equity[i] = cash

            elif sig == Signal.EXIT_SHORT and position < 0:
                trades.append(self._close_trade(
                    entry_price, price, abs(position), "SHORT", entry_bar, i,
                    str(df.index[entry_bar]), str(df.index[i]), "signal"))
                cash += abs(position) * (2 * entry_price - price) * (1 - cfg.commission_pct - cfg.slippage_pct)
                position = 0
                equity[i] = cash

            # Max drawdown circuit breaker
            if cfg.max_drawdown_limit:
                peak = np.max(equity[: i + 1])
                dd = (peak - equity[i]) / peak
                if dd > cfg.max_drawdown_limit:
                    if position > 0:
                        cash += position * price * (1 - cfg.commission_pct)
                        trades.append(self._close_trade(
                            entry_price, price, position, "LONG", entry_bar, i,
                            str(df.index[entry_bar]), str(df.index[i]), "max_drawdown"))
                    elif position < 0:
                        cash += abs(position) * (2 * entry_price - price) * (1 - cfg.commission_pct)
                        trades.append(self._close_trade(
                            entry_price, price, abs(position), "SHORT", entry_bar, i,
                            str(df.index[entry_bar]), str(df.index[i]), "max_drawdown"))
                    position = 0
                    equity[i] = cash
                    logger.warning("Max drawdown limit hit at bar %d — liquidated", i)
                    # Fill remaining equity flat
                    equity[i:] = cash
                    break

        # Close any open position at end
        if position > 0:
            trades.append(self._close_trade(
                entry_price, close[-1], position, "LONG", entry_bar, n - 1,
                str(df.index[entry_bar]), str(df.index[-1]), "end_of_data"))
            cash += position * close[-1] * (1 - cfg.commission_pct)
            equity[-1] = cash
        elif position < 0:
            trades.append(self._close_trade(
                entry_price, close[-1], abs(position), "SHORT", entry_bar, n - 1,
                str(df.index[entry_bar]), str(df.index[-1]), "end_of_data"))
            cash += abs(position) * (2 * entry_price - close[-1]) * (1 - cfg.commission_pct)
            equity[-1] = cash

        # ── Compute metrics ──
        metrics = self._compute_metrics(equity, trades, df, cfg)

        return BacktestResult(
            strategy_name=strategy.name,
            symbol=symbol,
            config=cfg,
            start_date=str(df.index[0]),
            end_date=str(df.index[-1]),
            total_bars=n,
            initial_capital=cfg.initial_capital,
            final_capital=round(equity[-1], 2),
            equity_curve=equity.tolist(),
            drawdown_curve=metrics["drawdown_curve"],
            monthly_returns=metrics["monthly_returns"],
            trades=trades,
            signals_df=signals_df,
            **metrics["stats"],
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _close_trade(
        self, entry_px: float, exit_px: float, shares: float, side: str,
        entry_bar: int, exit_bar: int, entry_date: str, exit_date: str,
        reason: str,
    ) -> Trade:
        cfg = self.config
        commission = shares * (entry_px + exit_px) * cfg.commission_pct
        slippage = shares * (entry_px + exit_px) * cfg.slippage_pct
        if side == "LONG":
            gross_pnl = shares * (exit_px - entry_px)
        else:
            gross_pnl = shares * (entry_px - exit_px)
        net_pnl = gross_pnl - commission - slippage
        pnl_pct = (net_pnl / (shares * entry_px)) * 100 if entry_px else 0

        return Trade(
            entry_date=entry_date, exit_date=exit_date, side=side,
            entry_price=round(entry_px, 4), exit_price=round(exit_px, 4),
            shares=shares, commission=round(commission, 4),
            slippage=round(slippage, 4), gross_pnl=round(gross_pnl, 2),
            net_pnl=round(net_pnl, 2), pnl_pct=round(pnl_pct, 2),
            holding_bars=exit_bar - entry_bar, exit_reason=reason,
        )

    def _compute_metrics(
        self, equity: np.ndarray, trades: list[Trade],
        df: pd.DataFrame, cfg: BacktestConfig,
    ) -> dict[str, Any]:
        """Compute all performance metrics from equity curve and trade list."""
        n = len(equity)
        returns = np.diff(equity) / equity[:-1]
        returns = returns[np.isfinite(returns)]

        # Drawdown
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / np.where(peak > 0, peak, 1)
        max_dd = float(np.max(dd) * 100) if len(dd) else 0.0

        # Max drawdown duration
        dd_dur = 0
        max_dd_dur = 0
        for i in range(len(dd)):
            if dd[i] > 0:
                dd_dur += 1
                max_dd_dur = max(max_dd_dur, dd_dur)
            else:
                dd_dur = 0

        # Annual metrics
        trading_days = 252
        years = n / trading_days if n > 0 else 1
        total_ret = (equity[-1] / cfg.initial_capital - 1) * 100
        annual_ret = ((equity[-1] / cfg.initial_capital) ** (1 / max(years, 0.01)) - 1) * 100 if equity[-1] > 0 else -100

        vol_daily = float(np.std(returns)) if len(returns) else 0
        vol_annual = vol_daily * math.sqrt(trading_days) * 100

        # Sharpe
        excess = returns - cfg.risk_free_rate / trading_days
        sharpe = float(np.mean(excess) / np.std(excess) * math.sqrt(trading_days)) if np.std(excess) > 0 else 0

        # Sortino
        downside = returns[returns < 0]
        down_std = float(np.std(downside)) if len(downside) > 0 else 0.001
        sortino = float(np.mean(excess) / down_std * math.sqrt(trading_days)) if down_std > 0 else 0

        # Calmar
        calmar = annual_ret / max_dd if max_dd > 0 else 0

        # Trade stats
        n_trades = len(trades)
        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl <= 0]
        n_wins = len(wins)
        n_losses = len(losses)
        win_rate = (n_wins / n_trades * 100) if n_trades else 0
        avg_win = float(np.mean([t.pnl_pct for t in wins])) if wins else 0
        avg_loss = float(np.mean([t.pnl_pct for t in losses])) if losses else 0
        gross_profit = sum(t.net_pnl for t in wins)
        gross_loss = abs(sum(t.net_pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0
        expectancy = float(np.mean([t.net_pnl for t in trades])) if trades else 0
        avg_hold = float(np.mean([t.holding_bars for t in trades])) if trades else 0

        # Consecutive wins / losses
        max_cons_w = max_cons_l = cons_w = cons_l = 0
        for t in trades:
            if t.net_pnl > 0:
                cons_w += 1
                cons_l = 0
                max_cons_w = max(max_cons_w, cons_w)
            else:
                cons_l += 1
                cons_w = 0
                max_cons_l = max(max_cons_l, cons_l)

        # Monthly returns
        monthly: dict[str, float] = {}
        if hasattr(df.index, "to_period"):
            eq_series = pd.Series(equity, index=df.index)
            monthly_eq = eq_series.resample("ME").last()
            monthly_ret = monthly_eq.pct_change().dropna()
            monthly = {str(k): round(float(v) * 100, 2) for k, v in monthly_ret.items()}

        return {
            "stats": {
                "total_return_pct": round(total_ret, 2),
                "annual_return_pct": round(annual_ret, 2),
                "sharpe_ratio": round(sharpe, 3),
                "sortino_ratio": round(sortino, 3),
                "calmar_ratio": round(calmar, 3),
                "max_drawdown_pct": round(max_dd, 2),
                "max_drawdown_duration": max_dd_dur,
                "volatility_annual": round(vol_annual, 2),
                "total_trades": n_trades,
                "winning_trades": n_wins,
                "losing_trades": n_losses,
                "win_rate": round(win_rate, 1),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "profit_factor": round(profit_factor, 3),
                "expectancy": round(expectancy, 2),
                "avg_holding_bars": round(avg_hold, 1),
                "max_consecutive_wins": max_cons_w,
                "max_consecutive_losses": max_cons_l,
            },
            "drawdown_curve": dd.tolist(),
            "monthly_returns": monthly,
        }


# ---------------------------------------------------------------------------
# Walk-forward analysis
# ---------------------------------------------------------------------------

def walk_forward(
    strategy: Strategy,
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    n_splits: int = 5,
    train_pct: float = 0.7,
    config: BacktestConfig | None = None,
) -> dict[str, Any]:
    """Run walk-forward analysis: train/test splits with out-of-sample metrics."""
    cfg = config or BacktestConfig()
    bt = Backtester(cfg)
    n = len(df)
    split_size = n // n_splits
    results = []

    for fold in range(n_splits):
        start = fold * split_size
        end = min(start + split_size, n)
        if end - start < 50:
            continue
        train_end = start + int((end - start) * train_pct)
        test_df = df.iloc[train_end:end]
        if len(test_df) < 20:
            continue
        result = bt.run(strategy, test_df, symbol)
        results.append({
            "fold": fold + 1,
            "test_start": str(test_df.index[0]),
            "test_end": str(test_df.index[-1]),
            "test_bars": len(test_df),
            "return_pct": result.total_return_pct,
            "sharpe": result.sharpe_ratio,
            "max_dd": result.max_drawdown_pct,
            "trades": result.total_trades,
            "win_rate": result.win_rate,
        })

    avg_return = float(np.mean([r["return_pct"] for r in results])) if results else 0
    avg_sharpe = float(np.mean([r["sharpe"] for r in results])) if results else 0

    return {
        "strategy": strategy.name,
        "symbol": symbol,
        "n_splits": n_splits,
        "folds": results,
        "avg_oos_return": round(avg_return, 2),
        "avg_oos_sharpe": round(avg_sharpe, 3),
        "robust": avg_sharpe > 0.5 and avg_return > 0,
    }


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------

def monte_carlo(
    trades: list[Trade],
    initial_capital: float = 100_000.0,
    n_simulations: int = 1_000,
) -> dict[str, Any]:
    """Monte Carlo simulation by resampling trade P&L sequence."""
    if not trades:
        return {"error": "No trades to simulate"}

    pnls = np.array([t.net_pnl for t in trades])
    n_trades = len(pnls)

    final_capitals = []
    max_dds = []

    rng = np.random.default_rng(42)

    for _ in range(n_simulations):
        shuffled = rng.choice(pnls, size=n_trades, replace=True)
        equity = np.cumsum(shuffled) + initial_capital
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / np.where(peak > 0, peak, 1)
        final_capitals.append(float(equity[-1]))
        max_dds.append(float(np.max(dd) * 100))

    finals = np.array(final_capitals)
    dds = np.array(max_dds)

    return {
        "n_simulations": n_simulations,
        "n_trades": n_trades,
        "initial_capital": initial_capital,
        "median_final": round(float(np.median(finals)), 2),
        "mean_final": round(float(np.mean(finals)), 2),
        "percentile_5": round(float(np.percentile(finals, 5)), 2),
        "percentile_25": round(float(np.percentile(finals, 25)), 2),
        "percentile_75": round(float(np.percentile(finals, 75)), 2),
        "percentile_95": round(float(np.percentile(finals, 95)), 2),
        "probability_profit": round(float(np.mean(finals > initial_capital) * 100), 1),
        "median_max_drawdown": round(float(np.median(dds)), 2),
        "worst_case_dd_95": round(float(np.percentile(dds, 95)), 2),
        "var_95": round(float(initial_capital - np.percentile(finals, 5)), 2),
    }
