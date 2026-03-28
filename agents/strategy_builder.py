"""Strategy Builder Agent — lets users define and backtest custom strategies.

Users can:
- Define entry/exit rules using technical indicators
- Combine indicators with AND/OR logic
- Set position sizing and risk parameters
- Backtest strategies on historical data
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# Pre-defined strategy templates
STRATEGY_TEMPLATES = {
    "ma_crossover": {
        "name": "Moving Average Crossover",
        "description": "Buy when short MA crosses above long MA, sell when it crosses below",
        "parameters": {
            "short_period": {"type": "int", "default": 20, "min": 5, "max": 100},
            "long_period": {"type": "int", "default": 50, "min": 20, "max": 200},
        },
        "entry_rules": ["short_ma > long_ma"],
        "exit_rules": ["short_ma < long_ma"],
    },
    "rsi_mean_reversion": {
        "name": "RSI Mean Reversion",
        "description": "Buy when RSI is oversold, sell when overbought",
        "parameters": {
            "rsi_period": {"type": "int", "default": 14, "min": 5, "max": 30},
            "oversold": {"type": "float", "default": 30, "min": 10, "max": 40},
            "overbought": {"type": "float", "default": 70, "min": 60, "max": 90},
        },
        "entry_rules": ["rsi < oversold"],
        "exit_rules": ["rsi > overbought"],
    },
    "bollinger_breakout": {
        "name": "Bollinger Band Breakout",
        "description": "Buy when price breaks above upper band, sell on lower band break",
        "parameters": {
            "bb_period": {"type": "int", "default": 20, "min": 10, "max": 50},
            "bb_std": {"type": "float", "default": 2.0, "min": 1.0, "max": 3.0},
        },
        "entry_rules": ["price > upper_band"],
        "exit_rules": ["price < lower_band"],
    },
    "macd_signal": {
        "name": "MACD Signal Line",
        "description": "Buy on MACD bullish crossover, sell on bearish crossover",
        "parameters": {
            "fast_period": {"type": "int", "default": 12, "min": 5, "max": 20},
            "slow_period": {"type": "int", "default": 26, "min": 15, "max": 50},
            "signal_period": {"type": "int", "default": 9, "min": 5, "max": 15},
        },
        "entry_rules": ["macd > signal_line", "macd_hist > 0"],
        "exit_rules": ["macd < signal_line"],
    },
    "momentum_trend": {
        "name": "Momentum + Trend Following",
        "description": "Buy in uptrend with positive momentum, exit on reversal",
        "parameters": {
            "trend_ma": {"type": "int", "default": 50, "min": 20, "max": 200},
            "momentum_period": {"type": "int", "default": 20, "min": 5, "max": 50},
            "momentum_threshold": {"type": "float", "default": 0.02, "min": 0.005, "max": 0.1},
        },
        "entry_rules": ["price > trend_ma", "momentum > threshold"],
        "exit_rules": ["price < trend_ma", "momentum < -threshold"],
    },
    "combined_multi_indicator": {
        "name": "Multi-Indicator Confluence",
        "description": "Buy when RSI, MACD, and MA all align bullish",
        "parameters": {
            "rsi_period": {"type": "int", "default": 14, "min": 5, "max": 30},
            "rsi_buy_level": {"type": "float", "default": 40, "min": 20, "max": 50},
            "rsi_sell_level": {"type": "float", "default": 65, "min": 55, "max": 80},
            "ma_period": {"type": "int", "default": 50, "min": 20, "max": 200},
            "min_signals": {"type": "int", "default": 2, "min": 1, "max": 3},
        },
        "entry_rules": ["rsi < rsi_buy_level", "price > ma", "macd > 0"],
        "exit_rules": ["rsi > rsi_sell_level", "price < ma"],
    },
}


class StrategyBuilderAgent:
    """Build, validate, and backtest user-defined strategies."""

    name = "StrategyBuilderAgent"

    def get_templates(self) -> dict:
        return STRATEGY_TEMPLATES

    async def build_strategy(self, name: str, strategy_type: str,
                              parameters: dict, user_id: str) -> dict[str, Any]:
        """Create and validate a user strategy."""
        template = STRATEGY_TEMPLATES.get(strategy_type)
        if not template:
            return {"error": f"Unknown strategy type: {strategy_type}. Available: {list(STRATEGY_TEMPLATES.keys())}"}

        # Validate parameters against template
        validated_params = {}
        for param_name, param_spec in template["parameters"].items():
            value = parameters.get(param_name, param_spec["default"])

            if param_spec["type"] == "int":
                value = int(value)
            elif param_spec["type"] == "float":
                value = float(value)

            if value < param_spec["min"] or value > param_spec["max"]:
                return {
                    "error": f"Parameter {param_name} must be between {param_spec['min']} and {param_spec['max']}"
                }
            validated_params[param_name] = value

        return {
            "name": name,
            "strategy_type": strategy_type,
            "parameters": validated_params,
            "entry_rules": template["entry_rules"],
            "exit_rules": template["exit_rules"],
            "description": template["description"],
            "valid": True,
        }

    async def backtest_custom_strategy(self, symbol: str, strategy_type: str,
                                        parameters: dict,
                                        prices: list[float],
                                        initial_capital: float = 100000) -> dict[str, Any]:
        """Backtest a user-defined strategy on historical price data."""
        if len(prices) < 60:
            return {"error": "Need at least 60 data points for backtesting"}

        template = STRATEGY_TEMPLATES.get(strategy_type)
        if not template:
            return {"error": f"Unknown strategy type: {strategy_type}"}

        try:
            result = await asyncio.to_thread(
                self._run_backtest_sync, symbol, strategy_type, parameters, prices, initial_capital
            )
            return result
        except Exception as e:
            logger.error("Strategy backtest failed: %s", e)
            return {"error": str(e)}

    def _run_backtest_sync(self, symbol: str, strategy_type: str,
                           params: dict, prices: list[float],
                           initial_capital: float) -> dict:
        arr = np.array(prices, dtype=float)
        n = len(arr)

        # Generate signals based on strategy type
        signals = self._generate_signals(strategy_type, params, arr)

        # Simulate trading
        capital = initial_capital
        position = 0
        trades = []
        equity_curve = [capital]
        entry_price = 0

        for i in range(1, n):
            signal = signals[i] if i < len(signals) else 0

            if signal == 1 and position == 0:  # BUY
                shares = int(capital * 0.95 / arr[i])  # 95% allocation
                if shares > 0:
                    position = shares
                    entry_price = arr[i]
                    capital -= shares * arr[i] * 1.001  # 0.1% commission

            elif signal == -1 and position > 0:  # SELL
                sale_value = position * arr[i] * 0.999  # 0.1% commission
                pnl = sale_value - (position * entry_price)
                capital += sale_value
                trades.append({
                    "entry_price": entry_price,
                    "exit_price": float(arr[i]),
                    "pnl": float(pnl),
                    "return_pct": float((arr[i] - entry_price) / entry_price) if entry_price > 0 else 0,
                })
                position = 0
                entry_price = 0

            total_value = capital + (position * arr[i] if position > 0 else 0)
            equity_curve.append(total_value)

        # Final position close
        if position > 0:
            final_value = position * arr[-1] * 0.999
            pnl = final_value - (position * entry_price)
            capital += final_value
            trades.append({
                "entry_price": entry_price,
                "exit_price": float(arr[-1]),
                "pnl": float(pnl),
                "return_pct": float((arr[-1] - entry_price) / entry_price) if entry_price > 0 else 0,
            })
            position = 0

        # Compute metrics
        total_return = (capital - initial_capital) / initial_capital
        equity = np.array(equity_curve)
        daily_returns = np.diff(equity) / equity[:-1]
        daily_returns = daily_returns[np.isfinite(daily_returns)]

        sharpe = float(np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)) if len(daily_returns) > 1 and np.std(daily_returns) > 0 else 0

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / peak
        max_drawdown = float(np.min(dd)) if len(dd) > 0 else 0

        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0

        avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t["pnl"] for t in losing_trades])) if losing_trades else 0
        profit_factor = float(avg_win / avg_loss) if avg_loss > 0 else float("inf") if avg_win > 0 else 0

        return {
            "symbol": symbol,
            "strategy_type": strategy_type,
            "parameters": params,
            "total_return": float(total_return),
            "total_return_pct": f"{total_return:.2%}",
            "final_capital": float(capital),
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": f"{max_drawdown:.2%}",
            "total_trades": len(trades),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "best_trade": max([t["return_pct"] for t in trades], default=0),
            "worst_trade": min([t["return_pct"] for t in trades], default=0),
            "trades": trades[-20:],  # Last 20 trades
        }

    def _generate_signals(self, strategy_type: str, params: dict, prices: np.ndarray) -> list[int]:
        """Generate buy (1) / sell (-1) / hold (0) signals."""
        n = len(prices)
        signals = [0] * n

        if strategy_type == "ma_crossover":
            short_p = params.get("short_period", 20)
            long_p = params.get("long_period", 50)
            for i in range(long_p, n):
                short_ma = np.mean(prices[i - short_p + 1:i + 1])
                long_ma = np.mean(prices[i - long_p + 1:i + 1])
                prev_short = np.mean(prices[i - short_p:i])
                prev_long = np.mean(prices[i - long_p:i])
                if short_ma > long_ma and prev_short <= prev_long:
                    signals[i] = 1
                elif short_ma < long_ma and prev_short >= prev_long:
                    signals[i] = -1

        elif strategy_type == "rsi_mean_reversion":
            rsi_p = params.get("rsi_period", 14)
            oversold = params.get("oversold", 30)
            overbought = params.get("overbought", 70)
            for i in range(rsi_p + 1, n):
                deltas = np.diff(prices[i - rsi_p:i + 1])
                gains = np.maximum(deltas, 0)
                losses = np.abs(np.minimum(deltas, 0))
                avg_gain = np.mean(gains) if len(gains) > 0 else 0
                avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
                rs = avg_gain / max(avg_loss, 0.001)
                rsi = 100 - (100 / (1 + rs))
                if rsi < oversold:
                    signals[i] = 1
                elif rsi > overbought:
                    signals[i] = -1

        elif strategy_type == "bollinger_breakout":
            bb_p = params.get("bb_period", 20)
            bb_std = params.get("bb_std", 2.0)
            for i in range(bb_p, n):
                window = prices[i - bb_p + 1:i + 1]
                ma = np.mean(window)
                std = np.std(window)
                upper = ma + bb_std * std
                lower = ma - bb_std * std
                if prices[i] > upper:
                    signals[i] = 1
                elif prices[i] < lower:
                    signals[i] = -1

        elif strategy_type == "macd_signal":
            fast = params.get("fast_period", 12)
            slow = params.get("slow_period", 26)
            sig = params.get("signal_period", 9)
            if n > slow + sig:
                ema_fast = self._ema_series(prices, fast)
                ema_slow = self._ema_series(prices, slow)
                macd_line = ema_fast - ema_slow
                signal_line = self._ema_series(macd_line, sig)
                for i in range(slow + sig, n):
                    if macd_line[i] > signal_line[i] and macd_line[i - 1] <= signal_line[i - 1]:
                        signals[i] = 1
                    elif macd_line[i] < signal_line[i] and macd_line[i - 1] >= signal_line[i - 1]:
                        signals[i] = -1

        elif strategy_type == "momentum_trend":
            trend_ma_p = params.get("trend_ma", 50)
            mom_p = params.get("momentum_period", 20)
            threshold = params.get("momentum_threshold", 0.02)
            for i in range(max(trend_ma_p, mom_p), n):
                ma = np.mean(prices[i - trend_ma_p + 1:i + 1])
                momentum = (prices[i] - prices[i - mom_p]) / prices[i - mom_p] if prices[i - mom_p] > 0 else 0
                if prices[i] > ma and momentum > threshold:
                    signals[i] = 1
                elif prices[i] < ma or momentum < -threshold:
                    signals[i] = -1

        elif strategy_type == "combined_multi_indicator":
            rsi_p = params.get("rsi_period", 14)
            rsi_buy = params.get("rsi_buy_level", 40)
            rsi_sell = params.get("rsi_sell_level", 65)
            ma_p = params.get("ma_period", 50)
            min_signals_needed = params.get("min_signals", 2)

            for i in range(max(ma_p, rsi_p + 1, 26), n):
                # RSI
                deltas = np.diff(prices[i - rsi_p:i + 1])
                gains = np.maximum(deltas, 0)
                losses = np.abs(np.minimum(deltas, 0))
                rs = np.mean(gains) / max(np.mean(losses), 0.001)
                rsi = 100 - (100 / (1 + rs))

                # MA
                ma = np.mean(prices[i - ma_p + 1:i + 1])

                # MACD
                ema12 = self._ema_point(prices[:i + 1], 12)
                ema26 = self._ema_point(prices[:i + 1], 26)
                macd = ema12 - ema26

                buy_signals = sum([rsi < rsi_buy, prices[i] > ma, macd > 0])
                sell_signals = sum([rsi > rsi_sell, prices[i] < ma, macd < 0])

                if buy_signals >= min_signals_needed:
                    signals[i] = 1
                elif sell_signals >= min_signals_needed:
                    signals[i] = -1

        return signals

    @staticmethod
    def _ema_series(prices, period: int) -> np.ndarray:
        arr = np.array(prices, dtype=float)
        ema = np.zeros_like(arr)
        ema[:period] = np.mean(arr[:period])
        multiplier = 2 / (period + 1)
        for i in range(period, len(arr)):
            ema[i] = (arr[i] - ema[i - 1]) * multiplier + ema[i - 1]
        return ema

    @staticmethod
    def _ema_point(prices, period: int) -> float:
        if len(prices) < period:
            return float(prices[-1])
        arr = np.array(prices[-period * 3:], dtype=float)
        multiplier = 2 / (period + 1)
        ema = float(np.mean(arr[:period]))
        for p in arr[period:]:
            ema = (p - ema) * multiplier + ema
        return ema
