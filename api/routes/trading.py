"""API routes for advanced trading features.

Endpoints for:
- Portfolio optimization
- Backtesting
- Volatility analysis
- Technical analysis
- Correlation analysis
- Paper trading execution

Note: These endpoints require scipy. If unavailable, they return 503 errors.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/advanced", tags=["advanced"])

# Lazy-loaded agents (require scipy)
_agents_loaded = False
_agents = {}

def _load_agents():
    """Lazy load advanced agents that require scipy."""
    global _agents_loaded, _agents
    if _agents_loaded:
        return bool(_agents)
    
    _agents_loaded = True
    try:
        from agents.portfolio_agent import PortfolioOptimizationAgent
        from agents.backtest_agent import BacktestingAgent
        from agents.volatility_agent import VolatilityModelingAgent
        from agents.technical_strategy_agent import TechnicalStrategyAgent
        from agents.correlation_agent import CorrelationAnalysisAgent
        from agents.adaptive_agent import AdaptiveLearningAgent
        from agents.execution_agent import ExecutionAgent
        
        _agents["portfolio"] = PortfolioOptimizationAgent()
        _agents["backtest"] = BacktestingAgent()
        _agents["volatility"] = VolatilityModelingAgent()
        _agents["technical"] = TechnicalStrategyAgent()
        _agents["correlation"] = CorrelationAnalysisAgent()
        _agents["adaptive"] = AdaptiveLearningAgent()
        _agents["execution"] = ExecutionAgent()
        logger.info("Advanced trading agents loaded successfully")
        return True
    except ImportError as e:
        logger.warning("Advanced trading agents unavailable: %s", e)
        return False

def _require_agents():
    """Ensure agents are loaded, raise 503 if unavailable."""
    if not _load_agents():
        raise HTTPException(
            status_code=503,
            detail="Advanced trading features require scipy which is not installed in this environment. "
                   "Please use Docker deployment or local installation."
        )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PortfolioRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=2, max_length=20, description="List of stock symbols")
    target_weights: dict[str, float] | None = Field(None, description="Optional target weights for rebalancing")
    risk_free_rate: float = Field(0.04, description="Risk-free rate (annualized)")


class PortfolioResponse(BaseModel):
    symbols: list[str]
    optimization: dict
    current_metrics: dict
    correlation_matrix: dict
    rebalancing: list


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol to backtest")
    strategy: str = Field("ma_crossover", description="Strategy: ma_crossover, rsi_mean_reversion, momentum, breakout, macd, bollinger")
    days: int = Field(365, ge=30, le=1825, description="Number of days to backtest")


class BacktestResponse(BaseModel):
    symbol: str
    strategy: str
    results: dict


class VolatilityRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    days: int = Field(365, ge=30, le=1825, description="Days of historical data")


class VolatilityResponse(BaseModel):
    symbol: str
    volatility_estimates: dict
    regime: dict
    forecast: list
    risk_assessment: dict
    term_structure: dict


class TechnicalRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    days: int = Field(365, ge=30, le=730, description="Days of historical data")


class TechnicalResponse(BaseModel):
    symbol: str
    trend_analysis: dict
    indicators: dict
    signals: list
    patterns: list[dict]
    support_resistance: dict
    fibonacci: dict


class CorrelationRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=2, max_length=20, description="List of stock symbols")
    days: int = Field(365, ge=30, le=1825, description="Days of historical data")


class CorrelationResponse(BaseModel):
    symbols: list[str]
    correlation_matrix: dict
    top_pairs: list[dict]
    cointegration: list[dict]
    diversification_metrics: dict
    betas: dict


class PairAnalysisRequest(BaseModel):
    symbol1: str = Field(..., description="First stock symbol")
    symbol2: str = Field(..., description="Second stock symbol")
    days: int = Field(365, ge=60, le=1825, description="Days of historical data")


class PairAnalysisResponse(BaseModel):
    pair: str
    correlation: float
    cointegrated: bool
    half_life: float | None
    spread_zscore: float
    trading_signal: dict
    hedge_ratio: float


class OrderRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    side: str = Field(..., description="buy or sell")
    quantity: float = Field(..., gt=0, description="Number of shares")
    order_type: str = Field("market", description="market, limit, stop, stop_limit")
    price: float | None = Field(None, description="Limit price (for limit orders)")
    stop_price: float | None = Field(None, description="Stop price (for stop orders)")


class OrderResponse(BaseModel):
    success: bool
    order_id: str | None = None
    status: str | None = None
    message: str | None = None
    error: str | None = None
    execution: dict | None = None


class PositionSizeRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    current_price: float = Field(..., gt=0, description="Current market price")
    confidence: float = Field(0.7, ge=0, le=1, description="Signal confidence")
    max_position_pct: float = Field(0.1, ge=0.01, le=0.5, description="Max portfolio % per position")
    max_risk_pct: float = Field(0.02, ge=0.005, le=0.1, description="Max risk % per trade")
    volatility: float | None = Field(None, description="Annualized volatility (optional)")


class PositionSizeResponse(BaseModel):
    symbol: str
    recommended_shares: int
    position_value: float
    position_pct: float
    sizing_methods: dict
    parameters: dict


class PortfolioSummaryResponse(BaseModel):
    summary: dict
    positions: list[dict]
    open_orders: int
    trade_statistics: dict


class AdaptiveAnalysisRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    days: int = Field(365, ge=60, le=730, description="Days of historical data")


class AdaptiveAnalysisResponse(BaseModel):
    symbol: str
    market_regime: dict
    features: dict
    feature_importance: dict
    strategy_recommendations: list[dict]
    adaptive_weights: dict
    regime_history: list[dict]
    adaptation_stats: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/portfolio/optimize", response_model=PortfolioResponse)
async def optimize_portfolio(req: PortfolioRequest):
    """
    Optimize portfolio allocation using Modern Portfolio Theory.
    
    Returns optimal weights for max Sharpe, min variance, and risk parity portfolios.
    """
    _require_agents()
    try:
        result = await _agents["portfolio"].analyze(
            symbols=req.symbols,
            current_weights=req.target_weights,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return PortfolioResponse(
            symbols=req.symbols,
            optimization=result.get("optimal_weights", {}),
            current_metrics=result.get("portfolio_metrics", {}),
            correlation_matrix=result.get("correlations", {}),
            rebalancing=result.get("rebalance_trades", []),
        )
    except Exception as e:
        logger.exception("Portfolio optimization failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """
    Backtest a trading strategy on historical data.
    
    Strategies: ma_crossover, rsi_mean_reversion, momentum, breakout, macd, bollinger
    """
    valid_strategies = ["ma_crossover", "rsi_mean_reversion", "momentum", "breakout", "macd", "bollinger"]
    if req.strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy. Choose from: {', '.join(valid_strategies)}"
        )
    
    _require_agents()
    try:
        result = await _agents["backtest"].backtest_strategy(
            symbol=req.symbol,
            strategy=req.strategy,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return BacktestResponse(
            symbol=req.symbol,
            strategy=req.strategy,
            results=result,
        )
    except Exception as e:
        logger.exception("Backtest failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest/monte-carlo")
async def run_monte_carlo(req: BacktestRequest, simulations: int = 100):
    """
    Run Monte Carlo simulation on a backtested strategy.
    """
    _require_agents()
    try:
        result = await _agents["backtest"].monte_carlo_simulation(
            symbol=req.symbol,
            strategy=req.strategy,
            num_simulations=min(simulations, 500),
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except Exception as e:
        logger.exception("Monte Carlo simulation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/volatility", response_model=VolatilityResponse)
async def analyze_volatility(req: VolatilityRequest):
    """
    Analyze volatility using multiple models (Historical, EWMA, Parkinson, GARCH).
    """
    _require_agents()
    try:
        result = await _agents["volatility"].analyze(
            symbol=req.symbol,
            lookback_days=req.days,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return VolatilityResponse(
            symbol=req.symbol,
            volatility_estimates=result.get("volatility_measures", {}),
            regime=result.get("regime", {}),
            forecast=result.get("forecast", {}),
            risk_assessment=result.get("risk_assessment", {}),
            term_structure=result.get("term_structure", []),
        )
    except Exception as e:
        logger.exception("Volatility analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/technical", response_model=TechnicalResponse)
async def analyze_technical(req: TechnicalRequest):
    """
    Comprehensive technical analysis with indicators, patterns, and signals.
    """
    _require_agents()
    try:
        result = await _agents["technical"].analyze(
            symbol=req.symbol,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return TechnicalResponse(
            symbol=req.symbol,
            trend_analysis=result.get("trend_analysis", {}),
            indicators=result.get("indicators", {}),
            signals=result.get("signals", {}),
            patterns=result.get("patterns", []),
            support_resistance=result.get("support_resistance", {}),
            fibonacci=result.get("fibonacci", {}),
        )
    except Exception as e:
        logger.exception("Technical analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correlation", response_model=CorrelationResponse)
async def analyze_correlation(req: CorrelationRequest):
    """
    Analyze correlations between multiple assets.
    """
    _require_agents()
    try:
        result = await _agents["correlation"].analyze_correlations(
            symbols=req.symbols,
            lookback_days=req.days,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return CorrelationResponse(
            symbols=req.symbols,
            correlation_matrix=result.get("correlation_matrix", {}),
            top_pairs=result.get("highest_correlations", []),
            cointegration=result.get("pair_trading_opportunities", []),
            diversification_metrics=result.get("diversification_metrics", {}),
            betas=result.get("betas", {}),
        )
    except Exception as e:
        logger.exception("Correlation analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correlation/pair", response_model=PairAnalysisResponse)
async def analyze_pair(req: PairAnalysisRequest):
    """
    Detailed pair trading analysis for two assets.
    """
    _require_agents()
    try:
        result = await _agents["correlation"].analyze_pair(
            symbol1=req.symbol1,
            symbol2=req.symbol2,
            lookback_days=req.days,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return PairAnalysisResponse(
            pair=f"{req.symbol1}/{req.symbol2}",
            correlation=result.get("correlation", {}).get("full_period", 0),
            cointegrated=result.get("cointegration", {}).get("is_cointegrated", False),
            half_life=result.get("spread_analysis", {}).get("half_life_days"),
            spread_zscore=result.get("spread_analysis", {}).get("z_score", 0),
            trading_signal=result.get("pair_trade", {}),
            hedge_ratio=result.get("cointegration", {}).get("hedge_ratio", 1),
        )
    except Exception as e:
        logger.exception("Pair analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adaptive", response_model=AdaptiveAnalysisResponse)
async def adaptive_analysis(req: AdaptiveAnalysisRequest):
    """
    Adaptive learning analysis with regime detection and strategy recommendations.
    """
    _require_agents()
    try:
        # Get price data first
        import asyncio
        from tools.stock_api import fetch_stock_data
        snapshot = await asyncio.to_thread(fetch_stock_data, req.symbol)
        price_data = snapshot.price_history_30d
        
        if not price_data or len(price_data) < 20:
            raise HTTPException(status_code=400, detail="Insufficient price data")
        
        result = await _agents["adaptive"].analyze(
            symbol=req.symbol,
            price_data=price_data,
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return AdaptiveAnalysisResponse(
            symbol=req.symbol,
            market_regime=result.get("market_regime", {}),
            features=result.get("features", {}),
            feature_importance=result.get("feature_importance", {}),
            strategy_recommendations=result.get("strategy_recommendations", []),
            adaptive_weights=result.get("adaptive_weights", {}),
            regime_history=result.get("regime_history", []),
            adaptation_stats=result.get("adaptation_stats", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Adaptive analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Paper Trading Endpoints
# ---------------------------------------------------------------------------

@router.post("/execution/order", response_model=OrderResponse)
async def submit_order(req: OrderRequest):
    """
    Submit a paper trading order.
    """
    _require_agents()
    try:
        # Get current price for market orders
        import asyncio
        from tools.stock_api import fetch_stock_data
        snapshot = await asyncio.to_thread(fetch_stock_data, req.symbol)
        current_price = snapshot.current_price
        
        if current_price is None:
            raise HTTPException(status_code=400, detail=f"Could not get price for {req.symbol}")
        
        result = await _agents["execution"].submit_order(
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            order_type=req.order_type,
            price=req.price,
            stop_price=req.stop_price,
            current_price=current_price,
        )
        
        return OrderResponse(
            success=result.get("success", False),
            order_id=result.get("order_id"),
            status=result.get("status"),
            message=result.get("message"),
            error=result.get("error"),
            execution=result.get("execution"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Order submission failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution/portfolio", response_model=PortfolioSummaryResponse)
async def get_portfolio(symbols: str = ""):
    """
    Get paper trading portfolio summary.
    
    Optionally pass symbols (comma-separated) to get current prices for valuation.
    """
    _require_agents()
    try:
        current_prices = {}
        if symbols:
            import asyncio
            from tools.stock_api import fetch_stock_data
            symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
            for sym in symbol_list:
                try:
                    snapshot = await asyncio.to_thread(fetch_stock_data, sym)
                    current_prices[sym] = snapshot.current_price
                except Exception:
                    pass
        
        result = await _agents["execution"].get_portfolio_summary(current_prices or None)
        
        return PortfolioSummaryResponse(
            summary=result.get("summary", {}),
            positions=result.get("positions", []),
            open_orders=result.get("open_orders", 0),
            trade_statistics=result.get("trade_statistics", {}),
        )
    except Exception as e:
        logger.exception("Portfolio fetch failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execution/position-size", response_model=PositionSizeResponse)
async def calculate_position_size(req: PositionSizeRequest):
    """
    Calculate recommended position size based on risk parameters.
    """
    _require_agents()
    try:
        result = await _agents["execution"].calculate_position_size(
            symbol=req.symbol,
            signal={"confidence": req.confidence},
            current_price=req.current_price,
            volatility=req.volatility,
            max_position_pct=req.max_position_pct,
            max_risk_pct=req.max_risk_pct,
        )
        
        return PositionSizeResponse(
            symbol=req.symbol,
            recommended_shares=result.get("recommended_shares", 0),
            position_value=result.get("position_value", 0),
            position_pct=result.get("position_pct", 0),
            sizing_methods=result.get("sizing_methods", {}),
            parameters=result.get("parameters", {}),
        )
    except Exception as e:
        logger.exception("Position sizing failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution/trades")
async def get_trade_history(symbol: str = None, limit: int = 50):
    """
    Get paper trading trade history.
    """
    _require_agents()
    try:
        trades = await _agents["execution"].get_trade_history(
            symbol=symbol,
            limit=min(limit, 200),
        )
        return {"trades": trades}
    except Exception as e:
        logger.exception("Trade history fetch failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution/analytics")
async def get_execution_analytics():
    """
    Get execution quality analytics.
    """
    _require_agents()
    try:
        analytics = await _agents["execution"].get_execution_analytics()
        return analytics
    except Exception as e:
        logger.exception("Analytics fetch failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execution/reset")
async def reset_portfolio(initial_capital: float = 100000.0):
    """
    Reset paper trading portfolio to initial state.
    """
    _require_agents()
    try:
        result = await _agents["execution"].reset_portfolio(initial_capital)
        return result
    except Exception as e:
        logger.exception("Portfolio reset failed")
        raise HTTPException(status_code=500, detail=str(e))
