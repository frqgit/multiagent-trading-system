"""Engine API routes — strategy execution, backtesting, signals, and portfolio."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/engine", tags=["engine"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RunStrategyRequest(BaseModel):
    symbol: str = Field(..., description="Ticker symbol (e.g. 'BHP.AX', 'AAPL')")
    strategy_name: str = Field(..., description="Built-in strategy name or 'custom'")
    period: str = Field("1y", description="Data period: 1mo, 3mo, 6mo, 1y, 2y, 5y, max")
    interval: str = Field("1d", description="Candle interval: 1d, 1wk, 1mo")
    parameters: dict = Field(default_factory=dict, description="Override strategy parameters")


class BacktestRequest(BaseModel):
    symbol: str
    strategy_name: str
    period: str = "2y"
    interval: str = "1d"
    parameters: dict = Field(default_factory=dict)
    initial_capital: float = Field(100_000, gt=0)
    commission_pct: float = Field(0.001, ge=0)
    slippage_pct: float = Field(0.0005, ge=0)
    short_selling: bool = True


class CustomStrategyRequest(BaseModel):
    symbol: str
    period: str = "1y"
    interval: str = "1d"
    name: str = "custom"
    entry_long: str = Field(..., description="Python expression for long entry")
    exit_long: str = Field(..., description="Python expression for long exit")
    entry_short: str = Field("", description="Python expression for short entry")
    exit_short: str = Field("", description="Python expression for short exit")
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None
    parameters: dict = Field(default_factory=dict)


class WalkForwardRequest(BaseModel):
    symbol: str
    strategy_name: str
    period: str = "5y"
    interval: str = "1d"
    n_splits: int = Field(5, ge=2, le=20)
    train_pct: float = Field(0.7, gt=0.3, lt=0.95)
    parameters: dict = Field(default_factory=dict)


class MonteCarloRequest(BaseModel):
    symbol: str
    strategy_name: str
    period: str = "2y"
    interval: str = "1d"
    n_simulations: int = Field(1000, ge=100, le=10000)
    initial_capital: float = Field(100_000, gt=0)
    parameters: dict = Field(default_factory=dict)


class PositionSizeRequest(BaseModel):
    price: float = Field(..., gt=0)
    method: str = Field("pct_risk", description="fixed, pct_equity, pct_risk, kelly, equal_weight, volatility")
    equity: float = Field(100_000, gt=0)
    risk_per_trade_pct: float = Field(0.02, gt=0, le=0.1)
    stop_distance: float | None = None
    win_rate: float | None = None
    avg_win_loss_ratio: float | None = None
    volatility: float | None = None
    n_assets: int = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_ohlcv(symbol: str, period: str, interval: str):
    """Fetch OHLCV data via yfinance."""
    import yfinance as yf
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    # Flatten MultiIndex columns if present (yfinance sometimes returns them)
    if hasattr(df.columns, 'levels') and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    return df


def _resolve_strategy(strategy_name: str, parameters: dict):
    """Resolve a built-in strategy by name, with optional parameter overrides."""
    from engine.strategy import BUILTIN_STRATEGIES, Strategy
    if strategy_name not in BUILTIN_STRATEGIES:
        available = list(BUILTIN_STRATEGIES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy '{strategy_name}'. Available: {available}",
        )
    strat = BUILTIN_STRATEGIES[strategy_name]
    if parameters:
        merged = {**strat.parameters, **parameters}
        strat = Strategy(**{**strat.__dict__, "parameters": merged})
    return strat


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/strategies")
async def list_builtin_strategies() -> dict[str, Any]:
    """List all built-in engine strategies with their parameters."""
    from engine.strategy import BUILTIN_STRATEGIES
    result = {}
    for name, strat in BUILTIN_STRATEGIES.items():
        result[name] = {
            "name": strat.name,
            "entry_long": strat.entry_long,
            "exit_long": strat.exit_long,
            "entry_short": strat.entry_short,
            "exit_short": strat.exit_short,
            "parameters": strat.parameters,
            "stop_loss_pct": strat.stop_loss_pct,
            "take_profit_pct": strat.take_profit_pct,
        }
    return {"strategies": result}


@router.get("/indicators")
async def list_indicators() -> dict[str, list[str]]:
    """List all available indicator functions."""
    from engine import indicators
    return {"indicators": indicators.__all__}


@router.post("/signals")
async def generate_signals(req: RunStrategyRequest) -> dict[str, Any]:
    """Generate buy/sell signals for a symbol using a built-in strategy."""
    from engine.strategy import StrategyEngine

    strat = _resolve_strategy(req.strategy_name, req.parameters)
    df = _fetch_ohlcv(req.symbol, req.period, req.interval)

    engine = StrategyEngine()
    signals = engine.generate_signals_list(strat, df)

    return {
        "symbol": req.symbol,
        "strategy": strat.name,
        "period": req.period,
        "total_bars": len(df),
        "signals_count": len(signals),
        "signals": signals[-50:],  # last 50 signals
    }


@router.post("/signals/custom")
async def generate_custom_signals(req: CustomStrategyRequest) -> dict[str, Any]:
    """Generate signals from a custom strategy expression."""
    from engine.strategy import Strategy, StrategyEngine, validate_expression

    # Validate expressions
    for label, expr in [("entry_long", req.entry_long), ("exit_long", req.exit_long),
                         ("entry_short", req.entry_short), ("exit_short", req.exit_short)]:
        if expr:
            errors = validate_expression(expr)
            if errors:
                raise HTTPException(status_code=400, detail=f"Invalid {label}: {errors}")

    strat = Strategy(
        name=req.name,
        entry_long=req.entry_long,
        exit_long=req.exit_long,
        entry_short=req.entry_short,
        exit_short=req.exit_short,
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        trailing_stop_pct=req.trailing_stop_pct,
        parameters=req.parameters,
    )
    df = _fetch_ohlcv(req.symbol, req.period, req.interval)
    engine = StrategyEngine()
    signals = engine.generate_signals_list(strat, df)

    return {
        "symbol": req.symbol,
        "strategy": req.name,
        "total_bars": len(df),
        "signals_count": len(signals),
        "signals": signals[-50:],
    }


@router.post("/backtest")
async def run_backtest(req: BacktestRequest) -> dict[str, Any]:
    """Run a full backtest with performance metrics."""
    from engine.backtest import Backtester, BacktestConfig

    strat = _resolve_strategy(req.strategy_name, req.parameters)
    df = _fetch_ohlcv(req.symbol, req.period, req.interval)

    config = BacktestConfig(
        initial_capital=req.initial_capital,
        commission_pct=req.commission_pct,
        slippage_pct=req.slippage_pct,
        short_selling=req.short_selling,
    )
    bt = Backtester(config)
    result = bt.run(strat, df, req.symbol)

    return {
        "summary": result.summary(),
        "equity_curve": result.equity_curve[-252:],  # last year
        "trades": [
            {
                "entry_date": t.entry_date, "exit_date": t.exit_date,
                "side": t.side, "entry_price": t.entry_price,
                "exit_price": t.exit_price, "shares": t.shares,
                "net_pnl": t.net_pnl, "pnl_pct": t.pnl_pct,
                "holding_bars": t.holding_bars, "exit_reason": t.exit_reason,
            }
            for t in result.trades[-100:]  # last 100 trades
        ],
    }


@router.post("/backtest/walk-forward")
async def run_walk_forward(req: WalkForwardRequest) -> dict[str, Any]:
    """Run walk-forward analysis for robustness testing."""
    from engine.backtest import walk_forward

    strat = _resolve_strategy(req.strategy_name, req.parameters)
    df = _fetch_ohlcv(req.symbol, req.period, req.interval)

    result = walk_forward(strat, df, req.symbol, req.n_splits, req.train_pct)
    return result


@router.post("/backtest/monte-carlo")
async def run_monte_carlo(req: MonteCarloRequest) -> dict[str, Any]:
    """Run Monte Carlo simulation on backtest trades."""
    from engine.backtest import Backtester, BacktestConfig, monte_carlo

    strat = _resolve_strategy(req.strategy_name, req.parameters)
    df = _fetch_ohlcv(req.symbol, req.period, req.interval)

    bt = Backtester(BacktestConfig(initial_capital=req.initial_capital))
    result = bt.run(strat, df, req.symbol)

    if not result.trades:
        raise HTTPException(status_code=400, detail="No trades generated — cannot run Monte Carlo")

    mc = monte_carlo(result.trades, req.initial_capital, req.n_simulations)
    return {
        "backtest_summary": result.summary(),
        "monte_carlo": mc,
    }


@router.post("/position-size")
async def calculate_position_size(req: PositionSizeRequest) -> dict[str, Any]:
    """Calculate optimal position size using various methods."""
    from engine.portfolio import PortfolioManager, PortfolioConfig

    pm = PortfolioManager(PortfolioConfig(
        initial_capital=req.equity,
        risk_per_trade_pct=req.risk_per_trade_pct,
    ))

    shares = pm.calculate_position_size(
        price=req.price,
        method=req.method,
        stop_distance=req.stop_distance,
        win_rate=req.win_rate,
        avg_win_loss_ratio=req.avg_win_loss_ratio,
        volatility=req.volatility,
        n_assets=req.n_assets,
    )

    return {
        "method": req.method,
        "shares": shares,
        "position_value": round(shares * req.price, 2),
        "position_pct": round(shares * req.price / req.equity * 100, 2),
        "equity": req.equity,
        "risk_per_trade": f"{req.risk_per_trade_pct * 100:.1f}%",
    }


@router.post("/validate-expression")
async def validate_expression_endpoint(expression: str) -> dict[str, Any]:
    """Validate a strategy expression for safety."""
    from engine.strategy import validate_expression
    errors = validate_expression(expression)
    return {"expression": expression, "valid": len(errors) == 0, "errors": errors}
