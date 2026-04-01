"""Strategy Framework — define, parse, validate and execute trading strategies.

Strategy scripting using safe Python expressions.

Usage:
    from engine.strategy import Strategy, StrategyEngine

    strat = Strategy(
        name="Golden Cross",
        entry_long="CrossAbove(SMA(C, 50), SMA(C, 200))",
        exit_long="CrossBelow(SMA(C, 50), SMA(C, 200))",
    )
    engine = StrategyEngine()
    signals = engine.run(strat, ohlcv_df)
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from engine import indicators as ind

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal enum
# ---------------------------------------------------------------------------

class Signal(int, Enum):
    """Trade signal values used in signal arrays."""
    FLAT = 0
    LONG = 1
    SHORT = -1
    EXIT_LONG = 2
    EXIT_SHORT = -2


# ---------------------------------------------------------------------------
# Strategy dataclass
# ---------------------------------------------------------------------------

@dataclass
class Strategy:
    """Declarative strategy definition."""

    name: str
    description: str = ""

    # Rule expressions — safe Python/indicator syntax
    entry_long: str = ""
    exit_long: str = ""
    entry_short: str = ""
    exit_short: str = ""

    # Position sizing
    position_size: str = "fixed"          # "fixed", "pct_equity", "pct_risk", "kelly"
    position_value: float = 10_000.0      # dollar amount or percentage
    max_positions: int = 10

    # Risk controls
    stop_loss_pct: float | None = None    # e.g. 0.05 for 5%
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None

    # Filters
    trade_on_close: bool = True           # execute at bar's close
    allow_pyramiding: bool = False
    max_bars_held: int | None = None      # force exit after N bars

    # Parameters (user-tuneable, injected into expression namespace)
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "entry_long": self.entry_long,
            "exit_long": self.exit_long,
            "entry_short": self.entry_short,
            "exit_short": self.exit_short,
            "position_size": self.position_size,
            "position_value": self.position_value,
            "max_positions": self.max_positions,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Strategy:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Built-in strategy templates
# ---------------------------------------------------------------------------

BUILTIN_STRATEGIES: dict[str, Strategy] = {
    "golden_cross": Strategy(
        name="Golden Cross",
        description="Classic SMA 50/200 crossover — long only",
        entry_long="CrossAbove(SMA(C, 50), SMA(C, 200))",
        exit_long="CrossBelow(SMA(C, 50), SMA(C, 200))",
        stop_loss_pct=0.08,
    ),
    "rsi_reversion": Strategy(
        name="RSI Mean Reversion",
        description="Buy oversold RSI, sell overbought",
        entry_long="RSI(C, period) < oversold",
        exit_long="RSI(C, period) > overbought",
        entry_short="RSI(C, period) > overbought",
        exit_short="RSI(C, period) < oversold",
        parameters={"period": 14, "oversold": 30, "overbought": 70},
        stop_loss_pct=0.05,
    ),
    "macd_crossover": Strategy(
        name="MACD Crossover",
        description="Enter on MACD line crossing signal line",
        entry_long="CrossAbove(MACD(C, 12, 26, 9)['MACD'], MACD(C, 12, 26, 9)['MACD_Signal'])",
        exit_long="CrossBelow(MACD(C, 12, 26, 9)['MACD'], MACD(C, 12, 26, 9)['MACD_Signal'])",
        stop_loss_pct=0.06,
    ),
    "bollinger_squeeze": Strategy(
        name="Bollinger Band Squeeze",
        description="Enter when price breaks out of squeezed bands",
        entry_long="(C > BollingerBands(C, 20, 2.0)['BB_Upper']) & (BollingerBands(C, 20, 2.0)['BB_Bandwidth'] < 10)",
        exit_long="C < BollingerBands(C, 20, 2.0)['BB_Middle']",
        stop_loss_pct=0.05,
    ),
    "supertrend_follow": Strategy(
        name="SuperTrend Trend Follower",
        description="Follow SuperTrend direction",
        entry_long="SuperTrend(H, L, C, 10, 3.0)['ST_Direction'] == 1",
        exit_long="SuperTrend(H, L, C, 10, 3.0)['ST_Direction'] == -1",
        entry_short="SuperTrend(H, L, C, 10, 3.0)['ST_Direction'] == -1",
        exit_short="SuperTrend(H, L, C, 10, 3.0)['ST_Direction'] == 1",
        stop_loss_pct=0.07,
    ),
    "triple_ema": Strategy(
        name="Triple EMA Momentum",
        description="EMA 8/21/55 alignment — trend filter + momentum entry",
        entry_long="(EMA(C, 8) > EMA(C, 21)) & (EMA(C, 21) > EMA(C, 55)) & (RSI(C, 14) > 50)",
        exit_long="(EMA(C, 8) < EMA(C, 21)) | (RSI(C, 14) < 40)",
        stop_loss_pct=0.06,
    ),
    "donchian_breakout": Strategy(
        name="Donchian Breakout",
        description="Turtle-style channel breakout — 20-bar high/low",
        entry_long="C > DonchianChannel(H, L, 20)['DC_Upper'].shift(1)",
        exit_long="C < DonchianChannel(H, L, 10)['DC_Lower'].shift(1)",
        entry_short="C < DonchianChannel(H, L, 20)['DC_Lower'].shift(1)",
        exit_short="C > DonchianChannel(H, L, 10)['DC_Upper'].shift(1)",
        stop_loss_pct=0.10,
    ),
    "keltner_mean_revert": Strategy(
        name="Keltner Channel Reversion",
        description="Mean-revert from Keltner extremes with RSI filter",
        entry_long="(C < KeltnerChannel(H, L, C, 20, 10, 2.0)['KC_Lower']) & (RSI(C, 14) < 35)",
        exit_long="C > KeltnerChannel(H, L, C, 20, 10, 2.0)['KC_Middle']",
        stop_loss_pct=0.04,
    ),
    "adx_trend_strength": Strategy(
        name="ADX Trend Strength",
        description="Trade strong trends identified by ADX > 25",
        entry_long="(ADX(H, L, C, 14)['ADX'] > 25) & (ADX(H, L, C, 14)['Plus_DI'] > ADX(H, L, C, 14)['Minus_DI'])",
        exit_long="(ADX(H, L, C, 14)['ADX'] < 20) | (ADX(H, L, C, 14)['Plus_DI'] < ADX(H, L, C, 14)['Minus_DI'])",
        stop_loss_pct=0.07,
    ),
    "ichimoku_cloud": Strategy(
        name="Ichimoku Cloud",
        description="Enter on Tenkan/Kijun cross above cloud",
        entry_long=(
            "(IchimokuCloud(H, L, C)['Tenkan'] > IchimokuCloud(H, L, C)['Kijun']) & "
            "(C > IchimokuCloud(H, L, C)['Senkou_A']) & (C > IchimokuCloud(H, L, C)['Senkou_B'])"
        ),
        exit_long="IchimokuCloud(H, L, C)['Tenkan'] < IchimokuCloud(H, L, C)['Kijun']",
        stop_loss_pct=0.08,
    ),
}


# ---------------------------------------------------------------------------
# Safe expression evaluator
# ---------------------------------------------------------------------------

# Allowed names that can appear in strategy expressions
_SAFE_NAMES: set[str] = {
    # OHLCV aliases
    "O", "H", "L", "C", "V",
    "Open", "High", "Low", "Close", "Volume",
    # Python builtins (numeric)
    "abs", "min", "max", "True", "False",
    # numpy
    "np",
}

# All public indicator function names
_INDICATOR_NAMES: set[str] = set(ind.__all__)

_ALLOWED_CALLS: set[str] = _SAFE_NAMES | _INDICATOR_NAMES


class _ExprValidator(ast.NodeVisitor):
    """Walk the AST and reject anything that's not a safe indicator expression."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Name):
            if node.func.id not in _ALLOWED_CALLS:
                self.errors.append(f"Forbidden function call: {node.func.id}")
        elif isinstance(node.func, ast.Attribute):
            pass  # e.g. df['col'].shift(1) — allowed
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        self.errors.append("Import statements are forbidden")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        self.errors.append("Import statements are forbidden")

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        # Block dunder access
        if node.attr.startswith("__"):
            self.errors.append(f"Dunder attribute access forbidden: __{node.attr}__")
        self.generic_visit(node)


def validate_expression(expr: str) -> list[str]:
    """Validate a strategy expression string. Returns list of errors (empty = ok)."""
    if not expr or not expr.strip():
        return []
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return [f"Syntax error: {e}"]
    validator = _ExprValidator()
    validator.visit(tree)
    return validator.errors


def _build_namespace(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    """Build the evaluation namespace from OHLCV DataFrame and user parameters."""
    ns: dict[str, Any] = {}

    # OHLCV aliases
    ns["O"] = ns["Open"] = df["Open"]
    ns["H"] = ns["High"] = df["High"]
    ns["L"] = ns["Low"] = df["Low"]
    ns["C"] = ns["Close"] = df["Close"]
    ns["V"] = ns["Volume"] = df["Volume"]

    # All indicator functions
    for name in ind.__all__:
        ns[name] = getattr(ind, name)

    # numpy for user expressions
    ns["np"] = np
    ns["pd"] = pd
    ns["abs"] = np.abs
    ns["min"] = np.minimum
    ns["max"] = np.maximum
    ns["True"] = True
    ns["False"] = False

    # User parameters
    ns.update(params)

    return ns


def evaluate_rule(expr: str, df: pd.DataFrame,
                  params: dict[str, Any] | None = None) -> pd.Series:
    """Evaluate a strategy rule expression against OHLCV data.

    Returns a boolean Series aligned to df.index.
    """
    if not expr or not expr.strip():
        return pd.Series(False, index=df.index)

    errors = validate_expression(expr)
    if errors:
        raise ValueError(f"Invalid expression: {'; '.join(errors)}")

    ns = _build_namespace(df, params or {})

    try:
        result = eval(expr, {"__builtins__": {}}, ns)  # noqa: S307
    except Exception as exc:
        raise ValueError(f"Expression evaluation failed: {exc}") from exc

    if isinstance(result, (bool, np.bool_)):
        return pd.Series(result, index=df.index)
    if isinstance(result, pd.Series):
        return result.astype(bool).reindex(df.index, fill_value=False)
    raise ValueError(f"Expression must return bool/Series, got {type(result).__name__}")


# ---------------------------------------------------------------------------
# Strategy Engine — generates signal array from strategy + data
# ---------------------------------------------------------------------------

@dataclass
class SignalRow:
    """Compact signal output per bar."""
    date: str
    signal: Signal
    price: float
    reason: str = ""


class StrategyEngine:
    """Evaluate a Strategy against OHLCV data and produce a signal array."""

    def run(self, strategy: Strategy, df: pd.DataFrame) -> pd.DataFrame:
        """Run strategy rules and produce a signal DataFrame.

        Returned columns:
            entry_long, exit_long, entry_short, exit_short — boolean
            signal — Signal enum (LONG / SHORT / EXIT_LONG / EXIT_SHORT / FLAT)
            position — current position state (1=long, -1=short, 0=flat)
        """
        params = strategy.parameters or {}

        entry_long = evaluate_rule(strategy.entry_long, df, params)
        exit_long = evaluate_rule(strategy.exit_long, df, params)
        entry_short = evaluate_rule(strategy.entry_short, df, params)
        exit_short = evaluate_rule(strategy.exit_short, df, params)

        sig = pd.Series(Signal.FLAT, index=df.index)
        pos = pd.Series(0, index=df.index, dtype=int)
        current_pos = 0
        bars_held = 0

        for i in range(1, len(df)):
            bars_held += 1 if current_pos != 0 else 0

            # Exit signals first
            if current_pos == 1:
                if exit_long.iloc[i]:
                    sig.iloc[i] = Signal.EXIT_LONG
                    current_pos = 0
                    bars_held = 0
                elif strategy.max_bars_held and bars_held >= strategy.max_bars_held:
                    sig.iloc[i] = Signal.EXIT_LONG
                    current_pos = 0
                    bars_held = 0
            elif current_pos == -1:
                if exit_short.iloc[i]:
                    sig.iloc[i] = Signal.EXIT_SHORT
                    current_pos = 0
                    bars_held = 0
                elif strategy.max_bars_held and bars_held >= strategy.max_bars_held:
                    sig.iloc[i] = Signal.EXIT_SHORT
                    current_pos = 0
                    bars_held = 0

            # Entry signals (only if flat or allowing pyramiding)
            if current_pos == 0 or strategy.allow_pyramiding:
                if entry_long.iloc[i] and current_pos <= 0:
                    if current_pos == -1:
                        sig.iloc[i] = Signal.EXIT_SHORT
                    sig.iloc[i] = Signal.LONG
                    current_pos = 1
                    bars_held = 0
                elif entry_short.iloc[i] and current_pos >= 0:
                    if current_pos == 1:
                        sig.iloc[i] = Signal.EXIT_LONG
                    sig.iloc[i] = Signal.SHORT
                    current_pos = -1
                    bars_held = 0

            pos.iloc[i] = current_pos

        result = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        result["entry_long"] = entry_long
        result["exit_long"] = exit_long
        result["entry_short"] = entry_short
        result["exit_short"] = exit_short
        result["signal"] = sig
        result["position"] = pos
        return result

    def generate_signals_list(self, strategy: Strategy, df: pd.DataFrame) -> list[dict]:
        """Return a list of signal events (non-FLAT bars only)."""
        result = self.run(strategy, df)
        signals = []
        for idx, row in result.iterrows():
            if row["signal"] != Signal.FLAT:
                signals.append({
                    "date": str(idx),
                    "signal": Signal(row["signal"]).name,
                    "price": round(float(row["Close"]), 4),
                    "position": int(row["position"]),
                })
        return signals
