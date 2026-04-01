"""TradingEdge Engine — AmiBroker-like quantitative trading engine.

Modules:
    indicators  — Technical indicator library (RSI, MACD, MA, Bollinger, ATR, etc.)
    strategy    — Strategy definition, parsing, and execution framework
    backtest    — Event-driven backtesting engine with full metrics
    portfolio   — Portfolio management, position sizing, and risk controls
"""

from engine.indicators import *  # noqa: F401,F403
from engine.strategy import Signal, Strategy, StrategyEngine, BUILTIN_STRATEGIES  # noqa: F401
from engine.backtest import Backtester, BacktestConfig, BacktestResult, walk_forward, monte_carlo  # noqa: F401
from engine.portfolio import PortfolioManager, PortfolioConfig, Position  # noqa: F401
